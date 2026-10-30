#!/usr/bin/python3
"""Root-owned restricted deployment entrypoint. Read one JSON request from stdin."""

try:
    import fcntl
except (
    ImportError
):  # Validation helpers remain importable on Windows; execution is Linux-only.
    fcntl = None
import ipaddress
import json
import os
import re
import socket
import subprocess
import sys
from pathlib import Path

CONFIG = Path("/etc/portfolio")
LIB = Path("/usr/local/lib/portfolio")
STATE = Path("/var/lib/portfolio/releases")
PREFIX = "ghcr.io/nandakumar-selvaraj/aiproductdemandanalyzer/"


def run(args, *, env=None, input=None):
    result = subprocess.run(
        args, input=input, env=env, capture_output=True, timeout=900
    )
    if result.returncode:
        # Container/Compose output may contain secrets; use root-only logs separately.
        raise RuntimeError(
            "Deployment command failed; inspect private host diagnostics"
        )
    return result.stdout


def validate_release(value):
    if set(value) != {
        "sha",
        "backend",
        "frontend",
        "postgres",
        "caddy",
        "domain",
        "email",
        "host",
    }:
        raise ValueError("Unexpected release fields")
    if not re.fullmatch(r"[0-9a-f]{40}", value["sha"]):
        raise ValueError("Commit must be a full SHA")
    for key, repository in [
        ("backend", PREFIX + "backend"),
        ("frontend", PREFIX + "frontend"),
        ("postgres", "docker.io/library/postgres"),
        ("caddy", "docker.io/library/caddy"),
    ]:
        if not re.fullmatch(
            re.escape(repository) + r"@sha256:[0-9a-f]{64}", value[key]
        ):
            raise ValueError("Only approved immutable image repositories are accepted")
    domain = value["domain"]
    if len(domain) > 253 or not re.fullmatch(
        r"(?=.{1,253}$)(?:[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?\.)+[a-z]{2,63}", domain
    ):
        raise ValueError("An explicit DNS hostname is required")
    ip = ipaddress.IPv4Address(value["host"])
    if not ip.is_global:
        raise ValueError("Expected a public server IPv4")
    if not re.fullmatch(
        r"[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,63}", value["email"]
    ):
        raise ValueError("Invalid ACME email")
    return value


def check_dns(value):
    ipv4 = {
        item[4][0] for item in socket.getaddrinfo(value["domain"], 443, socket.AF_INET)
    }
    ipv6 = {
        item[4][0]
        for item in socket.getaddrinfo(value["domain"], 443, socket.AF_UNSPEC)
        if item[0] == socket.AF_INET6
    }
    if ipv4 != {value["host"]} or ipv6:
        raise ValueError(
            "DNS must have only the expected A record and no unsupported AAAA record"
        )


def load_env():
    path = CONFIG / "demand.env"
    if path.stat().st_uid != 0 or path.stat().st_mode & 0o077:
        raise ValueError("demand.env must be root-owned mode 0600")
    values = {}
    for line in path.read_text().splitlines():
        if line and not line.startswith("#"):
            key, value = line.split("=", 1)
            values[key] = value
    required = [
        "POSTGRES_DB",
        "POSTGRES_USER",
        "POSTGRES_PASSWORD",
        "APP_DB_PASSWORD",
        "DEMO_DB_PASSWORD",
        "DATABASE_URL",
        "MIGRATION_DATABASE_URL",
        "JWT_SIGNING_SECRET",
    ]
    if any(not values.get(key) or "REPLACE" in values[key] for key in required):
        raise ValueError("Private host configuration is incomplete")
    if (
        values.get("PUBLIC_DEMO_ENABLED", "false") != "false"
        or values.get("AI_ENABLED", "false") != "false"
    ):
        raise ValueError(
            "Initial private deployment requires public demo and paid inference disabled"
        )
    if values.get("COMPOSE_PROJECT_NAME", "demand") != "demand":
        raise ValueError(
            "Stable demand project name required to preserve existing volumes"
        )
    if len(values["JWT_SIGNING_SECRET"]) < 64:
        raise ValueError("Signing secret must have at least 64 random characters")
    return values


