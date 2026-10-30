# Phase 8A validation report — 2026-10-30

## Executed locally

| Check | Actual result |
|---|---|
| Terraform 1.17.1 formatting | Passed |
| `terraform init -backend=false` | Passed; official UpCloud provider 5.48.0 downloaded and signature verified; no account credentials used |
| `terraform validate` | Passed |
| `terraform test` | 3 mocked-plan tests passed: domain-free server/storage/cloud-init contract, world-open SSH rejection, root deployment-user rejection |
| Provider lock | Linux amd64 and Windows amd64 checksums recorded in `.terraform.lock.hcl` |
| Infrastructure Python tests | 18 passed; sanitized summaries, deletion/replacement rejection, release/input injection, digest restrictions, DNS gating, missing secrets, Environment checks, run provenance, safe artifact redirects |
| Ruff | Passed for infrastructure and host operations |
| Actionlint 1.7.12 | Passed for all repository workflows |
| Trivy 0.76.1 Terraform config scan | No HIGH/CRITICAL findings; UpCloud rule coverage is limited, not proof of full infrastructure security |
| Trivy source secret scan | No findings in tracked/proposed files; ignored local `.env`, keys, state, caches and datasets were not scanned or printed |
| Bash syntax | Bootstrap and backup/restore/monitor wrappers passed syntax-only checks; bootstrap was not executed |
| Shared VPS Compose rendering | Passed: digest-only app images, no app/DB host ports, separate internal DB/edge networks, bounded resources, shared Caddy ports 80/443 |
| Generated shared Caddy config | Passed inside a network-disabled read-only container; no real certificate requested |
| Backend | 200 passed, 1 opt-in PostgreSQL integration skipped in the main suite |
| Angular | 266 passed (19 files); lint and production build passed, 662.77 kB initial / 122.53 kB estimated transfer |
| Disposable production Docker validation | Passed completely on Docker Desktop Linux Engine 29.1.3; PostgreSQL initialization/migrations, synthetic users/data, TLS, readiness, JWT/API token/RBAC, source-preserving backup/restore, restart and container-recreation persistence |
| Production browser E2E | Linux Chromium: 3 public-demo + 6 authentication/upload cases passed; 1 Swagger case intentionally skipped because production docs are disabled |
| Git whitespace | Passed |

The first backend invocation inherited the user's newly enabled local AUTH_ENABLED=true
configuration and nine legacy unauthenticated-route tests returned 401. The suite was
rerun with **process-only** ENVIRONMENT=test/AUTH_ENABLED=false, its established legacy
test profile. Dedicated authentication tests still construct enabled production settings
and validate JWT/RBAC/CSRF. No local `.env` or application authentication was changed,
no test was removed/skipped to hide the failure, and the full rerun passed 200 tests.

Docker was initially stopped/unavailable; after the user started it, the engine and
disposable stack checks completed. The new Caddy profile initially dropped the binary's
required NET_BIND_SERVICE file capability and refused execution; it now adds **only**
that bind capability while dropping all others and retaining no-new-privileges/read-only
root. Caddy config validation then passed. PostgreSQL's public init script was also given
read access for the image's unprivileged entrypoint; no secret is embedded in that script.

## Not executed / external prerequisites

- No real Terraform provider plan, remote backend initialization, apply or destroy.
- No UpCloud resource, DNS change, paid service, real production secret/account, cloud
  deployment, GHCR publication or push. A local commit was explicitly requested after review.
- New Phase 8A workflows have not run in GitHub. Their syntax and
  local safety contracts passed; successful local checks do not establish hosted CI results.
- The live GitHub `production` Environment was **not created/configured**. The connector
  lacks Environment mutation tools; browser computer-use was stopped by its URL-confidence
  safety check. It was not retried or bypassed. An owner must create/protect the Environment
  and select a genuine independent reviewer. Workflows reject missing/unprotected settings.
- State/KMS provisioning, access policies, lock contention/recovery, real saved-plan apply
  and GitHub reviewer enforcement need an explicitly authorized Phase 8B acceptance run.
- Ubuntu cloud-init execution, virtio disk mapping, SSH/firewall verification and mount
  failure behavior have not been tested on a VPS. Syntax/schema/mock checks are not a
  claim of successful machine bootstrap. Never run bootstrap against an existing machine.
- The existing standalone disposable Docker stack passed. The newly installed host release
  entrypoint/shared-ingress transaction and real encrypted off-host Restic repository have
  not been exercised on a real server/S3 identity. Verify initialization, retention,
  restore, schema compatibility, host-key pinning and failure recovery before public launch.
- Real subdomain/DNS/public CA issuance is intentionally deferred until the server IP
  exists. No insecure public HTTP workaround is configured.
- Review plan/zone capacity and total compute + extra encrypted disk + state/KMS + backup
  + IPv4 costs against $10–$20/month. No vendor price or affordable capacity is guaranteed.
- Arrange static trusted deployment-runner egress, public/read-only GHCR pulls, operator
  key custody, independent reviewer, external alerts, image scanning outcomes and actual
  CSV/forecast load measurements before activation.

The prepared automation is ready for repository review and local checks are green.
Live provisioning/deployment remains gated; this report is not authorization to run it.
