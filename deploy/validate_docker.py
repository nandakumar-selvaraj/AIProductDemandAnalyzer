"""Disposable production-stack verification. Never reads .env.production or local DB URLs.

Run: python deploy/validate_docker.py [--config-only]
Requires Docker Compose v2.24.4+ (!override), Docker Engine and Linux containers.
"""

import argparse
import json
import os
from pathlib import Path
import secrets
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


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config-only", action="store_true")
    parser.add_argument("--browser-tests", action="store_true")
    options = parser.parse_args()
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

    def run(args, *, input=None):
        # Capture output: never dump Compose environments or connection strings to CI logs.
        result = subprocess.run(
            args, input=input, capture_output=True, cwd=ROOT, env=env
        )
        if result.returncode:
            error = result.stderr.decode(errors="replace")[-6000:]
            for secret in (
                password,
                reader_password,
                owner_password,
                token,
                test_password,
            ):
                error = error.replace(secret, "[REDACTED]")
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
        req = urllib.request.Request(
            f"https://127.0.0.1:{port}{path}",
            data=data,
            headers={"Host": "localhost", **(headers or {})},
        )
        # Internal CA only for this loopback-bound disposable stack; never production.
        try:
            with urllib.request.urlopen(
                req, context=ssl._create_unverified_context(), timeout=15
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
        run(["docker", "info", "--format", "{{.ServerVersion}}"])
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
        assert sql("SELECT version_num FROM alembic_version") == "0002_authentication"
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
            "REVOKE ALL ON auth_users, auth_sessions FROM demand_demo_reader; "
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
            )
            run(["npm", "--prefix", "ui", "run", "e2e", "--", "public-demo.spec.ts"])
            print("PASS: production public-demo Playwright browser checks")
            env.update(
                E2E_AUTH="1",
                E2E_ADMIN_EMAIL=admin_email,
                E2E_VIEWER_EMAIL=viewer_email,
                E2E_AUTH_PASSWORD=test_password,
            )
            run(["npm", "--prefix", "ui", "run", "e2e", "--", "authentication.spec.ts"])
            print("PASS: production JWT authentication browser checks")
        # No destructive commands until all ownership checks below succeed.
        print(
            "Docker integration validation completed; disposable stack will be removed"
        )
    finally:
        try:
            if owned:
                assert project.startswith("phase7b-") and len(project) == 20
                compose("down", "--volumes", "--remove-orphans")
        finally:
            env_file.unlink(missing_ok=True)


if __name__ == "__main__":
    main()
