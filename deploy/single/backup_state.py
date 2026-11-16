"""Completed-backup journal and isolated restore acceptance for the dedicated host."""

import datetime as dt
import json
import os
import re
import select
import signal
import stat
import subprocess
import sys
import tempfile
import time
import uuid
from pathlib import Path

STATE = Path("/var/lib/demand")
BASE = Path("/opt/demand")
CONFIG = Path("/etc/demand")
COMPLETE = STATE / "backup-completed.json"
RECEIPT = STATE / "backup-restore-verified"
ARCHIVE = "demand.dump"
HEAD = "0003_api_tokens"
MAX_AGE = 26 * 3600
RESTIC = [
    "restic",
    "-o",
    "sftp.command=ssh -F /etc/demand/backup-ssh.conf demand-backup -s sftp",
]
TABLES = (
    "stores",
    "products",
    "sales_history",
    "inventory",
    "forecast_runs",
    "forecast_run_logs",
    "product_forecasts",
    "stock_recommendations",
    "auth_users",
    "auth_sessions",
    "auth_api_tokens",
)


def require(value, message):
    if not value:
        raise ValueError(message)


def private(path):
    info = path.lstat()
    require(
        stat.S_ISREG(info.st_mode)
        and info.st_nlink == 1
        and info.st_uid == 0
        and stat.S_IMODE(info.st_mode) == 0o600,
        "Unsafe backup metadata or configuration",
    )


def sync_state():
    fd = os.open(STATE, os.O_DIRECTORY)
    try:
        os.fsync(fd)
    finally:
        os.close(fd)


def save(path, value):
    with tempfile.NamedTemporaryFile(dir=STATE, delete=False) as stream:
        staged = Path(stream.name)
        try:
            stream.write(json.dumps(value, sort_keys=True).encode() + b"\n")
            stream.flush()
            os.fsync(stream.fileno())
            staged.replace(path)
            sync_state()
        finally:
            staged.unlink(missing_ok=True)


def load(path):
    private(path)
    return json.loads(path.read_text())


def run(args, *, timeout=900):
    result = subprocess.run(
        args, capture_output=True, timeout=timeout, check=False, cwd=BASE
    )
    require(result.returncode == 0, "Backup subprocess failed")
    return result.stdout


def restic(*args):
    return run([*RESTIC, *args])


def transfer(source, destination):
    """A downstream success cannot hide source failure or a truncated stream."""
    with subprocess.Popen(
        source, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL, cwd=BASE
    ) as producer:
        try:
            result = subprocess.run(
                destination,
                stdin=producer.stdout,
                capture_output=True,
                timeout=900,
                check=False,
                cwd=BASE,
            )
            producer.stdout.close()
            require(
                producer.wait(timeout=30) == result.returncode == 0,
                "Archive transfer failed",
            )
            return result.stdout
        finally:
            if producer.poll() is None:
                producer.kill()


def repo_id():
    value = json.loads(restic("cat", "config"))["id"]
    require(is_digest(value), "Invalid repository identity")
    return value


def is_digest(value):
    return isinstance(value, str) and re.fullmatch(r"[0-9a-f]{64}", value) is not None


def image_file(bootstrap):
    path = (
        CONFIG / "bootstrap-images.env" if bootstrap else STATE / "releases/active.env"
    )
    private(path)
    return path


def compose(images, *args):
    private(CONFIG / "runtime.env")
    return [
        "docker",
        "compose",
        "--env-file",
        str(CONFIG / "runtime.env"),
        "--env-file",
        str(images),
        "-f",
        str(BASE / "compose.prod.yml"),
        *args,
    ]


