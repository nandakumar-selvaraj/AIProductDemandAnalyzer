"""Disposable production-stack verification. Never reads .env.production or local DB URLs.

Run: python deploy/validate_docker.py [--config-only]
Requires Docker Compose v2.24.4+ (!override), Docker Engine and Linux containers.
"""

import argparse
import json
import os
import re
from pathlib import Path
import secrets
import shutil
import socket
import ssl
import subprocess
import urllib.error
import urllib.request

ROOT = Path(__file__).resolve().parents[1]


def validate_compose_config(configuration):
    """Check runtime-sensitive mounts that Compose schema validation alone accepts."""
    expected = {
        "backend": ["/tmp:size=64m,mode=1777"],
        "migrate": ["/tmp:size=64m,mode=1777"],
        "frontend": ["/tmp:size=16m"],
    }
    for service, mounts in expected.items():
        definition = configuration["services"][service]
        if definition.get("tmpfs") != mounts:
            raise ValueError(
                f"{service}: tmpfs must be a single quoted absolute mount: {mounts}"
            )
        if (
            definition.get("read_only") is not True
            or "ALL" not in definition.get("cap_drop", [])
            or "no-new-privileges:true" not in definition.get("security_opt", [])
        ):
            raise ValueError(
                f"{service}: production filesystem/capability safeguards are required"
            )


