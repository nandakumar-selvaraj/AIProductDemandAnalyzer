# Secret/configuration checklist

No secret values were inspected or generated.

All dedicated values live in the **`aiproductdemand-production`** GitHub Environment (Phase 5.16.1), never at repository or organization level. Names are namespaced so a same-named repository or organization secret cannot be picked up as a fallback. The shared `production` Environment and its `UPCLOUD_TOKEN` are not used by dedicated workflows.

| Environment secret | Purpose |
|---|---|
| `AIPD_UPCLOUD_TOKEN` | UpCloud API credential; owner adds it (the value is never copied by automation) |
| `AIPD_TF_STATE_ACCESS_KEY_ID`, `AIPD_TF_STATE_SECRET_ACCESS_KEY` | Dedicated IAM principal scoped to this project's state, lock, plan prefix and KMS key |
| `AIPD_DEPLOY_SSH_PRIVATE_KEY` | Distinct unencrypted OpenSSH Ed25519 deployer key (structure-checked) |
| `AIPD_DEPLOY_SSH_KNOWN_HOSTS` | Exactly one `IP ssh-ed25519 KEY` line, console-verified |

Environment variables, all required with no workflow defaults:

* State: `AIPD_TF_STATE_BUCKET`, `AIPD_TF_STATE_REGION`, `AIPD_TF_STATE_KMS_KEY`.
* Server: `SINGLE_UPCLOUD_ZONE` (must be `sg-sin1`), `SINGLE_UPCLOUD_PLAN`, `SINGLE_STORAGE_TIER` (`standard` or `maxiops`).
* SSH keys: `SINGLE_OPERATOR_PUBLIC_KEY`, `SINGLE_DEPLOY_PUBLIC_KEY`.
* Access and deployment: `SINGLE_SSH_ALLOWED_CIDRS` (JSON list of public IPv4 networks, /24 or narrower), `SINGLE_DEPLOY_HOST`, `SINGLE_DEPLOY_HOST_KEY_FINGERPRINT` (`SHA256:...`, from the console), `SINGLE_DEPLOY_RUNNER_LABEL`.

Runtime-only secrets: `POSTGRES_PASSWORD` (owner), `APP_DB_PASSWORD` (runtime), exact backend name `JWT_SIGNING_SECRET`; `DATABASE_URL` and `MIGRATION_DATABASE_URL` contain secret credentials too. Install manually as `/etc/demand/runtime.env`, root:root 0600, from example. These do not need GitHub copies because workflow does not transport them. If recovery policy stores copies in GitHub, use protected Environment secrets under these names; workflows do not consume them.

Set HTTPS `AUTH_ALLOWED_ORIGINS` and exact `TRUSTED_HOSTS` JSON, including localhost/127.0.0.1 for checks. Generate >=64 random JWT characters directly to protected storage using trusted cryptographic generator, never logs. URL-encode DB passwords in URLs; use URL-safe generated secrets or proper literal env quoting to avoid Compose `$` interpolation. AI is disabled; no AI key required.

Backup: root-only `/etc/demand/backup.env`, Restic HTTPS repository/scoped storage key and `RESTIC_PASSWORD_FILE`; password file root:0600 and separately escrowed. State/backup identities and repositories should be distinct, with approved retention/cost.

Future rotation only: JWT replacement invalidates signatures/CSRF material; revoke sessions/tokens and restart backend in maintenance. DB role and both URLs must change together; initializer does not rotate existing roles. Verify alternate SSH access before replacing/revoking keys. Never put secrets in frontend, images, Terraform, artifacts or reports.