def evidence_sql(bootstrap):
    if bootstrap:
        return (
            "SELECT json_build_object('revision','uninitialized','public_relations',count(*)) "
            "FROM pg_catalog.pg_class c JOIN pg_catalog.pg_namespace n ON n.oid=c.relnamespace "
            "WHERE n.nspname='public' AND c.relkind IN ('r','p','v','m','f','S');"
        )
    fields = [
        "'revision', (SELECT json_agg(version_num ORDER BY version_num) FROM public.alembic_version)",
        "'units_sold', (SELECT coalesce(sum(units_sold),0) FROM public.sales_history)",
        "'auth_columns', (SELECT count(*) FROM information_schema.columns WHERE table_schema='public' AND "
        "(table_name,column_name) IN (('auth_users','password_hash'),('auth_users','role'),"
        "('auth_sessions','revoked_at'),('auth_api_tokens','revoked_at')))",
    ]
    fields += [f"'{table}', (SELECT count(*) FROM public.{table})" for table in TABLES]
    return f"SELECT json_build_object({', '.join(fields)});"


def validate_evidence(evidence, bootstrap):
    if bootstrap:
        require(
            evidence == {"revision": "uninitialized", "public_relations": 0},
            "Bootstrap DB is not empty",
        )
    else:
        require(
            set(evidence) == {"revision", "auth_columns", "units_sold", *TABLES}
            and evidence["revision"] == [HEAD]
            and evidence["auth_columns"] == 4
            and all(
                type(evidence[table]) is int and evidence[table] >= 0
                for table in (*TABLES, "units_sold")
            ),
            "Unexpected schema or business-data evidence",
        )


def query(process, sql):
    process.stdin.write(sql.encode() + b"\n")
    process.stdin.flush()
    require(
        select.select([process.stdout], [], [], 120)[0], "Database evidence timed out"
    )
    line = process.stdout.readline(16384)
    require(line.endswith(b"\n"), "Database evidence was incomplete")
    return line.strip()


def make_snapshot(images, bootstrap, operation):
    db = compose(images, "exec", "-T", "db")
    with subprocess.Popen(
        [
            *db,
            "psql",
            "-XqAt",
            "-v",
            "ON_ERROR_STOP=1",
            "-U",
            "demand_owner",
            "-d",
            "demand",
        ],
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        stderr=subprocess.DEVNULL,
        cwd=BASE,
    ) as session:
        try:
            snapshot = query(
                session,
                "BEGIN ISOLATION LEVEL REPEATABLE READ READ ONLY; SELECT pg_export_snapshot();",
            ).decode()
            require(
                re.fullmatch(r"[0-9A-Fa-f-]+", snapshot), "Invalid PostgreSQL snapshot"
            )
            evidence = json.loads(query(session, evidence_sql(bootstrap)))
            validate_evidence(evidence, bootstrap)
            events = transfer(
                [
                    *db,
                    "pg_dump",
                    "-U",
                    "demand_owner",
                    "-d",
                    "demand",
                    "-Fc",
                    "--snapshot",
                    snapshot,
                ],
                [
                    *RESTIC,
                    "backup",
                    "--json",
                    "--stdin",
                    "--stdin-filename",
                    ARCHIVE,
                    "--tag",
                    "demand-single",
                    "--tag",
                    operation,
                ],
            )
            session.stdin.close()
            require(session.wait(timeout=30) == 0, "PostgreSQL snapshot session failed")
        finally:
            if session.poll() is None:
                session.kill()
    summaries = [
        event
        for line in events.splitlines()
        if (event := json.loads(line)).get("message_type") == "summary"
    ]
    require(len(summaries) == 1, "Restic backup did not return a unique summary")
    prefix = summaries[0].get("snapshot_id")
    require(
        isinstance(prefix, str) and re.fullmatch(r"[0-9a-f]{8,64}", prefix),
        "Invalid Restic summary ID",
    )
    entry = exact_snapshot(operation)
    require(
        entry["id"].startswith(prefix), "Snapshot ID did not match backup operation"
    )
    return entry["id"], evidence


def exact_snapshot(operation, expected=None):
    entries = json.loads(restic("snapshots", "--json", "--tag", operation))
    require(
        isinstance(entries, list) and len(entries) == 1,
        "Operation must identify exactly one snapshot",
    )
    entry = entries[0]
    require(
        is_digest(entry.get("id"))
        and (expected is None or entry["id"] == expected)
        and set(entry.get("tags", [])) == {"demand-single", operation}
        and entry.get("paths") == ["/" + ARCHIVE],
        "Snapshot identity or archive path did not match",
    )
    return entry


