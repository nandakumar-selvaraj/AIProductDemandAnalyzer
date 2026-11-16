"""Mocked host state, synthetic archive streams and deployment gate regressions."""

import base64
import errno
import importlib.util
import json
import sys
import time
from pathlib import Path

import pytest

from infra import ci, release_manifest

ROOT = Path(__file__).resolve().parents[2]


def load_module(name):
    spec = importlib.util.spec_from_file_location(
        name, ROOT / "deploy/single" / (name + ".py")
    )
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


host = load_module("bootstrap_host")
backup = load_module("backup_state")
OPERATOR = "8.8.8.8/32"
RUNNER = "9.9.9.9/32"
SNAPSHOT = "a" * 64
OPERATION = "demand-op-" + "1" * 32


@pytest.mark.parametrize("data", [None, "", "ssh-rsa AAAA", "ssh-ed25519 AAAA"])
def test_missing_or_bad_operator_key(tmp_path, monkeypatch, data):
    path = tmp_path / "operator.pub"
    if data is not None:
        path.write_text(data)
    monkeypatch.setattr(host, "source", lambda path: path.read_bytes())
    with pytest.raises((OSError, ValueError)):
        host.key(path)


def test_key_fingerprint_uses_decoded_ed25519_blob(tmp_path, monkeypatch):
    path = tmp_path / "operator.pub"
    blob = b"\0\0\0\x0bssh-ed25519\0\0\0\x20" + b"\1" * 32
    encoded = base64.b64encode(blob).decode()
    path.write_text(f"ssh-ed25519 {encoded} test")
    monkeypatch.setattr(host, "source", lambda path: path.read_bytes())
    assert host.key(path) == ("ssh-ed25519 " + encoded, host.fingerprint(blob))


def test_trusted_file_rejects_wrong_owner_or_symlink(monkeypatch):
    from types import SimpleNamespace

    target = Path("/home/operator/.ssh/authorized_keys")
    statuses = {
        **{path: SimpleNamespace(st_mode=0o40700, st_uid=0) for path in target.parents},
        target: SimpleNamespace(st_mode=0o100600, st_uid=1001, st_nlink=1),
    }
    monkeypatch.setattr(type(target), "lstat", lambda self: statuses[self])
    host.trusted(target, uid=1001)
    for mode, uid in ((0o120600, 1001), (0o100600, 1002), (0o100666, 1001)):
        statuses[target] = SimpleNamespace(st_mode=mode, st_uid=uid, st_nlink=1)
        with pytest.raises(ValueError):
            host.trusted(target, uid=1001)


def login(**fields):
    return {
        "_PID": "123",
        "_UID": "0",
        "_EXE": "/usr/sbin/sshd",
        "__REALTIME_TIMESTAMP": "101",
        "MESSAGE": "Accepted publickey for operator from 8.8.8.8 port 49001 ssh2: ED25519 SHA256:test",
        **fields,
    }


def test_operator_login_proof_binds_connection_source_and_key():
    assert (
        host.operator_peer(
            [(123, "sshd", 0)], [login()], "SHA256:test", [OPERATOR], 100
        )
        == "8.8.8.8"
    )


@pytest.mark.parametrize(
    "fields,expected_key,cidr",
    [
        ({"_PID": "456"}, "SHA256:test", OPERATOR),
        ({"_UID": "1001"}, "SHA256:test", OPERATOR),
        ({"_EXE": "/tmp/sshd"}, "SHA256:test", OPERATOR),
        ({"__REALTIME_TIMESTAMP": "99"}, "SHA256:test", OPERATOR),
        ({"MESSAGE": "Accepted password for operator"}, "SHA256:test", OPERATOR),
        ({}, "SHA256:different", OPERATOR),
        ({}, "SHA256:test", RUNNER),
    ],
)
def test_unrelated_or_unverified_ssh_connection_is_rejected(fields, expected_key, cidr):
    with pytest.raises(ValueError):
        host.operator_peer(
            [(123, "sshd", 0)], [login(**fields)], expected_key, [cidr], 100
        )


