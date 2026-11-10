"""Dedicated application CI gate, independent of provisioning and remote state."""

import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from infra import guards  # noqa: E402
from infrastructure import automation as shared  # noqa: E402


def main():
    operation = "publish" if os.environ.get("GITHUB_EVENT_NAME") == "push" else "deploy"
    guards.require_workflow(os.environ, operation)
    shared.WORKFLOWS[:] = guards.REQUIRED_CI
    shared.ci(os.environ["GITHUB_SHA"], wait=operation == "publish")


if __name__ == "__main__":
    main()
