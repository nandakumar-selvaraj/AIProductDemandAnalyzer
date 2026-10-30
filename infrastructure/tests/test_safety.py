import importlib.util
import json
from pathlib import Path

import pytest

from infrastructure import automation

ROOT = Path(__file__).resolve().parents[2]


def release_module():
    spec = importlib.util.spec_from_file_location(
        "release_validation", ROOT / "deploy/ops/release.py"
    )
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def fixture_release():
    return {
        "sha": "a" * 40,
        "backend": "ghcr.io/nandakumar-selvaraj/aiproductdemandanalyzer/backend@sha256:"
        + "1" * 64,
        "frontend": "ghcr.io/nandakumar-selvaraj/aiproductdemandanalyzer/frontend@sha256:"
        + "2" * 64,
        "postgres": "docker.io/library/postgres@sha256:" + "3" * 64,
        "caddy": "docker.io/library/caddy@sha256:" + "4" * 64,
        "domain": "demo.example.com",
        "email": "ops@example.com",
        "host": "8.8.8.8",
    }


def test_summary_never_discloses_attribute_values():
    document = {
        "resource_changes": [
            {
                "address": "upcloud_server.portfolio",
                "change": {
                    "actions": ["create"],
                    "after": {"secret": "DO_NOT_LEAK", "user_data": "PRIVATE_CONTENT"},
                },
            }
        ]
    }
    output = json.dumps(automation.safe_summary(document))
    assert "DO_NOT_LEAK" not in output and "PRIVATE_CONTENT" not in output
    assert "create" in output


@pytest.mark.parametrize(
    "actions", [["delete"], ["delete", "create"], ["create", "delete"]]
)
def test_plan_rejects_destruction_and_replacement(actions):
    with pytest.raises(ValueError):
        automation.safe_summary(
            {
                "resource_changes": [
                    {
                        "address": "upcloud_server.portfolio",
                        "change": {"actions": actions},
                    }
                ]
            }
        )


def test_plan_rejects_unexpected_resources():
    with pytest.raises(ValueError):
        automation.safe_summary(
            {
                "resource_changes": [
                    {
                        "address": "upcloud_server.other_demo",
                        "change": {"actions": ["create"]},
                    }
                ]
            }
        )


def test_release_accepts_only_complete_immutable_contract():
    assert release_module().validate_release(fixture_release())["sha"] == "a" * 40


@pytest.mark.parametrize(
    ("key", "value"),
    [
        ("backend", "ghcr.io/other/backend:latest"),
        (
            "frontend",
            "ghcr.io/nandakumar-selvaraj/aiproductdemandanalyzer/frontend:latest",
        ),
        ("domain", "demo.example.com { import /etc/passwd }"),
        ("domain", "http://demo.example.com"),
        ("email", "ops@example.com\nreverse_proxy attacker:8000"),
        ("host", "127.0.0.1"),
        ("sha", "master"),
    ],
)
def test_release_rejects_tags_shell_caddy_injection_and_wrong_identity(key, value):
    data = fixture_release()
    data[key] = value
    with pytest.raises(ValueError):
        release_module().validate_release(data)


def test_dns_gate_requires_exact_ipv4_and_no_aaaa(monkeypatch):
    module = release_module()
    import socket

    monkeypatch.setattr(
        module.socket,
        "getaddrinfo",
        lambda *_: [(socket.AF_INET, 1, 6, "", ("8.8.8.8", 443))],
    )
    module.check_dns(fixture_release())
    monkeypatch.setattr(
        module.socket,
        "getaddrinfo",
        lambda *_: [(socket.AF_INET, 1, 6, "", ("1.1.1.1", 443))],
    )
    with pytest.raises(ValueError):
        module.check_dns(fixture_release())
    monkeypatch.setattr(
        module.socket,
        "getaddrinfo",
        lambda *_: [(socket.AF_INET6, 1, 6, "", ("::1", 443, 0, 0))],
    )
    with pytest.raises(ValueError):
        module.check_dns(fixture_release())


def test_missing_configuration_fails_before_commands(monkeypatch):
    monkeypatch.delenv("UPCLOUD_TOKEN", raising=False)
    monkeypatch.setattr(
        automation, "run", lambda *_: pytest.fail("No command should run")
    )
    with pytest.raises(ValueError):
        automation.state_init()


def test_artifact_redirect_does_not_forward_github_token():
    import urllib.request

    request = urllib.request.Request(
        "https://api.github.com/artifact", headers={"Authorization": "Bearer synthetic"}
    )
    redirected = automation.SafeRedirect().redirect_request(
        request, None, 302, "Found", {}, "https://storage.example.com/signed"
    )
    assert redirected.get_header("Authorization") is None
    with pytest.raises(ValueError):
        automation.SafeRedirect().redirect_request(
            request, None, 302, "Found", {}, "http://storage.example.com/signed"
        )


def test_production_guard_rejects_unprotected_environment(monkeypatch):
    monkeypatch.setenv("GITHUB_REF", "refs/heads/master")
    monkeypatch.setattr(
        automation,
        "github",
        lambda _: {"protection_rules": [], "can_admins_bypass": True},
    )
    with pytest.raises(ValueError):
        automation.protected_environment()


def test_saved_run_must_match_exact_commit_workflow_and_repo(monkeypatch):
    monkeypatch.setenv("GITHUB_REPOSITORY", "owner/repo")
    details = {
        "conclusion": "success",
        "head_sha": "a" * 40,
        "path": ".github/workflows/terraform-plan.yml",
        "head_branch": "master",
        "head_repository": {"full_name": "owner/repo"},
    }
    monkeypatch.setattr(automation, "github", lambda _: details)
    automation.verify_run("123", "terraform-plan.yml", "a" * 40)
    for key, value in [
        ("head_sha", "b" * 40),
        ("conclusion", "failure"),
        ("head_branch", "feature"),
        ("path", ".github/workflows/untrusted.yml"),
    ]:
        original = details[key]
        details[key] = value
        with pytest.raises(ValueError):
            automation.verify_run("123", "terraform-plan.yml", "a" * 40)
        details[key] = original
