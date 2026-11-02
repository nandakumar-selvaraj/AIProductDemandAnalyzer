"""Synthetic Terraform plans, mocked GitHub responses and synthetic SSH structures; no real credentials."""

import base64
import copy
import hashlib
import json

import pytest

from infra import automation, guards

CIDRS = ["8.8.4.0/30", "8.8.8.8/32"]
ENV = {
    "TF_STATE_KEY": guards.STATE_KEY,
    "TF_VAR_project_name": guards.PROJECT,
    "TF_VAR_environment": guards.ENVIRONMENT,
    "TF_VAR_server_hostname": guards.HOSTNAME,
    "TF_VAR_upcloud_zone": "sg-sin1",
    "TF_VAR_server_plan": "2xCPU-4GB",
    "TF_VAR_boot_storage_tier": "standard",
    "TF_VAR_ssh_allowed_cidrs": json.dumps(CIDRS),
}


def approved(**override):
    return guards.approved_configuration({**ENV, **override})


def server():
    return {
        "zone": "sg-sin1",
        "plan": "2xCPU-4GB",
        "hostname": guards.HOSTNAME,
        "title": "aiproductdemand-production (Demo 3 only)",
        "labels": {
            "project": "aiproductdemand",
            "environment": "production",
            "managed_by": "terraform-single-app",
        },
        "firewall": True,
        "metadata": True,
        "user_data": "PRIVATE-USER-DATA",
        "template": [
            {
                "storage": guards.TEMPLATE,
                "size": 30,
                "tier": "standard",
                "encrypt": True,
                "title": "boot",
            }
        ],
        "login": [
            {
                "user": "operator",
                "keys": ["ssh-ed25519 AAAA"],
                "create_password": False,
                "password_delivery": "none",
            }
        ],
        "network_interface": [{"type": "public", "ip_address_family": "IPv4"}],
    }


def firewall():
    rules = guards.expected_firewall(approved()["ssh_cidrs"])
    # Providers render unset optional attributes as null; policy normalises them.
    return {
        "server_id": None,
        "firewall_rule": [
            {key: (value or None) for key, value in rule.items()} for rule in rules
        ],
    }


def change(address, after, actions=("create",), unknown=None):
    resource_type, name = address.split(".")
    return {
        "address": address,
        "mode": "managed",
        "type": resource_type,
        "name": name,
        "change": {
            "actions": list(actions),
            "after": after,
            "after_unknown": unknown or {},
        },
    }


def planned(address, values):
    resource_type, name = address.split(".")
    return {
        "address": address,
        "mode": "managed",
        "type": resource_type,
        "name": name,
        "values": values,
    }


def document(actions=("create",)):
    return {
        "format_version": "1.2",
        "resource_changes": [
            change(
                guards.SERVER,
                server(),
                actions,
                {"id": True, "network_interface": [{"ip_address": True}]},
            ),
            change(guards.FIREWALL, firewall(), actions, {"server_id": True}),
        ],
        "planned_values": {
            "root_module": {
                "resources": [
                    planned(guards.SERVER, server()),
                    planned(guards.FIREWALL, firewall()),
                ]
            }
        },
    }


def both(plan, address, mutate):
    """Apply the same mutation to resource_changes and planned_values (consistent tampering)."""
    for item in plan["resource_changes"]:
        if item["address"] == address:
            mutate(item["change"]["after"])
    for item in plan["planned_values"]["root_module"]["resources"]:
        if item["address"] == address:
            mutate(item["values"])
    return plan


def rules(plan):
    return [
        item["change"]["after"]["firewall_rule"]
        for item in plan["resource_changes"]
        if item["address"] == guards.FIREWALL
    ][0]


# ---------- accepted baselines ----------


def test_approved_create_plan_accepted():
    result = guards.validate_plan(document(), approved())
    assert [item["resource"] for item in result] == [guards.SERVER, guards.FIREWALL]
    assert "PRIVATE" not in json.dumps(result)


