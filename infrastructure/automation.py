"""GitHub-only orchestration. Raw plans/state/secrets never go to logs or artifacts."""

import argparse
import hashlib
import io
import ipaddress
import json
import os
import re
import subprocess
import tempfile
import time
import urllib.request
from urllib.parse import urlsplit
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
TF = ROOT / "infrastructure/terraform"
WORKFLOWS = [
    "backend-ci.yml",
    "e2e.yml",
    "docker-validation.yml",
    "terraform-validate.yml",
]


class SafeRedirect(urllib.request.HTTPRedirectHandler):
    """Never forward a GitHub token to the signed artifact-storage redirect host."""

    def redirect_request(self, request, fp, code, message, headers, new_url):
        if urlsplit(new_url).scheme != "https":
            raise ValueError("HTTPS-only artifact redirects")
        redirected = super().redirect_request(
            request, fp, code, message, headers, new_url
        )
        if urlsplit(request.full_url).netloc != urlsplit(new_url).netloc:
            redirected.remove_header("Authorization")
        return redirected


def required(*names):
    if any(not os.environ.get(name, "").strip() for name in names):
        raise ValueError("Missing mandatory GitHub Environment configuration")


def run(args, *, cwd=None, input=None):
    result = subprocess.run(
        args, input=input, cwd=cwd or ROOT, capture_output=True, timeout=1200
    )
    if result.returncode:
        raise RuntimeError("Automation command failed; sensitive diagnostics withheld")
    return result.stdout


def github(path):
    required("GH_TOKEN", "GITHUB_REPOSITORY")
    request = urllib.request.Request(
        "https://api.github.com/repos/" + os.environ["GITHUB_REPOSITORY"] + "/" + path,
        headers={
            "Authorization": "Bearer " + os.environ["GH_TOKEN"],
            "Accept": "application/vnd.github+json",
        },
    )
    return json.load(urllib.request.urlopen(request, timeout=30))


def protected_environment():
    if os.environ.get("GITHUB_REF") != "refs/heads/master":
        raise ValueError("Production operations require the reviewed master branch")
    env = github("environments/production")
    rules = env.get("protection_rules", [])
    if env.get("can_admins_bypass", True) or not any(
        rule.get("type") == "required_reviewers"
        and rule.get("reviewers")
        and rule.get("prevent_self_review")
        for rule in rules
    ):
        raise ValueError(
            "Configure production required reviewers, prevent self-review and disable admin bypass first"
        )
    policy = env.get("deployment_branch_policy") or {}
    if not policy.get("custom_branch_policies"):
        raise ValueError("Production must permit only the explicit master branch")
    branches = github("environments/production/deployment-branch-policies")[
        "branch_policies"
    ]
    if not branches or any(
        item["name"] != "master" or item.get("type", "branch") != "branch"
        for item in branches
    ):
        raise ValueError("Only master may deploy to production")


def safe_summary(document):
    """Only counts/actions and reviewed resource addresses; never planned attribute values."""
    output = []
    for item in document.get("resource_changes", []):
        actions = item["change"]["actions"]
        address = item["address"]
        if "delete" in actions:
            raise ValueError(
                "Deletion or replacement requires a separate operator procedure"
            )
        if not re.fullmatch(
            r"upcloud_(?:server\.portfolio|storage\.data|firewall_rules\.portfolio)",
            address,
        ):
            raise ValueError("Unexpected infrastructure resource")
        if actions != ["no-op"]:
            public_fields = (
                ["plan", "zone", "firewall"]
                if address == "upcloud_server.portfolio"
                else ["size", "zone", "tier", "encrypt"]
                if address == "upcloud_storage.data"
                else []
            )
            after = item["change"].get("after") or {}
            output.append(
                {
                    "resource": address,
                    "actions": actions,
                    "configuration": {
                        key: after[key] for key in public_fields if key in after
                    },
                }
            )
    return output


def configuration_fingerprint():
    names = [
        "TF_VAR_zone",
        "TF_VAR_plan",
        "TF_VAR_deploy_user",
        "TF_VAR_ssh_allowed_cidrs",
        "TF_VAR_deploy_ssh_public_key",
        "TF_VAR_operator_ssh_public_key",
        "TF_STATE_BUCKET",
        "TF_STATE_REGION",
        "TF_STATE_KMS_KEY",
        "TF_STATE_KEY",
    ]
    required(*names)
    return hashlib.sha256(
        json.dumps({key: os.environ[key] for key in names}, sort_keys=True).encode()
    ).hexdigest()


