"""Send only an immutable manifest through pinned, restricted SSH; never copy secrets."""

import ipaddress
import json
import os
import re
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from infra import guards  # noqa: E402
from infrastructure import automation as shared  # noqa: E402


def validate_transport(env):
    """Reject unpinned hosts, non-Ed25519 identities and non-public targets before any SSH use."""
    ip = ipaddress.IPv4Address(env["DEPLOY_HOST"])
    if not ip.is_global or env.get("SCHEMA_COMPATIBLE") != "true":
        raise ValueError("Public target and explicit schema review required")
    key = env["DEPLOY_SSH_PRIVATE_KEY"].strip()
    if not key.startswith("-----BEGIN OPENSSH PRIVATE KEY-----"):
        raise ValueError("OpenSSH private key required")
    pinned = [
        line.split()
        for line in env["DEPLOY_SSH_KNOWN_HOSTS"].splitlines()
        if line.strip() and not line.startswith("#")
    ]
    if not pinned or any(
        len(fields) < 3
        or fields[0] != str(ip)
        or fields[1] != "ssh-ed25519"
        or fields[0].startswith(("@", "|"))
        for fields in pinned
    ):
        raise ValueError("Known hosts must pin only the exact Ed25519 deployment host")
    return ip


def main():
    shared.protected_environment()
    shared.required("DEPLOY_HOST", "DEPLOY_SSH_PRIVATE_KEY", "DEPLOY_SSH_KNOWN_HOSTS")
    ip = validate_transport(os.environ)
    shared.WORKFLOWS[:] = guards.REQUIRED_CI
    shared.ci(os.environ["GITHUB_SHA"])
    repositories = {
        "BACKEND_IMAGE": "ghcr.io/nandakumar-selvaraj/aiproductdemandanalyzer/backend",
        "FRONTEND_IMAGE": "ghcr.io/nandakumar-selvaraj/aiproductdemandanalyzer/frontend",
        "POSTGRES_IMAGE": "ghcr.io/nandakumar-selvaraj/aiproductdemandanalyzer/postgres",
        "NGINX_IMAGE": "docker.io/nginx/nginx-unprivileged",
    }
    manifest = {key: os.environ[key] for key in repositories}
    for key, repo in repositories.items():
        if not re.fullmatch(re.escape(repo) + r"@sha256:[0-9a-f]{64}", manifest[key]):
            raise ValueError("Unapproved digest reference")
    manifest["sha"] = os.environ["GITHUB_SHA"]
    request = {
        "action": "deploy",
        "release": manifest,
        "schema_backward_compatible": True,
    }
    with tempfile.TemporaryDirectory() as temporary:
        key, hosts = Path(temporary) / "key", Path(temporary) / "hosts"
        key.write_text(os.environ["DEPLOY_SSH_PRIVATE_KEY"] + "\n")
        hosts.write_text(os.environ["DEPLOY_SSH_KNOWN_HOSTS"] + "\n")
        key.chmod(0o600)
        hosts.chmod(0o600)
        shared.run(
            [
                "ssh",
                "-F",
                "/dev/null",
                "-i",
                str(key),
                "-o",
                "IdentitiesOnly=yes",
                "-o",
                "BatchMode=yes",
                "-o",
                "ForwardAgent=no",
                "-o",
                "StrictHostKeyChecking=yes",
                "-o",
                "GlobalKnownHostsFile=/dev/null",
                "-o",
                "UserKnownHostsFile=" + str(hosts),
                "-o",
                "ConnectTimeout=15",
                "deployer@" + str(ip),
                "sudo",
                "-n",
                "/usr/local/sbin/demand-release",
            ],
            input=json.dumps(request).encode(),
        )
    print("Approved single-application release completed")


if __name__ == "__main__":
    try:
        main()
    except Exception:
        print(
            "Deployment failed or prerequisite missing; secrets and remote diagnostics withheld."
        )
        raise SystemExit(1) from None
