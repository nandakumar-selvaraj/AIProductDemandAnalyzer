> Phase 5.17: follow [manual provisioning](UPCLOUD_MANUAL_PROVISIONING.md) and [current audit stop gates](PHASE_5_17_FINAL_VALIDATION.md). Commands below are future separately authorized operations, not part of this audit. Active backups use [encrypted SFTP/Restic](BACKUP_RESTORE.md); no dedicated Terraform/S3/KMS is required.

# PostgreSQL

The dedicated image is built from `deploy/postgres/Dockerfile`: pinned official PostgreSQL 16.15 Alpine, with its obsolete Go-based gosu helper replaced by pinned native su-exec. The entrypoint privilege-drop command is adapted; PostgreSQL binaries, major version and data layout are retained. Build/scans publish only the repaired image under `ghcr.io/nandakumar-selvaraj/aiproductdemandanalyzer/postgres`, deployed by digest. Do not substitute the unmodified vulnerable upstream image.

Dedicated database `demand`; privileged bootstrap/DDL owner `demand_owner`; runtime `demand_app` is NOSUPERUSER/NOCREATEDB/NOCREATEROLE. No host port, internal database network only.

On empty volume initializer creates runtime role, revokes public schema CREATE, sets default DML/sequence grants. Existing migrations revoke broad auth_users access, retaining runtime SELECT/password-hash UPDATE; API token table runtime SELECT only. Runtime cannot create administrators. No demo database/reader is created here.

Revisions: `0001_initial`, `0002_authentication`, `0003_api_tokens`. Release applies owner migrations then compares MigrationContext database heads with image ScriptDirectory heads. Pinned Alembic1.16.5 does not support `current --check-heads`.

Owner and runtime passwords are distinct. Initializer runs once; changing env does not alter existing roles. Never delete a volume for credential mismatch. PostgreSQL major/minor digest changes after initial success require separate reviewed upgrade procedure; normal release refuses them.

After approval verify role grants/migration revision, data/user persistence through restarts and deploys against isolated test data first. Account management uses owner migration service, not runtime backend. See admin, backup and rollback runbooks.