def state_init():
    required("UPCLOUD_TOKEN", "AWS_ACCESS_KEY_ID", "AWS_SECRET_ACCESS_KEY")
    configuration_fingerprint()
    if (
        os.environ.get("TF_LOG")
        or os.environ.get("TF_LOG_PROVIDER")
        or any(
            key.startswith("TF_CLI_ARGS") and value for key, value in os.environ.items()
        )
    ):
        raise ValueError("Terraform debug logging is forbidden with credentials")
    bucket = os.environ["TF_STATE_BUCKET"]
    versioning = json.loads(
        run(["aws", "s3api", "get-bucket-versioning", "--bucket", bucket])
    )
    access = json.loads(
        run(["aws", "s3api", "get-public-access-block", "--bucket", bucket])
    )
    encryption = json.loads(
        run(["aws", "s3api", "get-bucket-encryption", "--bucket", bucket])
    )
    if versioning.get("Status") != "Enabled" or not all(
        access["PublicAccessBlockConfiguration"].values()
    ):
        raise ValueError("State bucket must be private and versioned")
    rules = encryption["ServerSideEncryptionConfiguration"]["Rules"]
    if not any(
        rule["ApplyServerSideEncryptionByDefault"].get("SSEAlgorithm") == "aws:kms"
        and rule["ApplyServerSideEncryptionByDefault"].get("KMSMasterKeyID")
        == os.environ["TF_STATE_KMS_KEY"]
        for rule in rules
    ):
        raise ValueError("State bucket must use the configured KMS key")
    with tempfile.TemporaryDirectory() as temporary:
        config = Path(temporary) / "backend.hcl"
        data = {
            "bucket": bucket,
            "region": os.environ["TF_STATE_REGION"],
            "key": os.environ["TF_STATE_KEY"],
            "kms_key_id": os.environ["TF_STATE_KMS_KEY"],
        }
        config.write_text(
            "\n".join(key + " = " + json.dumps(value) for key, value in data.items())
        )
        run(
            [
                "terraform",
                "init",
                "-input=false",
                "-lockfile=readonly",
                "-backend-config=" + str(config),
            ],
            cwd=TF,
        )


def catalog():
    required("UPCLOUD_TOKEN", "TF_VAR_zone", "TF_VAR_plan")

    def fetch(endpoint):
        request = urllib.request.Request(
            "https://api.upcloud.com/1.3/" + endpoint,
            headers={"Authorization": "Bearer " + os.environ["UPCLOUD_TOKEN"]},
        )
        return json.load(urllib.request.urlopen(request, timeout=30))

    plans = fetch("plan/")["plans"]["plan"]
    zones = fetch("zone/")["zones"]["zone"]
    if not any(plan["name"] == os.environ["TF_VAR_plan"] for plan in plans):
        raise ValueError("Selected plan is absent from current UpCloud catalog")
    if not any(
        zone["id"] == os.environ["TF_VAR_zone"] and zone.get("public", "yes") == "yes"
        for zone in zones
    ):
        raise ValueError("Selected zone is not available publicly")
    print(
        "Selected plan/zone exist in current catalog; verify regional capacity and total quote before apply."
    )


def object_path(run_id, name):
    if not re.fullmatch(r"[0-9]+", str(run_id)):
        raise ValueError("Invalid plan run identifier")
    return (
        "s3://"
        + os.environ["TF_STATE_BUCKET"]
        + "/reviewed-plans/"
        + str(run_id)
        + "/"
        + name
    )


def plan():
    protected_environment()
    state_init()
    catalog()
    with tempfile.TemporaryDirectory() as temporary:
        path = Path(temporary) / "reviewed.tfplan"
        run(
            [
                "terraform",
                "plan",
                "-input=false",
                "-lock-timeout=5m",
                "-out=" + str(path),
            ],
            cwd=TF,
        )
        changes = safe_summary(
            json.loads(run(["terraform", "show", "-json", str(path)], cwd=TF))
        )
        digest = hashlib.sha256(path.read_bytes()).hexdigest()
        metadata = {
            "sha": os.environ["GITHUB_SHA"],
            "run_id": os.environ["GITHUB_RUN_ID"],
            "digest": digest,
            "configuration": configuration_fingerprint(),
            "created": int(time.time()),
            "changes": changes,
            "lockfile": hashlib.sha256(
                (TF / ".terraform.lock.hcl").read_bytes()
            ).hexdigest(),
        }
        meta = Path(temporary) / "metadata.json"
        meta.write_text(json.dumps(metadata))
        for source, name in [(path, "reviewed.tfplan"), (meta, "metadata.json")]:
            run(
                [
                    "aws",
                    "s3",
                    "cp",
                    str(source),
                    object_path(metadata["run_id"], name),
                    "--only-show-errors",
                    "--sse",
                    "aws:kms",
                    "--sse-kms-key-id",
                    os.environ["TF_STATE_KMS_KEY"],
                ]
            )
        summary = (
            "### Reviewed Terraform plan\nCommit: `"
            + metadata["sha"]
            + "`\n\nRun: `"
            + metadata["run_id"]
            + "`\n\nPlan SHA256: `"
            + digest
            + "`\n\nChanges: `"
            + json.dumps(changes)
            + "`\n\nNo infrastructure was modified. Plan expires in 24 hours.\n"
        )
        Path(os.environ["GITHUB_STEP_SUMMARY"]).write_text(summary)
        print(
            "Sanitized plan summary written; encrypted plan stored privately, never as an Actions artifact."
        )


