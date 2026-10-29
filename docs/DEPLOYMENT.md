# Production deployment runbook

Prepared for Linux Docker Compose; no deployment has been performed.

## Phase 7C migration and restricted operations

The production image includes the Admin Data Management page and owner-only API-token
CLI. Before replacing the API image, take a backup and apply additive migration
`0003_api_tokens` with the owner migration service:

```sh
docker compose --env-file .env.production -f compose.production.yml build backend frontend
docker compose --env-file .env.production -f compose.production.yml run --rm migrate
docker compose --env-file .env.production -f compose.production.yml up -d --wait backend frontend proxy
```

These are future operator commands, not deployment actions taken during this phase.
Existing data and browser sessions are preserved; never remove volumes. Prefer a forward
fix or previous compatible application image on rollback; do not downgrade/drop the
token table as an automatic rollback. Revoke issued API tokens before reverting to code
that does not recognize them. Restores must preserve private auth ACLs (BACKUP_RESTORE.md).

Admin users see **Management → Data Management**. The page uses existing ingestion/upsert
semantics, HttpOnly cookies and CSRF. Viewers cannot access it or upload via the API.
Kaggle 2013–2017 imports are historical demo data; upload only approved synthetic/public
data to a public demo. CSV default limit remains 25 MiB; request/proxy limits also apply.

Swagger remains disabled in production. For a loopback development or isolated tunneled
operations instance, use AUTHENTICATION.md's owner-issued, short-lived API-token flow.
Never enable public developer docs, return browser JWTs from login, or place any token/key
in Angular configuration. No paid provider, cloud instance or production credential was
activated. Phase 7C was validated locally and a local commit explicitly requested;
push and deployment require their own instructions.

For local Docker validation when Windows security software intercepts the disposable
internal certificate, run browsers inside the isolated Linux test network:

```sh
python deploy/validate_docker.py --browser-tests --browser-container
```

This optional path uses the matching official Playwright 1.64.1 image, a read-only source
mount/root filesystem, temporary dependency installation, an unprivileged user, dropped
capabilities, no-new-privileges and bounded CPU/memory/PIDs. A test-only raw TCP forwarder
preserves the existing localhost TLS authority, port and Origin while connecting to Caddy
inside Docker. It exposes no additional host ports and changes no host trust/antivirus
settings. The runner and its files are disposable; the production services keep their
original restrictions. Allow extra local/CI disk and about 1.5 GiB memory for this temporary
test runner; do not count it as a resident VPS service. Keep the image version aligned with
the pinned @playwright/test dependency. Git for Windows supplies `sh` for backup scripts;
the validator also resolves Windows npm.CMD when using host browser mode.

The test-only install uses `npm ci --ignore-scripts` because it executes already-built
production assets and Playwright's image browsers. Angular/esbuild lifecycle scripts are
not needed there and cannot execute on the restricted temporary mount. Production image
builds still perform normal `npm ci` and the actual Angular production build. All browser
tests execute unchanged; authentication, TLS, RBAC and CSRF checks are preserved.

## Capacity and budget

Planning estimate, not a benchmark or provider quotation: 2 shared vCPU, 4 GiB RAM,
40–80 GiB SSD and 1–2 GiB swap for three light-traffic demos. Reserve 1 GiB for OS,
Docker and filesystem cache. This app typically budgets 250–650 MiB idle/light load;
configured container ceilings total about 1.1 GiB. Three apps can approach 3.3 GiB.
CSV parsing and forecasts need load measurement before larger datasets. Build images
on CI/a workstation; Angular compilation can consume 1–2 GiB transiently.
No production Ollama: a 4b model would compete for most of the VPS memory.

Target allocation: $10–16/month VPS, $1–3 backup storage allowance, $0 inference
with AI disabled, domain renewal outside the monthly VPS budget. These are budget
allowances, not verified current offers. Confirm taxes, region and storage charges
before purchase. Three isolated PostgreSQL instances fit only light portfolio use.

## Before first launch

1. Provisioning, DNS and cloud purchases require a separate decision. Choose a domain,
   Linux host, Docker Engine + Compose v2 and firewall permitting only SSH, 80 and 443.
2. Copy `.env.production.example` to `.env.production`, `chmod 600 .env.production`.
   Generate independent secrets with `openssl rand -hex 32`. Replace both password
   occurrences in their matching URLs. Do not use example values. Keep this file out
   of Git, CI artifacts and screenshots. Only trusted host admins can access Docker.
3. Set explicit JSON `TRUSTED_HOSTS`, domain and ACME email. Keep `127.0.0.1` for health
   probes. No wildcard hosts. CORS is denied by default: use the same HTTPS origin.
