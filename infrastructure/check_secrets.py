"""Scan tracked/proposed source only; never read ignored local credentials or state."""

import json
import shutil
import subprocess
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def main():
    paths = (
        subprocess.run(
            ["git", "ls-files", "--cached", "--others", "--exclude-standard", "-z"],
            cwd=ROOT,
            capture_output=True,
            check=True,
        )
        .stdout.decode()
        .split("\0")
    )
    validation = ROOT / "validation"
    validation.mkdir(exist_ok=True)
    with tempfile.TemporaryDirectory(
        prefix="phase8a-secret-check-", dir=validation
    ) as temporary:
        target = Path(temporary).resolve()
        assert target.is_relative_to(validation.resolve())
        for relative in set(paths) - {""}:
            source = (ROOT / relative).resolve()
            if source.is_file() and source.is_relative_to(ROOT):
                destination = target / relative
                destination.parent.mkdir(parents=True, exist_ok=True)
                shutil.copyfile(source, destination)
        result = subprocess.run(
            [
                "docker",
                "run",
                "--rm",
                "--mount",
                f"type=bind,src={target},dst=/src,readonly",
                "aquasec/trivy:0.76.1",
                "fs",
                "--scanners",
                "secret",
                "--quiet",
                "--format",
                "json",
                "/src",
            ],
            capture_output=True,
            timeout=300,
        )
        if result.returncode:
            raise RuntimeError("Secret scanner could not complete")
        report = json.loads(result.stdout)
        findings = [
            {"file": item["Target"], "rule": secret["RuleID"]}
            for item in report.get("Results", [])
            for secret in item.get("Secrets", [])
        ]
        if findings:
            print(
                json.dumps(findings)
            )  # Locations/rule IDs only; never print a credential match.
            raise RuntimeError("Potential committed secret detected; review privately")
    print(
        "PASS: no Trivy secret findings in tracked/proposed source; ignored local env/state/keys were not scanned"
    )


if __name__ == "__main__":
    main()
