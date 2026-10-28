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
