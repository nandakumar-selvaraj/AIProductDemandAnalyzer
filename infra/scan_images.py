"""Local image vulnerability gate. No ignore rules, severity filtering only, no publication."""

import argparse
import json
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("images", nargs="+")
    args = parser.parse_args()
    output = ROOT / "validation" / "phase5-remediation"
    cache = output / "trivy-cache"
    cache.mkdir(parents=True, exist_ok=True)
    summary = []
    for number, reference in enumerate(args.images):
        inspected = subprocess.run(
            ["docker", "image", "inspect", reference],
            capture_output=True,
            check=True,
            timeout=30,
        )
        metadata = json.loads(inspected.stdout)[0]
        result = subprocess.run(
            [
                "docker",
                "run",
                "--rm",
                "--mount",
                "type=bind,src=/var/run/docker.sock,dst=/var/run/docker.sock,readonly",
                "--mount",
                f"type=bind,src={cache},dst=/root/.cache/trivy",
                "aquasec/trivy:0.76.1",
                "image",
                "--quiet",
                "--no-progress",
                "--scanners",
                "vuln",
                "--exit-code",
                "1",
                "--severity",
                "HIGH,CRITICAL",
                "--format",
                "json",
                metadata["Id"],
            ],
            capture_output=True,
            timeout=300,
        )
        if result.returncode not in {0, 1}:
            raise RuntimeError("Scanner could not complete")
        report = json.loads(result.stdout)
        findings = [
            {
                "target": section["Target"],
                "package": finding["PkgName"],
                "installed": finding["InstalledVersion"],
                "fixed": finding.get("FixedVersion", ""),
                "severity": finding["Severity"],
                "id": finding["VulnerabilityID"],
            }
            for section in report.get("Results", [])
            for finding in section.get("Vulnerabilities", [])
        ]
        (output / f"scan-{number}.json").write_text(json.dumps(report, indent=2))
        row = {
            "image": reference,
            "id": metadata["Id"],
            "digests": metadata.get("RepoDigests", []),
            "status": "PASS" if result.returncode == 0 and not findings else "FAIL",
            "findings": findings,
        }
        summary.append(row)
        print(
            f"{row['status']}: {reference}: {len(findings)} HIGH/CRITICAL findings",
            flush=True,
        )
    (output / "summary.json").write_text(json.dumps(summary, indent=2))
    raise SystemExit(0 if all(row["status"] == "PASS" for row in summary) else 1)


if __name__ == "__main__":
    main()
