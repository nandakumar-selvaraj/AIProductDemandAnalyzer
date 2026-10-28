# Shared VPS architecture for three portfolio demos

This is a design and migration procedure, not a deployed service. Other repositories
were not modified. Budget figures are planning allocations, not current vendor quotes.

## Topology

```text
Internet 80/443 -> one Caddy ingress (TLS state in its own volume)
                     | demo-one domain -> demand API + Angular nginx
                     | demo-two domain -> separate app containers
                     | demo-three domain -> separate app containers

Each app API -> its own private database network -> its own PostgreSQL container
Each app owns its database/data volumes, owner/runtime/reader secrets and usage state.
Only APIs/frontends join the shared ingress network. No DB joins that network.
```

Use three PostgreSQL instances rather than one shared superuser or shared credential.
This costs some memory but keeps ownership, backup and recovery independent. Even
though the role names can be the same in isolated instances, passwords must differ.
A public demo reader must never point to another demo or a private business database.
Public synthetic data has no connection to clients' real business records.

## Network and ingress transition

The current `compose.production.yml` remains a standalone app stack. Before demo two:

1. Create an operator-managed external network `portfolio_ingress` and a separate
   ingress Compose project. Only this project binds host ports 80 and 443.
2. Move the Caddy service/TLS volumes there. Keep one domain block per application,
   explicit domain allowlists and unique aliases such as `demand-api` / `demand-web`.
3. In each application override, disable its standalone proxy, attach only its API
   and static frontend to `portfolio_ingress`, and retain the private per-app network.
   Do not publish backend/frontend ports. Never share a network alias such as `backend`
   between app projects on the ingress network: use app-specific names.
4. In shared Caddy routing, use the unique aliases. Reuse this repository's security
   headers and request limit, but change upstream names to the shared aliases.
5. Keep each DB, migration service and database volumes solely in its app project.
   Hosted inference needs outbound HTTPS from the API; no cloud GPU or Ollama service.
6. Validate host routing and rate limits for each domain, and test that APIs cannot
   reach other projects' databases. Preserve existing volumes and application project
   names during ingress migration; changing a project name changes volume selection.

Compose project names: use distinct identifiers for each deployed app. The random
`phase7b-*` projects are disposable tests and must never be reused for a deployment.
No application should mount Docker's socket. Docker/host administrators can read
container environments; store real env files with mode 600 and restrict host access.

## Memory and disk plan

| Component | Per-app ceiling | Three-app/shared ceiling |
|---|---:|---:|
| FastAPI | 512 MiB | 1536 MiB |
| PostgreSQL | 384 MiB | 1152 MiB |
| Angular nginx | 64 MiB | 192 MiB |
| Shared Caddy | 128 MiB once | 128 MiB |
| Total container ceilings | 960 MiB + ingress | 3008 MiB |

Reserve roughly 1 GiB for OS/Docker/cache. A 2-vCPU / 4-GiB host is a tight initial
portfolio target, assuming light traffic and small synthetic datasets. This app's
light-load planning estimate is 300–700 MiB, not a measured container result. A separate
public reader pool adds up to two PostgreSQL connections. Limits constrain failure
impact; they do not guarantee adequate performance. Measure CSV/forecast workloads
before allowing larger operator jobs. Use 1–2 GiB swap as a fallback, not as RAM capacity.

Plan 40–80 GiB SSD with disk alerts, bounded logs and image retention. Build images
on CI rather than concurrently compiling three Angular apps on the VPS. Never run
all migration jobs concurrently on a 4-GiB host. Each app has independent backup and
restore schedules and an off-host encrypted backup destination.

## Cost allocation

Target $10–16/month for compute and $1–3 for off-host backups: $11–19 total with AI
disabled, excluding taxes and domain renewal. Confirm actual regional offers before
any purchase. No provider was selected or purchased here. Keep hosted inference off
until separately approved with a provider spending limit; app request caps alone do
not guarantee a dollar budget. If a 4-GiB plan exceeds $20, reduce scope/traffic or
adjust the budget rather than introducing a GPU or running qwen3:4b on the same host.

## Recovery independence

Back up each database separately, with app-specific paths, encryption and credentials.
A restore must target a new database or disposable replacement stack; never drop an
existing database to test recovery. Preserve Caddy TLS state and each app's daily AI
usage volume across releases. See BACKUP_RESTORE.md and DEPLOYMENT.md.