def verify_run(run_id, filename, sha):
    if not re.fullmatch(r"\d+", str(run_id)) or not re.fullmatch(r"[0-9a-f]{40}", sha):
        raise ValueError("Invalid run/commit")
    details = github("actions/runs/" + str(run_id))
    if (
        details["conclusion"] != "success"
        or details["head_sha"] != sha
        or details["path"] != ".github/workflows/" + filename
        or details["head_branch"] != "master"
        or details["head_repository"]["full_name"] != os.environ["GITHUB_REPOSITORY"]
    ):
        raise ValueError(
            "Run must be successful on the exact repository/master commit and expected workflow"
        )
    return details


def apply():
    protected_environment()
    required("PLAN_RUN_ID", "EXPECTED_SHA", "PLAN_SHA256")
    if os.environ["EXPECTED_SHA"] != os.environ["GITHUB_SHA"]:
        raise ValueError("Apply must be dispatched on the exact planned commit")
    verify_run(
        os.environ["PLAN_RUN_ID"], "terraform-plan.yml", os.environ["EXPECTED_SHA"]
    )
    state_init()
    with tempfile.TemporaryDirectory() as temporary:
        path, meta = (
            Path(temporary) / "reviewed.tfplan",
            Path(temporary) / "metadata.json",
        )
        for name, destination in [("reviewed.tfplan", path), ("metadata.json", meta)]:
            run(
                [
                    "aws",
                    "s3",
                    "cp",
                    object_path(os.environ["PLAN_RUN_ID"], name),
                    str(destination),
                    "--only-show-errors",
                ]
            )
        data = json.loads(meta.read_text())
        digest = hashlib.sha256(path.read_bytes()).hexdigest()
        if (
            not re.fullmatch(r"[0-9a-f]{64}", os.environ["PLAN_SHA256"])
            or digest != os.environ["PLAN_SHA256"]
            or digest != data["digest"]
            or data["sha"] != os.environ["GITHUB_SHA"]
            or data["configuration"] != configuration_fingerprint()
            or data["lockfile"]
            != hashlib.sha256((TF / ".terraform.lock.hcl").read_bytes()).hexdigest()
            or not 0 <= time.time() - data["created"] <= 86400
        ):
            raise ValueError(
                "Reviewed plan integrity, configuration or age check failed"
            )
        safe_summary(json.loads(run(["terraform", "show", "-json", str(path)], cwd=TF)))
        # Saved plans reject stale state; backend locking and workflow concurrency are also enabled.
        run(
            ["terraform", "apply", "-input=false", "-lock-timeout=5m", str(path)],
            cwd=TF,
        )
        address = json.loads(
            run(["terraform", "output", "-json", "public_ipv4"], cwd=TF)
        )
        ipaddress.IPv4Address(address)
        with Path(os.environ["GITHUB_STEP_SUMMARY"]).open("a") as summary:
            summary.write(
                "\nPublic IPv4: `"
                + address
                + "`\n\nSTOP. Send this IP to the subdomain owner; no application is deployed.\n"
            )


def ci(sha, *, wait=False):
    if not re.fullmatch(r"[0-9a-f]{40}", sha):
        raise ValueError("Full commit SHA required")
    for attempt in range(45 if wait else 1):
        completed = []
        for workflow in WORKFLOWS:
            runs = github(
                "actions/workflows/"
                + workflow
                + "/runs?head_sha="
                + sha
                + "&event=push&per_page=100"
            )["workflow_runs"]
            matched = [
                item
                for item in runs
                if item["head_branch"] == "master"
                and item["head_repository"]["full_name"]
                == os.environ["GITHUB_REPOSITORY"]
            ]
            completed.append(bool(matched and matched[0]["conclusion"] == "success"))
        if all(completed):
            return
        if attempt < 44 and wait:
            time.sleep(20)
    raise ValueError(
        "All required CI workflows must succeed on the exact master commit"
    )


