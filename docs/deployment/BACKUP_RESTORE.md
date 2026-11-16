# Encrypted PostgreSQL backup, restore and retention

Use one authorized SFTP repository on a separate failure domain. Confirm the remote operator, storage, quota, transfer costs, recovery access and independent access controls. The host rejects its own assigned IPv4s, while the owner verifies the physical and administrative separation, including NAT. Plan for daily transfer and isolated restore capacity. Dedicated Terraform and AWS are inactive.

## Setup and initial acceptance

Use a dedicated restricted SFTP account and key, an independently verified pinned Ed25519 host key, and a separately escrowed Restic password. Store `backup.env`, `backup-key`, `backup-known-hosts` and `restic-password` under `/etc/demand` as root with mode 0600. See `deploy/single/backup.env.example` for variable names. Configure the preapproved SFTP repository and verify Restic can read its identity. Initializing a repository is a separately authorized operator action.

Start only the reviewed PostgreSQL service and its external volume. Pull the approved PostgreSQL 16 digest first. Before the first migration, run:

```bash
/opt/demand/backup.sh --bootstrap
/opt/demand/backup-preflight.sh
```

Bootstrap acceptance expects an empty, uninitialized application schema. After the first successful release, rerun `/opt/demand/backup.sh` and verify that the active schema and business evidence are accepted, then verify the daily timer and monitoring. The release host preflight requires the backup timer to be enabled. Enable it following initial backup acceptance, before first deployment. Start the monitoring timer after the TLS marker, runtime configuration and backup readiness are in place, before first deployment.

```bash
systemctl enable --now demand-backup.timer
# After TLS and initial backup acceptance
systemctl enable --now demand-monitor.timer
```

The daily timer triggers at 02:00 UTC. Each backup invalidates old acceptance before reading configuration, then exports a read-only PostgreSQL snapshot. The source evidence query and `pg_dump -Fc` use that same transaction snapshot. Restic streams authenticated encrypted data over pinned SFTP and tags it with a unique operation ID. The host checks both subprocess statuses and resolves the full remote snapshot ID before recording completion. A failed or terminated stream may leave an orphaned remote snapshot. It cannot become a completed backup or count toward retention.

## Isolated restore and deployment gate

Backup automatically verifies its exact completed snapshot. To repeat a failed or planned drill, read the exact `id` and operation from the root-private `/var/lib/demand/backup-completed.json`, then run:

```bash
/opt/demand/restore-verify.sh FULL_SNAPSHOT_ID
/opt/demand/backup-preflight.sh
```

A drill first removes the previous acceptance. It checks repository integrity and reads every byte of the selected authenticated archive into a new network-disabled PostgreSQL 16 restore container with no published ports or production mounts. The isolated target uses tmpfs (512 MB data, 768 MB memory cap). `pg_restore` uses one transaction and exits on error. The expected Alembic revision and authentication columns must match, as must the table counts and total units sold from the source transaction. The backup policy currently expects `0003_api_tokens`. Review and rehearse backup policy with future schema changes.

A successful restore and cleanup publish a root-owned 0600 receipt atomically. It binds the repository ID, configuration fingerprint, exact snapshot, backup operation, expected revision, data evidence, timestamp and integrity result. The release gate checks it against the latest completion and remote repository. A missing, failed, changed or more-than-26-hour-old backup blocks release. Pre-migration backups and daily backups both require restore acceptance. Manual backup and restore serialize with releases. If forced termination leaves a test container behind, identify the exact `demand-restore-*` ID and inspect it before owner cleanup. Never remove the production volume.

Aim for a 24-hour scheduled recovery point plus an on-demand verified pre-migration backup. Measure restore time and capacity with representative data before go-live. The local rehearsal cannot establish an off-server production recovery time.

## Explicit retention review

```bash
/opt/demand/backup-retention.sh
```

This command only returns an exact candidate list after current backup acceptance passes. It protects the latest accepted snapshot plus the most recent accepted point in each of 7 distinct UTC days, 4 ISO weeks and 2 calendar months. Incomplete, orphaned or unrecognized snapshots are excluded from both the keep calculation and deletion candidates. Backups, releases and timers never forget or prune.

For separately approved deletion, pause backup and release scheduling in a reviewed maintenance window, regenerate the proposal, recheck repository identity and preserve the latest accepted recovery points. Use only the approved full snapshot IDs for an explicit Restic forget operation. Review prune separately after signed-off inventory and recovery checks. Keep independent copies or storage-side retention as appropriate. A failed backup or drill blocks the retention proposal until a new successful acceptance.