def test_failed_sudo_or_console_cannot_record_proof(monkeypatch):
    monkeypatch.setattr(host, "challenge", lambda _: ({}, {}))
    monkeypatch.setenv("SUDO_USER", "root")
    monkeypatch.setattr(host.os, "ttyname", lambda _: "/dev/pts/1", raising=False)
    with pytest.raises(ValueError, match="sudo"):
        host.verify("text-only")
    with pytest.raises(ValueError, match="out-of-band"):
        host.recovery("text-only")


def test_finalization_does_nothing_without_current_proofs(monkeypatch):
    ticket = {"nonce": "new", "issued": 1}
    monkeypatch.setattr(host, "challenge", lambda _: ({"cidrs": [OPERATOR]}, ticket))
    monkeypatch.setattr(host, "record", lambda _: {"nonce": "old", "issued": 1})
    monkeypatch.setattr(
        host, "fresh_host", lambda: pytest.fail("Host mutation reached")
    )
    with pytest.raises(ValueError, match="receipts"):
        host.finalize("new")


@pytest.mark.parametrize("failure", ["candidate", "effective", "interrupt", "reload"])
def test_ssh_activation_failure_preserves_original(tmp_path, monkeypatch, failure):
    ssh = tmp_path / "sshd_config"
    original = (
        b"Include /etc/ssh/sshd_config.d/*.conf\nPermitRootLogin prohibit-password\n"
    )
    ssh.write_bytes(original)
    dropin = tmp_path / "sshd_config.d" / "00-demand-manual.conf"
    dropin.parent.mkdir()
    for name, value in (("SSH", ssh), ("DROPIN", dropin), ("STATE", tmp_path)):
        monkeypatch.setattr(host, name, value)
    reloads = []

    def run(*args):
        if failure == "candidate" and args[:3] == ("sshd", "-t", "-f"):
            raise ValueError("Invalid candidate")
        if args[:2] == ("systemctl", "reload"):
            reloads.append(dropin.exists())
            if reloads[-1] and failure == "interrupt":
                raise KeyboardInterrupt()
            if reloads[-1] and failure == "reload":
                raise ValueError("Injected reload failure")

    def effective(config=None, peer=None):
        if config is None and dropin.exists() and failure == "effective":
            raise ValueError("Invalid effective config")

    monkeypatch.setattr(host, "run", run)
    monkeypatch.setattr(host, "effective", effective)
    monkeypatch.setattr(
        host, "atomic", lambda path, data, *args: path.write_bytes(data)
    )
    monkeypatch.setattr(host, "source", lambda path: path.read_bytes())
    with pytest.raises((ValueError, KeyboardInterrupt)):
        host.ssh_activate("8.8.8.8")
    assert ssh.read_bytes() == original
    assert not dropin.exists()
    if failure == "candidate":
        assert not reloads
    else:
        assert reloads[-1] is False


@pytest.mark.parametrize(
    "cidrs",
    [
        [],
        ["0.0.0.0/0"],
        ["10.1.0.2/32"],
        ["8.8.8.1/24"],
        ["::/0"],
        [OPERATOR, "8.8.8.0/24"],
    ],
)
def test_firewall_rejects_invalid_or_unsafe_cidrs(cidrs):
    with pytest.raises(ValueError):
        host.firewall_policy(cidrs)


def test_firewall_policy_replaces_obsolete_rules_and_denies_ipv6():
    old = host.firewall_policy([OPERATOR, RUNNER])
    candidate = host.firewall_policy([OPERATOR, "1.1.1.1/32"])
    assert b"9.9.9.9/32" in old and b"9.9.9.9/32" not in candidate
    assert (
        b"1.1.1.1/32" in candidate and candidate.count(b"meta nfproto ipv6 drop") == 2
    )
    assert candidate.count(b"policy drop") == 2 and b"5432" not in candidate
    assert b"ct status dnat" in candidate
    script = (ROOT / "deploy/single/docker-firewall.sh").read_text()
    assert "nft --check" in script and script.count('nft --file "$candidate"') == 1
    assert "flush" not in script and "iptables" not in script
    boot_unit = (ROOT / "deploy/single/systemd/demand-firewall.service").read_text()
    assert "Before=docker.service docker.socket" in boot_unit
    assert "Requires=demand-firewall.service" in host.DOCKER_UNIT.decode()


