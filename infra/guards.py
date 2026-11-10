"""Fail-closed identity and plan policy keeping the dedicated demo apart from shared-portfolio infrastructure."""

import base64
import hashlib
import ipaddress
import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PROJECT = "aiproductdemand"
ENVIRONMENT = (
    "production"  # Terraform/label value; the GitHub Environment name differs.
)
GITHUB_ENVIRONMENT = "aiproductdemand-production"
SHARED_GITHUB_ENVIRONMENT = "production"
BRANCH = "master"
TERRAFORM_DIR = ROOT / "infra/terraform"
SHARED_TERRAFORM_DIR = ROOT / "infrastructure/terraform"
STATE_KEY = "aiproductdemand/production/terraform.tfstate"
SHARED_STATE_PREFIX = "portfolio/"
PLAN_PREFIX = "reviewed-plans/" + PROJECT + "/"
HOSTNAME = "aiproductdemand-prod"
# Adding a zone is a reviewed code change, never a variable edit.
APPROVED_ZONES = {"sg-sin1"}
STORAGE_TIERS = {"standard", "maxiops"}
TEMPLATE = "Ubuntu Server 24.04 LTS (Noble Numbat)"
BOOT_SIZE = 30
SERVER = "upcloud_server.app"
FIREWALL = "upcloud_firewall_rules.app"
ALLOWED_TYPES = {SERVER: "upcloud_server", FIREWALL: "upcloud_firewall_rules"}
NORMAL_ACTIONS = (["create"], ["update"], ["no-op"])
WORKFLOWS = {
    "plan": "single-terraform-plan.yml",
    "apply": "single-terraform-apply.yml",
    "destroy": "single-terraform-destroy.yml",
    "deploy": "single-deploy-production.yml",
    "publish": "single-publish-images.yml",
}
PLAN_MAX_AGE = {"normal": 86400, "destroy": 3600}
# Single-purpose workflows that may be named as required checks or plan producers.
REQUIRED_CI = [
    "backend-ci.yml",
    "e2e.yml",
    "docker-validation.yml",
    "single-validate.yml",
]
FIREWALL_FIELDS = [
    "action",
    "direction",
    "family",
    "protocol",
    "icmp_type",
    "source_address_start",
    "source_address_end",
    "source_port_start",
    "source_port_end",
    "destination_address_start",
    "destination_address_end",
    "destination_port_start",
    "destination_port_end",
]


def require_dedicated(env, terraform_dir=TERRAFORM_DIR):
    """Reject any configuration that could touch shared state or a foreign Terraform root."""
    if Path(terraform_dir).resolve() != TERRAFORM_DIR.resolve():
        raise ValueError("Dedicated operations must use infra/terraform only")
    if env.get("TF_STATE_KEY") != STATE_KEY or STATE_KEY.startswith(
        SHARED_STATE_PREFIX
    ):
        raise ValueError("Dedicated state key required; never reuse shared VPS state")
    if env.get("TF_VAR_project_name") != PROJECT:
        raise ValueError("Unexpected project identifier")
    if env.get("TF_VAR_environment") != ENVIRONMENT:
        raise ValueError("Unexpected environment identifier")
    if env.get("TF_VAR_server_hostname") != HOSTNAME:
        raise ValueError("Unexpected server hostname")
    if env.get("TF_VAR_upcloud_zone") not in APPROVED_ZONES:
        raise ValueError("Explicitly approved Singapore zone required")


def ssh_cidrs(value):
    """Parse the Terraform list variable; IPv4 /24 or narrower, mirroring variables.tf."""
    try:
        items = json.loads(value)
        networks = [ipaddress.IPv4Network(item, strict=True) for item in items]
    except (TypeError, ValueError):
        raise ValueError("SSH CIDRs must be a JSON list of IPv4 networks") from None
    if not 0 < len(networks) <= 20 or len(set(networks)) != len(networks):
        raise ValueError("Between 1 and 20 distinct SSH CIDRs required")
    for network in networks:
        if network.prefixlen < 24 or not network.is_global:
            raise ValueError("SSH CIDRs must be public and /24 or narrower")
    return networks