4. Production requires JWT cookie authentication for protected routes; AUTH_ENABLED=false
   is forbidden there. Configure a random JWT_SIGNING_SECRET (64+ characters), exact
   HTTPS AUTH_ALLOWED_ORIGINS, issuer/audience and the default 30-minute lifetime.
   OPERATOR_TOKEN no longer grants HTTP access. Apply migrations and provision admin /
   restricted viewer accounts through the owner CLI described in AUTHENTICATION.md.
   Angular receives no operator/provider/signing secret. Admins can write; viewers can
   read, evaluate/backtest and use the rate-limited assistant. Anonymous public access
   remains explicit opt-in on /demo routes using the separate synthetic reader DB.
5. Verify fresh PostgreSQL initialization and backup restoration on a disposable stack.
   The init script runs only on a new volume and creates `demand_app` with DML/sequence
   access, plus a SELECT-only `demand_demo_reader`; only the owner migrates. Existing volumes need a reviewed role provisioning
   migration; never delete a volume to trigger initialization.

## Commands (operator-run, not executed by this phase)

From repository root, use the same project name and env file for every command:

```sh
docker compose --env-file .env.production -f compose.production.yml config --quiet
docker compose --env-file .env.production -f compose.production.yml build --pull
docker compose --env-file .env.production -f compose.production.yml up -d db
docker compose --env-file .env.production -f compose.production.yml run --rm migrate
docker compose --env-file .env.production -f compose.production.yml up -d backend frontend proxy
docker compose --env-file .env.production -f compose.production.yml ps
curl --fail https://YOUR_DOMAIN/api/v1/ready
```

Do not use `down -v`. The migration service is an explicit tools profile job; regular
`up` does not migrate. Alembic head is `0002_authentication`, following `0001_initial`. Before each upgrade,
back up and review `alembic upgrade head --sql`; validate live `alembic current` and
`alembic check` on staging. Never run downgrade against valuable data: initial downgrade
drops all application tables. Owner secrets are absent from the running API environment.

## AI activation (optional, separately approved)

AI defaults off and no paid requests are made by provisioning. After choosing and
approving a provider, configure server-only `AI_PROVIDER=openai`, HTTPS `/v1` URL,
model and API key. Provider must support `/models`, chat completions and JSON-object
response format. Some compatible services differ: verify with mocks then a deliberate
staging request. No automatic fallback, retry, model download or account creation.
Readiness checks `/models`; it does not run inference. One inference at a time, 30-second
configured timeout, 512 output tokens. A global six assistant requests/minute and 50/day
UTC cap includes readiness and failed requests. Daily counts persist in `ai_usage` volume;
minute counts reset on restart. Never remove the usage volume to bypass limits.
Caps are request caps, not dollar guarantees; set a provider-side spend limit too.
Run one API worker/replica; distributed rate limits require a shared limiter first.

## Three demos on one VPS

Use one shared Caddy ingress binding 80/443 with separate domain blocks. The current
proxy is a standalone first-app configuration. Before a second app, move ingress into
an operator-owned stack, attach only frontend/API services to the ingress network, and
remove per-app proxy ports. Keep each DB on its own private network, project-scoped
volume, distinct owner/runtime credentials and database name. Do not attach DBs to the
shared ingress network. Do not reuse the default project name across clones. No DB or
Ollama ports are published. Back up each project independently.

## Operations and rollback

Use immutable image tags/digests for releases; record source revision, image digest and
Alembic revision. This preparation uses version tags which must be digest-pinned after
successful image testing. Log rotation is capped at 3 x 10 MiB/container. Monitor disk,
RAM/OOM events, HTTP errors, readiness, certificate expiry and backup age. Never log
Authorization headers, prompts, provider bodies or environment dumps. Public GET
analytics still need traffic/load evaluation and edge abuse controls before broad use.

Before updates: `sh deploy/backup.sh`, record release and review migration compatibility.
Roll back application images to the previous verified digest and recreate API/frontend.
Do not roll back schema automatically. For an incompatible schema, restore into a new
DB, verify, stop writes and deliberately switch runtime URL. Preserve original DB and
volumes until recovery is confirmed. See BACKUP_RESTORE.md.


## Phase 7B: disposable local/CI container validation

Docker must be running in Linux-container mode. From repository root on a Linux host:

```sh
python deploy/validate_docker.py --config-only
python deploy/validate_docker.py
# To include production browser assertions, first install UI dependencies/Chromium:
npm --prefix ui ci
(cd ui && npx playwright install --with-deps chromium)
python deploy/validate_docker.py --browser-tests
```

The runner creates fresh random credentials and a random `phase7b-*` project, binds
only a loopback TLS port, and uses Caddy's internal CA. It never reads `.env.production`
and overrides inherited database/AI variables. It removes only its own test project's
containers and volumes. Cleanup is destructive only to those newly created resources.
The internal TLS trust bypass is confined to the loopback test client/browser; production
Caddy uses public certificates and must retain normal client verification. Compose
v2.24.4+ is required for the disposable overlay's `!override` support.
The Docker validation workflow is configured but must actually run green before launch.

## Public synthetic demo setup