def test_broad_preexisting_rule_fails_closed(monkeypatch):
    monkeypatch.setattr(host.os.path, "lexists", lambda _: False)
    monkeypatch.setattr(host.Path, "exists", lambda _: False)
    monkeypatch.setattr(
        host, "run", lambda _: b"-A INPUT -p tcp --dport 22 -j ACCEPT\n"
    )
    with pytest.raises(ValueError, match="iptables"):
        host.fresh_host()


@pytest.mark.parametrize(
    "producer,consumer",
    [
        ("print('partial'); sys.exit(1)", "sys.stdin.read()"),  # pg_dump
        ("print('partial'); sys.exit(137)", "sys.stdin.read()"),  # termination
        ("print('archive')", "sys.stdin.read(); sys.exit(28)"),  # disk exhaustion
        ("print('archive')", "sys.stdin.read(); sys.exit(255)"),  # network or SFTP auth
        ("print('archive')", "sys.stdin.read(); sys.exit(3)"),  # Restic/pg_restore
    ],
)
def test_archive_pipeline_requires_both_exit_codes(
    tmp_path, monkeypatch, producer, consumer
):
    monkeypatch.setattr(backup, "BASE", tmp_path)
    with pytest.raises(ValueError, match="transfer failed"):
        backup.transfer(
            [sys.executable, "-c", "import sys; " + producer],
            [sys.executable, "-c", "import sys; " + consumer],
        )


def completion(**values):
    return {
        "id": SNAPSHOT,
        "operation": OPERATION,
        "repository": "b" * 64,
        "config": "c" * 64,
        "created": int(time.time()) - 1,
        "bootstrap": False,
        "evidence": {
            "revision": [backup.HEAD],
            "auth_columns": 4,
            "units_sold": 42,
            **dict.fromkeys(backup.TABLES, 1),
        },
        **values,
    }


@pytest.mark.parametrize(
    "state", ["stale", "tampered", "missing-repository", "failed-drill"]
)
def test_receipt_cannot_authorize_release_or_retention(monkeypatch, state):
    value = completion()
    receipt = {
        **value,
        "verified": value["created"],
        "integrity": "repository-check-and-authenticated-full-dump",
    }
    if state == "stale":
        value["created"] -= backup.MAX_AGE + 1
    if state == "tampered":
        receipt["evidence"] = {**value["evidence"], "stores": 99}

    def load(path):
        if path == backup.RECEIPT and state == "failed-drill":
            raise FileNotFoundError(path)
        return value if path == backup.COMPLETE else receipt

    def check(_value):
        if state == "missing-repository":
            raise ValueError("Off-server repository unavailable")

    monkeypatch.setattr(backup, "load", load)
    monkeypatch.setattr(backup, "check_repository", check)
    monkeypatch.setattr(
        backup, "restic", lambda *args: pytest.fail("Must block before retention")
    )
    with pytest.raises((ValueError, FileNotFoundError)):
        backup.retention_plan()


