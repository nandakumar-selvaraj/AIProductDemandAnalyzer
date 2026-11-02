# Validation and acceptance — 2026-11-02

Preparation only. No live/cloud-backed check is implied by a local PASS. Local Docker Engine 29.1.3 was accessed for disposable validation; no cloud resources, real administrator or deployment was created.

## Phase 5.16.1 security hardening — source READY FOR REVIEW, live BLOCKED

Dedicated GitHub Environment `aiproductdemand-production`, namespaced secrets, complete plan and firewall policy, and pinned SSH host fingerprint. Infrastructure tests: 212 passed. Backend: 200 passed, 1 skipped. Angular: 266 passed, lint passed. Terraform, Actionlint, Trivy and Docker checks: NOT TESTED in this session (Docker daemon unavailable). See [Phase 5.16.1](PHASE_5_16_1_SECURITY_HARDENING.md).

## Current remediation result — PASS

The image vulnerability blocker has been resolved. All four repaired dedicated runtime artifacts scan with zero HIGH/CRITICAL findings, with no exceptions. Backend200 tests, Angular266 tests, infrastructure33 tests, Terraform2 mock tests and separate PostgreSQL integration passed. See [current exact validation commands/results](REMEDIATION_VALIDATION.md) and [security identities/evidence](IMAGE_SECURITY.md). The table below records the earlier preparation run, including its historical failures; it is superseded for image readiness by these current reports. Live acceptance remains untested/approval-gated.

## Initial preparation checks — historical

Commands below ran from repository root except where stated. Terraform container used image `hashicorp/terraform:1.17.1`, repository bind-mounted at `/src`, working directory `/src/infra/terraform`, no cloud credentials. This is a local tooling container, not a deployed service.

| Exact command inside the validation environment | Outcome |
|---|---|
| `terraform fmt -check -recursive` | PASS |
| `terraform init -backend=false -input=false -lockfile=readonly` | PASS; provider 5.48.0 signature verified. Later `terraform init -backend=false -input=false` also passed, without remote backend access |
| `terraform validate` | PASS |
| `terraform test` | PASS: 2 mock tests, including rendered cloud-init read permissions and rejection of world-open SSH |
| `docker run --rm -v "$PWD:/src:ro" aquasec/trivy:0.76.1 config --exit-code 1 --severity HIGH,CRITICAL /src/infra/terraform` | PASS, 0 findings; scanner warns required operator variables are unset |
| `docker run --rm -v "$PWD:/repo:ro" -w /repo rhysd/actionlint:1.7.12 -color` | PASS for all original/new workflows |
| `bash -n deploy/single/*.sh` | PASS in cached Ubuntu validation container |
| `docker build -t demand-phase5-backend-check ./backend` | PASS, including final digest-pinned base and 43-package lock |
| `docker build -t demand-phase5-frontend-check ./ui` | PASS, including final CSP-compatible Angular production config |
| `npm run build -- --configuration production` | PASS locally and in Node24 image; initial bundle 662.77 kB, output dist/ui/browser |
| `docker compose -f compose.prod.yml config --quiet` | PASS with synthetic image/credential environment values only, no service start/config output |
| `python -m pytest tests -q` (backend, explicit `AUTH_ENABLED=false`, `ENVIRONMENT=test`, synthetic `DATABASE_URL`, Python3.13 container) | PASS: 200 passed, 1 opt-in PostgreSQL test skipped; includes authentication/API-token tests |
| `python -m pytest infra/tests infrastructure/tests -q` | PASS: 33 tests; includes immutable-reference policy and migration/health-failure rollback control tests |
| `ruff check infra deploy/single` | PASS |
| `ruff format --check infra deploy/single` | PASS |
| `python infra/validate.py` | PASS: source Compose/network/persistence/migration/workflow/script/doc/CSP contracts |
| `python infra/validate_containers.py` | PASS: no-public-ports disposable stack, actual migrations/readiness, Stage A login503, DB restart persistence, runtime cannot insert admin, synthetic pg_dump/isolated DB restore, separate PostgreSQL integration test (1 passed) |
| `nginx -t` in approved unprivileged ingress image with rendered TLS template and one-day synthetic local certificate | PASS; no real domain issuance or public binding |
| `python infrastructure/check_secrets.py` | PASS: no Trivy secret findings in tracked/proposed source; ignored local secrets/state not scanned |
| `git diff --check` | PASS |
| Trivy `image --scanners vuln --exit-code 1 --severity HIGH,CRITICAL --format json IMAGE` for all four runtime images | FAIL: backend50, frontend72, PostgreSQL26, ingress72 package/advisory findings. [Exact evidence](IMAGE_SECURITY.md). No exception added |

Windows invocations used equivalent absolute `--mount type=bind,src=E:\NANDHA\sources\AIProductDemandAnalyzer,dst=/src` arguments where PowerShell path translation required it. Python/Ruff ran in disposable Python3.13 containers with pytest8.4.2, PyYAML6.0.3 and Ruff0.14.3 installed for validation only.

Initial attempts/corrections: native Windows Terraform init could not resolve registry.terraform.io; equivalent Linux container provider initialization passed. Docker initially lacked sandbox pipe permission; approved local-engine access resolved it. An initial inherited local .env made 9 backend tests fail with401 (191 passed); explicit isolated test settings produced200 passes, without application changes. Unquoted tmpfs comma and IPv6 localhost ingress probe were corrected and the disposable stack passed. Duplicate test-module filename and shellcheck literal-backtick warning were corrected. Integration runner dependencies are built before entering the internal network; no internet access is added to the DB network.

Playwright/browser E2E was NOT TESTED in this preparation run; existing CI remains required before deployment. New CSP config removes Angular's inline critical-CSS loader; final output checked for inline executable scripts. Live cloud plan/apply/destroy/SSH/DNS/TLS/admin/off-host recovery were not attempted.

## Live acceptance — NOT TESTED

All require separate authorization and actual infrastructure:

| Area | Required evidence |
|---|---|
| Infrastructure | Current plan/zone/image/capacity quote, reviewed plan, one VPS, firewall ports/CIDRs, key access, console recovery, cloud-init, SSH final policy, security updates, Docker version, persistence/network isolation |
| Backend | Health/DB readiness, migration heads, errors, Kaggle upload, create/evaluate/backtest forecast, predictions/recommendations and preserved data |
| Authentication | Correct/incorrect login, secure cookie/CSRF, valid/expired/missing/invalid-signature JWT, active status, admin/viewer boundaries, session expiry, logout revocation |
| Angular | Login redirect, protected routes, dashboard/catalog, upload, forecasts/recommendations/reports, session expiration and logout |
| Database | Owner/runtime grants, accounts/data survive restart/update, off-host encrypted backup/integrity check, isolated restore and timed recovery |
| Release | Reviewer/branch gates, pinned SSH/fixed egress, digest provenance/scans, migration failure blocking, health failure rollback, recorded releases, schema compatibility |
| HTTPS | DNS, certificate trust/hostname, HTTP redirect/no plaintext login, SPA deep links, API proxy/security headers, renewal dry-run/hook, external verification |

Public production Swagger acceptance is BLOCKED by intentional existing production docs denial. Local OpenAPI/Bearer tests remain applicable; changing production exposure needs separate review.

Production backup status remains NOT TESTED until off-server backup and restore actually pass. Local synthetic dump/restore does not prove off-server credentials, scheduler, encryption escrow or RTO.
