"""Scan exact runtime image digests before emitting the non-secret release manifest."""

import json
import os
import re
from pathlib import Path

from automation import required, run


def main():
    required("EXPECTED_SHA", "IMAGE_PREFIX", "BACKEND_DIGEST", "FRONTEND_DIGEST")
    sha, prefix = os.environ["EXPECTED_SHA"], os.environ["IMAGE_PREFIX"]
    if (
        not re.fullmatch("[0-9a-f]{40}", sha)
        or prefix != "ghcr.io/" + os.environ["GITHUB_REPOSITORY"].lower()
    ):
        raise ValueError("Unexpected release identity")
    images = {"sha": sha}
    for service in ["backend", "frontend"]:
        digest = os.environ[service.upper() + "_DIGEST"]
        if not re.fullmatch("sha256:[0-9a-f]{64}", digest):
            raise ValueError("Expected a BuildKit immutable digest")
        images[service] = prefix + "/" + service + "@" + digest
    for service, major in [("postgres", "16"), ("caddy", "2")]:
        source = os.environ[service.upper() + "_RUNTIME_IMAGE"]
        if not re.fullmatch(
            r"docker.io/library/"
            + service
            + r"(?::"
            + major
            + r"-alpine|@sha256:[0-9a-f]{64})",
            source,
        ):
            raise ValueError("Approved upstream runtime image required")
        run(["docker", "pull", "--platform", "linux/amd64", source])
        info = json.loads(run(["docker", "image", "inspect", source]))[0]
        if service == "postgres" and "PG_MAJOR=16" not in info["Config"]["Env"]:
            raise ValueError(
                "Database major upgrade requires a separate migration procedure"
            )
        digest = info["RepoDigests"][0].split("@", 1)[1]
        images[service] = "docker.io/library/" + service + "@" + digest
    for service in ["backend", "frontend", "postgres", "caddy"]:
        run(
            [
                "docker",
                "run",
                "--rm",
                "--env",
                "TRIVY_USERNAME",
                "--env",
                "TRIVY_PASSWORD",
                "aquasec/trivy:0.76.1",
                "image",
                "--quiet",
                "--exit-code",
                "1",
                "--severity",
                "HIGH,CRITICAL",
                images[service],
            ]
        )
        print("Passed image vulnerability gate: " + service)
    Path("release-manifest.json").write_text(json.dumps(images, indent=2) + "\n")


if __name__ == "__main__":
    try:
        main()
    except Exception:
        print(
            "Image scan/publication gate failed. No verified release manifest was emitted."
        )
        raise SystemExit(1) from None