def test_no_op_resources_are_still_validated():
    guards.validate_plan(document(("no-op",)), approved())
    plan = both(
        document(("no-op",)), guards.FIREWALL, lambda v: v["firewall_rule"].pop()
    )
    with pytest.raises(ValueError):
        guards.validate_plan(plan, approved())


# ---------- resource identity and completeness ----------


def extra(plan, address, **fields):
    resource_type, name = address.split(".")
    plan["resource_changes"].append({**change(address, server()), **fields})
    plan["planned_values"]["root_module"]["resources"].append(
        {**planned(address, server()), **fields}
    )
    return plan


@pytest.mark.parametrize(
    "plan",
    [
        extra(document(), "upcloud_server.second"),  # 13 additional VPS
        extra(document(), "upcloud_storage.data"),  # 14 unexpected storage
        extra(document(), "upcloud_server.portfolio"),  # 28 shared resource
        extra(document(), "aws_s3_bucket.state"),
    ],
)
def test_additional_resources_rejected(plan):
    with pytest.raises(ValueError):
        guards.validate_plan(plan, approved())


def test_duplicate_and_indexed_and_data_resources_rejected():
    plan = document()
    plan["resource_changes"].append(copy.deepcopy(plan["resource_changes"][0]))
    with pytest.raises(ValueError):
        guards.validate_plan(plan, approved())
    for field, value in [("index", 1), ("mode", "data"), ("deposed", "abc")]:
        plan = document()
        plan["resource_changes"][0][field] = value
        with pytest.raises(ValueError):
            guards.validate_plan(plan, approved())


def test_nested_module_resource_rejected():  # 24
    plan = document()
    plan["planned_values"]["root_module"]["child_modules"] = [
        {"address": "module.x", "resources": [planned("upcloud_server.app", server())]}
    ]
    with pytest.raises(ValueError):
        guards.validate_plan(plan, approved())
    plan = document()
    plan["resource_changes"][0]["module_address"] = "module.x"
    with pytest.raises(ValueError):
        guards.validate_plan(plan, approved())


def test_resource_missing_from_changes_or_planned_values_rejected():
    plan = document()
    plan["resource_changes"].pop()
    with pytest.raises(ValueError):
        guards.validate_plan(plan, approved())
    plan = document()
    plan["planned_values"]["root_module"]["resources"].pop()
    with pytest.raises(ValueError):
        guards.validate_plan(plan, approved())


@pytest.mark.parametrize(
    "structure", [{}, {"resource_changes": None}, {"errored": True}]
)
def test_incomplete_plans_rejected(structure):
    plan = {**document(), **structure}
    if not structure:
        plan = {}
    with pytest.raises(ValueError):
        guards.validate_plan(plan, approved())


@pytest.mark.parametrize(
    "actions",
    [["delete"], ["delete", "create"], ["create", "delete"], ["read"], ["forget"]],
)
def test_replacement_deletion_and_unknown_actions_rejected(actions):  # 21
    with pytest.raises(ValueError):
        guards.validate_plan(document(actions), approved())


# ---------- region and server ----------


@pytest.mark.parametrize("zone", ["de-fra1", "sg-sin2", None, ""])  # 9, 10
def test_wrong_or_missing_region_rejected(zone):
    plan = both(document(), guards.SERVER, lambda v: v.update(zone=zone))
    with pytest.raises(ValueError):
        guards.validate_plan(plan, approved())


def test_unknown_region_rejected():  # 11
    plan = document()
    plan["resource_changes"][0]["change"]["after_unknown"]["zone"] = True
    with pytest.raises(ValueError):
        guards.validate_plan(plan, approved())


def test_arbitrary_singapore_zone_not_approved_by_variable():
    with pytest.raises(ValueError):
        approved(TF_VAR_upcloud_zone="sg-sin2")


