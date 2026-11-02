"""Dedicated demo orchestration; reuse the repository's protected saved-plan protocol."""

import argparse
import hashlib
import json
import os
import re
import sys
import tempfile
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from infra import guards  # noqa: E402
from infrastructure import automation as shared  # noqa: E402

shared.TF = ROOT / "infra/terraform"
ORIGINAL_RUN = shared.run
ORIGINAL_VERIFY = shared.verify_run
MODE = "normal"


def fingerprint():
    names = [
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
    ]
    shared.required(*names)
    guards.require_dedicated(os.environ, shared.TF)
    values = {name: os.environ[name] for name in names}
    values["operation"] = MODE
    return hashlib.sha256(json.dumps(values, sort_keys=True).encode()).hexdigest()


def summary(document):
    return guards.validate_plan(document, destroy=MODE == "destroy")


def object_path(run_id, name):
    return guards.plan_object_path(os.environ["TF_STATE_BUCKET"], run_id, name)


def run(args, **kwargs):
    if MODE == "destroy" and args[:2] == ["terraform", "plan"]:
        args = [*args[:2], "-destroy", *args[2:]]
    return ORIGINAL_RUN(args, **kwargs)


def verify(run_id, filename, sha):
    expected = (
        "single-terraform-destroy.yml"
        if MODE == "destroy"
        else "single-terraform-plan.yml"
    )
    return ORIGINAL_VERIFY(run_id, expected, sha)


def configure(mode):
    global MODE
    MODE = mode
    # Catalog helper expects these aliases; Terraform ignores undeclared TF_VAR aliases.
    os.environ["TF_VAR_zone"] = os.environ.get("TF_VAR_upcloud_zone", "")
    os.environ["TF_VAR_plan"] = os.environ.get("TF_VAR_server_plan", "")
    shared.configuration_fingerprint = fingerprint
    shared.safe_summary = summary
    shared.run = run
    shared.verify_run = verify
    shared.object_path = object_path
    shared.WORKFLOWS[:] = guards.REQUIRED_CI


def destroy_apply():
    shared.protected_environment()
    shared.required("PLAN_RUN_ID", "EXPECTED_SHA", "PLAN_SHA256")
    verify(os.environ["PLAN_RUN_ID"], "", os.environ["EXPECTED_SHA"])
    shared.state_init()
    with tempfile.TemporaryDirectory() as temporary:
        plan = Path(temporary) / "reviewed.tfplan"
        metadata = Path(temporary) / "metadata.json"
        for name, path in [("reviewed.tfplan", plan), ("metadata.json", metadata)]:
            run(
                [
                    "aws",
                    "s3",
                    "cp",
                    object_path(os.environ["PLAN_RUN_ID"], name),
                    str(path),
                    "--only-show-errors",
                ]
            )
        data = json.loads(metadata.read_text())
        digest = hashlib.sha256(plan.read_bytes()).hexdigest()
        if (
            digest != os.environ["PLAN_SHA256"]
            or digest != data["digest"]
            or data["sha"] != os.environ["GITHUB_SHA"]
            or data["configuration"] != fingerprint()
            or data["lockfile"]
            != hashlib.sha256(
                (shared.TF / ".terraform.lock.hcl").read_bytes()
            ).hexdigest()
            or not 0 <= time.time() - data["created"] <= 3600
        ):
            raise ValueError(
                "Destroy plan integrity, state configuration or age mismatch"
            )
        summary(
            json.loads(run(["terraform", "show", "-json", str(plan)], cwd=shared.TF))
        )
        # Terraform itself rejects changed state serial/lineage under backend locking.
        run(
            ["terraform", "apply", "-input=false", "-lock-timeout=5m", str(plan)],
            cwd=shared.TF,
        )
        print(
            "Reviewed destroy plan completed. Audit orphaned storage, snapshots and state separately."
        )


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "action", choices=["plan", "apply", "destroy-plan", "destroy-apply", "ci"]
    )
    args = parser.parse_args()
    try:
        configure("destroy" if args.action.startswith("destroy") else "normal")
        if args.action == "ci":
            shared.ci(os.environ["EXPECTED_SHA"])
            raise SystemExit(0)
        if MODE == "destroy":
            if os.environ.get("BACKUP_CONFIRMATION") != "OFFHOST-RESTORE-VERIFIED":
                raise ValueError(
                    "Verified off-host restore and resource inventory approval required"
                )
            if not re.fullmatch(r"[0-9a-f]{40}", os.environ.get("EXPECTED_SHA", "")):
                raise ValueError("Reviewed teardown commit required")
            if os.environ["EXPECTED_SHA"] != os.environ.get("GITHUB_SHA"):
                raise ValueError("Teardown commit mismatch")
        if args.action.endswith("plan"):
            shared.plan()
        elif MODE == "destroy":
            destroy_apply()
        else:
            shared.apply()
    except Exception:
        print(
            "Operation blocked or failed; sensitive cloud/state diagnostics withheld."
        )
        raise SystemExit(1) from None
