# Backup and restore

## Phase 8A automated host recovery

The standalone scripts below remain available for disposable/local validation. The new
shared VPS uses root-owned `deploy/ops/operations.py` through backup/restore shell wrappers.
Before any migration it streams pg_dump directly into Restic's authenticated client-side
encryption in a separate HTTPS off-host S3 repository. It then runs Restic integrity checks,
restores the latest tagged dump into a newly created `restore_verify_<time>_<pid>` database,
queries its catalog, and deletes only that newly created verification database. It never
drops/replaces an existing application database. Any failure blocks migration/deployment.

Configure `/etc/portfolio/backup.env` and its Restic password file as root-owned 0600;
use deploy/ops/backup.env.example. These are server-only credentials, distinct from
UpCloud, GitHub SSH and Terraform-state identities. Approve/create backup storage and
explicitly initialize its dedicated Restic repository before first deployment. No cloud
backup bucket, credentials or repository were created in Phase 8A. Store the encryption
passphrase in a separate encrypted recovery vault; losing it makes backups unusable.

A systemd timer backs up daily with jitter, retaining 7 daily/4 weekly/3 monthly snapshots
tagged `demand` in this app's dedicated repository. Retention/prune is intentionally
confined to that backup repository; never share it with Terraform state or another app.
Review retention/cost/recovery objectives before activation. Local monitoring rejects a
backup older than 26 hours. Assign off-host alerting separately: timers/journald cannot
report a completely failed VPS by themselves. Prove an off-host recovery in authorized
Phase 8B; local standalone Docker restore success is not proof of real off-host access.

For disaster recovery, stop writes, select the intended snapshot, restore to a NEW
database/replacement stack, apply the private ACLs below, verify schema/row counts and
application connectivity, then approve the connection cutover. Preserve the old database.
Take signing/backup configuration from the separate vault, and rotate JWT signing keys
if restoring old session/token rows could revive revoked access. Do not automatically
restore over a running database, downgrade schema or remove volumes.

Application rollback uses a previously successful image manifest and keeps the current
database/schema/ingress/domain. Schema-incompatible releases require a forward fix or an
explicit new-database restore/cutover, not an automatic migration downgrade. See
[UpCloud runbook](UPCLOUD_RUNBOOK.md) and [state recovery](TERRAFORM_STATE.md).

Scripts run on the Linux host from repository root using `.env.production` and
`compose.production.yml`. They never target development or seed/reset data.

```sh
sh deploy/backup.sh
sh deploy/restore.sh backups/demand-TIMESTAMP.dump demand_restore_20261028
```

Backup uses PostgreSQL custom-format `pg_dump`, restrictive umask and atomic rename;
partial dumps are removed on failure. It is transaction-consistent without stopping
reads/writes. The script does not prune backups. Schedule daily using a host timer only
after deployment approval; encrypt copies before copying off-host. Keep at least seven
daily and four weekly copies subject to storage budget. Alert on missing/failed backups.
A backup on the same VPS does not protect against disk/host loss.

Restore requires a new lowercase database name and fails if it already exists. It never
uses DROP, --clean, or overwrites an existing DB. Failed restores may leave an empty new
DB for operator inspection. Never reuse a failed target automatically. Use PostgreSQL
16 client/container for these dumps. Globals (roles), env secrets and TLS configuration
are separate recovery assets, not included in pg_dump. Securely back up secrets and
provider settings in an encrypted password manager. Caddy can renew certificates.

After restoring, grant runtime rights using the owner in the restored DB:

```sql
GRANT USAGE ON SCHEMA public TO demand_app, demand_demo_reader;
GRANT SELECT, INSERT, UPDATE, DELETE ON stores, products, sales_history, inventory,
  forecast_runs, forecast_run_logs, product_forecasts, stock_recommendations TO demand_app;
GRANT USAGE, SELECT ON ALL SEQUENCES IN SCHEMA public TO demand_app;
GRANT SELECT ON stores, products, sales_history, inventory, forecast_runs,
  forecast_run_logs, product_forecasts, stock_recommendations TO demand_demo_reader;
REVOKE ALL ON auth_users, auth_sessions, auth_api_tokens FROM demand_demo_reader;
REVOKE ALL ON auth_api_tokens FROM demand_app;
GRANT SELECT ON auth_api_tokens TO demand_app;
REVOKE ALL ON auth_users FROM demand_app;
GRANT SELECT ON auth_users TO demand_app;
GRANT UPDATE(password_hash) ON auth_users TO demand_app;
GRANT SELECT, INSERT, UPDATE, DELETE ON auth_sessions TO demand_app;
ALTER DEFAULT PRIVILEGES IN SCHEMA public REVOKE SELECT ON TABLES FROM demand_demo_reader;
```

Verify Alembic revision, row counts, latest forecast/reports and `/api/v1/ready` using
an isolated API instance pointed at the restored DB. Only then stop writes, change
DATABASE_URL and recreate backend. Preserve the original DB for rollback. Rehearse a
full restore before public launch and periodically afterwards. Initial target objectives:
RPO 24 hours with daily backups, RTO 1 hour; neither has been measured here.

AI daily usage persists separately in the `ai_usage` volume. Preserve this volume across
releases; a disaster recovery that loses it resets the app cap, so provider-side billing
limits remain necessary. Never use `docker compose down -v` in the recovery procedure.


## Phase 7B automation and isolation

`deploy/validate_docker.py` exercises these real scripts against a fresh random project,
compares five tables after restoring to a new database, and connects the application's
read-only demo engine to the restored database. It also checks source counts remain
unchanged. This is configured in `.github/workflows/docker-validation.yml`; it has not
run locally because Docker Engine is unavailable.

Scripts accept COMPOSE_ENV_FILE (default .env.production), COMPOSE_EXTRA_FILE (optional
validation overlay), and BACKUP_DIRECTORY (backup only; default backups). Keep the same
Compose project name throughout. These overrides enable isolated testing without
reading or changing production configuration. Dump and env files must not be uploaded
as CI artifacts. A restored public demo requires SELECT grants for demand_demo_reader
and the synthetic-v1 database marker after verification; retain normal runtime grants
above for operator connectivity. Never mark a private database as a demo.


Auth tables (including auth_api_tokens from revision 0003) contain password hashes and revocation state and are part of the database
backup. Encrypt them off-host and restrict access. JWT signing keys remain separate
server secrets and are not in the DB dump. A restore can reintroduce previously active
session rows from the snapshot: rotate the signing key on disaster recovery to invalidate
all old JWTs and require a new login. Reapply the explicit ACLs above after `--no-acl`
restores. Never grant the demo reader SELECT on auth tables or future tables by default.