def approved_configuration(env):
    """The reviewed values a plan must reproduce exactly."""
    require_dedicated(env)
    plan = env.get("TF_VAR_server_plan", "")
    tier = env.get("TF_VAR_boot_storage_tier", "")
    if not re.fullmatch(r"[A-Za-z0-9-]+", plan):
        raise ValueError("Approved server plan required")
    if tier not in STORAGE_TIERS:
        raise ValueError("Approved boot storage tier required")
    return {
        "zone": env["TF_VAR_upcloud_zone"],
        "plan": plan,
        "hostname": HOSTNAME,
        "tier": tier,
        "labels": {
            "project": PROJECT,
            "environment": ENVIRONMENT,
            "managed_by": "terraform-single-app",
        },
        "ssh_cidrs": ssh_cidrs(env.get("TF_VAR_ssh_allowed_cidrs")),
    }


def require_workflow(env, operation):
    """Only the matching dedicated workflow on master may run a dedicated operation."""
    expected = (
        env.get("GITHUB_REPOSITORY", "")
        + "/.github/workflows/"
        + WORKFLOWS[operation]
        + "@refs/heads/"
        + BRANCH
    )
    if (
        not env.get("GITHUB_REPOSITORY")
        or env.get("GITHUB_WORKFLOW_REF") != expected
        or env.get("GITHUB_REF") != "refs/heads/" + BRANCH
    ):
        raise ValueError("Dedicated operation must run from its own master workflow")


def require_environment(env, github):
    """Dedicated GitHub Environment identity and protection, checked before any cloud command."""
    name = env.get("DEPLOYMENT_ENVIRONMENT")
    if name == SHARED_GITHUB_ENVIRONMENT or name != GITHUB_ENVIRONMENT:
        raise ValueError("Dedicated GitHub Environment required; shared one rejected")
    settings = github("environments/" + GITHUB_ENVIRONMENT)
    if settings.get("name") != GITHUB_ENVIRONMENT:
        raise ValueError("Dedicated GitHub Environment missing")
    if settings.get("can_admins_bypass", True):
        raise ValueError("Administrator bypass must be disabled")
    if not any(
        rule.get("type") == "required_reviewers"
        and rule.get("reviewers")
        and rule.get("prevent_self_review") is True
        for rule in settings.get("protection_rules", [])
    ):
        raise ValueError("Required reviewers with self-review prevention required")
    policy = settings.get("deployment_branch_policy") or {}
    if policy.get("custom_branch_policies") is not True or policy.get(
        "protected_branches"
    ):
        raise ValueError("Only the explicit master branch may deploy")
    branches = github(
        "environments/" + GITHUB_ENVIRONMENT + "/deployment-branch-policies"
    ).get("branch_policies", [])
    if not branches or any(
        item.get("name") != BRANCH or item.get("type", "branch") != "branch"
        for item in branches
    ):
        raise ValueError("Only the explicit master branch may deploy")


def plan_object_path(bucket, run_id, name):
    if not re.fullmatch(r"[0-9]+", str(run_id)) or name not in (
        "reviewed.tfplan",
        "metadata.json",
    ):
        raise ValueError("Invalid plan object")
    return "s3://" + bucket + "/" + PLAN_PREFIX + str(run_id) + "/" + name


def plan_metadata(**values):
    return {
        **values,
        "environment": GITHUB_ENVIRONMENT,
        "prefix": PLAN_PREFIX,
        "state_key": STATE_KEY,
    }


