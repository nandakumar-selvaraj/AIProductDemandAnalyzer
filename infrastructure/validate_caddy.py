"""Validate generated shared-ingress Caddy syntax without network/certificate issuance."""

import importlib.util
import subprocess
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def main():
    spec = importlib.util.spec_from_file_location(
        "release_config", ROOT / "deploy/ops/release.py"
    )
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    with tempfile.TemporaryDirectory(prefix="phase8a-caddy-") as temporary:
        module.CONFIG = Path(temporary)
        (module.CONFIG / "sites").mkdir()
        module.configure_hostname(
            {"domain": "demo.example.com", "email": "ops@example.com"}
        )
        result = subprocess.run(
            [
                "docker",
                "run",
                "--rm",
                "--network",
                "none",
                "--read-only",
                "--tmpfs",
                "/data",
                "--tmpfs",
                "/config",
                "--tmpfs",
                "/tmp",
                "--cap-drop",
                "ALL",
                "--cap-add",
                "NET_BIND_SERVICE",
                "--security-opt",
                "no-new-privileges:true",
                "--memory",
                "128m",
                "--pids-limit",
                "100",
                "--mount",
                f"type=bind,src={temporary},dst=/etc/caddy,readonly",
                "caddy:2-alpine",
                "caddy",
                "validate",
                "--config",
                "/etc/caddy/Caddyfile",
            ],
            capture_output=True,
        )
        if result.returncode:
            raise RuntimeError(result.stderr.decode(errors="replace"))
    print(
        "PASS: generated shared Caddy configuration (network disabled, no certificate requested)"
    )


if __name__ == "__main__":
    main()