def configuration():
    value = os.environ["DEMAND_BACKUP_CONFIG_DIGEST"]
    require(is_digest(value), "Missing verified backup configuration fingerprint")
    return value


def validate_completed(value):
    require(
        set(value)
        == {
            "id",
            "operation",
            "repository",
            "config",
            "created",
            "bootstrap",
            "evidence",
        }
        and is_digest(value["id"])
        and is_digest(value["repository"])
        and is_digest(value["config"])
        and re.fullmatch(r"demand-op-[0-9a-f]{32}", value["operation"])
        and type(value["bootstrap"]) is bool
        and type(value["created"]) is int
        and 0 <= time.time() - value["created"] <= MAX_AGE,
        "Invalid or stale completed backup",
    )
    validate_evidence(value["evidence"], value["bootstrap"])
    return value


def check_repository(value):
    require(
        value["config"] == configuration() and value["repository"] == repo_id(),
        "Backup repository or configuration changed",
    )
    exact_snapshot(value["operation"], value["id"])


def restore(value):
    validate_completed(value)
    check_repository(value)
    restic("check")
    images = image_file(value["bootstrap"])
    lines = [
        line
        for line in images.read_text().splitlines()
        if line.startswith("POSTGRES_IMAGE=")
    ]
    require(len(lines) == 1, "Missing approved restore image")
    image = lines[0].split("=", 1)[1]
    require(
        re.fullmatch(
            r"ghcr\.io/nandakumar-selvaraj/aiproductdemandanalyzer/postgres@sha256:[0-9a-f]{64}",
            image,
        ),
        "Unapproved PostgreSQL restore image",
    )
    name = "demand-restore-" + uuid.uuid4().hex
    attempted = False
    try:
        attempted = True
        run(
            [
                "docker",
                "run",
                "--pull=never",
                "-d",
                "--name",
                name,
                "--network",
                "none",
                "--memory",
                "768m",
                "--cpus",
                "0.5",
                "--pids-limit",
                "128",
                "--tmpfs",
                "/var/lib/postgresql/data:rw,size=512m",
                "-e",
                "POSTGRES_HOST_AUTH_METHOD=trust",
                image,
            ]
        )
        while_start = time.monotonic()
        while True:
            try:
                # TCP loopback is unavailable during the image's temporary init server.
                run(
                    [
                        "docker",
                        "exec",
                        name,
                        "pg_isready",
                        "-h",
                        "127.0.0.1",
                        "-U",
                        "postgres",
                    ],
                    timeout=10,
                )
                break
            except (ValueError, subprocess.TimeoutExpired):
                require(
                    time.monotonic() - while_start < 120,
                    "Restore database was not ready",
                )
                time.sleep(2)
        run(["docker", "exec", name, "createdb", "-U", "postgres", "restore_check"])
        transfer(
            [*RESTIC, "dump", value["id"], "/" + ARCHIVE],
            [
                "docker",
                "exec",
                "-i",
                name,
                "pg_restore",
                "-U",
                "postgres",
                "-d",
                "restore_check",
                "--no-owner",
                "--no-acl",
                "--exit-on-error",
                "--single-transaction",
            ],
        )
        evidence = json.loads(
            run(
                [
                    "docker",
                    "exec",
                    name,
                    "psql",
                    "-XqAt",
                    "-v",
                    "ON_ERROR_STOP=1",
                    "-U",
                    "postgres",
                    "-d",
                    "restore_check",
                    "-c",
                    evidence_sql(value["bootstrap"]),
                ]
            )
        )
        validate_evidence(evidence, value["bootstrap"])
        require(
            evidence == value["evidence"],
            "Restored business-data evidence differs from source",
        )
    finally:
        if attempted:
            run(["docker", "rm", "-f", "-v", name])
    receipt = {
        **value,
        "verified": int(time.time()),
        "integrity": "repository-check-and-authenticated-full-dump",
    }
    save(STATE / ("verified-" + value["id"] + ".json"), receipt)
    save(RECEIPT, receipt)
    return receipt