def verify_plan_metadata(data, *, expected, digest, now):
    """Saved plan must match the reviewed commit, configuration, state identity and age."""
    keys = {
        "sha",
        "run_id",
        "digest",
        "configuration",
        "created",
        "changes",
        "lockfile",
        "mode",
        "state",
        "environment",
        "prefix",
        "state_key",
    }
    if not isinstance(data, dict) or set(data) != keys:
        raise ValueError("Unexpected saved-plan metadata")
    if not re.fullmatch(r"[0-9a-f]{64}", expected["digest"]) or not (
        digest == expected["digest"] == data["digest"]
    ):
        raise ValueError("Saved plan digest mismatch")
    for key in ("sha", "run_id", "configuration", "lockfile", "mode", "state"):
        if data[key] != expected[key]:
            raise ValueError("Saved plan " + key + " mismatch")
    if (
        data["environment"] != GITHUB_ENVIRONMENT
        or data["prefix"] != PLAN_PREFIX
        or data["state_key"] != STATE_KEY
    ):
        raise ValueError("Saved plan belongs to another environment or state")
    age = now - data["created"]
    if (
        not isinstance(data["created"], int)
        or not 0 <= age <= PLAN_MAX_AGE[data["mode"]]
    ):
        raise ValueError("Saved plan expired or from the future")


def state_identity(raw):
    """Lineage/serial only; the raw state is never stored or printed."""
    if not raw.strip():
        return {"lineage": None, "serial": 0}
    document = json.loads(raw)
    if not isinstance(document.get("lineage"), str) or not isinstance(
        document.get("serial"), int
    ):
        raise ValueError("Malformed remote state")
    return {"lineage": document["lineage"], "serial": document["serial"]}


def _resources(module, path="root"):
    if not isinstance(module, dict):
        raise ValueError("Malformed planned values")
    if module.get("child_modules"):
        raise ValueError("Unexpected child module in plan")
    if module.get("address") not in (None, ""):
        raise ValueError("Unexpected module address")
    return module.get("resources") or []


def _identity(item):
    address = item.get("address")
    if (
        address not in ALLOWED_TYPES
        or item.get("type") != ALLOWED_TYPES[address]
        or item.get("mode") != "managed"
        or item.get("name") != "app"
        or "index" in item
        or item.get("module_address")
        or item.get("deposed")
    ):
        raise ValueError("Unexpected infrastructure resource")
    return address


def _any_unknown(value):
    if isinstance(value, dict):
        return any(_any_unknown(item) for item in value.values())
    if isinstance(value, list):
        return any(_any_unknown(item) for item in value)
    return value is True


def _known(unknown, key, deep=True):
    """after_unknown marks unknown leaves with true; nested blocks are lists/maps of markers."""
    value = unknown.get(key) if isinstance(unknown, dict) else unknown
    if unknown is True or value is True or (deep and _any_unknown(value)):
        raise ValueError("Security-critical value unknown until apply: " + key)


def _single(after, unknown, key):
    _known(unknown, key, deep=False)  # individual fields are checked by the caller
    value = after.get(key)
    if not isinstance(value, list) or len(value) != 1 or not isinstance(value[0], dict):
        raise ValueError("Exactly one " + key + " block required")
    nested = unknown.get(key) if isinstance(unknown, dict) else None
    return value[0], (nested[0] if isinstance(nested, list) and nested else {})


def validate_server(after, unknown, approved):
    for key in ("zone", "plan", "hostname", "labels", "firewall"):
        _known(unknown, key)
    if after.get("zone") != approved["zone"] or after["zone"] not in APPROVED_ZONES:
        raise ValueError("Unexpected region")
    if after.get("plan") != approved["plan"]:
        raise ValueError("Unexpected server plan")
    if after.get("hostname") != approved["hostname"]:
        raise ValueError("Unexpected hostname")
    if after.get("labels") != approved["labels"]:
        raise ValueError("Unexpected labels")
    if after.get("firewall") is not True:
        raise ValueError("Server firewall must be enabled")
    template, template_unknown = _single(after, unknown, "template")
    for key in ("storage", "size", "tier", "encrypt"):
        _known(template_unknown, key)
    if (
        template.get("storage") != TEMPLATE
        or template.get("size") != BOOT_SIZE
        or template.get("tier") != approved["tier"]
        or template.get("encrypt") is not True
    ):
        raise ValueError("Unexpected boot storage")
    login, login_unknown = _single(after, unknown, "login")
    for key in ("create_password", "password_delivery"):
        _known(login_unknown, key)
    if login.get("create_password") is not False or login.get(
        "password_delivery"
    ) not in ("none",):
        raise ValueError("Password login must stay disabled")
    interface, interface_unknown = _single(after, unknown, "network_interface")
    for key in ("type", "ip_address_family"):
        _known(interface_unknown, key)
    if (
        interface.get("type") != "public"
        or interface.get("ip_address_family") != "IPv4"
    ):
        raise ValueError("Exactly one public IPv4 interface required")
    if after.get("storage_devices"):
        raise ValueError("Unexpected additional storage")


