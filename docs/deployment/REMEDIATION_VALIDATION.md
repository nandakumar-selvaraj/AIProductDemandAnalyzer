# Image remediation validation — 2026-11-02

**PASS: the four dedicated production runtime images have zero HIGH/CRITICAL vulnerability findings.** No scan exceptions, ignore files, severity downgrades or metadata-only removal were used. No UpCloud operation or production deployment was performed. Existing application dependency versions, endpoints, authentication and migrations remain unchanged.

## Changes and compatibility

- Backend moves from affected Debian packages to a maintained digest-pinned Python3.13 Alpine base. All43 locked application versions remain identical; compatible binary wheels are required. UID/GID1000, home/state paths, non-root execution, Uvicorn command, readiness, management scripts and Alembic are preserved. Complete pip/ensurepip installer tooling is absent only from the immutable runtime; separate build/test images retain installation tools.
- Frontend and ingress use the maintained digest-pinned Nginx1.30.6 image from the current `nginx/nginx-unprivileged` namespace, retaining UID/GID101 and ports/configuration.
- PostgreSQL remains16.15 with the same database binaries/data layout. The derivative recipe replaces vulnerable Go gosu with pinned native su-exec0.3-r0; its entrypoint privilege drop is changed accordingly. Initial database creation, authentication/grants, migrations, persistence and restore are tested rather than assuming helper equivalence.
- The dedicated workflow builds the repaired PostgreSQL image, asserts major16, scans its digest and the other three runtime digests, then retains the existing manual environment/deployment gates. Controller, transport and restore repository allowlists match. There is no unpatched upstream fallback.

## Executed checks

All commands ran locally. Python test tools run in an isolated Python3.13 Alpine build/test target; runtime smoke tests use the final installer-free image. Only synthetic databases/accounts/certificates are used.

| Command/check | Result |
|---|---|
| `docker build -t demand-phase5-backend-check ./backend` | PASS |
| `docker build -t demand-phase5-frontend-check ./ui` | PASS; production Angular build662.77 kB initial bundle |
| `docker build -t demand-phase5-postgres-check ./deploy/postgres` | PASS; native privilege drop verifies postgres UID |
| `python infra/scan_images.py demand-phase5-backend-check:latest demand-phase5-frontend-check:latest demand-phase5-postgres-check:latest nginx/nginx-unprivileged:stable-alpine` | PASS,0 HIGH/CRITICAL on every image; exact local image IDs in security report |
| Runtime importlib.metadata validation against requirements.production.lock.txt | PASS, all43 versions unchanged; pip/ensurepip absent, UID/GID1000 |
| `python -m pytest tests -q` in backend with AUTH_ENABLED=false, ENVIRONMENT=test, synthetic DATABASE_URL | PASS,200 passed/1 opt-in PostgreSQL test skipped; includes authentication/API-token boundaries |
| `python infra/validate_containers.py` | PASS: actual repaired runtime services, migrations/readiness, Stage A denies login, grants, restart persistence, isolated DB dump/restore, separate PostgreSQL ingestion integration1passed |
| `docker build --target build -t demand-phase5-ui-test ./ui` then `docker run --rm --init demand-phase5-ui-test npm test -- --watch=false` | PASS,266 Angular tests in19 files; existing nonfatal NG0956 tracking warnings |
| `python deploy/validate_docker.py --browser-tests --browser-container` | PASS, existing production-stack regressions: TLS/static/proxy, JWT roles/revocation/API tokens, private Swagger, disabled AI, backup/restore, restart/recreation; browser public-demo3passed and authentication6passed/1skipped |
| `python -m pytest infra/tests infrastructure/tests -q` | PASS,33 safety tests |
| `ruff check infra deploy/single` and `ruff format --check infra deploy/single` | PASS |
| `python infra/validate.py` | PASS, source/deployment/doc links/CSP contracts |
| `terraform fmt -check -recursive`, `terraform init -backend=false -input=false -lockfile=readonly`, `terraform validate`, `terraform test` | PASS in Terraform1.17.1 container, locked provider5.48.0;2mock tests; no cloud backend/credentials |
| Trivy0.76.1 `config --exit-code 1 --severity HIGH,CRITICAL /src/infra/terraform` | PASS,0 findings; required live inputs deliberately unset |
| actionlint1.7.12 across all workflows | PASS |
| `bash -n deploy/single/*.sh` | PASS |
| `nginx -t` against exact repaired ingress digest, rendered TLS template and synthetic certificate | PASS |
| `python infrastructure/check_secrets.py` | PASS; tracked/proposed source only, no secret values printed |
| `git diff --check` | PASS |

The PostgreSQL integration skip in the general suite is covered by the separate real disposable integration test. The browser Swagger case is deliberately skipped under production docs denial; API-token/private-Swagger HTTP checks pass separately. No public production Swagger exposure is claimed.

The existing full Docker regression harness tests the legacy shared-portfolio Compose path with the refreshed common application Dockerfiles; the dedicated stack separately tests its repaired PostgreSQL and pinned ingress. It does not approve the legacy upstream image references for production. Development/test images containing installers are not deployable runtime candidates.

## Security evidence and remaining gates

Before/after findings and exact scanned identities are in [IMAGE_SECURITY](IMAGE_SECURITY.md); historical findings are retained in [IMAGE_SECURITY_BASELINE](IMAGE_SECURITY_BASELINE.md). Raw JSON and scanner cache are ignored local files under validation/phase5-remediation. Scanner fails if any image has a HIGH/CRITICAL finding; no --ignore-unfixed or waiver is configured.

Live catalog/capacity/pricing, protected GitHub settings, approved external state/backup services, fixed-egress SSH access/host trust, real domain/TLS renewal, production secrets/admin and live recovery remain NOT TESTED and separately approval-gated. No image was pushed, no workflow dispatched and no cloud deployment started.

**DEPLOYMENT PREPARATION STATUS: READY FOR REVIEW**

**UPCLOUD INFRASTRUCTURE STATUS: NOT PROVISIONED**

**PRODUCTION ADMIN STATUS: NOT CREATED**

**LIVE DEPLOYMENT STATUS: NOT STARTED**

**USER APPROVAL REQUIRED: YES**
