"""Dedicated demo orchestration with its own GitHub Environment, plan policy and saved-plan checks.

The shared portfolio module supplies only low-level helpers (process execution, GitHub API,
state-bucket verification, catalog lookup, run verification). Its protected_environment(),
plan() and apply() are never called from here.
"""

import argparse
import hashlib
import ipaddress
import json
import os
import sys
import tempfile
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from infra import guards  # noqa: E402
from infrastructure import automation as shared  # noqa: E402

TF = guards.TERRAFORM_DIR
FINGERPRINT = [
    "TF_VAR_project_name",
    "TF_VAR_environment",
    "TF_VAR_upcloud_zone",
    "TF_VAR_server_plan",
    "TF_VAR_server_hostname",
    "TF_VAR_ssh_public_key",
    "TF_VAR_deploy_ssh_public_key",
    "TF_VAR_ssh_allowed_cidrs",
    "TF_VAR_server_timezone",
    "TF_VAR_boot_storage_tier",
    "TF_STATE_BUCKET",
    "TF_STATE_REGION",
    "TF_STATE_KMS_KEY",
    "TF_STATE_KEY",
    "DEPLOYMENT_ENVIRONMENT",
]


def fingerprint(mode):
    shared.required(*FINGERPRINT)
    guards.require_dedicated(os.environ, TF)
    values = {name: os.environ[name] for name in FINGERPRINT}
    values["operation"] = mode
    return hashlib.sha256(json.dumps(values, sort_keys=True).encode()).hexdigest()


def lockfile():
    return hashlib.sha256((TF / ".terraform.lock.hcl").read_bytes()).hexdigest()


def object_path(run_id, name):
    return guards.plan_object_path(os.environ["TF_STATE_BUCKET"], run_id, name)


def preflight(operation, mode):
    """Workflow, Environment and identity checks before any cloud or state command."""
    guards.require_workflow(os.environ, operation)
    guards.require_environment(os.environ, shared.github)
    if mode == "destroy":
        guards.authorize_destroy(os.environ)
    guards.approved_configuration(os.environ)
    # Shared state_init reads these module globals; bind them to the dedicated root.
    shared.TF = TF
    shared.configuration_fingerprint = lambda: fingerprint(mode)
    # Catalog helper expects these aliases; Terraform ignores undeclared TF_VAR aliases.
    os.environ["TF_VAR_zone"] = os.environ["TF_VAR_upcloud_zone"]
    os.environ["TF_VAR_plan"] = os.environ["TF_VAR_server_plan"]
    shared.state_init()


def state():
    return guards.state_identity(
        shared.run(["terraform", "state", "pull"], cwd=TF).decode()
    )


def inspect(path, mode):
    document = json.loads(shared.run(["terraform", "show", "-json", str(path)], cwd=TF))
    return guards.validate_plan(
        document,
        guards.approved_configuration(os.environ),
        destroy=mode == "destroy",
    )


