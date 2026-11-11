# Encrypted SFTP/Restic backup and recovery

Active dedicated scripts are deploy/single/{backup-common,backup-preflight,backup,restore-verify}.sh. Earlier S3/HTTPS object-storage instructions are HISTORICAL AND INACTIVE for this path. No backup account or repository was created.

pg_dump -Fc streams with pipefail directly into Restic client-side authenticated encryption over pinned SFTP. No plaintext dump is intentionally persisted. Use a separate public off-server IPv4, dedicated restricted SFTP account and independently verified host key. The script's hostname-based self-address check cannot prove a separate failure domain: verify different host/storage/account manually. Escrow the Restic password independently; losing it prevents recovery.

After separate authorization install the four root-owned 0600 files described in [configuration](GITHUB_SECRETS.md). Confirm repository capacity, access and retention. Owner root-shell commands for future authorized work:

```bash
source /opt/demand/backup-common.sh
restic_safe snapshots
# Only for a separately authorized, confirmed NEW empty repository:
# restic_safe init
```

An unreachable repository is not permission to initialize or replace it. Diagnose connectivity, pin, password and destination.

After separately approved initial database-only setup with reviewed bootstrap image digests, run /opt/demand/backup.sh --bootstrap; later use /opt/demand/backup.sh. WARNING: this script also prunes snapshots (7 daily, 4 weekly, 2 monthly). Obtain retention/deletion authorization first; this audit did not execute it.

Select the exact snapshot from restic_safe snapshots --tag demand-single, then use /opt/demand/restore-verify.sh SNAPSHOT_ID. It checks all repository data and imports into isolated PostgreSQL with no network, public port or production volume, using pg_restore --exit-on-error. Data tmpfs is 512MB, memory limit 768MB; larger datasets need reviewed isolated capacity. Record snapshot, source revision, expected business counts/queries and measured restore time externally.

## Open audit findings

- Bootstrap verification only runs SELECT 1; post-release checks read Alembic/auth tables but do not assert expected revision/counts. Successful import is real; semantic verification is incomplete.
- A failed drill leaves an older receipt usable for up to 35 days. Receipt binds configuration, not snapshot/data. Preflight checks structure and receipt age, not a fresh restore. This is not strict fail-closed restore acceptance.
- Failed pg_dump can still leave a partial snapshot finalized by Restic before pipefail reports failure. Never select latest without exact successful-backup evidence.
- Prune occurs before the new snapshot passes restore verification. Review separate retention before production reliance.

Remediation and isolated failure-injection tests are required. Never fabricate a receipt or bypass preflight. See [final evidence](PHASE_5_17_FINAL_VALIDATION.md).

After real off-host restore verification and approved retention, enable demand-backup.timer and verify timer/service/alerts. Bootstrap installs but does not enable it. Objectives: RPO <=24h (02:00 UTC daily plus pre-release), RTO <=2h for small demo data; neither measured nor guaranteed.

Recovery requires separate approval: stop writes, preserve failed volume, restore into a NEW isolated empty database/volume, reconstruct owner/runtime grants, verify revision/business data/auth and compatible images, then switch after private acceptance. Dumps omit cluster roles. Never reset, downgrade, overwrite production data, run down -v or delete storage during ordinary recovery. Escrow runtime configuration, release manifests and keys separately; these scripts back up the DB, not the whole host.
