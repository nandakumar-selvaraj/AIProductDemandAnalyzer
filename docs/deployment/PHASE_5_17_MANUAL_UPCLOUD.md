# Phase 5.17 — manual UpCloud host and approved application releases

## Dependency audit (before implementation)

| Area | Existing dependency | Phase 5.17 decision |
| --- | --- | --- |
| Dedicated provisioning | `single-terraform-{plan,apply,destroy}.yml`, `infra/automation.py`, `infra/terraform` | Archive workflow definitions outside Actions discovery; retain all Terraform source/state |
| Dedicated CI | `single-validate.yml` installs Terraform and validates its provider | Remove provider/backend requirement; retain offline historical policy tests and security checks |
| Shared portfolio | `terraform-{plan,apply,validate}.yml`, `production-deploy.yml`, `infrastructure/`, `deploy/ops`, `compose.production.yml` | Preserve unchanged |
| Application CI | `backend-ci.yml`, `e2e.yml`, `docker-validation.yml` | Preserve backend, Angular, synthetic DB/browser and image validation gates |
| Release | `single-deploy-production.yml` builds/scans GHCR digests, then `infra/deploy_transport.py` | Retain protected dedicated environment and restricted SSH; separate automatic image publication from approved release |
| Authorization | `infra/guards.py`, shared low-level GitHub helpers | Preserve master, independent review, no self-review/admin bypass, fixed egress and Ed25519 pin checks |
| Runtime | `compose.prod.yml`, `deploy/single`, `deploy/postgres`, backend/ui Dockerfiles | Preserve external PostgreSQL 16 volume, internal DB network, owner migrations and nginx-only published ports |
| Host setup | Dedicated cloud-init template | Manual bootstrap exists but rerun/lockout safety remains unverified; see final audit |
| State | Dedicated AWS S3, KMS, AWS CLI, plan lock/approval | Retire from active dedicated path; retain historical material |
| Backups | `backup.sh`, Restic S3, `restore-verify.sh` | Encrypted Restic over pinned SFTP to owner-controlled off-server host; require verified repository/restore before release |
| Rollback | `release.py` records active/previous digests, verifies HTTPS/readiness | Preserve volume, reject DB image changes, no destructive schema rollback |
| Admin | `scripts/manage_users.py` in owner migration context | Manual after separately authorized deployment; no default administrator |
| Tests | `infra/tests`, `infrastructure/tests`, backend unit/integration, Angular, disposable Docker | Add manual-host and backup failure regressions; run available local checks |

This audit was recorded before source changes. Live UpCloud status is unknown. No existing resource or state is assumed absent or safe to remove. This phase permits local source changes and validation only.

## Target and boundaries

One manually provisioned Ubuntu 24.04 VPS in `sg-sin1`, Docker Compose, PostgreSQL 16, Angular/FastAPI and TLS nginx. No AWS, Terraform backend or paid object-storage dependency. Off-server backup capacity and fixed-egress runner availability must be independently arranged; neither is presumed free.

Host provisioning is an owner operation. Application release is a separately approved GitHub operation. The deployer cannot update root-owned code, Compose files, TLS or secrets; owners install reviewed host artifacts manually. A release transfers only an allowlisted immutable image manifest over SSH.

See [manual provisioning](UPCLOUD_MANUAL_PROVISIONING.md), [GitHub Actions](GITHUB_ACTIONS.md), [backup/recovery](BACKUP_RESTORE.md) and [acceptance](ACCEPTANCE.md). Final executed validation is recorded in [final validation](PHASE_5_17_FINAL_VALIDATION.md).