@pytest.mark.parametrize(
    "mutate",
    [
        lambda v: v.update(plan="8xCPU-32GB"),  # 12
        lambda v: v.update(hostname="portfolio-prod"),
        lambda v: v["labels"].update(project="portfolio"),
        lambda v: v["labels"].update(extra="x"),
        lambda v: v.update(firewall=False),
        lambda v: v["template"][0].update(encrypt=False),
        lambda v: v["template"][0].update(size=200),
        lambda v: v["template"][0].update(tier="maxiops"),
        lambda v: v["template"][0].update(storage="Debian"),
        lambda v: v["template"].append(dict(v["template"][0])),
        lambda v: v["login"][0].update(create_password=True),
        lambda v: v["network_interface"].append(
            {"type": "public", "ip_address_family": "IPv6"}
        ),  # 18
        lambda v: v["network_interface"][0].update(ip_address_family="IPv6"),
        lambda v: v["network_interface"][0].update(type="private"),
        lambda v: v.update(storage_devices=[{"storage": "x"}]),  # 14
        lambda v: v.pop("template"),  # 23
        lambda v: v.pop("network_interface"),
    ],
)
def test_unexpected_server_configuration_rejected(mutate):
    plan = both(document(), guards.SERVER, mutate)
    with pytest.raises(ValueError):
        guards.validate_plan(plan, approved())


@pytest.mark.parametrize(
    "unknown",
    [
        {"plan": True},
        {"template": [{"encrypt": True}]},
        {"network_interface": [{"ip_address_family": True}]},
        {"labels": True},
    ],
)
def test_unknown_security_critical_server_values_rejected(unknown):  # 23
    plan = document()
    plan["resource_changes"][0]["change"]["after_unknown"].update(unknown)
    with pytest.raises(ValueError):
        guards.validate_plan(plan, approved())


def test_planned_values_must_agree_with_resource_changes():  # 22 inconsistent tamper
    plan = document()
    plan["planned_values"]["root_module"]["resources"][0]["values"]["zone"] = "de-fra1"
    with pytest.raises(ValueError):
        guards.validate_plan(plan, approved())


# ---------- firewall ----------


def tcp(port, **extra):
    return {
        "action": "accept",
        "direction": "in",
        "family": "IPv4",
        "protocol": "tcp",
        "destination_port_start": port,
        "destination_port_end": port,
        **extra,
    }


@pytest.mark.parametrize(
    "mutate",
    [
        lambda r: r.insert(0, tcp("5432")),  # 15
        lambda r: r.insert(0, tcp("8000")),
        lambda r: r.insert(
            0,
            tcp(
                "22",
                source_address_start="0.0.0.0",
                source_address_end="255.255.255.255",
            ),
        ),  # 16
        lambda r: r[0].update(source_address_end="8.8.255.255"),  # widened range
        lambda r: r[0].update(source_address_start=None, source_address_end=None),
        lambda r: r.insert(0, {**tcp("53"), "protocol": "udp"}),  # 17
        lambda r: r.insert(0, {**tcp("443"), "family": "IPv6"}),  # 18
        lambda r: r.insert(0, {"action": "accept", "direction": "in"}),  # broad
        lambda r: r.pop(-2),  # 19 default drop
        lambda r: r.pop(0),  # missing approved SSH CIDR
        lambda r: r[-2].update(action="accept"),
        lambda r: r.reverse(),
        lambda r: r.clear(),
    ],
)
def test_unapproved_firewall_policy_rejected(mutate):
    plan = document()
    mutate(rules(plan))
    plan["planned_values"]["root_module"]["resources"][1]["values"] = copy.deepcopy(
        plan["resource_changes"][1]["change"]["after"]
    )
    with pytest.raises(ValueError):
        guards.validate_plan(plan, approved())


def test_unknown_firewall_fields_rejected():
    plan = document()
    plan["resource_changes"][1]["change"]["after_unknown"]["firewall_rule"] = [
        {"source_address_start": True}
    ]
    with pytest.raises(ValueError):
        guards.validate_plan(plan, approved())
    plan = document()
    plan["resource_changes"][1]["change"]["after_unknown"]["firewall_rule"] = True
    with pytest.raises(ValueError):
        guards.validate_plan(plan, approved())


def test_ssh_ranges_must_match_approved_cidrs_exactly():
    with pytest.raises(ValueError):
        guards.validate_plan(
            document(), approved(TF_VAR_ssh_allowed_cidrs='["8.8.8.8/32"]')
        )


