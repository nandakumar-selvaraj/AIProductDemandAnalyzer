# Phase 7B validation — 2026-10-28

Baseline: d3849e6. Scope: application security/public synthetic demo, local QA, and
repeatable Docker/CI validation. No cloud deployment, purchase, paid AI call, real
dataset import, existing development-data reset, commit or push was performed.

## Results actually executed

| Check | Command / environment | Result |
|---|---|---|
| Docker availability | `docker info --format '{{.ServerVersion}}'` | Failed: Docker Desktop Linux engine pipe absent; no image or container checks claimed |
| Backend regression/security/provider mocks | From backend: `venv/Scripts/python.exe -m pytest tests -q` | 147 passed, 1 skipped; integration requires TEST_DATABASE_URL in this run |
| Backend/deployment lint | `backend/venv/Scripts/python.exe -m ruff check backend deploy/validate_docker.py` | Passed |
| Backend/deployment format | Same interpreter: `-m ruff format --check backend deploy/validate_docker.py` | Passed |
| Real PostgreSQL migration/upsert integration | From backend: `venv/Scripts/python.exe -m scripts.validate_local --postgres-only` | Passed: migration and 1 integration test in a newly created random loopback DB; only that new DB removed |
| Synthetic public-demo seed | From backend: `venv/Scripts/python.exe -m scripts.validate_local --demo-seed-only` | Passed: 364 sales, 28 predictions, marker, nonempty seed refusal; only that new DB removed |
| Angular lint | From ui: `npm run lint` | Passed |
| Angular tests | From ui: `npm test -- --watch=false` with TEMP/TMP pointing at ui/tmp | 240 passed in 17 files |
| Angular production build | From ui: `npm run build -- --configuration production` | Passed; initial bundle 655.60 kB, estimated transfer 119.66 kB |
| Playwright TypeScript | From ui: `npm run e2e:typecheck` | Passed |
| Synthetic browser E2E | From backend: `venv/Scripts/python.exe -m scripts.validate_local` | 8 passed using installed Edge, 3 production-Docker-only tests skipped; fresh synthetic DB and temporary API/UI servers only |
| Production Compose | `docker compose --env-file .env.production.example -f compose.production.yml config --quiet` | Passed |
| Disposable Compose override | `backend/venv/Scripts/python.exe deploy/validate_docker.py --config-only` | Passed; random env removed, no containers started |
| Linux shell syntax | Git Bash `-n` for deploy/backup.sh, restore.sh and init-db.sh | Passed outside sandbox; does not execute backup/restore |
| Git whitespace | `git diff --check` | Passed |

Windows FastAPI tests and local database/browser servers required execution outside
the filesystem sandbox's socket restrictions. No application dependency versions were
changed in Phase 7B. Phase 7A advisory results remain historical, not a fresh audit claim.
Temporary validation logs and env/dump outputs are ignored and excluded from commits.

## Docker checks configured, not executed here

`.github/workflows/docker-validation.yml` runs:

```sh
python deploy/validate_docker.py --browser-tests
```

The Ubuntu runner installs UI dependencies and Chromium first. The orchestrator:

1. Creates a fresh random project and credentials; refuses existing containers,
   networks or volumes with its project label. Never reads `.env.production`.
2. Builds production images and provisions the Caddy config using the same route
   snippet as production. Uses internal CA TLS on a random loopback host port;
   it does not request public certificates or paid inference.
3. Initializes PostgreSQL roles, migrates, seeds synthetic data and verifies counts.
4. Waits for DB/API/nginx/Caddy health; inspects restart policies, memory/CPU/PID limits,
   and absence of application/database host port bindings.
5. Checks static/SPA hosting, HTTPS API routing, anonymous write rejection, disabled AI,
   role permissions and read-only evaluation access.
6. Runs the actual backup and restore scripts into a new database, compares five table
   counts and connects the application's demo reader to the restored DB.
7. Verifies source counts, restarts DB/API, recreates DB container and checks persistence.
8. Runs production public-demo Playwright tests (banner, hidden mutation controls,
   denied operator routes and disabled AI), then removes only its newly created stack.