def plan(mode):
    preflight("destroy" if mode == "destroy" else "plan", mode)
    if mode == "normal":
        shared.catalog()
    with tempfile.TemporaryDirectory() as temporary:
        path = Path(temporary) / "reviewed.tfplan"
        command = ["terraform", "plan", "-input=false", "-lock-timeout=5m"]
        if mode == "destroy":
            command.append("-destroy")
        shared.run([*command, "-out=" + str(path)], cwd=TF)
        changes = inspect(path, mode)
        digest = hashlib.sha256(path.read_bytes()).hexdigest()
        metadata = guards.plan_metadata(
            sha=os.environ["GITHUB_SHA"],
            run_id=os.environ["GITHUB_RUN_ID"],
            digest=digest,
            configuration=fingerprint(mode),
            created=int(time.time()),
            changes=changes,
            lockfile=lockfile(),
            mode=mode,
            state=state(),
        )
        meta = Path(temporary) / "metadata.json"
        meta.write_text(json.dumps(metadata))
        for source, name in [(path, "reviewed.tfplan"), (meta, "metadata.json")]:
            shared.run(
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
    hours = guards.PLAN_MAX_AGE[mode] // 3600
    Path(os.environ["GITHUB_STEP_SUMMARY"]).write_text(
        "### Reviewed dedicated Terraform plan ("
        + mode
        + ")\nEnvironment: `"
        + guards.GITHUB_ENVIRONMENT
        + "`\n\nCommit: `"
        + metadata["sha"]
        + "`\n\nRun: `"
        + metadata["run_id"]
        + "`\n\nPlan SHA256: `"
        + digest
        + "`\n\nChanges: `"
        + json.dumps(changes)
        + "`\n\nNo infrastructure was modified. Plan expires in "
        + str(hours)
        + " hour(s).\n"
    )
    print("Sanitized plan summary written; encrypted plan stored privately.")


def apply(mode):
    preflight("destroy" if mode == "destroy" else "apply", mode)
    shared.required("PLAN_RUN_ID", "EXPECTED_SHA", "PLAN_SHA256")
    if os.environ["EXPECTED_SHA"] != os.environ["GITHUB_SHA"]:
        raise ValueError("Apply must be dispatched on the exact planned commit")
    producer = guards.WORKFLOWS["destroy" if mode == "destroy" else "plan"]
    shared.verify_run(os.environ["PLAN_RUN_ID"], producer, os.environ["EXPECTED_SHA"])
    with tempfile.TemporaryDirectory() as temporary:
        path = Path(temporary) / "reviewed.tfplan"
        meta = Path(temporary) / "metadata.json"
        for name, destination in [("reviewed.tfplan", path), ("metadata.json", meta)]:
            shared.run(
                [
                    "aws",
                    "s3",
                    "cp",
                    object_path(os.environ["PLAN_RUN_ID"], name),
                    str(destination),
                    "--only-show-errors",
                ]
            )
        guards.verify_plan_metadata(
            json.loads(meta.read_text()),
            expected={
                "digest": os.environ["PLAN_SHA256"],
                "sha": os.environ["GITHUB_SHA"],
                "run_id": os.environ["PLAN_RUN_ID"],
                "configuration": fingerprint(mode),
                "lockfile": lockfile(),
                "mode": mode,
                "state": state(),
            },
            digest=hashlib.sha256(path.read_bytes()).hexdigest(),
            now=int(time.time()),
        )
        inspect(path, mode)
        # Terraform also rejects a saved plan whose state lineage/serial changed.
        shared.run(
            ["terraform", "apply", "-input=false", "-lock-timeout=5m", str(path)],
            cwd=TF,
        )
    if mode == "destroy":
        print("Reviewed destroy plan completed. Audit storage, snapshots and billing.")
        return
    address = json.loads(
        shared.run(["terraform", "output", "-json", "public_ipv4"], cwd=TF)
    )
    ipaddress.IPv4Address(address)
    with Path(os.environ["GITHUB_STEP_SUMMARY"]).open("a") as summary:
        summary.write(
            "\nPublic IPv4: `"
            + address
            + "`\n\nSTOP. Verify the host key via the UpCloud console before any deployment.\n"
        )


def ci():
    guards.require_workflow(os.environ, "deploy")
    shared.WORKFLOWS[:] = guards.REQUIRED_CI
    shared.ci(os.environ["EXPECTED_SHA"])


ACTIONS = {
    "plan": lambda: plan("normal"),
    "apply": lambda: apply("normal"),
    "destroy-plan": lambda: plan("destroy"),
    "destroy-apply": lambda: apply("destroy"),
    "ci": ci,
}


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action", choices=list(ACTIONS))
    try:
        ACTIONS[parser.parse_args().action]()
    except Exception:
        print(
            "Operation blocked or failed; sensitive cloud/state diagnostics withheld."
        )
        raise SystemExit(1) from None