def expected_firewall(networks):
    def rule(**values):
        return {field: str(values.get(field, "")) for field in FIREWALL_FIELDS}

    inbound = dict(action="accept", direction="in", family="IPv4", protocol="tcp")
    return [
        *[
            rule(
                **inbound,
                destination_port_start="22",
                destination_port_end="22",
                source_address_start=network.network_address,
                source_address_end=network.broadcast_address,
            )
            for network in networks
        ],
        *[
            rule(**inbound, destination_port_start=port, destination_port_end=port)
            for port in ("80", "443")
        ],
        rule(action="accept", direction="in", family="IPv4", protocol="icmp"),
        rule(action="drop", direction="in"),
        rule(action="accept", direction="out"),
    ]


def validate_firewall(after, unknown, approved):
    _known(unknown, "firewall_rule")  # server_id may stay unknown; it is not policy
    rules = after.get("firewall_rule")
    nested = unknown.get("firewall_rule") if isinstance(unknown, dict) else None
    if not isinstance(rules, list):
        raise ValueError("Firewall rules missing")
    for index, rule in enumerate(rules):
        flags = (
            nested[index] if isinstance(nested, list) and index < len(nested) else {}
        )
        if not isinstance(rule, dict) or any(
            flags.get(field) for field in FIREWALL_FIELDS
        ):
            raise ValueError("Security-critical firewall value unknown or malformed")
    actual = [
        {
            field: "" if rule.get(field) is None else str(rule.get(field))
            for field in FIREWALL_FIELDS
        }
        for rule in rules
    ]
    if actual != expected_firewall(approved["ssh_cidrs"]):
        raise ValueError("Firewall policy differs from the approved policy")


VALIDATORS = {SERVER: validate_server, FIREWALL: validate_firewall}


def validate_plan(document, approved, destroy=False):
    """Whole-plan policy over resource_changes and planned_values; never returns attribute values."""
    if not isinstance(document, dict) or document.get("errored"):
        raise ValueError("Incomplete or errored plan")
    changes = document.get("resource_changes")
    if not isinstance(changes, list):
        raise ValueError("Plan has no resource_changes")
    planned = document.get("planned_values", {}).get("root_module", {})
    planned_resources = {}
    for item in _resources(planned):
        address = _identity(item)
        if address in planned_resources:
            raise ValueError("Duplicate planned resource")
        planned_resources[address] = item
    seen, output = {}, []
    for item in changes:
        address = _identity(item)
        if address in seen:
            raise ValueError("Duplicate resource change")
        seen[address] = item
        actions = item.get("change", {}).get("actions")
        if destroy:
            if actions != ["delete"]:
                raise ValueError("Destroy plan may only delete approved resources")
        elif actions not in NORMAL_ACTIONS:
            raise ValueError("Deletion, replacement or unknown action forbidden")
        output.append({"resource": address, "actions": actions})
    if destroy:
        if not seen or planned_resources:
            raise ValueError("Destroy plan must remove only approved resources")
        return output
    if set(seen) != set(ALLOWED_TYPES) or set(planned_resources) != set(ALLOWED_TYPES):
        raise ValueError("Plan must cover exactly one server and its firewall")
    for address, item in seen.items():
        change = item["change"]
        after = change.get("after")
        unknown = change.get("after_unknown") or {}
        if not isinstance(after, dict):
            raise ValueError("Planned values missing")
        VALIDATORS[address](after, unknown, approved)
        # planned_values omits unknowns; known values must agree with resource_changes.
        values = planned_resources[address].get("values")
        if not isinstance(values, dict):
            raise ValueError("Planned values missing")
        VALIDATORS[address](values, unknown, approved)
    return output


