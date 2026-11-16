# Phase 5.17.1 production deployment security remediation

## Decision

The audited starting point was `master` at `a5d5302a4a7ed19e2eedf4e2f98c925e6f547c37`, with the local origin default ref pointing to `master`. The source is ready for review. Provisioning remains **NO-GO** until the complete isolated Ubuntu VM rehearsal, the relevant hosted CI checks, recovery tests and owner cost approval. One manual Singapore VPS, Docker Compose, GHCR, PostgreSQL 16, Nginx and encrypted Restic over SFTP remain the active design. Dedicated Terraform and its S3/KMS backend are inactive.

## Findings and changes

| Finding | Root cause | Remediation and evidence |
| --- | --- | --- |
| SSH lockout and unsafe reruns | A text flag was accepted as proof of access. Bootstrap wrote account keys, sudoers and live SSH policy during one invocation. | Preparation leaves existing SSH access intact and accepts an exact rerun of the same managed accounts and keys. A short-lived challenge binds the host, key, source, sudo session and prepared SSH configuration. The operator’s independent login must match a root-owned OpenSSH journal event. A separate local root console supplies recovery proof. Finalization validates the staged and effective policy and restores the previous fragment set on a recoverable reload failure. Network-isolated Ubuntu tests proved Stage A rerun, real journal-backed login and sudo, root-key preservation, and a real sshd reload. Full console and reboot testing is outstanding. |
| Firewall exposure | UFW reruns retained obsolete rules. Docker ingress rules were flushed before replacement. | A dedicated nftables IPv4 input and forward policy replaces only its own `inet` table in one checked transaction. It denies IPv6 and admits only approved-source SSH and exact web ingress. The firewall is loaded before Docker and its socket. An existing active legacy policy blocks fresh setup. Docker Compose publishes only the IPv4 web ports. Tests ran real first and repeat commits, rejected an invalid candidate, and replaced an obsolete CIDR in an isolated network namespace. Full Docker forwarding and reboot behavior still need the VM rehearsal. |
| Invalid backup could authorize deployment or deletion | Both sides of the source stream were not tied to a completed record, the restore marker could survive failure, and ordinary backup pruned before restore. | Restic operation tag and exact snapshot ID identify the completed upload. The row counts, aggregate sales and auth/schema evidence come from the same PostgreSQL snapshot as `pg_dump`. The release gate requires a fresh matching root-private receipt. A failed restore invalidates acceptance, and retention is an explicit review-only report. Real PostgreSQL and pinned loopback SFTP exercised the backup and exact restore data path. Production SFTP and recovery time remain owner acceptance gates. |
| Broken regression and validation gates | Tests referenced retired workflows and the old build-in-deploy job. Ruff found manifest formatting drift. The Bash glob was parsed as one script plus arguments. | Recovered all 19 failures, formatting, checked per-file Bash and ShellCheck, added infrastructure and hostile-input regressions, and tested the manual deployment’s selection of an unexpired same-SHA artifact. Actionlint passed locally. Hosted protections and production runner were not exercised. |

A fresh host is the only supported installation target. An interrupted or customized install stops for console maintenance. The helper keeps a root-private SSH baseline and never truncates an existing managed file to make it fit. Package installation is a one-time operation, with privileged candidates staged and validated before activation. The dedicated firewall stays loaded independently of Docker. See the [manual provisioning procedure](UPCLOUD_MANUAL_PROVISIONING.md).

## Files changed