def backup(bootstrap):
    operation = "demand-op-" + uuid.uuid4().hex
    created = int(time.time())
    repository = repo_id()
    snapshot, evidence = make_snapshot(image_file(bootstrap), bootstrap, operation)
    value = {
        "id": snapshot,
        "operation": operation,
        "repository": repository,
        "config": configuration(),
        "created": created,
        "bootstrap": bootstrap,
        "evidence": evidence,
    }
    restic("check")
    save(COMPLETE, value)
    restore(value)
    return snapshot


def preflight():
    value = validate_completed(load(COMPLETE))
    receipt = load(RECEIPT)
    require(
        set(receipt) == {*value, "verified", "integrity"}
        and all(receipt[k] == v for k, v in value.items())
        and receipt["integrity"] == "repository-check-and-authenticated-full-dump"
        and type(receipt["verified"]) is int
        and value["created"] <= receipt["verified"] <= time.time(),
        "Missing, stale or mismatched restore acceptance",
    )
    check_repository(value)
    restic("check")
    return value


def retention_plan():
    current = preflight()
    entries = json.loads(restic("snapshots", "--json", "--tag", "demand-single"))
    verified = []
    for entry in entries:
        snapshot = entry["id"]
        require(is_digest(snapshot), "Invalid snapshot inventory")
        if snapshot == current["id"]:
            continue
        try:
            receipt = load(STATE / ("verified-" + snapshot + ".json"))
        except FileNotFoundError:
            # Failed/orphaned snapshots never count as retained recovery points.
            continue
        require(
            receipt["id"] == snapshot
            and receipt["repository"] == current["repository"]
            and receipt["integrity"] == "repository-check-and-authenticated-full-dump"
            and set(entry.get("tags", [])) == {"demand-single", receipt["operation"]},
            "Verified snapshot inventory differs",
        )
        verified.append((receipt["created"], snapshot))
    keep = {current["id"]}
    periods = ({}, {}, {})
    for timestamp, snapshot in sorted(
        verified + [(current["created"], current["id"])], reverse=True
    ):
        date = dt.datetime.fromtimestamp(timestamp, dt.UTC)
        iso = date.isocalendar()
        for bucket, key, limit in zip(
            periods,
            (date.date(), (iso.year, iso.week), (date.year, date.month)),
            (7, 4, 2),
            strict=True,
        ):
            if key not in bucket and len(bucket) < limit:
                bucket[key] = snapshot
                keep.add(snapshot)
    return sorted(snapshot for _, snapshot in verified if snapshot not in keep)


def terminated(_signum, _frame):
    raise InterruptedError("Backup interrupted")


def main():
    signal.signal(signal.SIGTERM, terminated)
    os.umask(0o077)
    require(os.geteuid() == 0, "Root backup operation only")
    args = sys.argv[1:]
    if args in (["invalidate-backup"], ["invalidate-restore"]):
        RECEIPT.unlink(missing_ok=True)
        if args == ["invalidate-backup"]:
            COMPLETE.unlink(missing_ok=True)
        sync_state()
    elif args in (["backup"], ["backup", "--bootstrap"]):
        print(backup(len(args) == 2))
    elif len(args) == 2 and args[0] == "restore":
        require(is_digest(args[1]), "A full snapshot SHA is required")
        value = validate_completed(load(COMPLETE))
        require(value["id"] == args[1], "Select the exact current completed snapshot")
        restore(value)
        print(value["id"])
    elif args == ["preflight"]:
        preflight()
    elif args == ["retention-plan"]:
        print(json.dumps({"review_only_forget_candidates": retention_plan()}))
    else:
        raise ValueError("Invalid backup operation")


if __name__ == "__main__":
    try:
        main()
    except Exception:
        print(
            "Backup or restore acceptance failed. Check owner runbook and service status.",
            file=sys.stderr,
        )
        raise SystemExit(1) from None
