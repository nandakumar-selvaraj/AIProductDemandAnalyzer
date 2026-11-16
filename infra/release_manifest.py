"""Resolve only a successful same-commit publication; artifacts contain no credentials."""

import json
import os
import re
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from infra import guards  # noqa: E402
from infrastructure import automation as shared  # noqa: E402

REPOS = {
    name: "ghcr.io/nandakumar-selvaraj/aiproductdemandanalyzer/" + name
    for name in ("backend", "frontend", "postgres")
}
REPOS["nginx"] = "docker.io/nginx/nginx-unprivileged"


def validate(value, sha):
    if set(value) != {*REPOS, "sha"} or value["sha"] != sha:
        raise ValueError("Manifest must match the approved source revision")
    for name, repo in REPOS.items():
        if not re.fullmatch(re.escape(repo) + r"@sha256:[0-9a-f]{64}", value[name]):
            raise ValueError("Immutable approved image required")
    return value


def main():
    guards.require_workflow(os.environ, "deploy")
    run_id, sha = os.environ["PUBLISH_RUN_ID"], os.environ["GITHUB_SHA"]
    run = shared.verify_run(run_id, "single-publish-images.yml", sha)
    if run.get("event") != "push":
        raise ValueError("Publication must originate from master push CI")
    artifacts = shared.github(
        f"actions/runs/{run_id}/artifacts?name=single-release-manifest&per_page=100"
    )
    matches = [
        item
        for item in artifacts["artifacts"]
        if item["name"] == "single-release-manifest"
    ]
    if (
        artifacts["total_count"] != 1
        or len(matches) != 1
        or matches[0].get("expired") is not False
    ):
        raise ValueError("A unique, unexpired publication manifest is required")
    with tempfile.TemporaryDirectory() as folder:
        shared.run(
            [
                "gh",
                "run",
                "download",
                run_id,
                "--repo",
                os.environ["GITHUB_REPOSITORY"],
                "--name",
                "single-release-manifest",
                "--dir",
                folder,
            ]
        )
        value = validate(
            json.loads((Path(folder) / "release-manifest.json").read_text()), sha
        )
    with Path(os.environ["GITHUB_OUTPUT"]).open("a") as output:
        for name in REPOS:
            output.write(name + "=" + value[name] + "\n")
    Path(os.environ["GITHUB_STEP_SUMMARY"]).write_text(
        "Approved source and scanned immutable images:\n```json\n"
        + json.dumps(value, indent=2)
        + "\n```\n"
    )


if __name__ == "__main__":
    try:
        main()
    except Exception:
        print("Publication or release manifest verification failed.", file=sys.stderr)
        raise SystemExit(1) from None