@pytest.mark.parametrize(
    "failure", ["revision", "business-count", "auth", "corrupt", "disk"]
)
def test_failed_isolated_restore_never_writes_receipt(tmp_path, monkeypatch, failure):
    value = completion()
    image = tmp_path / "active.env"
    image.write_text(
        "POSTGRES_IMAGE=ghcr.io/nandakumar-selvaraj/aiproductdemandanalyzer/postgres@sha256:"
        + "a" * 64
    )
    restored = dict(value["evidence"])
    if failure == "revision":
        restored["revision"] = ["incorrect"]
    if failure == "business-count":
        restored["stores"] = 2
    if failure == "auth":
        restored["auth_columns"] = 3
    calls = []

    def run(args, **kwargs):
        calls.append(args)
        return json.dumps(restored).encode()

    def transfer(*args):
        if failure == "corrupt":
            raise ValueError("pg_restore failed")
        if failure == "disk":
            raise OSError(errno.ENOSPC, "Isolated tmpfs capacity exceeded")

    monkeypatch.setattr(backup, "check_repository", lambda value: None)
    monkeypatch.setattr(backup, "restic", lambda *args: None)
    monkeypatch.setattr(backup, "image_file", lambda bootstrap: image)
    monkeypatch.setattr(backup, "run", run)
    monkeypatch.setattr(backup, "transfer", transfer)
    monkeypatch.setattr(
        backup, "save", lambda *args: pytest.fail("Receipt should not exist")
    )
    with pytest.raises((ValueError, OSError)):
        backup.restore(value)
    assert calls[-1][:4] == ["docker", "rm", "-f", "-v"]
    assert calls[0][calls[0].index("--network") + 1] == "none"


@pytest.mark.parametrize("snapshot", ["latest", "a1" * 4, "Z" * 64])
def test_invalid_restore_snapshot_is_rejected(snapshot):
    assert not backup.is_digest(snapshot)


def test_restore_invalidation_precedes_configuration_and_work():
    for file, operation in (("restore-verify.sh", "restore"), ("backup.sh", "backup")):
        script = (ROOT / "deploy/single" / file).read_text()
        assert script.index("flock -x") < script.index("invalidate-" + operation)
        assert script.index("invalidate-" + operation) < script.index(
            "source /opt/demand/backup-common.sh"
        )
        assert "forget" not in script and "prune" not in script


def test_missing_or_expired_artifact_does_not_download(monkeypatch):
    monkeypatch.setenv("PUBLISH_RUN_ID", "12")
    monkeypatch.setenv("GITHUB_SHA", "a" * 40)
    monkeypatch.setattr(release_manifest.guards, "require_workflow", lambda *args: None)
    monkeypatch.setattr(
        release_manifest.shared, "verify_run", lambda *args: {"event": "push"}
    )
    monkeypatch.setattr(
        release_manifest.shared, "run", lambda *args: pytest.fail("Unexpected download")
    )
    for items in ([], [{"name": "single-release-manifest", "expired": True}]):
        monkeypatch.setattr(
            release_manifest.shared,
            "github",
            lambda _: {
                "total_count": len(items),
                "artifacts": items,
            },
        )
        with pytest.raises(ValueError, match="unexpired"):
            release_manifest.main()


def test_manifest_binds_sha_and_approved_repository():
    sha = "a" * 40
    value = {
        "sha": sha,
        **{
            name: repo + "@sha256:" + "c" * 64
            for name, repo in release_manifest.REPOS.items()
        },
    }
    assert release_manifest.validate(value, sha) == value
    with pytest.raises(ValueError, match="revision"):
        release_manifest.validate(value, "b" * 40)
    with pytest.raises(ValueError, match="approved image"):
        release_manifest.validate(
            {**value, "postgres": "example.invalid/postgres@sha256:" + "c" * 64}, sha
        )


def test_failed_exact_commit_ci_blocks_publication(monkeypatch):
    monkeypatch.setenv("GITHUB_EVENT_NAME", "push")
    monkeypatch.setenv("GITHUB_SHA", "a" * 40)
    monkeypatch.setattr(ci.guards, "require_workflow", lambda env, op: op == "publish")

    def checks(sha, wait):
        assert sha == "a" * 40 and wait is True
        raise ValueError("CI failed")

    monkeypatch.setattr(ci.shared, "ci", checks)
    monkeypatch.setattr(ci.shared, "WORKFLOWS", [])
    with pytest.raises(ValueError, match="CI failed"):
        ci.main()
