"""Static workflow boundaries: dedicated and shared infrastructure can never cross."""

import re
from pathlib import Path

import pytest
import yaml

from infra import guards

ROOT = Path(__file__).resolve().parents[2]
WORKFLOWS = ROOT / ".github/workflows"
DEDICATED = sorted(WORKFLOWS.glob("single-*.yml"))
SHARED_MUTATING = ["terraform-plan.yml", "terraform-apply.yml", "production-deploy.yml"]
MUTATING = [
    "single-terraform-plan.yml",
    "single-terraform-apply.yml",
    "single-terraform-destroy.yml",
    "single-deploy-production.yml",
]


def load(name):
    document = yaml.safe_load((WORKFLOWS / name).read_text())
    document["on"] = document.pop(True, document.get("on"))  # YAML parses `on` as True
    return document


def environments(name):
    return [
        job.get("environment")
        for job in load(name)["jobs"].values()
        if "environment" in job
    ]


@pytest.mark.parametrize("name", MUTATING)
def test_dedicated_workflows_use_only_dedicated_environment(name):
    assert environments(name) == [guards.GITHUB_ENVIRONMENT]
    text = (WORKFLOWS / name).read_text()
    assert not re.search(r"^\s+environment: production\s*$", text, re.M)
    assert "DEPLOYMENT_ENVIRONMENT: " + guards.GITHUB_ENVIRONMENT in text


@pytest.mark.parametrize("name", SHARED_MUTATING)
def test_shared_workflows_keep_shared_environment_and_paths(name):
    text = (WORKFLOWS / name).read_text()
    assert environments(name) == [guards.SHARED_GITHUB_ENVIRONMENT]
    assert guards.GITHUB_ENVIRONMENT not in text
    # 27: shared workflows never invoke dedicated automation or Terraform root.
    assert "infra/" not in text.replace("infrastructure/", "")
    assert "AIPD_" not in text


@pytest.mark.parametrize("workflow", DEDICATED, ids=lambda path: path.name)
def test_dedicated_workflows_never_reference_shared_paths(workflow):  # 28
    text = workflow.read_text()
    for forbidden in (
        "infrastructure/terraform",
        "infrastructure/automation.py",
        "portfolio",
        "compose.production.yml",
        "deploy/ops",
    ):
        assert forbidden not in text, forbidden


@pytest.mark.parametrize("name", MUTATING)
def test_dedicated_secrets_and_variables_are_namespaced(name):
    text = (WORKFLOWS / name).read_text()
    for secret in re.findall(r"secrets\.(\w+)", text):
        assert secret.startswith("AIPD_"), secret
    for variable in re.findall(r"vars\.(\w+)", text):
        assert variable.startswith(("AIPD_", "SINGLE_")), variable


@pytest.mark.parametrize("name", MUTATING)
def test_no_fallback_values_except_fail_closed_runner_label(name):
    for line in (WORKFLOWS / name).read_text().splitlines():
        if "||" in line:
            assert "runs-on:" in line and "not-configured" in line, line


@pytest.mark.parametrize("name", MUTATING)
def test_mutating_workflows_manual_only_with_safe_concurrency(name):
    document = load(name)
    assert set(document["on"]) == {"workflow_dispatch"}
    text = (WORKFLOWS / name).read_text()
    assert "cancel-in-progress: false" in text
    assert "write-all" not in text and "pull_request" not in text
    assert set(document["permissions"].values()) <= {"read", "none"}


def test_only_build_job_may_write_packages():
    for name in MUTATING:
        for job_name, job in load(name)["jobs"].items():
            permissions = job.get("permissions", {})
            writes = {k for k, v in permissions.items() if v == "write"}
            if name == "single-deploy-production.yml" and job_name == "build":
                assert writes == {"packages"}
                assert "environment" not in job
                assert "secrets." not in str(job)
            else:
                assert not writes, (name, job_name)


@pytest.mark.parametrize("name", [n for n in MUTATING if "terraform" in n])
def test_terraform_workflows_use_dedicated_state_and_group(name):
    text = (WORKFLOWS / name).read_text()
    assert "TF_STATE_KEY: " + guards.STATE_KEY in text
    assert "group: aiproductdemand-terraform-production" in text
    assert "python infra/automation.py" in text


def test_shared_and_dedicated_concurrency_groups_do_not_overlap():
    def groups(names):
        return {
            re.search(r"group: (\S+)", (WORKFLOWS / n).read_text()).group(1)
            for n in names
        }

    shared, dedicated = groups(SHARED_MUTATING), groups(MUTATING)
    assert not shared & dedicated
    assert all(g.startswith("portfolio-") for g in shared)
    assert all(g.startswith("aiproductdemand-") for g in dedicated)


def test_only_manual_workflows_can_mutate_cloud_resources():
    for workflow in WORKFLOWS.glob("*.yml"):
        text = workflow.read_text()
        if "UPCLOUD_TOKEN" in text or "terraform apply" in text:
            assert set(load(workflow.name)["on"]) == {"workflow_dispatch"}, (
                workflow.name
            )


def test_apply_and_deploy_are_not_chained_to_plan_or_build():
    for workflow in DEDICATED:
        text = workflow.read_text()
        assert "workflow_run" not in text and "gh workflow run" not in text


def test_dedicated_actions_are_pinned_to_immutable_commits():
    for workflow in DEDICATED:
        for ref in re.findall(r"uses: (\S+)", workflow.read_text()):
            assert re.search(r"@[0-9a-f]{40}$", ref), (workflow.name, ref)


def test_application_deploy_does_not_invoke_terraform_or_cloud_token():
    text = (WORKFLOWS / "single-deploy-production.yml").read_text()
    assert "terraform" not in text.lower() and "UPCLOUD_TOKEN" not in text


def test_deploy_runs_on_fixed_egress_runner_with_pinned_host():
    job = load("single-deploy-production.yml")["jobs"]["deploy"]
    assert "ubuntu-latest" not in job["runs-on"]
    assert "SINGLE_DEPLOY_RUNNER_LABEL" in job["runs-on"]
    assert job["env"]["DEPLOY_HOST_KEY_FINGERPRINT"].startswith("${{ vars.")
    assert "python infra/deploy_transport.py" in str(job["steps"])


def test_build_ci_gate_uses_dedicated_required_checks():
    text = (WORKFLOWS / "single-deploy-production.yml").read_text()
    assert "python infra/automation.py ci" in text
    assert "single-validate.yml" in guards.REQUIRED_CI


def test_destroy_target_is_dedicated_environment_only():
    inputs = load("single-terraform-destroy.yml")["on"]["workflow_dispatch"]["inputs"]
    assert inputs["environment"]["options"] == [guards.GITHUB_ENVIRONMENT]


def test_offline_validation_has_no_secrets():
    assert "${{ secrets." not in (WORKFLOWS / "single-validate.yml").read_text()


def test_shared_protected_environment_unchanged():
    source = (ROOT / "infrastructure/automation.py").read_text()
    assert 'github("environments/production")' in source
    assert "aiproductdemand" not in source