def dns(domain, host):
    # Reuse the host's input restrictions and exact A/no-AAAA policy without root execution.
    import importlib.util

    spec = importlib.util.spec_from_file_location(
        "release_validation", ROOT / "deploy/ops/release.py"
    )
    module = importlib.util.module_from_spec(spec)
    # fcntl is Linux-only; this orchestration command is used on Linux CI.
    spec.loader.exec_module(module)
    module.check_dns({"domain": domain, "host": host})


def deploy():
    protected_environment()
    required(
        "BUILD_RUN_ID",
        "EXPECTED_SHA",
        "DEPLOY_HOST",
        "DEPLOY_USER",
        "APP_DOMAIN",
        "ACME_EMAIL",
        "DEPLOY_SSH_PRIVATE_KEY",
        "DEPLOY_SSH_KNOWN_HOSTS",
    )
    sha = os.environ["EXPECTED_SHA"]
    if (
        os.environ.get("DEPLOY_ACTION", "deploy") == "deploy"
        and sha != os.environ["GITHUB_SHA"]
    ):
        raise ValueError("Deployment must use the reviewed workflow commit")
    verify_run(os.environ["BUILD_RUN_ID"], "docker-build.yml", sha)
    ci(sha)
    artifacts = github("actions/runs/" + os.environ["BUILD_RUN_ID"] + "/artifacts")[
        "artifacts"
    ]
    artifacts = [
        item
        for item in artifacts
        if item["name"] == "release-manifest" and not item["expired"]
    ]
    if len(artifacts) != 1:
        raise ValueError("One nonexpired verified release manifest is required")
    request = urllib.request.Request(
        artifacts[0]["archive_download_url"],
        headers={"Authorization": "Bearer " + os.environ["GH_TOKEN"]},
    )
    with urllib.request.build_opener(SafeRedirect()).open(
        request, timeout=30
    ) as response:
        archive = zipfile.ZipFile(io.BytesIO(response.read(1048576)))
    if archive.getinfo("release-manifest.json").file_size > 16384:
        raise ValueError("Oversized release manifest")
    value = json.loads(archive.read("release-manifest.json"))
    if value["sha"] != sha:
        raise ValueError("Image manifest commit mismatch")
    action = os.environ.get("DEPLOY_ACTION", "deploy")
    value.update(
        domain=os.environ["APP_DOMAIN"],
        email=os.environ["ACME_EMAIL"],
        host=os.environ["DEPLOY_HOST"],
    )
    if action != "remove-domain":
        dns(value["domain"], value["host"])
    if not re.fullmatch(
        r"[a-z][a-z0-9_]{2,20}", os.environ["DEPLOY_USER"]
    ) or os.environ["DEPLOY_USER"] in ["root", "operator"]:
        raise ValueError("Restricted non-root deployment identity required")
    ipaddress.IPv4Address(value["host"])
    with tempfile.TemporaryDirectory() as temporary:
        key, hosts = Path(temporary) / "key", Path(temporary) / "known_hosts"
        key.write_text(os.environ["DEPLOY_SSH_PRIVATE_KEY"] + "\n")
        hosts.write_text(os.environ["DEPLOY_SSH_KNOWN_HOSTS"] + "\n")
        key.chmod(0o600)
        hosts.chmod(0o600)
        # No shell interpolation, ssh-keyscan trust-on-first-use or private registry credentials.
        run(
            [
                "ssh",
                "-F",
                "/dev/null",
                "-i",
                str(key),
                "-o",
                "IdentitiesOnly=yes",
                "-o",
                "BatchMode=yes",
                "-o",
                "ForwardAgent=no",
                "-o",
                "GlobalKnownHostsFile=/dev/null",
                "-o",
                "StrictHostKeyChecking=yes",
                "-o",
                "UserKnownHostsFile=" + str(hosts),
                "-o",
                "ConnectTimeout=15",
                os.environ["DEPLOY_USER"] + "@" + value["host"],
                "sudo",
                "-n",
                "/usr/local/sbin/portfolio-release",
            ],
            input=json.dumps({"action": action, "release": value}).encode(),
        )
    print("Production operation completed and verified; no persistent volumes deleted")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action", choices=["plan", "apply", "deploy", "ci"])
    args = parser.parse_args()
    try:
        if args.action == "ci":
            ci(os.environ["EXPECTED_SHA"], wait=True)
        else:
            {"plan": plan, "apply": apply, "deploy": deploy}[args.action]()
    except Exception:
        print(
            "Automation failed safely. Check prerequisites/protected configuration; sensitive diagnostics were not printed.",
            flush=True,
        )
        raise SystemExit(1) from None
