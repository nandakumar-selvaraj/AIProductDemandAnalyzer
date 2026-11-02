# Backup and recovery

Objectives: RPO <=24h with successful daily02:00 UTC backups, plus pre-update backup; target RTO2h for small demo dataset, pending measured live drill. These are objectives, not guarantees. Docker volume alone is not a backup.

`backup.sh` streams owner pg_dump -Fc into Restic authenticated client-side encryption over required HTTPS S3 endpoint. Pipefail catches dump errors, separate lock serializes backup; root-only config/password; no plaintext dump persisted. Each run checks10% repository data and retains7 daily/4 weekly/2 monthly snapshots. Prune policy applies to this dedicated repository/tag; do not share repository with unrelated apps. Escrow Restic password off-server.

Off-host repository needs separate cost/destination/security approval, scoped credentials and private storage. No bucket/repository created. Review object-lock/recovery policy where supported. Dump is transactionally consistent with concurrent DB writes.

After approval manually initialize repository, run backup, record snapshot ID, then `/opt/demand/restore-verify.sh SNAPSHOT_ID`. It restores to ephemeral PostgreSQL with --network none, no public ports or production volume, 512MB tmpfs, and verifies Alembic revision/user count. Increase isolated test budget for larger dump. Review business-table counts and application queries too. No production administrator is created by drill.

Only after off-host backup and isolated restore pass enable `demand-backup.timer`. Monitor timer age/service failures/journal, repository checks and operator alerts; periodically run full `restic check --read-data` and timed drills. Unit is installed but not automatically enabled.

Production recovery requires approval/maintenance: block writes, preserve failed volume, restore chosen dump into NEW empty database/volume, recreate reviewed owner/runtime roles/grants, review owner/ACL restore policy, verify revision/business rows/users, test privately then switch runtime config and verify HTTPS. Logical dumps exclude cluster roles; use audited initializer/grants, not arbitrary superuser role restore.

Failed migration: preserve snapshot/logs, inspect partial DDL and exact revision; prefer verified forward fix. Incompatible rollback requires restored DB and matching prior app under maintenance. Never automatically downgrade Alembic/reset/delete volume. See acceptance for local synthetic checks; production off-host backup/scheduling remain NOT TESTED.