@pytest.mark.parametrize(
    "value",
    [
        '["0.0.0.0/0"]',
        '["8.8.0.0/16"]',
        '["10.0.0.0/24"]',
        '["8.8.8.1/24"]',
        '["2001:db8::/64"]',
        '["not-a-cidr"]',
        "[]",
        "8.8.8.8/32",
        '["8.8.8.8/32", "8.8.8.8/32"]',
    ],
)
def test_invalid_ssh_cidrs_rejected(value):  # 20
    with pytest.raises(ValueError):
        approved(TF_VAR_ssh_allowed_cidrs=value)


# ---------- destroy policy ----------


def destroy_document(*addresses):
    return {
        "format_version": "1.2",
        "resource_changes": [
            change(address, None, ("delete",)) for address in addresses
        ],
        "planned_values": {"root_module": {}},
    }


def test_destroy_policy_accepts_only_deletion_of_approved_resources():
    guards.validate_plan(
        destroy_document(guards.SERVER, guards.FIREWALL), approved(), destroy=True
    )
    for plan in [
        destroy_document(),
        destroy_document("upcloud_storage.data"),
        document(),
    ]:
        with pytest.raises(ValueError):
            guards.validate_plan(plan, approved(), destroy=True)
    leftover = destroy_document(guards.FIREWALL)
    leftover["planned_values"]["root_module"]["resources"] = [
        planned(guards.SERVER, server())
    ]
    with pytest.raises(ValueError):
        guards.validate_plan(leftover, approved(), destroy=True)


def destroy_env(**override):
    return {
        "BACKUP_CONFIRMATION": "OFFHOST-RESTORE-VERIFIED",
        "DESTROY_TARGET": guards.GITHUB_ENVIRONMENT,
        "EXPECTED_SHA": "a" * 40,
        "GITHUB_SHA": "a" * 40,
        **override,
    }


def test_authorized_destroy_accepted():
    guards.authorize_destroy(destroy_env())


@pytest.mark.parametrize(
    "override",
    [
        {"BACKUP_CONFIRMATION": "yes"},
        {"DESTROY_TARGET": "production"},
        {"EXPECTED_SHA": "b" * 40},
        {"EXPECTED_SHA": "short"},
    ],
)
def test_unauthorized_destroy_rejected(override):  # 25
    with pytest.raises(ValueError):
        guards.authorize_destroy(destroy_env(**override))


# ---------- saved-plan integrity ----------


def metadata(**override):
    value = guards.plan_metadata(
        sha="a" * 40,
        run_id="42",
        digest="d" * 64,
        configuration="c" * 64,
        created=1_000_000,
        changes=[],
        lockfile="l" * 64,
        mode="normal",
        state={"lineage": "x", "serial": 3},
    )
    value.update(override)
    return value


def expected(**override):
    return {
        "digest": "d" * 64,
        "sha": "a" * 40,
        "run_id": "42",
        "configuration": "c" * 64,
        "lockfile": "l" * 64,
        "mode": "normal",
        "state": {"lineage": "x", "serial": 3},
        **override,
    }


def test_untampered_metadata_accepted():
    guards.verify_plan_metadata(
        metadata(), expected=expected(), digest="d" * 64, now=1_000_100
    )


