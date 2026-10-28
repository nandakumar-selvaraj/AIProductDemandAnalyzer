"""Validate against a fresh loopback PostgreSQL DB; never seed/reset existing data.

Run from backend: python -m scripts.validate_local [--postgres-only]
The browser path uses installed Edge by default; E2E_BROWSER_CHANNEL can override it.
"""

import argparse
import os
import secrets
import socket
import subprocess
import sys
import time
from pathlib import Path

import httpx
from sqlalchemy import create_engine, text
from sqlalchemy.engine import make_url

from app.core.config import Settings

parser = argparse.ArgumentParser(description=__doc__)
modes = parser.add_mutually_exclusive_group()
modes.add_argument("--postgres-only", action="store_true")
modes.add_argument("--demo-seed-only", action="store_true")
modes.add_argument("--auth-e2e", action="store_true")
options = parser.parse_args()
root = Path(__file__).resolve().parents[2]
work = root / "validation" / "phase7b-e2e"
work.mkdir(parents=True, exist_ok=True)
name = "phase7b_" + secrets.token_hex(6) + ("_demo" if options.demo_seed_only else "_e2e_test")
url = make_url(str(Settings().database_url)).set(database="postgres")
if url.get_backend_name() != "postgresql" or url.host not in {"localhost", "127.0.0.1", "::1"}:
    raise SystemExit("Local validation requires loopback PostgreSQL; remote URLs are refused")
engine = create_engine(url, isolation_level="AUTOCOMMIT")
created = False
processes = []
logs = []


def port():
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


def wait(address):
    for _ in range(90):
        try:
            if httpx.get(address, timeout=2).status_code == 200:
                return
        except httpx.HTTPError:
            pass
        time.sleep(1)
    raise RuntimeError("Isolated E2E server did not become ready")