def probe_request(port, path, data=None, headers=None):
    """TLS SNI, certificate hostname and HTTP authority must all match Caddy's site."""
    return urllib.request.Request(
        f"https://localhost:{port}{path}", data=data, headers=headers or {}
    )


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config-only", action="store_true")
    parser.add_argument("--browser-tests", action="store_true")
    parser.add_argument(
        "--browser-container",
        action="store_true",
        help="Run production browsers in isolated Linux instead of the host",
    )
    options = parser.parse_args()
    if options.browser_container and not options.browser_tests:
        parser.error("--browser-container requires --browser-tests")
    project = "phase7b-" + secrets.token_hex(6)
    work = ROOT / "validation" / project
    work.mkdir(parents=True, mode=0o700)
    with socket.socket() as reservation:
        reservation.bind(("127.0.0.1", 0))
        port = reservation.getsockname()[1]
    password, reader_password, owner_password, token = [
        secrets.token_hex(32) for _ in range(4)
    ]
    values = {
        "COMPOSE_PROJECT_NAME": project,
        "APP_DOMAIN": "localhost",
        "ACME_EMAIL": "test@example.invalid",
        "POSTGRES_DB": "phase7b_demo",
        "POSTGRES_USER": "phase7b_owner",
        "POSTGRES_PASSWORD": owner_password,
        "APP_DB_PASSWORD": password,
        "DEMO_DB_PASSWORD": reader_password,
        "DATABASE_URL": f"postgresql+psycopg://demand_app:{password}@db:5432/phase7b_demo",
        "MIGRATION_DATABASE_URL": f"postgresql+psycopg://phase7b_owner:{owner_password}@db:5432/phase7b_demo",
        "DEMO_DATABASE_URL": f"postgresql+psycopg://demand_demo_reader:{reader_password}@db:5432/phase7b_demo",
        "TRUSTED_HOSTS": '["localhost","127.0.0.1","backend"]',
        "JWT_SIGNING_SECRET": token,
        "AUTH_ALLOWED_ORIGINS": json.dumps([f"https://localhost:{port}"]),
        "PUBLIC_DEMO_ENABLED": "true",
        "AI_ENABLED": "false",
        "DEMO_AI_ENABLED": "false",
        "AI_PROVIDER": "openai",
        "AI_BASE_URL": "",
        "AI_MODEL": "",
        "AI_API_KEY": "",
        "DEMO_READS_PER_MINUTE": "120",
    }
    # Explicit values override inherited shell variables, never the reverse.
    env = {**os.environ, **values}
    env_file, overlay = work / "compose.env", work / "compose.override.yml"
    env_file.write_text("".join(f"{k}={v}\n" for k, v in values.items()))
    env_file.chmod(0o600)
    overlay.write_text(
        "services:\n  proxy:\n    ports: !override\n"
        f'      - "127.0.0.1:{port}:443"\n'
        "    volumes: !override\n"
        "      - ./deploy/Caddyfile.validation:/etc/caddy/Caddyfile:ro\n"
        "      - ./deploy/Caddy.routes:/etc/caddy/app.routes:ro\n"
        "      - certificates:/data\n      - proxy_config:/config\n"
    )
    base = [
        "docker",
        "compose",
        "--project-name",
        project,
        "--env-file",
        str(env_file),
        "-f",
        str(ROOT / "compose.production.yml"),
        "-f",
        str(overlay),
    ]
    test_password = secrets.token_urlsafe(32)
    admin_email = "admin-" + secrets.token_hex(4) + "@example.invalid"
    viewer_email = "viewer-" + secrets.token_hex(4) + "@example.invalid"
    owned = False
    tls_context = None

    def redact(value):
        for secret in (password, reader_password, owner_password, token, test_password):
            value = value.replace(secret, "[REDACTED]")
        return re.sub(
            r"\beyJ[A-Za-z0-9_-]*\.[A-Za-z0-9_-]+\.[A-Za-z0-9_-]+\b",
            "[REDACTED JWT]",
            value,
        )

    def run(args, *, input=None, timeout=600):
        # Capture output: never dump Compose environments or connection strings to CI logs.
        args = list(args)
        executable = shutil.which(args[0])
        if not executable and args[0] == "sh" and os.name == "nt":
            candidate = (
                Path(os.environ.get("ProgramFiles", "C:/Program Files"))
                / "Git/bin/sh.exe"
            )
            if candidate.is_file():
                executable = str(candidate)
        if executable:
            args[0] = executable
        try:
            result = subprocess.run(
                args,
                input=input,
                capture_output=True,
                cwd=ROOT,
                env=env,
                timeout=timeout,
            )
        except subprocess.TimeoutExpired:
            raise RuntimeError(
                f"Command {args[0]} timed out after {timeout} seconds"
            ) from None
        if result.returncode:
            error = redact(
                (
                    result.stdout.decode(errors="replace")
                    + "\n"
                    + result.stderr.decode(errors="replace")
                )
            )[-12000:]
            raise RuntimeError(f"Command {args[0]} failed: {error}")
        return result.stdout

    def compose(*args, input=None):
        return run(base + list(args), input=input)

    def sql(query, database="phase7b_demo"):
        return (
            compose(
                "exec",
                "-T",
                "db",
                "psql",
                "-U",
                "phase7b_owner",
                "-d",
                database,
                "-At",
                "-v",
                "ON_ERROR_STOP=1",
                "-c",
                query,
            )
            .decode()
            .strip()
        )

    def request(path, expected=200, data=None, headers=None, return_headers=False):
        req = probe_request(port, path, data=data, headers=headers)
        # Trust only the internal test CA and verify localhost's certificate/hostname.
        try:
            with urllib.request.urlopen(
                req, context=tls_context, timeout=15
            ) as response:
                assert response.status == expected
                body = response.read()
                return (body, response.headers) if return_headers else body
        except urllib.error.HTTPError as error:
            assert error.code == expected, (path, error.code, expected)
            return error.read()

    try:
        configuration = json.loads(
            compose("--profile", "tools", "config", "--format", "json")
        )
        validate_compose_config(configuration)
        print(
            "PASS: isolated Compose configuration and runtime mount/security contract",
            flush=True,
        )
        if options.config_only:
            return
        run(["docker", "info", "--format", "{{.ServerVersion}}"], timeout=30)
        existing = run(
            [
                "docker",
                "ps",
                "-aq",
                "--filter",
                f"label=com.docker.compose.project={project}",
            ]
        )
        if existing.strip():
            raise RuntimeError("Refusing to reuse an existing project")
        for resource in ("volume", "network"):
            existing = run(
                [
                    "docker",
                    resource,
                    "ls",
                    "-q",
                    "--filter",
                    f"label=com.docker.compose.project={project}",
                ]
            )
            if existing.strip():
                raise RuntimeError("Refusing to reuse existing project resources")
        owned = True
        compose("build", "--pull")
        print("PASS: production backend/frontend image builds")
        compose(
            "run",
            "--rm",
            "--no-deps",
            "proxy",
            "caddy",
            "validate",
            "--config",
            "/etc/caddy/Caddyfile",
            "--adapter",
            "caddyfile",
        )
        print("PASS: Caddy configuration provision check")
        compose("up", "-d", "--wait", "--wait-timeout", "120", "db")
        compose("run", "--rm", "migrate")
        compose(
            "run",
            "--rm",
            "-e",
            "DEMO_ALLOW_SEED=1",
            "migrate",
            "python",
            "-m",
            "scripts.seed_demo",
        )
        assert sql("SELECT version_num FROM alembic_version") == "0003_api_tokens"
        assert sql("SELECT count(*) FROM sales_history") == "364"
        assert sql("SELECT count(*) FROM product_forecasts") == "28"
        print("PASS: PostgreSQL initialization, migration and synthetic seed")
        compose(
            "up",
            "-d",
            "--wait",
            "--wait-timeout",
            "180",
            "backend",
            "frontend",
            "proxy",
        )
        for service, memory in (
            ("db", 384),
            ("backend", 512),
            ("frontend", 64),
            ("proxy", 128),
        ):
            container = compose("ps", "-q", service).decode().strip()
            state = json.loads(run(["docker", "inspect", container]))[0]
            assert state["State"]["Health"]["Status"] == "healthy"
            config = state["HostConfig"]
            assert config["Memory"] == memory * 1024 * 1024
            assert config["NanoCpus"] > 0 and config["PidsLimit"] > 0
            assert config["RestartPolicy"]["Name"] == "unless-stopped"
            if service != "proxy":
                assert not config["PortBindings"]
        certificate = compose(
            "exec", "-T", "proxy", "cat", "/data/caddy/pki/authorities/local/root.crt"
        ).decode()
        tls_context = ssl.create_default_context(cadata=certificate)
        assert "<app-root" in request("/").decode()
        request("/forecasts")  # SPA fallback
        request("/api/v1/health")
        request("/api/v1/ready")
        assert json.loads(request("/api/v1/demo/config"))["enabled"]
        products = json.loads(request("/api/v1/products"))
        assert products["total_records"] == 2
        run_id = json.loads(request("/api/v1/forecasts/latest"))["id"]
        request(f"/api/v1/forecasts/{run_id}/evaluation")
        for path in (
            "/api/v1/ingestion/sales",
            "/api/v1/forecasts",
            "/api/v1/forecasts/backtest",
            "/api/v1/assistant/chat",
            "/api/v1/demo/assistant",
        ):
            request(path, 401, data=b"{}", headers={"Content-Type": "application/json"})
        request("/api/v1/not-reviewed", 401)
        for role, email in (("admin", admin_email), ("viewer", viewer_email)):
            compose(
                "run",
                "--rm",
                "migrate",
                "python",
                "-m",
                "scripts.manage_users",
                "create",
                "--email",
                email,
                "--role",
                role,
                "--password-stdin",
                input=(test_password + "\n").encode(),
            )
        payload, login_headers = request(
            "/api/v1/auth/login",
            data=json.dumps({"email": admin_email, "password": test_password}).encode(),
            headers={
                "Content-Type": "application/json",
                "Origin": f"https://localhost:{port}",
                "X-Requested-With": "AIProductDemandAnalyzer",
            },
            return_headers=True,
        )
        from http.cookies import SimpleCookie

        cookies = SimpleCookie()
        cookies.load(login_headers["Set-Cookie"])
        cookie = "; ".join(f"{key}={value.value}" for key, value in cookies.items())
        request("/api/v1/assistant/ready", 503, headers={"Cookie": cookie})
        print("PASS: internal TLS, static hosting, proxy routes, auth and disabled AI")
        for role, email in (("admin", admin_email), ("viewer", viewer_email)):
            api_token = (
                compose(
                    "run",
                    "--rm",
                    "migrate",
                    "sh",
                    "-c",
                    'python -m scripts.manage_api_tokens issue --email "$1" '
                    "--output /tmp/api-token >/dev/null && cat /tmp/api-token",
                    "sh",
                    email,
                )
                .decode()
                .strip()
            )
            api_headers = {"Authorization": "Bearer " + api_token}
            request(
                "/api/v1/ingestion/config",
                200 if role == "admin" else 403,
                headers=api_headers,
            )
            request("/api/v1/auth/me", 403, headers=api_headers)
            compose(
                "run",
                "--rm",
                "migrate",
                "python",
                "-m",
                "scripts.manage_api_tokens",
                "revoke",
                "--email",
                email,
            )
            request("/api/v1/ingestion/config", 401, headers=api_headers)
        request("/docs", 404)
        request("/openapi.json", 404)
        assert (
            sql(
                "SELECT has_table_privilege('demand_demo_reader','auth_api_tokens','SELECT')"
            )
            == "f"
        )
        assert (
            sql("SELECT has_table_privilege('demand_app','auth_api_tokens','INSERT')")
            == "f"
        )
        assert (
            sql("SELECT has_table_privilege('demand_app','auth_api_tokens','UPDATE')")
            == "f"
        )
        print(
            "PASS: owner-issued API tokens, role enforcement, revocation and private Swagger"
        )
        # Prove the demo reader cannot mutate data and the runtime cannot create schema.
        for role in ("demand_demo_reader", "demand_app"):
            assert (
                sql(
                    f"SELECT rolsuper OR rolcreatedb OR rolcreaterole FROM pg_roles "
                    f"WHERE rolname='{role}'"
                )
                == "f"
            )
        assert (
            sql(
                "SELECT has_table_privilege('demand_demo_reader','sales_history','INSERT')"
            )
            == "f"
        )
        assert sql("SELECT has_schema_privilege('demand_app','public','CREATE')") == "f"
        assert (
            sql(
                "SELECT has_table_privilege('demand_demo_reader','auth_users','SELECT')"
            )
            == "f"
        )
        assert (
            sql(
                "SELECT has_table_privilege('demand_demo_reader','auth_sessions','SELECT')"
            )
            == "f"
        )
        assert (
            sql("SELECT has_table_privilege('demand_app','auth_users','INSERT')") == "f"
        )
        assert (
            sql(
                "SELECT has_column_privilege('demand_app','auth_users','role','UPDATE')"
            )
            == "f"
        )
        # Exercise the real backup/restore scripts, targeting ONLY this random project.
        env.update(
            COMPOSE_ENV_FILE=str(env_file),
            COMPOSE_EXTRA_FILE=str(overlay),
            BACKUP_DIRECTORY=str(work / "backups"),
        )
        run(["sh", "deploy/backup.sh"])
        dumps = list((work / "backups").glob("*.dump"))
        assert len(dumps) == 1
        run(["sh", "deploy/restore.sh", str(dumps[0]), "phase7b_restore_demo"])
        for table in (
            "stores",
            "products",
            "sales_history",
            "forecast_runs",
            "product_forecasts",
        ):
            assert sql(f"SELECT count(*) FROM {table}") == sql(
                f"SELECT count(*) FROM {table}", "phase7b_restore_demo"
            )
        sql(
            "GRANT SELECT ON stores, products, sales_history, inventory, forecast_runs, "
            "forecast_run_logs, product_forecasts, stock_recommendations TO demand_demo_reader",
            "phase7b_restore_demo",
        )
        sql(
            "COMMENT ON DATABASE phase7b_restore_demo IS 'AIProductDemandAnalyzer synthetic-v1'",
            "phase7b_restore_demo",
        )
        sql(
            "REVOKE ALL ON auth_users, auth_sessions, auth_api_tokens FROM demand_demo_reader; "
            "GRANT SELECT ON auth_api_tokens TO demand_app; "
            "REVOKE ALL ON auth_users FROM demand_app; "
            "GRANT SELECT ON auth_users TO demand_app; "
            "GRANT UPDATE(password_hash) ON auth_users TO demand_app",
            "phase7b_restore_demo",
        )
        restored = values["DEMO_DATABASE_URL"].replace(
            "/phase7b_demo", "/phase7b_restore_demo"
        )
        compose(
            "run",
            "--rm",
            "-e",
            f"DEMO_DATABASE_URL={restored}",
            "backend",
            "python",
            "-c",
            "from app.db.session import verify_demo_database, get_demo_engine; "
            "from sqlalchemy import text; verify_demo_database(); "
            "c=get_demo_engine().connect(); "
            "assert c.scalar(text('SELECT count(*) FROM sales_history')) == 364; c.close()",
        )
        assert sql("SELECT count(*) FROM sales_history") == "364"
        print(
            "PASS: backup/restore counts, restored app connectivity, source unchanged"
        )
        compose("restart", "db", "backend")
        compose(
            "up",
            "-d",
            "--wait",
            "--wait-timeout",
            "180",
            "backend",
            "frontend",
            "proxy",
        )
        request("/api/v1/ready")
        assert sql("SELECT count(*) FROM sales_history") == "364"
        compose("up", "-d", "--force-recreate", "--wait", "--wait-timeout", "180", "db")
        compose(
            "up",
            "-d",
            "--wait",
            "--wait-timeout",
            "180",
            "backend",
            "frontend",
            "proxy",
        )
        request("/api/v1/ready")
        assert sql("SELECT count(*) FROM sales_history") == "364"
        print("PASS: restart, container recreation and persistent database volume")
        if options.browser_tests:
            env.update(
                E2E_EXTERNAL_SERVERS="1",
                E2E_PUBLIC_DEMO="1",
                E2E_BASE_URL=f"https://localhost:{port}",
                E2E_AUTH="1",
                E2E_ADMIN_EMAIL=admin_email,
                E2E_VIEWER_EMAIL=viewer_email,
                E2E_AUTH_PASSWORD=test_password,
                E2E_CAPTURE_ARTIFACTS="0",
            )
            if options.browser_container:
                browser_args = [
                    "docker",
                    "run",
                    "--rm",
                    "--name",
                    project + "-browser",
                    "--label",
                    "com.docker.compose.project=" + project,
                    "--network",
                    project + "_private",
                    "--user",
                    "pwuser",
                    "--read-only",
                    "--tmpfs",
                    "/tmp:size=1g,mode=1777",
                    "--memory",
                    "1536m",
                    "--cpus",
                    "2",
                    "--pids-limit",
                    "256",
                    "--shm-size",
                    "256m",
                    "--cap-drop",
                    "ALL",
                    "--security-opt",
                    "no-new-privileges:true",
                    "--mount",
                    f"type=bind,src={ROOT / 'ui'},dst=/source,readonly",
                    "--mount",
                    f"type=bind,src={ROOT / 'deploy/browser-validation.cjs'},dst=/runner.cjs,readonly",
                    "--env",
                    "NPM_CONFIG_CACHE=/tmp/npm-cache",
                ]
                for key in (
                    "E2E_EXTERNAL_SERVERS",
                    "E2E_PUBLIC_DEMO",
                    "E2E_BASE_URL",
                    "E2E_AUTH",
                    "E2E_ADMIN_EMAIL",
                    "E2E_VIEWER_EMAIL",
                    "E2E_AUTH_PASSWORD",
                    "E2E_CAPTURE_ARTIFACTS",
                ):
                    browser_args.extend(["--env", key])
                browser_args.extend(
                    [
                        "mcr.microsoft.com/playwright:v1.64.1-noble",
                        "sh",
                        "-c",
                        "mkdir /tmp/tests && cd /tmp/tests && "
                        "cp /source/package.json /source/package-lock.json /source/playwright.config.ts . && "
                        "cp -R /source/e2e . && npm ci --ignore-scripts --no-audit --no-fund && node /runner.cjs",
                    ]
                )
                print(redact(run(browser_args).decode(errors="replace")), flush=True)
                print(
                    "PASS: isolated Linux production public-demo and JWT browser checks"
                )
            else:
                for suite in ("public-demo.spec.ts", "authentication.spec.ts"):
                    print(
                        redact(
                            run(
                                ["npm", "--prefix", "ui", "run", "e2e", "--", suite]
                            ).decode(errors="replace")
                        ),
                        flush=True,
                    )
                print("PASS: production public-demo and JWT browser checks")
        # No destructive commands until all ownership checks below succeed.
        print(
            "Docker integration validation completed; disposable stack will be removed"
        )
    except Exception:
        if owned:
            try:
                print(
                    redact(
                        compose("logs", "--no-color", "--tail", "80").decode(
                            errors="replace"
                        )
                    ),
                    flush=True,
                )
            except Exception:
                print(
                    "Container diagnostics unavailable; original validation failure follows.",
                    flush=True,
                )
        raise
    finally:
        try:
            if owned:
                assert project.startswith("phase7b-") and len(project) == 20
                if options.browser_container:
                    # This exact random name/label was reserved by the collision checks above.
                    remaining = (
                        run(
                            [
                                "docker",
                                "ps",
                                "-aq",
                                "--filter",
                                "name=^/" + project + "-browser$",
                                "--filter",
                                "label=com.docker.compose.project=" + project,
                            ]
                        )
                        .decode()
                        .strip()
                    )
                    if remaining:
                        run(["docker", "rm", "-f", remaining])
                compose("down", "--volumes", "--remove-orphans")
        finally:
            env_file.unlink(missing_ok=True)


if __name__ == "__main__":
    main()