@pytest.mark.parametrize(
    "data,exp,digest,now",
    [
        (metadata(), expected(), "e" * 64, 1_000_100),  # 22 plan bytes tampered
        (metadata(digest="e" * 64), expected(), "d" * 64, 1_000_100),
        (metadata(sha="b" * 40), expected(), "d" * 64, 1_000_100),
        (metadata(configuration="x" * 64), expected(), "d" * 64, 1_000_100),
        (metadata(lockfile="x" * 64), expected(), "d" * 64, 1_000_100),
        (metadata(run_id="43"), expected(), "d" * 64, 1_000_100),
        (
            metadata(),
            expected(state={"lineage": "x", "serial": 4}),
            "d" * 64,
            1_000_100,
        ),
        (
            metadata(),
            expected(state={"lineage": "y", "serial": 3}),
            "d" * 64,
            1_000_100,
        ),
        (metadata(environment="production"), expected(), "d" * 64, 1_000_100),
        (metadata(prefix="reviewed-plans/"), expected(), "d" * 64, 1_000_100),  # 8
        (
            metadata(state_key="portfolio/production/terraform.tfstate"),
            expected(),
            "d" * 64,
            1_000_100,
        ),  # 7
        (metadata(mode="destroy"), expected(), "d" * 64, 1_000_100),
        (metadata(), expected(), "d" * 64, 1_000_000 + 86401),  # stale
        (metadata(), expected(), "d" * 64, 999_000),  # future
        (metadata(extra=1), expected(), "d" * 64, 1_000_100),
        (metadata(), expected(digest="D" * 64), "D" * 64, 1_000_100),
    ],
)
def test_tampered_or_stale_plans_rejected(data, exp, digest, now):
    with pytest.raises(ValueError):
        guards.verify_plan_metadata(data, expected=exp, digest=digest, now=now)


def test_destroy_plans_expire_after_one_hour():
    data = metadata(mode="destroy")
    with pytest.raises(ValueError):
        guards.verify_plan_metadata(
            data,
            expected=expected(mode="destroy"),
            digest="d" * 64,
            now=1_000_000 + 3601,
        )


def test_state_identity_never_keeps_resources():
    raw = json.dumps({"lineage": "abc", "serial": 7, "resources": [{"secret": "x"}]})
    assert guards.state_identity(raw) == {"lineage": "abc", "serial": 7}
    assert guards.state_identity("") == {"lineage": None, "serial": 0}
    with pytest.raises(ValueError):
        guards.state_identity('{"serial": "7"}')


def test_plan_objects_use_dedicated_prefix_only():  # 8
    assert guards.plan_object_path("b", "1", "metadata.json") == (
        "s3://b/reviewed-plans/aiproductdemand/1/metadata.json"
    )
    for run_id, name in [("../1", "metadata.json"), ("1", "../state"), ("1", "x")]:
        with pytest.raises(ValueError):
            guards.plan_object_path("b", run_id, name)


# ---------- GitHub Environment (mocked API) ----------


def github_settings(**override):
    environment = {
        "name": guards.GITHUB_ENVIRONMENT,
        "can_admins_bypass": False,
        "protection_rules": [
            {
                "type": "required_reviewers",
                "prevent_self_review": True,
                "reviewers": [{"type": "User", "reviewer": {"login": "reviewer"}}],
            }
        ],
        "deployment_branch_policy": {
            "protected_branches": False,
            "custom_branch_policies": True,
        },
    }
    environment.update(override)
    branches = {"branch_policies": [{"name": "master", "type": "branch"}]}

    def github(path):
        if path == "environments/" + guards.GITHUB_ENVIRONMENT:
            return environment
        if (
            path
            == "environments/"
            + guards.GITHUB_ENVIRONMENT
            + "/deployment-branch-policies"
        ):
            return branches
        raise AssertionError("unexpected API path " + path)

    return github, branches


def test_dedicated_environment_accepted():  # 2
    github, _ = github_settings()
    guards.require_environment(
        {"DEPLOYMENT_ENVIRONMENT": guards.GITHUB_ENVIRONMENT}, github
    )


@pytest.mark.parametrize("name", ["production", "", None, "aiproductdemand-staging"])
def test_shared_or_other_environment_rejected(name):  # 1
    github, _ = github_settings()
    with pytest.raises(ValueError):
        guards.require_environment({"DEPLOYMENT_ENVIRONMENT": name}, github)


@pytest.mark.parametrize(
    "override",
    [
        {"can_admins_bypass": True},  # 5
        {"protection_rules": []},  # 4
        {
            "protection_rules": [
                {
                    "type": "required_reviewers",
                    "reviewers": [],
                    "prevent_self_review": True,
                }
            ]
        },
        {
            "protection_rules": [
                {
                    "type": "required_reviewers",
                    "reviewers": [{}],
                    "prevent_self_review": False,
                }
            ]
        },
        {"deployment_branch_policy": None},
        {
            "deployment_branch_policy": {
                "protected_branches": True,
                "custom_branch_policies": False,
            }
        },
        {"name": "production"},
    ],
)
def test_unprotected_environment_rejected(override):
    github, _ = github_settings(**override)
    with pytest.raises(ValueError):
        guards.require_environment(
            {"DEPLOYMENT_ENVIRONMENT": guards.GITHUB_ENVIRONMENT}, github
        )


