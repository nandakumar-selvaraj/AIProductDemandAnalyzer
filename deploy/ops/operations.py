#!/usr/bin/python3
"""Root-only encrypted backup, isolated restore verification, and local monitoring."""

import importlib.machinery
import importlib.util
import json
import os
import subprocess
import sys
import time
from pathlib import Path

loader = importlib.machinery.SourceFileLoader(
    "portfolio_release", "/usr/local/sbin/portfolio-release"
)
release = importlib.util.module_from_spec(
    importlib.util.spec_from_loader(loader.name, loader)
)
loader.exec_module(release)


def private_values(path):
    path = Path(path)
    if path.stat().st_uid != 0 or path.stat().st_mode & 0o077:
        raise ValueError("Private configuration permissions must be root:0600")
    return dict(
        line.split("=", 1)
        for line in path.read_text().splitlines()
        if line and not line.startswith("#")
    )


def context():
    if os.environ.get("BACKEND_IMAGE"):
        return dict(os.environ)
    return release.environment(json.loads((release.CONFIG / "active.json").read_text()))


def backup_env():
    env = {**context(), **private_values("/etc/portfolio/backup.env")}
    if not env.get("RESTIC_REPOSITORY", "").startswith("s3:https://"):
        raise ValueError("A dedicated HTTPS off-host S3 Restic repository is required")
    password = Path(env["RESTIC_PASSWORD_FILE"])
    if password.stat().st_uid != 0 or password.stat().st_mode & 0o077:
        raise ValueError("Restic password file must be root-owned mode 0600")
    if not password.read_bytes().strip():
        raise ValueError("Empty Restic passphrase")
    return env


def restic(env, *args):
    return release.run(["restic", *args], env=env)


def backup():
    env = backup_env()
    dump_command = [
        "docker",
        "compose",
        "--project-name",
        "demand",
        "-f",
        str(release.LIB / "compose.production.yml"),
        "-f",
        str(release.LIB / "compose.app.yml"),
        "exec",
        "-T",
        "db",
        "sh",
        "-c",
        'pg_dump -U "$POSTGRES_USER" -d "$POSTGRES_DB" -Fc',
    ]
    # Stream directly into client-side encryption; never persist plaintext dumps.
    with subprocess.Popen(
        dump_command, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL, env=env
    ) as dump:
        result = subprocess.run(
            [
                "restic",
                "backup",
                "--stdin",
                "--stdin-filename",
                "demand.dump",
                "--tag",
                "demand",
                "--quiet",
            ],
            stdin=dump.stdout,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            env=env,
            timeout=900,
        )
        dump.stdout.close()
        if dump.wait(timeout=30) or result.returncode:
            raise RuntimeError("Encrypted off-host database backup failed")
    restic(
        env,
        "forget",
        "--tag",
        "demand",
        "--group-by",
        "host,tags",
        "--keep-daily",
        "7",
        "--keep-weekly",
        "4",
        "--keep-monthly",
        "3",
        "--prune",
        "--quiet",
    )
    (release.CONFIG / "last-backup-success").write_text(str(int(time.time())))
    print("Encrypted off-host backup and retention completed")


def verify_restore():
    env = backup_env()
    restic(env, "check", "--quiet")
    target = "restore_verify_" + str(int(time.time())) + "_" + str(os.getpid())
    created = False
    try:
        release.compose(
            env,
            "exec",
            "-T",
            "db",
            "sh",
            "-c",
            'createdb -U "$POSTGRES_USER" -- "$1"',
            "sh",
            target,
        )
        created = True
        with subprocess.Popen(
            ["restic", "dump", "--tag", "demand", "latest", "demand.dump"],
            stdout=subprocess.PIPE,
            stderr=subprocess.DEVNULL,
            env=env,
        ) as dump:
            command = [
                "docker",
                "compose",
                "--project-name",
                "demand",
                "-f",
                str(release.LIB / "compose.production.yml"),
                "-f",
                str(release.LIB / "compose.app.yml"),
                "exec",
                "-T",
                "db",
                "sh",
                "-c",
                'pg_restore --exit-on-error --single-transaction --no-owner --no-acl -U "$POSTGRES_USER" -d "$1"',
                "sh",
                target,
            ]
            result = subprocess.run(
                command,
                stdin=dump.stdout,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                env=env,
                timeout=900,
            )
            dump.stdout.close()
            if dump.wait(timeout=30) or result.returncode:
                raise RuntimeError("Restore verification failed")
        # Fresh first deployment can legitimately have no application tables yet.
        result = release.compose(
            env,
            "exec",
            "-T",
            "db",
            "sh",
            "-c",
            'psql -U "$POSTGRES_USER" -d "$1" -Atc "SELECT count(*) FROM pg_catalog.pg_tables WHERE schemaname=\'public\'"',
            "sh",
            target,
        )
        if not result.strip().isdigit():
            raise RuntimeError("Restored database could not be queried")
        (release.CONFIG / "last-restore-success").write_text(str(int(time.time())))
        print(
            "Encrypted backup restored and queried successfully in a new isolated database"
        )
    finally:
        if created:
            assert target.startswith("restore_verify_")
            release.compose(
                env,
                "exec",
                "-T",
                "db",
                "sh",
                "-c",
                'dropdb -U "$POSTGRES_USER" -- "$1"',
                "sh",
                target,
            )


def monitor():
    import shutil

    env = context()
    disk = shutil.disk_usage("/var/lib/portfolio")
    memory = dict(
        (line.split(":")[0], int(line.split()[1]))
        for line in Path("/proc/meminfo").read_text().splitlines()
    )
    if (
        disk.free / disk.total < 0.15
        or memory["MemAvailable"] / memory["MemTotal"] < 0.1
    ):
        raise RuntimeError("Disk or memory pressure; inspect host metrics")
    if os.getloadavg()[1] > (os.cpu_count() or 1) * 2:
        raise RuntimeError("Sustained CPU/load pressure")
    release.compose(
        env,
        "exec",
        "-T",
        "backend",
        "python",
        "-c",
        "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8000/api/v1/ready',timeout=5)",
    )
    active = json.loads((release.CONFIG / "active.json").read_text())
    if not (release.CONFIG / "domain-detached").exists():
        release.smoke(active)
        certificate = subprocess.run(
            [
                "openssl",
                "s_client",
                "-connect",
                active["domain"] + ":443",
                "-servername",
                active["domain"],
            ],
            input=b"",
            capture_output=True,
            timeout=20,
        )
        release.run(
            ["openssl", "x509", "-checkend", str(7 * 86400), "-noout"],
            input=certificate.stdout,
        )
    marker = release.CONFIG / "last-backup-success"
    if not marker.exists() or time.time() - int(marker.read_text()) > 26 * 3600:
        raise RuntimeError("Backup is missing or older than 26 hours")
    print("CPU, RAM, disk, readiness, TLS lifetime and backup age checks passed")


if __name__ == "__main__":
    try:
        if os.geteuid() != 0:
            raise ValueError("Root-only operation")
        os.umask(0o077)
        {"backup": backup, "restore": verify_restore, "monitor": monitor}[sys.argv[1]]()
    except Exception:
        print(
            "Portfolio operation failed; inspect private host diagnostics",
            file=sys.stderr,
        )
        raise SystemExit(1) from None
