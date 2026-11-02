"""Static and behavioral guards: the dedicated demo must never reach shared-portfolio infrastructure."""

import re
from pathlib import Path

import pytest
import yaml

from infra import automation, deploy_transport, guards

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


def env():
    return {
        "TF_STATE_KEY": guards.STATE_KEY,
        "TF_VAR_project_name": guards.PROJECT,
        "TF_VAR_environment": guards.ENVIRONMENT,
        "TF_VAR_server_hostname": guards.HOSTNAME,
        "TF_VAR_upcloud_zone": "sg-sin1",
    }


def test_valid_dedicated_identity_accepted():
    guards.require_dedicated(env())


@pytest.mark.parametrize(
    "name,value",
    [
        ("TF_STATE_KEY", "portfolio/production/terraform.tfstate"),
        ("TF_STATE_KEY", "aiproductdemand/staging/terraform.tfstate"),
        ("TF_VAR_project_name", "portfolio"),
        ("TF_VAR_environment", "staging"),
        ("TF_VAR_server_hostname", "portfolio-prod"),
        ("TF_VAR_upcloud_zone", "de-fra1"),
        ("TF_VAR_upcloud_zone", "sg-sin1; rm"),
    ],
)
def test_mismatched_identity_rejected(name, value):
    values = env()
    values[name] = value
    with pytest.raises(ValueError):
        guards.require_dedicated(values)


def test_shared_terraform_directory_rejected():
    with pytest.raises(ValueError):
        guards.require_dedicated(env(), guards.SHARED_TERRAFORM_DIR)


def test_dedicated_automation_binds_dedicated_root_and_checks(monkeypatch):
    for name in (
        "configuration_fingerprint",
        "safe_summary",
        "run",
        "verify_run",
        "object_path",
    ):
        monkeypatch.setattr(automation.shared, name, getattr(automation.shared, name))
    monkeypatch.setattr(
        automation.shared, "WORKFLOWS", list(automation.shared.WORKFLOWS)
    )
    monkeypatch.setattr(automation, "MODE", "normal")
    assert automation.shared.TF.resolve() == guards.TERRAFORM_DIR.resolve()
    automation.configure("normal")
    assert "single-validate.yml" in automation.shared.WORKFLOWS
    assert automation.shared.object_path.__module__ == automation.__name__


def test_plan_objects_are_project_scoped_and_validated():
    path = guards.plan_object_path("bucket", "123", "reviewed.tfplan")
    assert path == "s3://bucket/reviewed-plans/aiproductdemand/123/reviewed.tfplan"
    for run_id, name in [
        ("../1", "metadata.json"),
        ("1", "../../state"),
        ("x", "metadata.json"),
    ]:
        with pytest.raises(ValueError):
            guards.plan_object_path("bucket", run_id, name)


def plan(address, after=None, actions=("create",), **extra):
    return {
        "resource_changes": [
            {
                "address": address,
                "change": {"actions": list(actions), "after": after or {}},
                **extra,
            }
        ]
    }


def rule(port, **extra):
    return {
        "direction": "in",
        "action": "accept",
        "protocol": "tcp",
        "destination_port_start": port,
        "destination_port_end": port,
        **extra,
    }


def test_expected_plan_accepted():
    guards.validate_plan(plan(guards.SERVER, {"zone": "sg-sin1"}))
    ssh = rule(
        "22", source_address_start="203.0.113.4", source_address_end="203.0.113.4"
    )
    guards.validate_plan(
        plan(guards.FIREWALL, {"firewall_rule": [ssh, rule("80"), rule("443")]})
    )


@pytest.mark.parametrize(
    "document",
    [
        plan("upcloud_storage.data"),
        plan("upcloud_server.app", index=1),
        plan("upcloud_server.app", mode="data"),
        plan("aws_s3_bucket.state"),
        plan(guards.SERVER, {"zone": "de-fra1"}),
        plan(guards.FIREWALL, {"firewall_rule": [rule("5432")]}),
        plan(guards.FIREWALL, {"firewall_rule": [rule("8000")]}),
        plan(
            guards.FIREWALL,
            {
                "firewall_rule": [
                    rule(
                        "22",
                        source_address_start="0.0.0.0",
                        source_address_end="255.255.255.255",
                    )
                ]
            },
        ),
        plan(guards.FIREWALL, {"firewall_rule": [rule("22")]}),
        plan(guards.SERVER, actions=("delete", "create")),
    ],
)
def test_unexpected_plans_rejected(document):
    with pytest.raises(ValueError):
        guards.validate_plan(document)


