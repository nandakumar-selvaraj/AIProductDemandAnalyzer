import importlib.util
import io
import json
from pathlib import Path
from types import SimpleNamespace

import pytest

from infra import automation

ROOT = Path(__file__).resolve().parents[2]
spec = importlib.util.spec_from_file_location(
    "single_release", ROOT / "deploy/single/release.py"
)
release = importlib.util.module_from_spec(spec)
spec.loader.exec_module(release)


def fixture():
    value = {
        key: repo + "@sha256:" + "1" * 64 for key, repo in release.REPOSITORIES.items()
    }
    value["sha"] = "a" * 40
    return value


@pytest.mark.parametrize("key", release.REPOSITORIES)
def test_reject_mutable_or_foreign_images(key):
    value = fixture()
    value[key] = "attacker.invalid/image@sha256:" + "1" * 64
    with pytest.raises(ValueError):
        release.validate(value)
    value[key] = release.REPOSITORIES[key] + ":latest"
    with pytest.raises(ValueError):
        release.validate(value)


def test_accept_exact_digest_manifest():
    assert release.validate(fixture()) == fixture()


@pytest.mark.parametrize(
    "actions", [["delete"], ["create", "delete"], ["delete", "create"]]
)
def test_normal_plan_rejects_delete_and_replace(actions, monkeypatch):
    monkeypatch.setattr(automation, "MODE", "normal")
    with pytest.raises(ValueError):
        automation.summary(
            {
                "resource_changes": [
                    {"address": "upcloud_server.app", "change": {"actions": actions}}
                ]
            }
        )


def test_destroy_plan_rejects_creation(monkeypatch):
    monkeypatch.setattr(automation, "MODE", "destroy")
    with pytest.raises(ValueError):
        automation.summary(
            {
                "resource_changes": [
                    {"address": "upcloud_server.app", "change": {"actions": ["create"]}}
                ]
            }
        )


def test_unknown_resources_rejected():
    with pytest.raises(ValueError):
        automation.summary(
            {
                "resource_changes": [
                    {
                        "address": "upcloud_server.other",
                        "change": {"actions": ["create"]},
                    }
                ]
            }
        )


def test_plan_summary_does_not_leak_user_data(monkeypatch):
    monkeypatch.setattr(automation, "MODE", "normal")
    result = automation.summary(
        {
            "resource_changes": [
                {
                    "address": "upcloud_server.app",
                    "change": {
                        "actions": ["create"],
                        "after": {"user_data": "PRIVATE"},
                    },
                }
            ]
        }
    )
    assert "PRIVATE" not in str(result)


@pytest.mark.parametrize("check_migrations", [True, False])
def test_rollback_starts_images_without_requiring_old_schema_head(
    monkeypatch, check_migrations
):
    calls, revisions = [], []
    monkeypatch.setattr(release, "compose", lambda value, *args: calls.append(args))
    monkeypatch.setattr(
        release, "verify_migrations", lambda value: revisions.append(value)
    )
    monkeypatch.setattr(release, "run", lambda args: None)
    monkeypatch.setattr(
        release,
        "Path",
        lambda path: SimpleNamespace(read_text=lambda: "demo.example.com"),
    )
    release.healthy(fixture(), check_migrations=check_migrations)
    assert calls[0][:2] == ("up", "-d")
    assert bool(revisions) == check_migrations


@pytest.mark.parametrize("failure", ["migration", "health"])
def test_failure_preserves_release_and_does_not_downgrade(
    monkeypatch, tmp_path, failure
):
    old, new = fixture(), fixture()
    new["sha"] = "b" * 40
    new["BACKEND_IMAGE"] = release.REPOSITORIES["BACKEND_IMAGE"] + "@sha256:" + "2" * 64
    (tmp_path / "active.json").write_text(json.dumps(old))
    monkeypatch.setattr(release, "STATE", tmp_path)
    monkeypatch.setattr(release, "BASE", tmp_path)
    monkeypatch.setattr(release, "private", lambda path: None)
    monkeypatch.setattr(release.os, "geteuid", lambda: 0, raising=False)
    monkeypatch.setattr(
        release,
        "fcntl",
        SimpleNamespace(LOCK_EX=1, LOCK_NB=2, flock=lambda *args: None),
    )
    # TLS marker is a local fixture; no real system paths are touched.
    real_is_file = Path.is_file
    monkeypatch.setattr(
        Path,
        "is_file",
        lambda path: True
        if str(path) == "/etc/demand/tls-ready"
        else real_is_file(path),
    )
    monkeypatch.setattr(release.sys, "argv", ["demand-release"])
    request = {"action": "deploy", "release": new, "schema_backward_compatible": True}
    monkeypatch.setattr(
        release.sys,
        "stdin",
        SimpleNamespace(buffer=io.BytesIO(json.dumps(request).encode())),
    )
    commands, checks = [], []
    monkeypatch.setattr(release, "run", lambda args: commands.append(args))

    def compose(value, *args):
        commands.append(args)
        if failure == "migration" and args[0] == "run":
            raise RuntimeError("synthetic migration failure")

    def healthy(value, *, check_migrations):
        checks.append((value["sha"], check_migrations))
        if value == new:
            raise RuntimeError("synthetic health failure")

    monkeypatch.setattr(release, "compose", compose)
    monkeypatch.setattr(release, "healthy", healthy)
    with pytest.raises(RuntimeError):
        release.main()
    assert json.loads((tmp_path / "active.json").read_text()) == old
    assert "downgrade" not in str(commands)
    if failure == "migration":
        assert not checks
        assert (
            "migration-failed-manual-recovery-required"
            in (tmp_path / "history.jsonl").read_text()
        )
    else:
        assert checks[-1] == (old["sha"], False)
        assert "automatic-rollback" in (tmp_path / "history.jsonl").read_text()
