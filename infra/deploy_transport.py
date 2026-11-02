"""Send only an immutable manifest through pinned, restricted SSH; never copy secrets."""

import ipaddress
import json
import os
import re
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from infrastructure import automation as shared  # noqa: E402


def main():
    shared.protected_environment()
    shared.required("DEPLOY_HOST", "DEPLOY_SSH_PRIVATE_KEY", "DEPLOY_SSH_KNOWN_HOSTS")
    ip = ipaddress.IPv4Address(os.environ["DEPLOY_HOST"])
    if not ip.is_global or os.environ.get("SCHEMA_COMPATIBLE") != "true":
        raise ValueError("Public target and explicit schema review required")
    shared.WORKFLOWS.append("single-validate.yml")
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
