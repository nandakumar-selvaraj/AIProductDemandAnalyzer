"""Disposable local validation only. Never reads production configuration or uses public ports."""

import json
import os
import shutil
import subprocess
import tempfile
import uuid
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[1]


def run(args, *, env=None, input=None):
    result = subprocess.run(
        args, env=env, input=input, capture_output=True, timeout=240
    )
    if result.returncode:
        raise RuntimeError(
            "Disposable validation command failed: " + result.stderr.decode()[-1500:]
        )
    return result.stdout


def main():
    project = "demand-check-" + uuid.uuid4().hex[:12]
    validation = ROOT / "validation"
    validation.mkdir(exist_ok=True)
    with tempfile.TemporaryDirectory(prefix=project, dir=validation) as temporary:
        target = Path(temporary).resolve()
        assert target.is_relative_to(validation.resolve())
        value = yaml.safe_load((ROOT / "compose.prod.yml").read_text())
        value["name"] = project
        value["services"]["nginx"].pop("ports")
        value["services"]["nginx"]["volumes"] = [
            "./nginx.conf:/etc/nginx/conf.d/default.conf:ro"
        ]
        value["volumes"]["database"] = {"name": project + "-database"}
        (target / "compose.yml").write_text(yaml.safe_dump(value))
        (target / "Dockerfile.tests").write_text(
            f"FROM {project}-test-base\nUSER root\nRUN pip install --no-cache-dir pytest==8.4.2\n"
        )
        shutil.copyfile(ROOT / "deploy/single/init-db.sh", target / "init-db.sh")
        shutil.copyfile(
            ROOT / "deploy/single/nginx.stage-a.conf", target / "nginx.conf"
        )
        env = {
            **os.environ,
            "BACKEND_IMAGE": "demand-phase5-backend-check:latest",
            "FRONTEND_IMAGE": "demand-phase5-frontend-check:latest",
            "POSTGRES_IMAGE": "demand-phase5-postgres-check:latest",
            "NGINX_IMAGE": json.loads((ROOT / "deploy/single/images.json").read_text())[
                "nginx"
            ],
            "POSTGRES_PASSWORD": "synthetic-owner-only",
            "APP_DB_PASSWORD": "synthetic-app-only",
            "DATABASE_URL": "postgresql+psycopg://demand_app:synthetic-app-only@db:5432/demand",
            "MIGRATION_DATABASE_URL": "postgresql+psycopg://demand_owner:synthetic-owner-only@db:5432/demand",
            "JWT_SIGNING_SECRET": "local-validation-only-" + "x" * 64,
            "AUTH_ALLOWED_ORIGINS": '["https://validation.invalid"]',
            "TRUSTED_HOSTS": '["validation.invalid","localhost","127.0.0.1"]',
        }
        dc = [
            "docker",
            "compose",
            "--project-name",
            project,
            "-f",
            str(target / "compose.yml"),
        ]

        def compose(*args, input=None):
            return run([*dc, *args], env=env, input=input)

        try:
            compose("up", "-d", "--wait", "--wait-timeout", "180")
            compose(
                "exec",
                "-T",
                "backend",
                "python",
                "-c",
                "import urllib.request; "
                "assert urllib.request.urlopen('http://localhost:8000/api/v1/ready').status==200",
            )
            compose(
                "exec",
                "-T",
                "nginx",
                "wget",
                "-q",
                "-O",
                "/dev/null",
                "http://127.0.0.1:8080/healthz",
            )
            compose(
                "exec",
                "-T",
                "backend",
                "python",
                "-c",
                "import http.client; c=http.client.HTTPConnection('nginx',8080,timeout=5); "
                "c.request('POST','/api/v1/auth/login',body='{}'); assert c.getresponse().status==503",
            )
            # Owner creates only synthetic business data; no administrator command is executed.
            compose(
                "exec",
                "-T",
                "db",
                "psql",
                "-U",
                "demand_owner",
                "-d",
                "demand",
                "-v",
                "ON_ERROR_STOP=1",
                "-c",
                "INSERT INTO stores(store_code,name) VALUES ('validation','Synthetic')",
            )
            compose("restart", "db")
            compose("up", "-d", "--wait", "--wait-timeout", "120", "db")
            count = compose(
                "exec",
                "-T",
                "db",
                "psql",
                "-U",
                "demand_owner",
                "-d",
                "demand",
                "-Atc",
                "SELECT count(*) FROM stores WHERE store_code='validation'",
            )
            assert count.strip() == b"1"
            permission = compose(
                "exec",
                "-T",
                "db",
                "psql",
                "-U",
                "demand_owner",
                "-d",
                "demand",
                "-Atc",
                "SELECT has_table_privilege('demand_app','auth_users','INSERT')",
            )
            assert permission.strip() == b"f"
            dump = compose(
                "exec",
                "-T",
                "db",
                "pg_dump",
                "-U",
                "demand_owner",
                "-d",
                "demand",
                "-Fc",
            )
            compose(
                "exec",
                "-T",
                "db",
                "createdb",
                "-U",
                "demand_owner",
                "restore_validation",
            )
            compose(
                "exec",
                "-T",
                "db",
                "pg_restore",
                "-U",
                "demand_owner",
                "-d",
                "restore_validation",
                "--no-owner",
                "--no-acl",
                "--exit-on-error",
                input=dump,
            )
            restored = compose(
                "exec",
                "-T",
                "db",
                "psql",
                "-U",
                "demand_owner",
                "-d",
                "restore_validation",
                "-Atc",
                "SELECT count(*) FROM stores WHERE store_code='validation'",
            )
            assert restored.strip() == b"1"
            compose(
                "exec",
                "-T",
                "db",
                "createdb",
                "-U",
                "demand_owner",
                "demand_integration_test",
            )
            test_url = "postgresql+psycopg://demand_owner:synthetic-owner-only@db:5432/demand_integration_test"
            run(
                [
                    "docker",
                    "build",
                    "--target",
                    "build",
                    "-t",
                    project + "-test-base",
                    str(ROOT / "backend"),
                ]
            )
            run(
                [
                    "docker",
                    "build",
                    "-t",
                    project + "-tests",
                    "-f",
                    str(target / "Dockerfile.tests"),
                    str(target),
                ]
            )
            integration = run(
                [
                    "docker",
                    "run",
                    "--rm",
                    "--user",
                    "0",
                    "--network",
                    project + "_database",
                    "--mount",
                    "type=bind,src="
                    + str(ROOT / "backend/tests")
                    + ",dst=/app/tests,readonly",
                    "-e",
                    "DATABASE_URL=" + test_url,
                    "-e",
                    "TEST_DATABASE_URL=" + test_url,
                    "-e",
                    "AUTH_ENABLED=false",
                    "-e",
                    "ENVIRONMENT=test",
                    project + "-tests",
                    "sh",
                    "-c",
                    "alembic upgrade head && python -m pytest tests/integration -q -p no:cacheprovider",
                ]
            )
            assert b"1 passed" in integration
            print(
                json.dumps(
                    {
                        "status": "PASS",
                        "checks": [
                            "migrations",
                            "runtime readiness",
                            "Stage A blocks login",
                            "DB restart persistence",
                            "runtime cannot create admin",
                            "synthetic dump/isolated-database restore",
                            "PostgreSQL ingestion integration",
                        ],
                    }
                )
            )
        finally:
            # Removal is limited to this randomly named disposable validation project/volume.
            assert project.startswith("demand-check-") and len(project) == 25
            compose("down", "--volumes", "--remove-orphans")
            subprocess.run(
                ["docker", "image", "rm", project + "-tests", project + "-test-base"],
                capture_output=True,
                timeout=30,
            )


if __name__ == "__main__":
    main()