try:
    with engine.connect() as c:
        c.execute(text(f'CREATE DATABASE "{name}"'))
    created = True
    test_url = url.set(database=name).render_as_string(hide_password=False)
    env = {
        **os.environ,
        "DATABASE_URL": test_url,
        "ENVIRONMENT": "development",
        "PUBLIC_DEMO_ENABLED": "false",
        "DEMO_AI_ENABLED": "false",
        "AI_ENABLED": "false",
        "AUTH_ENABLED": "false",
        "E2E_ALLOW_SEED": "1",
        "DEMO_ALLOW_SEED": "1",
        "TEST_DATABASE_URL": test_url,
        "E2E_AI_DISABLED": "1",
        "E2E_EXTERNAL_SERVERS": "1",
        "E2E_BROWSER_CHANNEL": os.environ.get("E2E_BROWSER_CHANNEL", "msedge"),
        "E2E_PYTHON": sys.executable,
        "E2E_CAPTURE_ARTIFACTS": "0",
    }
    setup = [["-m", "alembic", "upgrade", "head"]]
    if options.demo_seed_only:
        setup.append(["-m", "scripts.seed_demo"])
    elif options.postgres_only:
        setup.append(["-m", "pytest", "tests/integration", "-q"])
    else:
        setup.append(["-m", "scripts.seed_e2e"])
    for args in setup:
        r = subprocess.run([sys.executable, *args], capture_output=True, text=True, env=env)
        if r.returncode:
            raise RuntimeError("Disposable validation setup failed; credentials omitted")
        if options.postgres_only:
            print(r.stdout.strip())
    if options.demo_seed_only:
        demo_engine = create_engine(url.set(database=name))
        try:
            with demo_engine.connect() as connection:
                assert connection.scalar(text("SELECT count(*) FROM sales_history")) == 364
                assert connection.scalar(text("SELECT count(*) FROM product_forecasts")) == 28
                marker = connection.scalar(
                    text(
                        "SELECT shobj_description(oid, 'pg_database') FROM pg_database "
                        "WHERE datname=current_database()"
                    )
                )
                assert marker == "AIProductDemandAnalyzer synthetic-v1"
            duplicate = subprocess.run(
                [sys.executable, "-m", "scripts.seed_demo"], capture_output=True, env=env
            )
            assert duplicate.returncode != 0
            with demo_engine.connect() as connection:
                assert connection.scalar(text("SELECT count(*) FROM sales_history")) == 364
            print("PASS: synthetic demo seed, marker, and nonempty-database refusal")
        finally:
            demo_engine.dispose()
        sys.exit(0)
    if options.postgres_only:
        print("PASS: migrations and PostgreSQL integration in newly created database")
        sys.exit(0)
    api_port, ui_port = port(), port()
    env.update(
        E2E_API_URL=f"http://127.0.0.1:{api_port}/api/v1/",
        E2E_BASE_URL=f"http://127.0.0.1:{ui_port}",
    )
    if options.auth_e2e:
        env.update(
            AUTH_ENABLED="true",
            JWT_SIGNING_SECRET=secrets.token_hex(32),
            AUTH_ALLOWED_ORIGINS='["http://127.0.0.1:' + str(ui_port) + '"]',
            E2E_AUTH="1",
            E2E_AUTH_PASSWORD=secrets.token_urlsafe(24),
            E2E_ADMIN_EMAIL="admin-" + secrets.token_hex(4) + "@example.invalid",
            E2E_VIEWER_EMAIL="viewer-" + secrets.token_hex(4) + "@example.invalid",
        )
        for role, email_key in (("admin", "E2E_ADMIN_EMAIL"), ("viewer", "E2E_VIEWER_EMAIL")):
            provision = subprocess.run(
                [
                    sys.executable,
                    "-m",
                    "scripts.manage_users",
                    "create",
                    "--email",
                    env[email_key],
                    "--role",
                    role,
                    "--password-stdin",
                ],
                input=env["E2E_AUTH_PASSWORD"] + "\n",
                capture_output=True,
                text=True,
                env=env,
            )
            if provision.returncode:
                raise RuntimeError("Synthetic user provisioning failed; credentials omitted")
    proxy = work / "proxy.json"
    proxy.write_text('{"/api":{"target":"http://127.0.0.1:' + str(api_port) + '","secure":false}}')
    commands = [
        (
            [
                sys.executable,
                "-m",
                "uvicorn",
                "app.main:app",
                "--host",
                "127.0.0.1",
                "--port",
                str(api_port),
            ],
            root / "backend",
        ),
        (
            [
                "node",
                "node_modules/@angular/cli/bin/ng.js",
                "serve",
                "--host",
                "127.0.0.1",
                "--port",
                str(ui_port),
                "--proxy-config",
                str(proxy),
            ],
            root / "ui",
        ),
    ]
    if options.auth_e2e:
        commands[1][0].extend(["--configuration", "authentication"])
    for i, (args, cwd) in enumerate(commands):
        log = (work / f"server-{i}.log").open("w")
        logs.append(log)
        processes.append(
            subprocess.Popen(
                args,
                cwd=cwd,
                env=env,
                stdout=log,
                stderr=log,
                creationflags=subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0,
            )
        )
    wait(f"http://127.0.0.1:{api_port}/api/v1/ready")
    wait(f"http://127.0.0.1:{ui_port}")
    browser_args = ["node", "node_modules/@playwright/test/cli.js", "test"]
    if options.auth_e2e:
        browser_args.append("authentication.spec.ts")
    result = subprocess.run(browser_args, cwd=root / "ui", env=env)
    if result.returncode:
        raise RuntimeError("Isolated synthetic E2E suite failed")
    print("PASS: synthetic-only browser E2E; no development data used")
finally:
    for process in reversed(processes):
        process.terminate()
        try:
            process.wait(timeout=15)
        except subprocess.TimeoutExpired:
            process.kill()
            process.wait()
    for log in logs:
        log.close()
    if created:
        assert name.startswith("phase7b_") and name.endswith(("_e2e_test", "_demo"))
        with engine.connect() as c:
            c.execute(text(f'DROP DATABASE "{name}"'))
        print("Removed only newly created E2E database")
    engine.dispose()
