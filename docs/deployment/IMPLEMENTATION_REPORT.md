> HISTORICAL AND INACTIVE for the Phase 5.17 dedicated manual deployment. Do not execute Terraform, AWS, S3/KMS or teardown instructions below. Preserve existing resources/state. Prior passes are not current evidence. Use [manual provisioning](UPCLOUD_MANUAL_PROVISIONING.md) and [final validation](PHASE_5_17_FINAL_VALIDATION.md).

# Phase 5 implementation report — 2026-11-02

**READY FOR REVIEW after local image-security remediation.** All four dedicated runtime images pass the unchanged HIGH/CRITICAL gate with zero findings. Application dependency versions and behavior are preserved. This is not permission to provision or deploy; live configuration/acceptance gates remain. See [security evidence](IMAGE_SECURITY.md) and [remediation validation](REMEDIATION_VALIDATION.md).

## 1. Repository baseline — PASS

Inspected backend/UI/models/migrations/auth/management/health/API/test/build/deployment configuration. Working existing architecture and exact implementation details are recorded in [ARCHITECTURE](ARCHITECTURE.md). Existing shared infrastructure differs from this dedicated-app request; it is retained, not repurposed. All original workflows preserved.

## 2. Architecture — PASS

One dedicated Ubuntu24.04 VPS, preferred Singapore, explicit UTC, encrypted30GB boot disk, single IPv4. Nginx ingress -> Angular static frontend or FastAPI -> private PostgreSQL. AI/public demo disabled by default; existing application remains available for authenticated use. No other demo infrastructure configured.

## 3. Files created/modified — PASS

Created:

- `infra/terraform/versions.tf`, `variables.tf`, `main.tf`, `outputs.tf`, `cloud-init.yml.tftpl`, `.terraform.lock.hcl`, `terraform.tfvars.example`, `backend.hcl.example`, `tests/single.tftest.hcl`.
- `infra/automation.py`, `deploy_transport.py`, `validate.py`, `validate_containers.py`, `tests/test_single_safety.py`.
- `compose.prod.yml`.
- `deploy/single/init-db.sh`, `nginx.stage-a.conf`, `nginx.tls.conf`, `release.py`, `release-entry.sh`, `harden-ssh.sh`, `backup.sh`, `restore-verify.sh`, `renew-certificate.sh`, `runtime.env.example`, `backup.env.example`.
- `.github/workflows/single-validate.yml`, `single-terraform-plan.yml`, `single-terraform-apply.yml`, `single-terraform-destroy.yml`, `single-deploy-production.yml`.
- `backend/requirements.production.lock.txt` (43 exact installed Linux/Python3.13 package versions).
- `deploy/postgres/Dockerfile` (PostgreSQL16 with native privilege helper), `deploy/single/images.json` (approved ingress digest), `infra/scan_images.py` (local immutable-image vulnerability gate).
- All16 requested deployment runbooks, this report and [image findings](IMAGE_SECURITY.md).

Modified: root README (deployment links), `.gitattributes` (Linux script LF), existing backend/UI Dockerfiles (maintained pinned bases; backend transitive lock; build-only installer tooling excluded from runtime; UID/GID1000 retained), `ui/nginx.conf` (index revalidation/static cache), `ui/angular.json` (production critical-CSS inlining disabled so its inline loader cannot violate self-only script CSP). Dedicated workflow, transport/controller and restore allowlists use the repaired PostgreSQL repository and current Nginx namespace. No application logic, endpoint or migration edits. No commit/push performed.

## 4. Terraform resources — PASS

Exactly one `upcloud_server.app` and one `upcloud_firewall_rules.app`. Boot disk belongs to server template; no extra storage/IP resources. Prevent-destroy barrier, labels, operator/public keys and nonsecret outputs. Official provider5.48.0 locked; no guessed plan default. [Terraform](TERRAFORM.md), [UpCloud setup](UPCLOUD_SETUP.md).

## 5. Terraform validation — PASS; live catalog/state — NOT TESTED

Formatting, backend-disabled signed-provider initialization, schema validation, two mock tests and static Trivy configuration scan passed. Offline checks cannot prove Singapore capacity, selected plan/tier compatibility or live plan safety. Existing encrypted/versioned/locked S3/KMS backend must be approved/configured; no local fallback.

## 6. Docker Compose — PASS functional; image security — PASS

Real DB/migration readiness gates, runtime/migration credential separation, non-root applications, limits, logs, private networks, external persistent volume, no public DB/backend. Stage A blocks app/login. Builds, Compose syntax and disposable stack functional checks pass. All four repaired runtime artifacts pass the security threshold; historical failures remain in the baseline report.

## 7. GitHub workflows — PASS static; live protection — NOT TESTED

Separate dedicated validation/plan/apply/deploy/destroy workflows. Cloud operations manual only, production reviewers/branch policy checked at runtime, least permissions, concurrency and exact saved-plan integrity/state checks. Deploy requires existing tests/builds and scans, digest-only manifests, pinned SSH/fixed egress, migrations/readiness/history/rollback. YAML cannot configure actual environment reviewers. See [actions](GITHUB_ACTIONS.md).

## 8. Secrets — PASS source scan; configuration — BLOCKED

