# Phase 8A infrastructure readiness — 2026-10-30

Local implementation and validation are described in [PHASE8A_INFRASTRUCTURE.md](PHASE8A_INFRASTRUCTURE.md)
and [PHASE8A_VALIDATION.md](PHASE8A_VALIDATION.md). Terraform/provider lock, cloud-init,
shared ingress, manual plan/apply/deploy workflows, digest publication, encrypted backup
and restore verification are prepared. A local commit was explicitly requested after
review. No apply/destroy, cloud resources, real production credentials, deployment or push
was performed.

Before Phase 8B: configure the live GitHub production Environment and independent review
policy, separate encrypted/versioned/locked state backend, real scoped secrets/public keys,
approved static SSH runner egress, current UpCloud quote/capacity and an off-host backup
repository. Provisioning does not require a domain and stops at the public-IP output.
Application deployment waits for the friend's DNS record and validates HTTPS. Bootstrap,
real state/approval/SSH, disk mapping and off-host recovery still need an authorized live
acceptance run. Terraform mock tests and local Docker checks do not claim those passed.

---

# Phase 7C readiness — 2026-10-29

Implemented and validated locally. A local commit was explicitly requested after review;
no push, cloud deployment, paid inference or real credential provisioning was performed.
Forecasting and existing ingestion/upsert algorithms are unchanged.

## Architecture and security

- Admin-only Data Management navigation/guard and server-enforced ingestion RBAC.
  File extension/empty/size validation uses Admin-only server configuration; uploads use
  the existing endpoint and cookie/CSRF interceptor. Progress, errors, current result,
  duplicate-submission prevention and cancellation/expiry behavior are covered.
- Owner CLI-issued API tokens use a distinct purpose/audience and separate revocation
  table; default 10-minute, maximum 15-minute lifetime. Signature, claims, user status,
  role, JWT expiry and database state are checked per request. No public token endpoint.
- Browser login never returns a JWT. Cookies remain HttpOnly; cookie mutations retain
  Origin/CSRF checks. Mixed credentials and cross-transport token reuse are rejected.
- OpenAPI declares HTTP Bearer and cookie alternatives; Swagger authorization is memory
  only. Documentation remains inaccessible in production. See AUTHENTICATION.md for
  restricted access, provisioning, expiry, revocation and token-file handling.
- Additive migration `0003_api_tokens` preserves existing business data/session rows.
  Runtime receives SELECT only on API tokens; demo reader receives no auth-table access.
  Backup/restore ACL instructions and Docker validation assertions include the new table.

## Executed validation

| Check | Phase 7C result |
|---|---|
| Backend `python -m pytest tests -q` | 200 passed; 1 opt-in PostgreSQL test skipped here |
| Disposable PostgreSQL `scripts.validate_local --postgres-only` | 1 passed; migrations through 0003 and actual repeat/upsert persistence |
| Backend/deploy Ruff lint and format | Passed |
| Angular unit tests | 266 passed (19 files) |
| Angular lint and E2E TypeScript | Passed |
| Angular production build | Passed; 662.77 kB initial / 122.53 kB estimated transfer; upload page is a 6.30 kB lazy chunk |
| Authenticated browser `scripts.validate_local --auth-e2e` | 7 passed in installed Edge: Admin CSV upload/re-upload, Viewer route/API denial, upload-page expiry, Swagger Authorize + actual API request, cookie refresh, logout/replay and navigation |
| Existing browser `scripts.validate_local` | 8 passed; 10 mode-specific tests skipped here and executed in their separate auth/Docker modes |
| `deploy/validate_docker.py --browser-tests --browser-container` | Passed completely on local Docker Desktop Linux Engine 29.1.3; 3 public-demo + 6 production-auth/upload browser tests passed; 1 Swagger test intentionally skipped because production docs are disabled |

