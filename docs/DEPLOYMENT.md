# Production deployment runbook

Prepared for Linux Docker Compose; no deployment has been performed.

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
4. Production data routes require an operator Bearer token by default. Public access
   is explicit opt-in via PUBLIC_DEMO_ENABLED and uses DEMO_DATABASE_URL, never the
   private runtime connection. All writes and unrestricted assistant routes still
   require `Authorization: Bearer <OPERATOR_TOKEN>`. This is one operator role, not
   multi-user identity. Rotate by replacing the token and recreating the backend.
   Angular receives no operator/provider secret and offers no production write forms.
   Use a trusted API client for operator tasks.
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
`up` does not migrate. Alembic has one revision (`0001_initial`). Before each upgrade,
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
   pool and five-second statement timeout. Operator calls retain their original DB.
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
Unrestricted `/assistant/*` remains operator-only. No operator token, API key or signed
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