- Delivery and configuration: `.gitattributes`, `.github/workflows/single-deploy-production.yml`, `.github/workflows/single-validate.yml`, `compose.prod.yml`, `ui/Dockerfile`, `deploy/postgres/Dockerfile`.
- Under `deploy/single/`: `bootstrap-host.sh`, `bootstrap_host.py`, `docker-firewall.sh`, `host-check.sh`, `host-monitor.sh`, `release.py`, `images.json`, `backup-common.sh`, `backup-preflight.sh`, `backup.sh`, `backup_state.py`, `restore-verify.sh`, `backup-retention.sh`, `systemd/demand-backup.service`, `systemd/demand-firewall.service`.
- Under `infra/`: `release_manifest.py`, `validate.py`, `validate_containers.py`, `tests/test_isolation.py`, `tests/test_single_safety.py`, `tests/test_host_security.py`.
- Documentation: root `README.md` and `docs/deployment/` files `PHASE_5_17_1_SECURITY_REMEDIATION.md`, `PHASE_5_17_FINAL_VALIDATION.md`, `UPCLOUD_MANUAL_PROVISIONING.md`, `GITHUB_ACTIONS.md`, `BACKUP_RESTORE.md`, `ACCEPTANCE.md`, `SSH_SETUP.md`, `ROLLBACK.md`, `DOCKER_COMPOSE.md`.

The Git diff against the baseline is empty for shared infrastructure and workflow files, and for the retired dedicated workflows.

## Infrastructure regression detail

The starting suite exited 1 with 191 passes and 19 failures. The archive test loader now requires the three Terraform definitions to exist only under `infra/retired-workflows` with the `.disabled` suffix. It retains their historical contract assertions.

| Previously failing cases | Count | Repair |
| --- | ---: | --- |
| Dedicated Environment, secret namespacing, fallback prevention and manual concurrency for each historical plan/apply/destroy definition | 12 | Read the archived definitions and assert they are not discoverable. Check the active deployment job independently. |
| Build package-write authority | 1 | Check the active publication job and deny package writes to deployment and validation. |
| Plan/apply/destroy state key and Terraform concurrency assertions | 3 | Preserve archival constraints and require no active dedicated state or cloud-provisioning workflow. |
| Dedicated versus shared concurrency comparison | 1 | Read archived definitions explicitly and verify the active group remains separate. |
| Exact-commit build CI gate | 1 | Check `infra/ci.py` in both publication and deployment before image publication or artifact use. |
| Destroy environment input | 1 | Verify only the archived destroy definition retains the input. |

New tests cover proof age, process/host/source binding, invalid sudo and console evidence, symlinks and ownership, candidate rejection and interruption, IPv6 and firewall CIDR limits, source/consumer failure, restore revision and data mismatch, stale/tampered acceptance, retention refusal, artifact expiration, immutable repositories and the runner gate. Negative host and workflow API responses are mocked. Pipe-exit tests run real synthetic subprocesses.

## Runtime image refresh