The first Swagger browser run exposed a test selector mismatch: Swagger's accessible
button name is "Apply credentials" although its visible text is "Authorize". The test
was corrected and all seven tests passed on rerun; no authentication check was bypassed.
Synthetic tokens are issued privately, removed after provisioning, and never printed.
Swagger test failures clear the page and omit credential details before diagnostics.
Authentication tests disable traces/video/screenshots and enter the API token without
putting its value in a Playwright fill-step title. Production JavaScript was scanned for
JWT literals, private-key markers and server-only signing/provider-key variable names;
none were found.

Docker Desktop was initially unavailable, then started by the user. The first container
run exposed `/docs` falling through to Angular's SPA (not an exposed Swagger page); Caddy
now explicitly returns 404 for developer-doc paths. Windows tool resolution supports Git
for Windows `sh` and npm.CMD. Host browser attempts first lacked Playwright Chromium,
then installed Edge was intercepted by Kaspersky's certificate-block page. Host trust
and security settings were left unchanged. The final optional Linux browser runner uses
the exact same TLS authority/Origin, read-only root/source, restricted temporary storage,
non-root user, dropped capabilities and resource limits. It skips unused dependency
build lifecycle scripts, not tests; the production build still executes normally.

An upload E2E timing issue was also corrected: file selection now waits until server
limits load and the input becomes enabled, matching actual browser interaction. The final
restricted auth suite passed all seven tests and the final Docker run exited zero.

The Docker run verified new PostgreSQL initialization, revision 0003, synthetic seed,
Admin/Viewer provisioning, private token-table ACLs, CLI issue/revoke, FastAPI readiness,
verified internal TLS, Caddy/Angular routing, production cookie login/expiry, CSV upsert,
Viewer/anonymous write denial, restored counts/connectivity, unchanged source data, and
restart/container-recreation persistence. Disposable containers, volumes and networks
were removed afterwards. Sampled four-service idle memory was approximately 154 MiB
(API 84, PostgreSQL 40, nginx 18, Caddy 13 MiB); this is not a peak/import/VPS load result.

## Prior Docker repair and CI provenance

