# Phase 7A production readiness

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