def environment(release):
    values = load_env()
    values.update(
        COMPOSE_PROJECT_NAME="demand",
        ENVIRONMENT="production",
        AUTH_ENABLED="true",
        AUTH_ACCESS_TOKEN_MINUTES="30",
        AI_ENABLED="false",
        DEMO_AI_ENABLED="false",
        PUBLIC_DEMO_ENABLED="false",
        APP_DOMAIN=release["domain"],
        ACME_EMAIL=release["email"],
        AUTH_ALLOWED_ORIGINS=json.dumps(["https://" + release["domain"]]),
        TRUSTED_HOSTS=json.dumps([release["domain"], "127.0.0.1", "backend"]),
        BACKEND_IMAGE=release["backend"],
        FRONTEND_IMAGE=release["frontend"],
        POSTGRES_IMAGE=release["postgres"],
        CADDY_IMAGE=release["caddy"],
    )
    return {**os.environ, **values}


def compose(env, *args):
    return run(
        [
            "docker",
            "compose",
            "--project-name",
            "demand",
            "-f",
            str(LIB / "compose.production.yml"),
            "-f",
            str(LIB / "compose.app.yml"),
            *args,
        ],
        env=env,
    )


def ingress(env, *args):
    return run(
        ["docker", "compose", "-f", str(LIB / "compose.ingress.yml"), *args], env=env
    )


def write_json(path, value):
    temporary = path.with_suffix(".new")
    temporary.write_text(json.dumps(value, indent=2) + "\n")
    temporary.chmod(0o600)
    temporary.replace(path)


def configure_hostname(release):
    (CONFIG / "Caddyfile").write_text("import /etc/caddy/sites/*.caddy\n")
    site = """%s {
    tls %s
    request_body {
        max_size 26MB
    }
    header {
        Cache-Control "no-store"
        X-Content-Type-Options nosniff
        Referrer-Policy strict-origin-when-cross-origin
        X-Frame-Options DENY
        Strict-Transport-Security "max-age=31536000"
        -Server
    }
    @developer_docs path /docs /docs/* /redoc /openapi.json
    handle @developer_docs {
        respond 404
    }
    handle /api/* {
        reverse_proxy demand-api:8000
    }
    handle {
        reverse_proxy demand-web:8080
    }
}
""" % (release["domain"], release["email"])
    (CONFIG / "sites/demand.caddy").write_text(site)


def smoke(release):
    # No -k/--insecure: a publicly trusted certificate is mandatory.
    for path in ["/", "/data-management", "/api/v1/health", "/api/v1/ready"]:
        run(
            [
                "curl",
                "--fail",
                "--silent",
                "--show-error",
                "--retry",
                "12",
                "--retry-all-errors",
                "--retry-delay",
                "5",
                "--max-time",
                "15",
                "https://" + release["domain"] + path,
            ]
        )
    for path in ["/docs", "/openapi.json"]:
        code = run(
            [
                "curl",
                "--silent",
                "--output",
                "/dev/null",
                "--write-out",
                "%{http_code}",
                "--max-time",
                "15",
                "https://" + release["domain"] + path,
            ]
        )
        if code != b"404":
            raise RuntimeError("Production documentation is not blocked")
    code = run(
        [
            "curl",
            "--silent",
            "--output",
            "/dev/null",
            "--write-out",
            "%{http_code}",
            "--max-time",
            "15",
            "-X",
            "POST",
            "https://" + release["domain"] + "/api/v1/ingestion/sales",
        ]
    )
    if code != b"401":
        raise RuntimeError("Anonymous upload was not rejected")