@pytest.mark.parametrize(
    "branches",
    [
        [],
        [{"name": "main"}],
        [{"name": "master"}, {"name": "dev"}],
        [{"name": "master", "type": "tag"}],
        [{"name": "*"}],
    ],
)
def test_branch_policies_other_than_master_rejected(branches):  # 3
    github, policy = github_settings()
    policy["branch_policies"] = branches
    with pytest.raises(ValueError):
        guards.require_environment(
            {"DEPLOYMENT_ENVIRONMENT": guards.GITHUB_ENVIRONMENT}, github
        )


def workflow_env(workflow, ref="refs/heads/master"):
    return {
        "GITHUB_REPOSITORY": "owner/repo",
        "GITHUB_WORKFLOW_REF": "owner/repo/.github/workflows/" + workflow + "@" + ref,
        "GITHUB_REF": ref,
    }


def test_dedicated_workflow_identity_accepted():
    for operation, workflow in guards.WORKFLOWS.items():
        guards.require_workflow(workflow_env(workflow), operation)


@pytest.mark.parametrize(
    "env",
    [
        workflow_env("single-terraform-apply.yml", "refs/heads/feature"),  # 3
        workflow_env("terraform-apply.yml"),  # 27 shared workflow
        workflow_env("production-deploy.yml"),
        workflow_env("single-terraform-plan.yml"),  # wrong operation
        {
            **workflow_env("single-terraform-apply.yml"),
            "GITHUB_REPOSITORY": "fork/repo",
        },
        {},
    ],
)
def test_foreign_branch_or_workflow_rejected(env):
    with pytest.raises(ValueError):
        guards.require_workflow(env, "apply")


def test_shared_environment_blocks_before_any_cloud_or_state_command(monkeypatch):
    calls = []
    monkeypatch.setattr(automation.shared, "run", lambda *a, **k: calls.append(a))
    monkeypatch.setattr(automation.shared, "state_init", lambda: calls.append("state"))
    monkeypatch.setattr(
        automation.shared, "github", lambda path: calls.append(path) or {}
    )
    monkeypatch.setattr(automation.shared, "TF", automation.shared.TF)
    monkeypatch.setattr(
        automation.shared,
        "configuration_fingerprint",
        automation.shared.configuration_fingerprint,
    )
    for key, value in {
        **ENV,
        **workflow_env("single-terraform-plan.yml"),
        "DEPLOYMENT_ENVIRONMENT": "production",
    }.items():
        monkeypatch.setenv(key, value)
    with pytest.raises(ValueError):
        automation.plan("normal")
    assert calls == []


def test_wrong_terraform_root_rejected():  # 6
    with pytest.raises(ValueError):
        guards.require_dedicated(ENV, guards.SHARED_TERRAFORM_DIR)
    assert automation.TF.resolve() == guards.TERRAFORM_DIR.resolve()


@pytest.mark.parametrize(
    "name,value",
    [
        ("TF_STATE_KEY", "portfolio/production/terraform.tfstate"),  # 7
        ("TF_STATE_KEY", "aiproductdemand/staging/terraform.tfstate"),
        ("TF_VAR_project_name", "portfolio"),
        ("TF_VAR_environment", "staging"),
        ("TF_VAR_server_hostname", "portfolio-prod"),
        ("TF_VAR_upcloud_zone", "de-fra1"),
        ("TF_VAR_server_plan", ""),
        ("TF_VAR_server_plan", "plan; rm"),
        ("TF_VAR_boot_storage_tier", "hdd"),
    ],
)
def test_mismatched_identity_rejected(name, value):
    with pytest.raises(ValueError):
        approved(**{name: value})


# ---------- SSH ----------


def ssh_string(value):
    return len(value).to_bytes(4, "big") + value


