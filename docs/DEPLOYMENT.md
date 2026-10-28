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
4. Production API exposes read-only synthetic portfolio data publicly. All writes and
   assistant readiness/chat require `Authorization: Bearer <OPERATOR_TOKEN>`.
   This is a single operator role, not multi-user identity. Rotate by replacing token
   and recreating the backend. Angular receives no token or provider key. Use a trusted
   API client for operator tasks. Production write/assistant UI calls return 401 until
   a future user login workflow is implemented; do not embed an operator token in JS.
5. Verify fresh PostgreSQL initialization and backup restoration on a disposable stack.
   The init script runs only on a new volume and creates `demand_app` with DML/sequence
   access; only the owner migrates. Existing volumes need a reviewed role provisioning
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