All three workflows succeeded on code commit `24ad80e6905dfb79d314388aac6d55ca749e38cc`:
[Backend CI](https://github.com/nandakumar-selvaraj/AIProductDemandAnalyzer/actions/runs/40725299376),
[synthetic E2E](https://github.com/nandakumar-selvaraj/AIProductDemandAnalyzer/actions/runs/40725299365),
[production Docker validation](https://github.com/nandakumar-selvaraj/AIProductDemandAnalyzer/actions/runs/40725299361).
That production run verified PostgreSQL initialization/migration, provisioning, FastAPI,
Caddy TLS/routing, Angular login, expiration, persistence and backup/restore. The original
mount failure and the subsequent TLS probe identity issue are described below.

These successful CI runs predate Phase 7C. The new Phase 7C checks passed locally in the
Linux Docker stack, including production upload E2E. No same-commit CI result is claimed
for Phase 7C; push only when instructed, then require all three workflows to pass before
deployment approval.

## Remaining deployment gates and operational risks

Local Phase 7C acceptance checks are green. Do not deploy yet: require post-review CI
after an authorized push. Then configure real domain/HTTPS origins and private server secrets, scan/pin deployment
images, rehearse encrypted off-host recovery and key rotation, and measure concurrent
login/import/forecast memory on the proposed VPS. Historical Kaggle imports can be large;
split under upload bounds and load-test representative data. Revocation cannot undo an
already accepted in-flight import. Never put private customer data in the public demo.

No dependencies were added. The preceding audit found zero production npm advisories
but outstanding Angular-build/Vite development-tool advisories; update and revalidate
those tools before exposing any development server. The default development profile is
loopback-only guidance, not a production authentication substitute. Preserve single-worker
rate-limit assumptions or add shared admission accounting before scaling.

The sections below are historical phase records; this section is the current assessment.

## Phase 7C file inventory (31 files)

```text
.gitignore
backend/Dockerfile
backend/alembic/versions/0003_api_tokens.py
backend/app/api/v1/endpoints/ingestion.py
backend/app/core/security.py
backend/app/main.py
backend/app/models/__init__.py
backend/app/models/auth.py
backend/app/services/auth_service.py
backend/scripts/manage_api_tokens.py
backend/scripts/manage_users.py
backend/scripts/validate_local.py
backend/tests/unit/test_api_tokens.py
backend/tests/unit/test_ingestion_http.py
deploy/Caddy.routes
deploy/browser-validation.cjs
deploy/validate_docker.py
docs/AUTHENTICATION.md
docs/BACKUP_RESTORE.md
docs/DEPLOYMENT.md
docs/PRODUCTION_READINESS.md
ui/e2e/authentication.spec.ts
ui/src/app/app.html
ui/src/app/app.routes.ts
ui/src/app/app.spec.ts
ui/src/app/app.ts
ui/src/app/core/auth.guard.ts
ui/src/app/core/auth.spec.ts
ui/src/app/features/data-management/data-management.page.html
ui/src/app/features/data-management/data-management.page.spec.ts
ui/src/app/features/data-management/data-management.page.ts
```

---

# Docker validation follow-up: TLS probe — 2026-10-28

Commit ccf6386 passed container creation, PostgreSQL initialization, migrations and
synthetic seeding on the Linux runner, then exposed a second validation-client defect:
HTTPS connected to 127.0.0.1 while the internal Caddy site/certificate was localhost.
An HTTP Host override does not set TLS SNI. The probe now uses the correct localhost
URL and validates the chain/hostname using Caddy's generated public test CA certificate,
rather than disabling certificate verification. Browser tests still use their explicit
internal-CA test setting; production public-certificate policy is unchanged.

Diagnostics now include redacted stdout/stderr and container logs on failure, with
bounded command timeouts and no environment dumps. Regression tests cover the Caddy
hostname contract. Full Docker validation passed on 24ad80e (links above).

---

# Docker validation repair — 2026-10-28

The production-stack failure on 29a415c was reproduced by rerunning workflow
40721919563 (job 122941174565). Docker rejected `mode=1777` as a relative mount target
before Alembic started. The YAML flow sequence `[/tmp:size=64m,mode=1777]` was parsed as
two tmpfs entries; Compose schema validation passed despite the invalid runtime target.
Quoting the complete mount preserves `/tmp:size=64m,mode=1777` as one entry for both
backend and migration services. Read-only filesystems, ALL capability drops, no-new-
privileges, the 64 MiB allocation and mode 1777 are unchanged.

The disposable validator now checks rendered tmpfs and filesystem/capability safeguards
before starting containers. Regression tests reject the original split and removal of
safeguards. Baseline logs confirm production image builds, Caddy provisioning and DB
health succeeded before the mount failure; later stages had not run on that baseline.

Fixed-commit Docker integration and all three same-commit workflows passed on 24ad80e.
Local Docker Desktop startup has been
attempted but its Linux engine is not yet responsive; no local container success is claimed.

---

# Current readiness — JWT authentication and RBAC (2026-10-28)

JWT browser sessions now replace operator Bearer authorization in production. The
previous Phase 7B container/demo preparation was committed as ce6515a before this work;
the JWT implementation is not committed or pushed. No UpCloud/cloud deployment occurred.

Production requires AUTH_ENABLED=true, a random server signing key and exact HTTPS
origins. HttpOnly/Secure/Strict cookies carry 30-minute HS256 JWTs backed by revocable
DB sessions. Users/roles/active state are checked on every protected request. Login uses
Argon2id and global rate/concurrency admission; logout revokes the session immediately.
Origin plus session-bound CSRF protects authenticated POSTs. Admin writes and viewer
analytical POSTs are explicitly separated. Public synthetic demo reads remain isolated.
Auth tables are excluded from demo-reader grants; owner CLI alone provisions users.

Local validation: 166 backend tests passed (one optional integration skipped in the main
run); PostgreSQL migration/upsert integration and demo seed checks passed separately in
new disposable DBs. Angular: 253 tests passed, production build passed. JWT browser E2E:
4 passed using random synthetic users, including admin/viewer login, refresh, expiry,
viewer upload denial, analytical evaluation, logout replay rejection and Back protection.
Ruff, Angular lint and E2E TypeScript checks passed. Production/disposable Compose config
validation and Git whitespace checks passed. The production build is 661.97 kB initial
(estimated transfer 122.31 kB). The resolved Python production dependency audit reports
no known vulnerabilities. Legacy synthetic browser tests: 8 passed, 7 skipped (the four
JWT tests ran separately; three production-Docker tests remain unexecuted).

Executed commands (backend working directory unless specified):

```text
venv/Scripts/python.exe -m pytest tests -q
venv/Scripts/python.exe -m scripts.validate_local --postgres-only
venv/Scripts/python.exe -m scripts.validate_local --demo-seed-only
venv/Scripts/python.exe -m scripts.validate_local --auth-e2e
venv/Scripts/python.exe -m scripts.validate_local
```

Repository-root static/config checks:

```text
backend/venv/Scripts/python.exe -m ruff check backend deploy/validate_docker.py
backend/venv/Scripts/python.exe -m ruff format --check backend deploy/validate_docker.py
backend/venv/Scripts/python.exe deploy/validate_docker.py --config-only
docker compose --env-file .env.production.example -f compose.production.yml config --quiet
git diff --check
```

From ui: `npm test -- --watch=false` with TEMP/TMP set to ui/tmp,
`node node_modules/eslint/bin/eslint.js src --max-warnings=0`, `npm run e2e:typecheck`,
and `npm run build -- --configuration production`. Local browser runs used installed
Edge and socket permission outside the Windows sandbox. The dependency audit used
`python -m pip_audit -r backend/requirements.production.txt` from an isolated ignored
tool directory; no audit tool was added to runtime dependencies. Docker info still
failed because the Linux engine pipe is absent. No remote CI run was triggered.

Remaining deployment gates are unchanged: Docker Linux engine is unavailable locally,
so production container startup, restore/ACL checks and production-cookie browser runs
must pass in the configured workflow. Configure real secrets/origins, scan/pin final
images, verify HTTPS and off-host recovery, and measure concurrent-login/forecast memory
before launch. CI is configured, not claimed as executed. AI remains off by default.

No default users, public registration, refresh tokens, frontend JWT storage or legacy
operator bypass are introduced. Development auth is optional via an explicit profile;
production cannot disable it. See AUTHENTICATION.md, DEPLOYMENT.md and BACKUP_RESTORE.md.

---

## Historical Phase 7B assessment (superseded by JWT authentication above)

# Current readiness — Phase 7B (2026-10-28)

Phase 7B implementation is prepared and local application checks passed. **Production
container validation remains pending:** Docker's Linux engine is unavailable. A new
disposable Docker workflow covers image builds, Caddy provisioning/internal TLS,
initialization/migrations, real backup/restore, health/resource/restart/persistence
checks and production browser tests. A configured workflow is not a verified result.

Current local evidence: 147 backend tests passed (one optional integration test skipped
in the unit run), PostgreSQL integration separately passed in a fresh test DB, demo
seed/marker/nonempty refusal passed in a fresh DB, 240 Angular tests passed, lint and
production build passed, and synthetic-only Edge E2E passed 8 tests with 3 Docker-only
tests skipped. No paid inference, cloud deployment, commit or push was performed.

Public deployment now defaults private: operator authentication gates data reads unless
public demo mode is explicitly enabled. Public demo uses a separate SELECT-only reader
URL for a marked synthetic database, not the operator data connection. Read routes are
allowlisted/rate-limited, writes remain private, and optional guided AI accepts only
fixed question IDs with persistent caps. Angular labels demo data and hides production
write/backtest controls. Free-form assistant access remains operator-only.

Remaining High launch gates: run the Docker workflow green, rehearse actual restore,
scan/pin built images, and validate public TLS/DNS in the eventual deployment. Medium:
measure load/memory, install backup monitoring/off-host copies, approve synthetic data
handling and shared allowance tradeoffs, and configure one shared ingress before demo
two/three. Hosted AI remains off until provider and spending approval.

See PHASE_7B_VALIDATION.md for exact commands/results and changed files,
SHARED_VPS_ARCHITECTURE.md for the three-demo design, and DEPLOYMENT.md for setup.

---

## Historical Phase 7A baseline (superseded by Phase 7B above)

### Phase 7A production readiness

Assessment date: 2026-10-28. Preparation complete; public deployment is not yet approved
or validated. No cloud deployment, paid inference, seed/reset, commit or push performed.
Forecast algorithms and deterministic evidence verification remain unchanged.

## Audit findings

Severity describes the original issue or the residual risk, as indicated below.

| Priority | Finding | Resolution / remaining work |
|---|---|---|
| Critical | Anonymous ingestion overwrites historical sales; forecast/backtest writes were unrestricted | Production middleware requires constant-time operator Bearer authentication before body parsing or database work, for all non-read methods. Local development remains open. |
| High | Public assistant could exhaust local compute or incur hosted inference charges | Production assistant requires operator auth; global minute limit, persistent UTC daily admission cap, provider semaphore, timeout, bounded output and no retry/fallback. Provider-side spend cap still required before enabling paid inference. |
| High | No production database/service isolation | Only Caddy publishes 80/443. DB and API have no published ports; Ollama is absent. Separate project volumes/networks and unique per-demo credentials; owner and DML-only runtime roles. |
| High | No tested production deployment path | Dockerfiles, Compose, initialization and migration job prepared. Docker engine unavailable locally: image builds, startup, mounted-volume permissions, real HTTPS and health checks remain launch blockers. CI build job added but not executed in this phase. |
| High | Disaster recovery unproven | Atomic custom-format dump and restore-to-new-database scripts prepared. Actual dump/restore rehearsal, off-host encrypted copies and alerts remain launch requirements. No existing data changed. |
| High | Multipart and Starlette dependency advisories | pip-audit found 24 advisory entries in two resolved packages (including duplicate aliases). Upgraded FastAPI to 0.162.0, Starlette to 1.10.0 and python-multipart to 0.0.32; full tests passed and resolved production requirements re-audit reports no known vulnerabilities. |
| Medium | Upload file limit applied after multipart parsing | Total ASGI body limit before parsing plus Caddy 26 MB edge limit; CSV retains existing 25 MiB limit. Uvicorn admits at most 16 concurrent requests. Large ingestion still needs measured memory/CPU tests. |
| Medium | Development docs exposed, hosts unchecked and validation echoes inputs | Production blocks root/docs/schema; exact Host allowlist; production validation omits input details; existing generic exception handling retained. Same-origin API only, no cross-origin access headers, no cookie auth. |
| Medium | API connection pool too generous for a shared VPS | Pool reduced to 2 + 2 overflow, ten-second pool wait and thirty-second PostgreSQL statement timeout. Bound containers and one API worker. Load/soak tests remain. |
| Medium | No user-facing production identity workflow | Operator API role is implemented. Angular has no login/token storage and production write/chat actions return 401; operator uses trusted API client. A public interactive assistant/write demo needs a separately designed login or safe synthetic sandbox. |
| Medium | Mutable image tags and incomplete supply-chain controls | Pin tested images to digests before release, scan final images, continue dependency advisory review. CI minimum contents:read added, Compose validation and image build job added. Action SHA pinning remains optional hardening. |
| Medium | Public reporting endpoints can expose business data and consume CPU | Intended exclusively for synthetic portfolio data. Real/private data requires read authentication. Traffic abuse controls and representative load tests remain before wider promotion. |
| Low | Backup scheduling/monitoring and shared ingress not installed | Procedures documented; no scheduler or VPS purchased. One shared ingress is required before adding demo two/three. |

## Architecture

```text
Internet :80/:443 -> Caddy (TLS and body limit)
                         | /api/* -> FastAPI :8000 -> PostgreSQL :5432
                         |                 |-> optional hosted HTTPS inference
                         | other  -> non-root nginx :8080 -> Angular static files
```

PostgreSQL stores data in a project-scoped persistent volume. Caddy persists TLS state.
AI daily admission counters use a separate persistent SQLite volume. No Ollama or DB
host port. Non-root read-only API/static containers have temporary filesystems,
resource limits, PID limits, restart policies, health probes and bounded logs.
Migration runs explicitly with the DB owner; runtime receives only its DML credential.
No secrets are copied into Angular build context; production API URL is `/api/v1`.

## Validation executed

| Check | Result |
|---|---|
| Backend pytest, documented backend working directory | 126 passed, 1 skipped (no TEST_DATABASE_URL), no warnings after security upgrades |
| Ruff lint and format | Passed |
| Angular lint | Passed |
| Angular unit tests | 238 passed / 16 files; initial sandbox temp-path failure resolved using workspace TEMP/TMP |
| Angular production build | Passed; initial bundle 654.79 kB, estimated transfer 119.34 kB |
| Python production advisory audit | Executed after dependency fixes: no known vulnerabilities in resolved requirements |
| npm production advisory audit | Executed against registry: zero reported vulnerabilities |
| Playwright TypeScript and discovery | Passed; 8 non-Ollama tests discovered |
| Playwright browser tests | Bundled Chromium missing; rerun using installed Edge: 7 passed, 1 skipped (disabled-AI mode not selected) |
| Alembic | Single head 0001_initial; offline upgrade SQL generated; existing local DB reports head; no upgrade/downgrade run locally |
| Compose config | Passed with `.env.production.example`; real production secrets file never created |
| Docker image/startup/health validation | Not executed: Docker Linux engine pipe unavailable |
| Backup/restore execution | Not executed; no disposable production container database available |
| Hosted provider | Mocked success, readiness, invalid JSON, timeout, upstream auth error, truncation and no retries tested; no paid request made |
| Production security | Auth-before-body/DB, denied hosts/docs, oversized body, rate limit, daily cap across middleware recreation tested |

The Windows sandbox prevented asyncio local socket creation; final pytest ran with
local socket permission. Initial root-directory pytest failures were due to missing
backend `.env` context, then resolved by using the documented backend directory.
The E2E run used the existing local API and did not seed, create forecasts or overwrite data.
Real Ollama inference was excluded from this readiness run.

## Files

Created: `.env.production.example`, `compose.production.yml`, `deploy/Caddyfile`,
`deploy/init-db.sh`, `deploy/backup.sh`, `deploy/restore.sh`,
`backend/app/core/security.py`, `backend/requirements.production.txt`,
`backend/tests/unit/test_production.py`, `ui/Dockerfile`, `ui/.dockerignore`,
`ui/nginx.conf`, and these three production documents.

Modified/added repository policy: `.gitattributes`.

Modified: `backend/Dockerfile`, `backend/.dockerignore`, `backend/app/core/config.py`,
`backend/app/main.py`, `backend/app/db/session.py`,
`backend/app/services/ai_provider.py`, `backend/requirements.txt`, `backend/pyproject.toml`, `.gitignore`, `.github/workflows/backend-ci.yml`.
No Angular source or forecasting code changes were necessary.

## Release gate

Complete container boot/health/migration and restore rehearsal on an isolated stack;
finish built-image advisory review; replace placeholders; pin image digests; approve
public synthetic data policy and operator-only functionality; select DNS/host and
measure representative ingestion/forecast workload. Hosted AI remains disabled until
provider approval, compatibility test and provider-side spending limit are in place.

See DEPLOYMENT.md for sizing, commands, operating costs and rollback;
BACKUP_RESTORE.md for recovery. Estimates are unbenchmarked: 2 vCPU / 4 GiB RAM /
40–80 GiB SSD for three light demos, about 250–650 MiB typical allocation for this app
and 1.1 GiB container ceilings. Budget allowances total $11–19/month with AI disabled,
excluding domain renewal and tax; no offer or purchase is implied.

Suggested commit: `feat: prepare secure production containers and hosted AI safeguards`