def public_blob(kind=b"ssh-ed25519", key=b"\x01" * 32):
    return ssh_string(kind) + ssh_string(key)


def private_key(kind=b"ssh-ed25519", cipher=b"none", count=1):
    blob = (
        b"openssh-key-v1\0"
        + ssh_string(cipher)
        + ssh_string(b"none" if cipher == b"none" else b"bcrypt")
        + ssh_string(b"")
        + count.to_bytes(4, "big")
        + ssh_string(public_blob(kind))
        + ssh_string(b"synthetic-private-section")
    )
    return (
        "-----BEGIN OPENSSH PRIVATE KEY-----\n"
        + base64.b64encode(blob).decode()
        + "\n-----END OPENSSH PRIVATE KEY-----"
    )


def fingerprint(blob=None):
    digest = hashlib.sha256(blob or public_blob()).digest()
    return "SHA256:" + base64.b64encode(digest).decode().rstrip("=")


def transport(**override):
    host = "8.8.8.8"
    return {
        "DEPLOY_HOST": host,
        "SCHEMA_COMPATIBLE": "true",
        "DEPLOY_SSH_PRIVATE_KEY": private_key(),
        "DEPLOY_SSH_KNOWN_HOSTS": host
        + " ssh-ed25519 "
        + base64.b64encode(public_blob()).decode(),
        "DEPLOY_HOST_KEY_FINGERPRINT": fingerprint(),
        **override,
    }


def test_valid_transport_accepted():
    from infra import deploy_transport

    assert str(deploy_transport.validate_transport(transport())) == "8.8.8.8"


HOST_KEY = base64.b64encode(public_blob()).decode()


@pytest.mark.parametrize(
    "override",
    [
        {
            "DEPLOY_HOST": "10.0.0.5",
            "DEPLOY_SSH_KNOWN_HOSTS": "10.0.0.5 ssh-ed25519 " + HOST_KEY,
        },
        {"SCHEMA_COMPATIBLE": "false"},
        {
            "DEPLOY_SSH_PRIVATE_KEY": "-----BEGIN RSA PRIVATE KEY-----\nabc\n-----END RSA PRIVATE KEY-----"
        },
        {"DEPLOY_SSH_PRIVATE_KEY": private_key(kind=b"ssh-rsa")},
        {"DEPLOY_SSH_PRIVATE_KEY": private_key(cipher=b"aes256-ctr")},
        {"DEPLOY_SSH_PRIVATE_KEY": private_key(count=2)},
        {
            "DEPLOY_SSH_PRIVATE_KEY": "-----BEGIN OPENSSH PRIVATE KEY-----\n!!!\n-----END OPENSSH PRIVATE KEY-----"
        },
        {"DEPLOY_SSH_KNOWN_HOSTS": ""},  # 26
        {"DEPLOY_SSH_KNOWN_HOSTS": "9.9.9.9 ssh-ed25519 " + HOST_KEY},
        {"DEPLOY_SSH_KNOWN_HOSTS": "* ssh-ed25519 " + HOST_KEY},
        {"DEPLOY_SSH_KNOWN_HOSTS": "8.8.8.8 ssh-rsa " + HOST_KEY},
        {"DEPLOY_SSH_KNOWN_HOSTS": "@cert-authority 8.8.8.8 ssh-ed25519 " + HOST_KEY},
        {"DEPLOY_SSH_KNOWN_HOSTS": "8.8.8.8 ssh-ed25519 AAAA"},
        {
            "DEPLOY_SSH_KNOWN_HOSTS": "8.8.8.8 ssh-ed25519 "
            + HOST_KEY
            + "\n8.8.8.8 ssh-ed25519 "
            + HOST_KEY
        },
        {"DEPLOY_HOST_KEY_FINGERPRINT": fingerprint(public_blob(key=b"\x02" * 32))},
        {"DEPLOY_HOST_KEY_FINGERPRINT": ""},
    ],
)
def test_unsafe_transport_rejected(override):  # 26
    from infra import deploy_transport

    with pytest.raises(ValueError):
        deploy_transport.validate_transport(transport(**override))