No success is claimed for these configured checks until a verified workflow/local
Docker run completes. Cleanup requires Compose v2.24.4+ and a Linux Docker host.
The scripts never remove existing development volumes or reuse a deployment project.

## Security audit and mitigations

| Priority | Finding | Phase 7B response |
|---|---|---|
| High | Phase 7A public GETs could expose a mistakenly configured private DB | Production reads now require operator auth by default. Explicit demo mode uses a dedicated *_demo reader URL and validates a synthetic-v1 DB marker on startup. Public handlers select the demo engine, never the private engine. |
| High | A browser-visible operator token would authorize uploads/forecast writes | No operator credential is issued to Angular. Production mutation forms/backtesting are hidden; server authentication remains mandatory. |
| High | Anonymous unrestricted AI could disclose context or exhaust spending | Separate stateless fixed-question endpoint, no context/conversation/free-form input, demo-only retrieval, deterministic fact verification, global minute/persistent daily limits. Disabled by default; no paid calls made. |
| High | Production Caddy used inline blocks inconsistent with documented syntax | Replaced them with multiline blocks in the shared route snippet; configured container Caddy validation remains pending. |
| High | Fresh initialization, restore and mounted-volume startup lacked evidence | Added disposable Docker CI covering these paths; remains a launch gate until executed. |
| Medium | Read analytics could consume shared VPS capacity | Global public read limit, read-only reader, small separate pool and 5-second statement timeout; readiness has a separate 60/minute cap. Limits do not replace load/edge traffic testing. |
| Medium | Rate-limit resets or spoofed client identities | Daily counters persist and migrate Phase 7A counts; tests cover restart and spoofed forwarding headers. Limits are global and require one worker/replica. |
| Medium | Shared public allowance can be exhausted by one visitor | Accepted bounded showcase tradeoff; fixed prompts and budgets constrain cost. Individual fair-use requires invitations/accounts or a separately reviewed challenge, not a shared frontend secret. |
| Medium | Operator can accidentally import private data into the synthetic DB | Provisioning marker is not data classification. Keep the demo dataset/reader in a dedicated synthetic stack and never import real records. Separate private credentials/data sources are mandatory. |

Caddy syntax reference: [official Caddyfile block rules](https://caddyserver.com/docs/caddyfile/concepts#blocks).

## Tests added

Public route authorization, default-private GETs, read throttling, fail-closed demo
configuration, rejection of arbitrary assistant input, origin rejection, persistent
public caps, Phase 7A usage carry-forward, demo-only database selection, secret-free
configuration, fixed-prompt inference and unverified evidence rejection. Hosted request
mocks additionally assert JSON response format, authentication and token bounds.
Angular tests verify fixed-question requests without Authorization and disabled AI UX.
Production browser tests are deliberately separated from development-server E2E.

## Files changed

- Backend: config/security/session/main, router and demo/evaluation endpoints,
  provider readiness error handling, seed_demo/validate_local scripts, and production/
  public demo tests. No forecasting algorithm changes.
- Containers/operations: production Compose/env example, backend image seed script,
  Caddy shared routes and local TLS config, backup/restore overrides, Docker validator.
- Frontend: demo capability service/banner, read-only forecast controls, guided assistant
  component and tests, production evaluation GET routing, Playwright config/demo tests.
- CI/docs: Docker integration workflow, production readiness/deployment/recovery updates,
  this validation report and shared VPS architecture.

## Remaining launch gates

Run the Docker workflow successfully (build, startup, real restore and production browser
checks); scan/digest-pin final images; rehearse off-host disaster recovery; measure load;
select domain/host and validate real HTTPS after a separately authorized deployment.
Approve hosted provider and provider-side spending cap before enabling either AI flag.
No CI run or cloud deployment was triggered by this phase.

Planning resources for three light demos: 2 vCPU, 4 GiB RAM, 40–80 GiB SSD, 1–2 GiB swap;
300–700 MiB estimated light usage for this app. Three app container ceilings plus one
shared proxy total 3008 MiB, leaving roughly 1 GiB for the host. These are not measured
container results. Budget allocation $11–19/month with AI off, excluding tax/domain.

Recommended commit: `feat: add isolated Docker validation and read-only public demo access`
