"""Offline source contracts; never connect to Docker, PostgreSQL, GitHub or UpCloud."""

from pathlib import Path
import json
import re

import yaml

ROOT = Path(__file__).resolve().parents[1]
DOCUMENTS = [
    "ARCHITECTURE",
    "UPCLOUD_SETUP",
    "TERRAFORM",
    "SSH_SETUP",
    "GITHUB_ACTIONS",
    "GITHUB_SECRETS",
    "DOCKER_COMPOSE",
    "POSTGRESQL",
    "AUTHENTICATION",
    "ADMIN_USER_SETUP",
    "DOMAIN_HTTPS",
    "BACKUP_RESTORE",
    "ROLLBACK",
    "COST_ESTIMATE",
    "ACCEPTANCE",
    "TEARDOWN",
]


def main():
    compose = yaml.safe_load((ROOT / "compose.prod.yml").read_text())
    assert set(compose["services"]) == {"db", "migrate", "backend", "frontend", "nginx"}
    for name, service in compose["services"].items():
        assert (
            "image" in service and "@sha256:" not in service["image"]
        )  # Runtime digest substitution.
        if name != "nginx":
            assert "ports" not in service
    assert compose["networks"]["database"]["internal"] is True
    assert compose["volumes"]["database"]["external"] is True
    assert (
        compose["services"]["backend"]["depends_on"]["migrate"]["condition"]
        == "service_completed_successfully"
    )
    stage_a = (ROOT / "deploy/single/nginx.stage-a.conf").read_text()
    assert "proxy_pass" not in stage_a and "return 503" in stage_a
    for path in (ROOT / ".github/workflows").glob("single-*.yml"):
        value = yaml.safe_load(path.read_text())
        triggers = value.get("on", value.get(True))  # PyYAML uses YAML 1.1 booleans.
        if path.name not in {"single-validate.yml", "single-publish-images.yml"}:
            assert set(triggers) == {"workflow_dispatch"}
    for name in DOCUMENTS:
        assert (ROOT / "docs/deployment" / (name + ".md")).is_file(), name
    for document in [ROOT / "README.md", *(ROOT / "docs/deployment").glob("*.md")]:
        for link in re.findall(
            r"\[[^\]]+\]\(([^)]+\.md)(?:#[^)]*)?\)", document.read_text()
        ):
            if not link.startswith(("https://", "http://")):
                assert (document.parent / link).resolve().is_file(), (document, link)
    assert (
        "COPY scripts/seed_demo.py scripts/manage_users.py"
        in (ROOT / "backend/Dockerfile").read_text()
    )
    assert "dist/ui/browser" in (ROOT / "ui/Dockerfile").read_text()
    angular = json.loads((ROOT / "ui/angular.json").read_text())
    assert (
        angular["projects"]["ui"]["architect"]["build"]["configurations"]["production"][
            "optimization"
        ]["styles"]["inlineCritical"]
        is False
    )
    for path in (ROOT / "deploy/single").glob("*.sh"):
        assert b"\r\n" not in path.read_bytes(), str(path)
    print(
        "PASS: Compose isolation, migration gate, manual-only operations, script LF and documentation contracts"
    )


if __name__ == "__main__":
    main()