Use a dedicated deployment with an empty database named, for example, `portfolio_demo`.
Do not rename or empty an existing database/volume. For an existing deployment, provision
a separate database or a separately named synthetic stack and its reader role instead.

1. Set POSTGRES_DB and matching owner/runtime URLs to the new `*_demo` database, generate
   DEMO_DB_PASSWORD, and set DEMO_DATABASE_URL to the same synthetic database using the
   `demand_demo_reader` account. Do not point this reader at a private dataset.
2. Keep PUBLIC_DEMO_ENABLED=false while initializing. Start DB, migrate explicitly,
   then run the guarded deterministic seed with owner credentials:

```sh
docker compose --env-file .env.production -f compose.production.yml run --rm \
  -e DEMO_ALLOW_SEED=1 migrate python -m scripts.seed_demo
```

3. The seed refuses any nonempty application table and accepts only a lowercase
   `*_demo` database name. It creates 364 historical synthetic sales rows, a completed
   run with 28 predictions, and a database-level synthetic-v1 marker. It never resets
   data or downloads a real dataset. If partial seeding fails, investigate in that new
   stack; do not rerun against an existing valuable database.
4. Set PUBLIC_DEMO_ENABLED=true and recreate the backend. Startup validates the marker
   through the demo reader connection. No marker or missing reader rights means startup
   fails. Public queries use a read-only transaction, SELECT-only role, two-connection
   pool and five-second statement timeout. Admin calls retain their original DB; demo viewers remain on synthetic reads.
5. Angular shows the historical synthetic data banner, hides forecast creation and
   backtesting, uses GET evaluation, and offers guided demo questions only when enabled.
   Server-side route allowlists and database permissions enforce these boundaries even
   if someone bypasses the UI. Unknown/new API routes remain private by default.

The marker is an operator provisioning safeguard, not proof that arbitrary future imports
are synthetic. Never import client data into a demo database; use a separate private
stack/database and credentials for private work. Public readers cannot choose connection
strings, access operator conversations, or issue SQL.

## Optional guided public AI

AI_ENABLED and DEMO_AI_ENABLED default false. Only after provider/spend approval may
both be enabled with HTTPS hosted configuration. `/api/v1/demo/assistant` accepts exactly
one enum question_id (forecast, historical, accuracy); extra fields/free-form text,
context IDs and conversation IDs are rejected. Each call is stateless, retrieves only
from the demo database and uses unchanged deterministic evidence verification.
Unrestricted `/assistant/*` requires an authenticated admin/viewer session and server limits. No operator token, API key or signed
admin capability is issued to the browser.

Anonymous clients share a global read allowance (120/minute), guided AI allowance
(3/minute, 10/day UTC), and the overall AI allowance (6/minute, 50/day by default).
AI daily counters persist across restart and carry Phase 7A usage forward. Invalid and
failed admitted attempts consume allowance conservatively. Forwarded-IP headers cannot
bypass these global counters. One worker/replica is required. Counters fail closed on
storage failure; preserve /state across releases. Cross-origin browser AI POSTs are
rejected; browser same-origin policy alone is not a bot defense.

Tradeoff: visitors can exhaust the shared public allowance for everyone. A fixed prompt
set and hard server/provider budgets limit impact without collecting user identities.
For individual quotas, add verified invitations/accounts or a challenge service after
review; a browser-visible shared secret or localStorage token would not solve abuse.
Public readiness checks have a separate 60/minute allowance; configuration checks are lightweight; add edge traffic controls before
promoting to significant traffic. No paid request was made during validation.

Existing initialized volumes do not rerun init-db.sh. Provision the demo reader and
SELECT grants with a reviewed owner SQL change, rather than deleting volumes. Restored
demo databases also need reader grants and a deliberate marker after synthetic-data
verification; database comments are not recreated by the ordinary per-DB dump script.
See SHARED_VPS_ARCHITECTURE.md for ingress/network separation across all three demos.


## JWT deployment transition

See AUTHENTICATION.md for the full login/logout/expiry/CSRF/RBAC lifecycle. The previous
operator Bearer secret is deprecated and ignored by HTTP authorization. Apply the new
additive migration before starting the updated API; provision explicit accounts with
owner credentials, never a default password or public registration endpoint.

The production Angular build always enables route guards and HttpOnly-cookie sessions.
For local authenticated development, use `ng serve --configuration authentication`,
AUTH_ENABLED=true on FastAPI, a random signing key and an approved loopback origin.
Default unauthenticated local development remains unchanged. Cookies are Secure only
in production; production AUTH_ALLOWED_ORIGINS must all use HTTPS.

Take a backup before upgrading. Auth schema rollback would remove users/sessions, so
prefer a forward fix or compatible application image rollback. A signing-key change
invalidates all JWTs and requires users to log in again. Preserve session records across
API restarts so logout revocation remains effective. Periodically purge only expired
sessions with the owner CLI after deployment approval. Never restore broad SELECT grants
to the public reader: auth_users and auth_sessions must remain private.
