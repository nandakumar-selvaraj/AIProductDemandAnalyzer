"""Render production overlays with synthetic placeholders; do not start services."""

import json
import os
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def main():
    env = dict(os.environ)
    for name in ["BACKEND_IMAGE", "FRONTEND_IMAGE"]:
        env[name] = (
            "ghcr.io/nandakumar-selvaraj/aiproductdemandanalyzer/"
            + name.split("_")[0].lower()
            + "@sha256:"
            + "1" * 64
        )
    env.update(
        POSTGRES_IMAGE="docker.io/library/postgres@sha256:" + "2" * 64,
        CADDY_IMAGE="docker.io/library/caddy@sha256:" + "3" * 64,
    )
    base = ["docker", "compose", "--env-file", str(ROOT / ".env.production.example")]
    result = subprocess.run(
        [
            *base,
            "-f",
            str(ROOT / "compose.production.yml"),
            "-f",
            str(ROOT / "deploy/ops/compose.app.yml"),
            "--profile",
            "tools",
            "config",
            "--format",
            "json",
        ],
        capture_output=True,
        env=env,
        check=True,
    )
    value = json.loads(result.stdout)
    for service in ["backend", "frontend", "migrate"]:
        assert "build" not in value["services"][service]
        assert "@sha256:" in value["services"][service]["image"]
    assert value["networks"]["private"]["internal"]
    assert set(value["services"]["db"]["networks"]) == {"private"}
    assert set(value["services"]["frontend"]["networks"]) == {"edge"}
    for name, service in value["services"].items():
        assert not service.get("ports"), name
        assert (
            service.get("mem_limit")
            and service.get("cpus")
            and service.get("pids_limit")
        )
    ingress = subprocess.run(
        [
            *base,
            "-f",
            str(ROOT / "deploy/ops/compose.ingress.yml"),
            "config",
            "--format",
            "json",
        ],
        capture_output=True,
        env=env,
        check=True,
    )
    value = json.loads(ingress.stdout)
    assert {str(port["published"]) for port in value["services"]["caddy"]["ports"]} == {
        "80",
        "443",
    }
    print(
        "PASS: immutable image overlay, separate DB/edge networks, no app/DB ports, shared ingress and resource limits"
    )


if __name__ == "__main__":
    main()
