"""Fail-closed identity checks keeping the dedicated demo apart from shared-portfolio infrastructure."""

import ipaddress
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PROJECT = "aiproductdemand"
ENVIRONMENT = "production"
TERRAFORM_DIR = ROOT / "infra/terraform"
SHARED_TERRAFORM_DIR = ROOT / "infrastructure/terraform"
STATE_KEY = "aiproductdemand/production/terraform.tfstate"
SHARED_STATE_PREFIX = "portfolio/"
PLAN_PREFIX = "reviewed-plans/" + PROJECT + "/"
HOSTNAME = "aiproductdemand-prod"
ZONE = re.compile(r"sg-[a-z]+[0-9]+")
SERVER = "upcloud_server.app"
FIREWALL = "upcloud_firewall_rules.app"
ALLOWED_TYPES = {SERVER: "upcloud_server", FIREWALL: "upcloud_firewall_rules"}
ALLOWED_PORTS = {"22", "80", "443"}
# Single-purpose workflows that may be named as required checks or plan producers.
REQUIRED_CI = [
    "backend-ci.yml",
    "e2e.yml",
    "docker-validation.yml",
    "single-validate.yml",
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
    if not ZONE.fullmatch(env.get("TF_VAR_upcloud_zone", "")):
        raise ValueError("Singapore zone required")


def plan_object_path(bucket, run_id, name):
    if not re.fullmatch(r"[0-9]+", str(run_id)) or name not in (
        "reviewed.tfplan",
        "metadata.json",
    ):
        raise ValueError("Invalid plan object")
    return "s3://" + bucket + "/" + PLAN_PREFIX + str(run_id) + "/" + name


def _rules(after):
    rules = after.get("firewall_rule") or []
    return rules if isinstance(rules, list) else []


def validate_plan(document, destroy=False):
    """Allow exactly one VPS and its firewall; inspect region and public ports, never print values."""
    changes, seen = [], set()
    for item in document.get("resource_changes", []):
        address, change = item["address"], item["change"]
        actions = change["actions"]
        if (
            address not in ALLOWED_TYPES
            or address in seen
            or item.get("type", ALLOWED_TYPES[address]) != ALLOWED_TYPES[address]
            or item.get("mode", "managed") != "managed"
            or "index" in item
        ):
            raise ValueError("Unexpected or duplicate infrastructure resource")
        seen.add(address)
        if destroy:
            if actions not in (["delete"], ["no-op"]):
                raise ValueError("Destroy plan contains a non-delete operation")
        elif "delete" in actions:
            raise ValueError("Deletion/replacement forbidden in normal workflow")
        after = change.get("after") or {}
        if not destroy and actions != ["no-op"]:
            if (
                address == SERVER
                and after.get("zone") not in (None, "")
                and not str(after["zone"]).startswith("sg-")
            ):
                raise ValueError("Unexpected region")
            if address == FIREWALL:
                for rule in _rules(after):
                    if rule.get("direction") == "in" and rule.get("action") == "accept":
                        start = str(rule.get("destination_port_start") or "")
                        end = str(rule.get("destination_port_end") or "")
                        if rule.get("protocol") == "tcp" and (
                            start != end or start not in ALLOWED_PORTS
                        ):
                            raise ValueError("Unapproved public port")
                        if start == "22":
                            low = rule.get("source_address_start")
                            high = rule.get("source_address_end")
                            if (
                                not low
                                or ipaddress.ip_address(low)
                                == ipaddress.ip_address("0.0.0.0")
                                or str(high) == "255.255.255.255"
                            ):
                                raise ValueError("World-open SSH is forbidden")
        changes.append({"resource": address, "actions": actions})
    return changes
