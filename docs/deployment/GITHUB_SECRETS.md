# Secret/configuration checklist

No secret values were inspected or generated.

| Protected production secret | Purpose |
|---|---|
| `UPCLOUD_TOKEN` | Existing UpCloud API credential |
| `TF_STATE_ACCESS_KEY_ID`, `TF_STATE_SECRET_ACCESS_KEY` | Approved S3/KMS state/private plan access |
| `DEPLOY_SSH_PRIVATE_KEY` | Distinct restricted deployer key |
| `DEPLOY_SSH_KNOWN_HOSTS` | Console-verified SSH host identity |

Protected variables: `TF_STATE_BUCKET`, `TF_STATE_REGION`, `TF_STATE_KMS_KEY`, `SINGLE_UPCLOUD_ZONE` (sg-sin1 default), required `SINGLE_UPCLOUD_PLAN`, `SINGLE_STORAGE_TIER` (standard default), `SINGLE_OPERATOR_PUBLIC_KEY`, `SINGLE_DEPLOY_PUBLIC_KEY`, `SINGLE_SSH_ALLOWED_CIDRS` (JSON), `SINGLE_DEPLOY_HOST`, `SINGLE_DEPLOY_RUNNER_LABEL`.

Runtime-only secrets: `POSTGRES_PASSWORD` (owner), `APP_DB_PASSWORD` (runtime), exact backend name `JWT_SIGNING_SECRET`; `DATABASE_URL` and `MIGRATION_DATABASE_URL` contain secret credentials too. Install manually as `/etc/demand/runtime.env`, root:root 0600, from example. These do not need GitHub copies because workflow does not transport them. If recovery policy stores copies in GitHub, use protected Environment secrets under these names; workflows do not consume them.

Set HTTPS `AUTH_ALLOWED_ORIGINS` and exact `TRUSTED_HOSTS` JSON, including localhost/127.0.0.1 for checks. Generate >=64 random JWT characters directly to protected storage using trusted cryptographic generator, never logs. URL-encode DB passwords in URLs; use URL-safe generated secrets or proper literal env quoting to avoid Compose `$` interpolation. AI is disabled; no AI key required.

Backup: root-only `/etc/demand/backup.env`, Restic HTTPS repository/scoped storage key and `RESTIC_PASSWORD_FILE`; password file root:0600 and separately escrowed. State/backup identities and repositories should be distinct, with approved retention/cost.

Future rotation only: JWT replacement invalidates signatures/CSRF material; revoke sessions/tokens and restart backend in maintenance. DB role and both URLs must change together; initializer does not rotate existing roles. Verify alternate SSH access before replacing/revoking keys. Never put secrets in frontend, images, Terraform, artifacts or reports.