def activate(release, *, migrate):
    env = environment(release)
    configure_hostname(release)
    compose(env, "config", "--quiet")
    compose(env, "--profile", "tools", "pull", "backend", "frontend", "db", "migrate")
    ingress(env, "pull")
    compose(env, "up", "-d", "--no-build", "--wait", "--wait-timeout", "180", "db")
    if migrate:
        # Fail closed: an off-host encrypted backup and a real isolated restore precede migrations.
        run(["/bin/bash", str(LIB / "backup.sh")], env=env)
        run(["/bin/bash", str(LIB / "restore-verify.sh")], env=env)
        compose(env, "run", "--rm", "--no-deps", "migrate")
    compose(
        env,
        "up",
        "-d",
        "--no-build",
        "--wait",
        "--wait-timeout",
        "180",
        "backend",
        "frontend",
    )
    ingress(
        env,
        "run",
        "--rm",
        "--no-deps",
        "caddy",
        "caddy",
        "validate",
        "--config",
        "/etc/caddy/Caddyfile",
    )
    ingress(env, "up", "-d", "--no-build", "--wait", "--wait-timeout", "180")
    ingress(
        env,
        "exec",
        "-T",
        "caddy",
        "caddy",
        "reload",
        "--config",
        "/etc/caddy/Caddyfile",
    )
    smoke(release)


def main():
    if os.geteuid() != 0:
        raise ValueError("Use the restricted sudo entrypoint")
    if (
        not os.path.ismount("/var/lib/portfolio")
        or not Path("/var/lib/cloud/instance/boot-finished").exists()
    ):
        raise ValueError(
            "Verified cloud-init completion and persistent storage mount are required"
        )
    os.umask(0o077)
    request = json.loads(sys.stdin.buffer.read(16385))
    if set(request) != {"action", "release"} or request["action"] not in [
        "deploy",
        "rollback",
        "remove-domain",
    ]:
        raise ValueError("Invalid operation")
    release = validate_release(request["release"])
    with (CONFIG / "deployment.lock").open("w") as lock:
        fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        active_file = CONFIG / "active.json"
        previous = json.loads(active_file.read_text()) if active_file.exists() else None
        if request["action"] == "remove-domain":
            if not previous or previous["domain"] != release["domain"]:
                raise ValueError("Removal must match the active domain")
            site = CONFIG / "sites/demand.caddy"
            old = site.read_text()
            site.write_text(
                "# Demand hostname deliberately detached; data remains intact.\n"
            )
            try:
                env = environment(previous)
                ingress(
                    env,
                    "exec",
                    "-T",
                    "caddy",
                    "caddy",
                    "reload",
                    "--config",
                    "/etc/caddy/Caddyfile",
                )
            except Exception:
                site.write_text(old)
                raise
            print(
                "Hostname detached; application/database volumes preserved. Ask DNS owner to remove A record."
            )
            (CONFIG / "domain-detached").touch(mode=0o600)
            return
        check_dns(release)
        STATE.mkdir(parents=True, exist_ok=True, mode=0o700)
        network = subprocess.run(
            ["docker", "network", "inspect", "portfolio_demand_edge"],
            capture_output=True,
        )
        if network.returncode:
            run(["docker", "network", "create", "portfolio_demand_edge"])
        if request["action"] == "rollback":
            stored = STATE / (release["sha"] + ".json")
            old = json.loads(stored.read_text()) if stored.exists() else None
            if (
                not previous
                or not old
                or any(
                    old[key] != release[key] for key in ["sha", "backend", "frontend"]
                )
            ):
                raise ValueError(
                    "Rollback requires an exact previously successful local release"
                )
            # Application rollback keeps the current database, ingress and active hostname.
            release = {
                **previous,
                **{key: old[key] for key in ["sha", "backend", "frontend"]},
            }
        if previous and previous["postgres"] != release["postgres"]:
            raise ValueError(
                "Database image changes require a separate reviewed maintenance procedure"
            )
        # No automatic schema downgrade or destructive cleanup on failure.
        activate(release, migrate=request["action"] == "deploy")
        if previous:
            write_json(CONFIG / "previous.json", previous)
        write_json(active_file, release)
        write_json(STATE / (release["sha"] + ".json"), release)
        (CONFIG / "domain-detached").unlink(missing_ok=True)
        print(
            "Release verified; persistent volumes preserved. No default users were created."
        )


if __name__ == "__main__":
    try:
        main()
    except Exception:
        print(
            "Release failed safely. No volumes were deleted; inspect private host diagnostics.",
            file=sys.stderr,
        )
        raise SystemExit(1) from None
