"""Root-owned, single-application release controller. One bounded JSON request on stdin."""

try:
    import fcntl
except (
    ImportError
):  # Permit pure validation tests on Windows; execution remains Linux-only.
    fcntl = None
import json
import os
import re
import subprocess
import sys
from datetime import UTC, datetime
from pathlib import Path

BASE = Path("/opt/demand")
STATE = Path("/var/lib/demand/releases")
PREFIX = "ghcr.io/nandakumar-selvaraj/aiproductdemandanalyzer/"
REPOSITORIES = {
    "BACKEND_IMAGE": PREFIX + "backend",
    "FRONTEND_IMAGE": PREFIX + "frontend",
    "POSTGRES_IMAGE": PREFIX + "postgres",
    "NGINX_IMAGE": "docker.io/nginx/nginx-unprivileged",
}


def run(args):
    result = subprocess.run(args, cwd=BASE, capture_output=True, timeout=1200)
    if result.returncode:
        raise RuntimeError(
            "Command failed; output withheld to protect runtime credentials"
        )
    return result.stdout


def validate(value):
    if set(value) != {*REPOSITORIES, "sha"}:
        raise ValueError("Unexpected release fields")
    if not re.fullmatch(r"[0-9a-f]{40}", value["sha"]):
        raise ValueError("Full commit SHA required")
    for key, repository in REPOSITORIES.items():
        if not re.fullmatch(
            re.escape(repository) + r"@sha256:[0-9a-f]{64}", value[key]
        ):
            raise ValueError("Unapproved or mutable image reference")
    return value


def private(path):
    info = path.stat()
    if info.st_uid != 0 or info.st_mode & 0o077:
        raise ValueError("Configuration must be root owned and private")


def write(path, content):
    temporary = path.with_suffix(path.suffix + ".new")
    temporary.write_text(content)
    temporary.chmod(0o600)
    temporary.replace(path)


def image_env(value):
    return "".join(key + "=" + value[key] + "\n" for key in REPOSITORIES)


def compose(value, *args):
    candidate = STATE / "candidate.env"
    write(candidate, image_env(value))
    return run(
        [
            "docker",
            "compose",
            "--env-file",
            "/etc/demand/runtime.env",
            "--env-file",
            str(candidate),
            "-f",
            str(BASE / "compose.prod.yml"),
            *args,
        ]
    )


def healthy(value, *, check_migrations=True):
    compose(
        value,
        "up",
        "-d",
        "--no-deps",
        "--wait",
        "--wait-timeout",
        "180",
        "backend",
        "frontend",
        "nginx",
    )
    if check_migrations:
        verify_migrations(value)
    domain = Path("/etc/demand/domain").read_text().strip()
    if not re.fullmatch(
        r"(?:[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?\.)+[a-z]{2,63}", domain
    ):
        raise ValueError("Invalid operator-approved domain")
    run(
        [
            "curl",
            "--fail",
            "--silent",
            "--show-error",
            "--max-time",
            "30",
            "--resolve",
            domain + ":443:127.0.0.1",
            "https://" + domain + "/api/v1/ready",
        ]
    )
    run(
        [
            "curl",
            "--fail",
            "--silent",
            "--show-error",
            "--max-time",
            "30",
            "--resolve",
            domain + ":443:127.0.0.1",
            "https://" + domain + "/",
        ]
    )


def verify_migrations(value):
    compose(
        value,
        "exec",
        "-T",
        "backend",
        "python",
        "-c",
        "from alembic.config import Config; from alembic.script import ScriptDirectory; "
        "from alembic.runtime.migration import MigrationContext; "
        "from app.db.session import get_engine; "
        "c=get_engine().connect(); "
        "assert set(MigrationContext.configure(c).get_current_heads()) == "
        "set(ScriptDirectory.from_config(Config('alembic.ini')).get_heads()); c.close()",
    )


def record(action, sha, status):
    with (STATE / "history.jsonl").open("a") as stream:
        stream.write(
            json.dumps(
                {
                    "at": datetime.now(UTC).isoformat(),
                    "action": action,
                    "sha": sha,
                    "status": status,
                }
            )
            + "\n"
        )


def main():
    if fcntl is None or os.geteuid() != 0 or len(sys.argv) != 1:
        raise ValueError("Restricted root entrypoint only")
    os.umask(0o077)
    private(Path("/etc/demand/runtime.env"))
    private(BASE)
    run(["/opt/demand/host-check.sh"])
    run(["/opt/demand/backup-preflight.sh"])
    if not Path("/etc/demand/tls-ready").is_file():
        raise ValueError(
            "Manual DNS, certificate and HTTPS acceptance gate is incomplete"
        )
    request = json.loads(sys.stdin.buffer.read(16385))
    if set(request) != {"action", "release", "schema_backward_compatible"}:
        raise ValueError("Unexpected request fields")
    if request["schema_backward_compatible"] is not True:
        raise ValueError("Explicit migration compatibility review is required")
    action = request["action"]
    if action not in {"deploy", "rollback"}:
        raise ValueError("Unknown operation")
    value = validate(request["release"])
    STATE.mkdir(parents=True, exist_ok=True, mode=0o700)
    with (STATE / "operation.lock").open("w") as lock:
        fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        active = STATE / "active.json"
        old = validate(json.loads(active.read_text())) if active.exists() else None
        if old and value["POSTGRES_IMAGE"] != old["POSTGRES_IMAGE"]:
            raise ValueError(
                "Database image upgrades require a separate reviewed procedure"
            )
        compose(value, "config", "--quiet")
        compose(value, "pull")
        if action == "rollback":
            previous = validate(json.loads((STATE / "previous.json").read_text()))
            if value != previous:
                raise ValueError("Rollback must select the previous successful release")
        else:
            if old:
                run(["/opt/demand/backup.sh"])
                compose(old, "stop", "backend")
            else:
                # Volume is created once by an operator; never implicitly replace a missing volume.
                run(["docker", "volume", "inspect", "demand-single-database"])
            compose(value, "up", "-d", "--wait", "--wait-timeout", "120", "db")
            if not old:
                run(["/opt/demand/backup.sh", "--bootstrap"])
            try:
                compose(value, "run", "--rm", "--no-deps", "migrate")
            except Exception:
                record(
                    action, value["sha"], "migration-failed-manual-recovery-required"
                )
                # Partial DDL is never assumed compatible; do not restart old application blindly.
                raise
        try:
            healthy(value, check_migrations=action == "deploy")
        except Exception:
            record(action, value["sha"], "health-failed")
            if old:
                try:
                    # Compatible additive schema can legitimately be newer than old image heads.
                    healthy(old, check_migrations=False)
                    record("automatic-rollback", old["sha"], "passed")
                except Exception:
                    record(
                        "automatic-rollback",
                        old["sha"],
                        "failed-manual-recovery-required",
                    )
                    raise
            raise
        if old:
            write(STATE / "previous.json", json.dumps(old))
        write(active, json.dumps(value))
        write(STATE / "active.env", image_env(value))
        record(action, value["sha"], "passed")
        print("Release passed database, container and HTTPS readiness checks")


if __name__ == "__main__":
    try:
        main()
    except Exception:
        print(
            "Release failed. Inspect root-only release history and follow recovery runbook."
        )
        raise SystemExit(1) from None