def test_duplicate_server_rejected():
    document = plan(guards.SERVER)
    document["resource_changes"] *= 2
    with pytest.raises(ValueError):
        guards.validate_plan(document)


def transport(**override):
    ip = "8.8.8.8"
    values = {
        "DEPLOY_HOST": ip,
        "SCHEMA_COMPATIBLE": "true",
        "DEPLOY_SSH_PRIVATE_KEY": "-----BEGIN OPENSSH PRIVATE KEY-----\nabc\n-----END OPENSSH PRIVATE KEY-----",
        "DEPLOY_SSH_KNOWN_HOSTS": ip + " ssh-ed25519 AAAA",
    }
    values.update(override)
    return values


def test_valid_transport_accepted():
    assert str(deploy_transport.validate_transport(transport())) == "8.8.8.8"


@pytest.mark.parametrize(
    "override",
    [
        {
            "DEPLOY_HOST": "10.0.0.5",
            "DEPLOY_SSH_KNOWN_HOSTS": "10.0.0.5 ssh-ed25519 AAAA",
        },
        {"SCHEMA_COMPATIBLE": "false"},
        {"DEPLOY_SSH_PRIVATE_KEY": "-----BEGIN RSA PRIVATE KEY-----\nabc"},
        {"DEPLOY_SSH_KNOWN_HOSTS": ""},
        {"DEPLOY_SSH_KNOWN_HOSTS": "9.9.9.9 ssh-ed25519 AAAA"},
        {"DEPLOY_SSH_KNOWN_HOSTS": "* ssh-ed25519 AAAA"},
        {"DEPLOY_SSH_KNOWN_HOSTS": "8.8.8.8 ssh-rsa AAAA"},
        {"DEPLOY_SSH_KNOWN_HOSTS": "@cert-authority 8.8.8.8 ssh-ed25519 AAAA"},
    ],
)
def test_unsafe_transport_rejected(override):
    with pytest.raises(ValueError):
        deploy_transport.validate_transport(transport(**override))


def test_deploy_uses_deployer_user_with_restricted_command():
    source = (ROOT / "infra/deploy_transport.py").read_text()
    assert '"deployer@"' in source and "ForwardAgent=no" in source
    assert "StrictHostKeyChecking=yes" in source and "BatchMode=yes" in source


@pytest.mark.parametrize("workflow", DEDICATED, ids=lambda path: path.name)
def test_dedicated_workflows_never_reference_shared_paths(workflow):
    text = workflow.read_text()
    assert "infrastructure/terraform" not in text
    assert "portfolio/" not in text and "compose.production.yml" not in text
    assert "deploy/ops" not in text
    assert "infrastructure/automation.py" not in text


@pytest.mark.parametrize("name", MUTATING)
def test_mutating_workflows_manual_only_with_environment(name):
    document = load(name)
    assert set(document["on"]) == {"workflow_dispatch"}
    text = (WORKFLOWS / name).read_text()
    assert "environment: production" in text
    assert "cancel-in-progress: false" in text
    assert "write-all" not in text
    assert "pull_request" not in text


@pytest.mark.parametrize("name", [n for n in MUTATING if "terraform" in n])
def test_terraform_workflows_use_dedicated_state_and_group(name):
    text = (WORKFLOWS / name).read_text()
    assert "TF_STATE_KEY: aiproductdemand/production/terraform.tfstate" in text
    assert "group: aiproductdemand-terraform-production" in text
    assert "infra/automation.py" in text


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


def test_offline_validation_has_no_secrets():
    text = (WORKFLOWS / "single-validate.yml").read_text()
    assert "${{ secrets." not in text