def authorize_destroy(env):
    if env.get("BACKUP_CONFIRMATION") != "OFFHOST-RESTORE-VERIFIED":
        raise ValueError(
            "Verified off-host restore and resource inventory approval required"
        )
    if env.get("DESTROY_TARGET") != GITHUB_ENVIRONMENT:
        raise ValueError("Destroy target must be the dedicated environment")
    if not re.fullmatch(r"[0-9a-f]{40}", env.get("EXPECTED_SHA", "")):
        raise ValueError("Reviewed teardown commit required")
    if env["EXPECTED_SHA"] != env.get("GITHUB_SHA"):
        raise ValueError("Teardown commit mismatch")


def _ssh_strings(blob):
    while blob:
        if len(blob) < 4:
            raise ValueError("Malformed SSH structure")
        size = int.from_bytes(blob[:4], "big")
        if size > len(blob) - 4:
            raise ValueError("Malformed SSH structure")
        yield blob[4 : 4 + size]
        blob = blob[4 + size :]


def ed25519_public(blob):
    parts = list(_ssh_strings(blob))
    if len(parts) != 2 or parts[0] != b"ssh-ed25519" or len(parts[1]) != 32:
        raise ValueError("Ed25519 key required")
    return blob


def ed25519_private_key(text):
    """Structural check of an unencrypted OpenSSH Ed25519 private key; the key is never printed."""
    lines = text.strip().splitlines()
    if (
        len(lines) < 3
        or lines[0] != "-----BEGIN OPENSSH PRIVATE KEY-----"
        or lines[-1] != "-----END OPENSSH PRIVATE KEY-----"
    ):
        raise ValueError("OpenSSH private key required")
    try:
        blob = base64.b64decode("".join(lines[1:-1]), validate=True)
    except ValueError:
        raise ValueError("OpenSSH private key required") from None
    magic = b"openssh-key-v1\0"
    if not blob.startswith(magic):
        raise ValueError("OpenSSH private key required")
    rest = blob[len(magic) :]
    header = []
    for _ in range(3):
        size = int.from_bytes(rest[:4], "big")
        header.append(rest[4 : 4 + size])
        rest = rest[4 + size :]
    if header[0] != b"none" or int.from_bytes(rest[:4], "big") != 1:
        raise ValueError("Single unencrypted deployment key required")
    size = int.from_bytes(rest[4:8], "big")
    ed25519_public(rest[8 : 8 + size])


def pinned_host(known_hosts, host, fingerprint):
    """Exactly one Ed25519 entry for the exact IPv4 target, matching an independently verified fingerprint."""
    lines = [
        line.split()
        for line in known_hosts.splitlines()
        if line.strip() and not line.lstrip().startswith("#")
    ]
    if len(lines) != 1 or len(lines[0]) not in (3, 4):
        raise ValueError("Known hosts must pin exactly one deployment host")
    name, kind, key = lines[0][:3]
    if name != str(host) or kind != "ssh-ed25519":
        raise ValueError("Known hosts must pin only the exact Ed25519 deployment host")
    try:
        blob = ed25519_public(base64.b64decode(key, validate=True))
    except ValueError:
        raise ValueError("Malformed Ed25519 host key") from None
    actual = "SHA256:" + base64.b64encode(
        hashlib.sha256(blob).digest()
    ).decode().rstrip("=")
    if not re.fullmatch(r"SHA256:[A-Za-z0-9+/]{43}", fingerprint or "") or (
        actual != fingerprint
    ):
        raise ValueError(
            "Host key does not match the independently verified fingerprint"
        )