Existing `UPCLOUD_TOKEN` reused by name only. State access pair, restricted deployer private key and pinned known_hosts documented; runtime owner/app passwords, credential URLs and exact `JWT_SIGNING_SECRET` stay in root-only host configuration. Backup credentials/password escrow separate. Source secret scan passed; no values displayed/generated/rotated. [Checklist](GITHUB_SECRETS.md).

## 9. SSH — PASS configuration; live access — NOT TESTED

Documented Windows Ed25519 generation, separate operator/CI keys, /24-or-narrower allowlist, no world-open runner SSH. Deployer forced fixed sudo command, no Docker-group access/PTY/forwarding. Operator retains audited bootstrap/recovery root authority. Explicit final hardening after key-access verification; console recovery prerequisite. [SSH](SSH_SETUP.md).

## 10. Authentication — PASS local; production — NOT TESTED

Reused Argon2id/strict HS256 JWT/HttpOnly Secure cookie/CSRF/DB revocation/live roles/account-status logic. No localStorage JWT redesign. Admin ingestion/create boundaries preserved; viewer evaluation/backtesting follow existing policy. Logout really revokes browser session. Global single-worker login admission is not per-client distributed rate limiting. Public Swagger remains intentionally disabled; public Swagger acceptance is BLOCKED without separately reviewed access policy. [Assessment](AUTHENTICATION.md).

## 11. Manual admin — PASS procedure; NOT TESTED production

Owner-only interactive `migrate` service runs existing `python -m scripts.manage_users create --email ... --role admin` after approved migration/TLS. Runtime backend cannot insert auth_users; using exec backend would violate current DB grants. Password confirmation/duplicate-email handling/reset/revocation documented. No production account created or production management command executed. [Procedure](ADMIN_USER_SETUP.md).

## 12. Backup/recovery — PASS local design/synthetic DB restore; off-host — NOT TESTED

Daily and pre-update pg_dump -> encrypted Restic HTTPS off-host storage, retention7daily/4weekly/2monthly, integrity checks, root-only secrets/escrow. Timer installed but disabled until successful off-host backup/isolated restore. RPO24h/RTO2h are unmeasured objectives. Local synthetic archive restored into separate database and row persistence verified; this does not prove off-host operations. [Recovery](BACKUP_RESTORE.md).

## 13. Rollback — PASS control tests; live rollback — NOT TESTED

Current/prior digest manifests, safe migrations, readiness/HTTPS checks and history. Health failure restores compatible old images without requiring old image's migration head to equal newer additive schema. Migration failure stops for manual recovery; no automatic downgrade. Failure-path tests verify old release metadata preserved and no downgrade. [Rollback](ROLLBACK.md).

## 14. Cost — provisional, approval BLOCKED

Official current Starter2vCPU/4GB/30GB list price EUR12/month; about EUR0.01786/h equivalent under28-day cap assumption, exact quote still required. Backup/state/KMS/runner/taxes additional and unselected. Pricing changes announced November16; recheck before spend. [Pricing source](https://upcloud.com/pricing/), [assumptions](COST_ESTIMATE.md).

## 15. Validation results

See [ACCEPTANCE](ACCEPTANCE.md) and [remediation validation](REMEDIATION_VALIDATION.md) for exact commands/results. Backend suite200passed/1opt-in test skipped (separate real PostgreSQL integration passed); Angular266passed; infrastructure safety33passed; Terraform mock2passed. Image builds/production Angular build, static workflows/security/source checks pass. Current runtime security: zero HIGH/CRITICAL findings across backend, frontend, repaired PostgreSQL and ingress. Previous50/72/26/72 findings remain archived as historical evidence. [Image evidence](IMAGE_SECURITY.md).

## 16. Remaining blockers

- **PASS:** image vulnerability blocker resolved without suppressions. Continue scanning every future immutable release; current zero findings is not a permanent guarantee.
- **BLOCKED:** no approved exact regional plan/tier/capacity quote, state/backup destination/cost, reviewer settings, fixed-egress runner/key allowlist, host trust, real runtime secrets or friend domain yet.
- **NOT TESTED:** all real SSH/cloud-init/firewall/host hardening, DNS/TLS/renewal/public auth, protected workflow runs, actual off-host restore/RTO, production rollback and admin acceptance.
- **BLOCKED:** public production Swagger request conflicts with intentional current docs denial; preserve policy unless approved alternative is specified.

## 17. Exact steps requiring separate approval

Approve architecture/total cost and external state/backup services; approve live catalog/inventory and live plan; review saved plan and explicitly authorize provisioning; separately authorize host bootstrap/runtime secrets/volume/backup/DNS/TLS setup; approve scanned digest release/deployment; manually authorize/administer first production user and run live acceptance. Teardown needs distinct authorization, final restore evidence, reviewed prevent_destroy removal and fresh exact destroy plan. No next step is automatic.

**DEPLOYMENT PREPARATION STATUS: READY FOR REVIEW**

**UPCLOUD INFRASTRUCTURE STATUS: NOT PROVISIONED**

**PRODUCTION ADMIN STATUS: NOT CREATED**

**LIVE DEPLOYMENT STATUS: NOT STARTED**

**USER APPROVAL REQUIRED: YES**