A current Trivy database exposed 7 HIGH findings each in the cached frontend and ingress images (`libexpat`, `libxslt`) and 19 HIGH findings in the cached PostgreSQL image (`krb5-libs`, `libxslt`). The backend had zero. The frontend and ingress now pin the same refreshed unprivileged Nginx 1.30.6 index. PostgreSQL now pins official 16.16 Alpine and retains the tested `su-exec` privilege drop. The refreshed bases have `libexpat 2.10.0-r0`, `libxslt 1.1.43-r4` and `krb5-libs 1.22.3-r0` where applicable. All four exact local runtime artifacts passed a fresh HIGH/CRITICAL vulnerability scan. The workflow still scans and approves its own immutable release digests for the reviewed commit. [Nginx upstream source](https://github.com/nginx/docker-nginx-unprivileged) · [Official PostgreSQL 16.16 image source](https://github.com/docker-library/postgres/tree/168a848e5905af32aaa5fd6fad4f30906c80af95/16/alpine3.24)

| Runtime | Scanned local identity |
| --- | --- |
| Backend | `sha256:ac39179457575d13c8d386dbb119d9682fdd2ecb09c978396362e85c2a28fc1e` |
| Frontend | `sha256:0c82a852b7240b8951af0655bcd2c65ae427c10a88be018ad2fe9b1d8375d318` |
| PostgreSQL | `sha256:ea864bdded285b3e0567887f2b80d6cce3e68f9af1a33c01649cbe4baaed440d` |
| Ingress | `sha256:ea4fd7ab5a8dc6348c18240bd3546f355f8373cd8f112580f7d8bd8ff5a74772` |

## Exact validation evidence

Commands run from the repository root unless indicated. `python` and `ruff` below use `backend/venv/Scripts/python.exe` and its Ruff module on Windows. Disposable scripts and synthetic files are under `validation/phase5171-tools/` in the local workspace. Disposable containers had no live cloud connectivity or production data. Public downloads for validation images and Trivy checks were restricted to tooling.

| Command | Result and evidence |
| --- | --- |
| `git rev-parse HEAD` and `git symbolic-ref refs/remotes/origin/HEAD` | PASS, exit 0. Baseline recorded above. |
| `python -m pytest infra/tests infrastructure/tests -q --basetemp=validation/phase5171-baseline --tb=line` | FAIL, exit 1. Reproduced 19 failures and 191 passes. |
| `python -m pytest infra/tests infrastructure/tests -q --basetemp=validation/phase5171-infra-final --tb=short` | PASS, exit 0. 263 passes. Includes prior 19 cases and new regression tests. |
| `ruff check infra infrastructure deploy/single` and `ruff format --check infra infrastructure deploy/single` | PASS, exit 0 for each. |
| `ruff check backend` and `ruff format --check backend` | PASS, exit 0 for each. |
| `python infra/validate.py` and `git diff --check` | PASS, exit 0. Includes Compose port, persistence, migration, workflow, shell line endings and documentation contracts. |
| Backend `python -m pytest tests -q --basetemp=../validation/phase5171-backend-approved --tb=short` | PASS, exit 0. 200 passed, one opt-in PostgreSQL test skipped here. Synthetic unreachable loopback database URL, test environment and `AUTH_ENABLED=false`. Tests explicitly enabling auth remain included. |
| Backend `python -m pytest tests -q -k "auth or token or session or csrf or role or login" --basetemp=../validation/phase5171-auth` | PASS, exit 0. 42 passed, 159 deselected. |
| `python infra/validate_containers.py` and `python infra/validate_containers.py --frontend-image demand-phase5171-frontend:local --postgres-image demand-phase5171-postgres:local` | PASS, exit 0 on both sets. Disposable Compose migration, API readiness, Stage A ingress denial, persistence through DB container restart, limited application role, dump/restore and one PostgreSQL ingestion integration test. |
| `npm run lint`, `npm run build -- --configuration production`, `npm run e2e:typecheck`, `npm run e2e:list` in `ui` | PASS. Production build initial size 662.77 kB. Browser discovery found 18 cases. |
| `python validation/phase5171-tools/e2e-local.py` | PASS, exit 0. Synthetic browser flows 8 passed and 10 opt-in tests skipped. Separate JWT browser run 7 passed. The three public-demo scenarios were outside the dedicated production configuration. First launch failed to import the backend from the helper directory and was rerun with the explicit backend import path. |
| `npm test -- --watch=false --runner-config ../validation/phase517-vitest.mjs` in `ui` | FAIL on Windows, exit 1. Vitest fork workers timed out before tests. A thread-worker retry also timed out. |
| `docker run --rm --network none -v "${PWD}/ui/src:/src/src:ro" -v "${PWD}/ui/angular.json:/src/angular.json:ro" -v "${PWD}/validation/phase517-vitest.mjs:/tmp/demand-vitest.mjs:ro" demand-phase5-ui-test:latest npm test -- --watch=false --runner-config /tmp/demand-vitest.mjs` | PASS, exit 0. Current Angular source, 266 tests in 19 files. |
| `docker run --rm --network none -v "${PWD}:/repo:ro" -w /repo demand-phase5171-tools:local bash -ec 'for script in deploy/single/*.sh; do bash -n "$script"; done; shellcheck -x deploy/single/*.sh'` | PASS, exit 0. Bash parsed each file and ShellCheck 0.9.0 reported no findings. An earlier CRLF failure was corrected. |
| `docker run --rm --network none -v "${PWD}:/repo:ro" -w /repo rhysd/actionlint:1.7.12 -color` | PASS, exit 0 for discoverable workflows. Workflow YAML is also covered by the contract tests. |
| `docker compose --env-file validation/phase5171-tools/compose-synthetic.env -f compose.prod.yml config --quiet` | PASS, exit 0 with synthetic data. |
| `docker run --rm -v "${PWD}:/src:ro" aquasec/trivy:0.76.1 config --exit-code 1 --severity HIGH,CRITICAL --file-patterns 'dockerfile:.*Dockerfile$' /src/backend/Dockerfile` | PASS, exit 0, one parsed file and no HIGH/CRITICAL findings. The former Compose scan returned zero supported files. Compose is asserted separately. |
| Same Trivy command with `/src/deploy/postgres` | FAIL, exit 1 for DS-0002. The PostgreSQL image starts its initialization entrypoint as root and drops privileges. The independent tmpfs probe confirmed the running PostgreSQL PID 1 was UID 70. This static finding remains visible. |
| `docker build --platform linux/amd64 -t demand-phase5171-frontend:local ./ui` and `docker build --platform linux/amd64 -t demand-phase5171-postgres:local ./deploy/postgres` | PASS, exit 0 for each refreshed artifact. |
| `python validation/phase5171-tools/scan-cached-images.py` | FAIL, exit 1 on the old images. Raw results in `validation/phase5171-tools/*-vulnerabilities.json`. |
| `python validation/phase5171-tools/scan-refreshed-images.py` | PASS, exit 0. Trivy 0.76.1 with the current vulnerability database, `image --input /tmp/image.tar --skip-db-update --scanners vuln --severity HIGH,CRITICAL --exit-code 1 --format json`. Zero findings across all four exact local artifacts. Raw new results in `validation/phase5171-tools/refreshed-*-vulnerabilities.json`. |
| `python infrastructure/check_secrets.py` | PASS, exit 0, no Trivy secret findings in tracked and proposed source. Ignored local secret files were outside the scan. |
| `docker run --rm --network none --cap-add NET_ADMIN -v "${PWD}:/repo:ro" demand-phase5171-tools:local bash /repo/validation/phase5171-tools/rehearse-host.sh` | PASS, exit 0 for isolated host components. Actual OpenSSH journald proof, sudo, key preservation and hardening. Actual nftables transactions, forced interruption before commit and a denied IPv6 loopback connection. No host kernel namespace or published port was used. |
| `docker run --rm --network none -v "${PWD}:/repo:ro" demand-phase5171-pg:local python3 /repo/validation/phase5171-tools/rehearse-backup.py` | PASS, exit 0. PostgreSQL 16 source and isolated restore clusters on Unix sockets, Restic 0.16.4 over pinned loopback SFTP, matching revision/data, failed mismatch denies retention. The harness substitutes PostgreSQL process lifecycle for Docker calls. The separate Docker probe ran the PostgreSQL image on tmpfs with networking disabled. |
| Full isolated Ubuntu VM and hosted exact-SHA CI | NOT TESTED. Component containers do not cover privileged console, actual package/systemd bootstrap, Docker daemon restart, DHCP/firewall path and OS reboot. GitHub workflow dispatch, settings and current image publication were outside this phase. |

## Operational prerequisites

1. Rehearse fresh finalization, root provider console access, failed update recovery, Docker DNAT isolation, Docker daemon restart and reboot on a disposable Ubuntu 24.04 amd64 VM. Test both allowed and disallowed SSH sources and IPv6.
2. Review the current hosted build, scan and publication for the reviewed SHA. Verify protection and fixed-egress runner settings through the owner-controlled GitHub Environment. Keep legacy shared workflows outside the dedicated release.
3. Confirm current Singapore quote and the independent SFTP failure domain, storage/transfer budget, repository capacity, credential escrow and restore time. Obtain the owner’s separate provisioning approval.
4. After provisioning approval, stop at the IPv4 for the domain owner. DNS/TLS, current backup receipt, protected release and manual administrator creation require their own acceptance.

No UpCloud, AWS, DNS, production database, GitHub Environment or production release operations were performed. Retention was tested without deleting or pruning backup data.
