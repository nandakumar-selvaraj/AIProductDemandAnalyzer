# Active dedicated GitHub Actions — Phase 5.17

Actions do not provision this dedicated host. Start with [manual provisioning](UPCLOUD_MANUAL_PROVISIONING.md) and [security remediation](PHASE_5_17_1_SECURITY_REMEDIATION.md).

| Workflow | Trigger and gates |
| --- | --- |
| backend-ci.yml | Push/PR: backend lint/tests/migrations, Angular lint/tests/build, legacy production Compose build |
| e2e.yml | Existing synthetic browser/database validation |
| docker-validation.yml | Existing disposable production Docker integration |
| single-validate.yml | Push/PR/manual: Trivy backend Dockerfile policy and Compose source contracts, Actionlint, per-file Bash parsing and ShellCheck, safety tests, Ruff, source contracts and secret scan; no Terraform install |
| single-publish-images.yml | Master push: waits for the four preceding workflows on the exact SHA, publishes GHCR backend/frontend/PostgreSQL, checks PostgreSQL16, scans all four runtime images, uploads a 30-day digest manifest |
| single-deploy-production.yml | Manual master only, explicit compatible-schema attestation, successful same-SHA publication run and validated manifest, then independently approved SSH deployment |

Only publication has package-write permission. Publication is automatic on master push; deployment is not. Expired/missing artifacts require reviewed publication rerun, never mutable tags. Host pull access to GHCR must be arranged separately.

The deploy job uses aiproductdemand-production with independent required reviewer, self-review prevention, disabled admin bypass and custom master-only branch policy. infra/guards.py verifies these through GitHub before SSH. Live settings were not changed or verified. Missing protections fail closed.

SINGLE_DEPLOY_RUNNER_LABEL selects an isolated fixed-egress Linux runner, never the VPS. Configure this as a repository/organization configuration variable: runner selection cannot rely on job Environment variables being available yet. Other deployment values belong in the protected Environment. Without the label the preapproval build gate fails and the protected SSH job cannot start.

Transport requires a distinct Ed25519 key and independently console-verified host pin. Only digest manifests cross SSH. The preflight requires a unique, unexpired publication artifact from the successful run at the deployment SHA. Root-owned host code requires matching completed backup and isolated restore receipt, TLS marker, external DB volume, owner migration, matching heads and HTTPS/container health. Failed migrations stop for manual recovery; application rollback preserves storage and requires compatible schema.

## Historical and separate paths

Dedicated single-terraform-plan/apply/destroy definitions are archived outside Actions discovery: HISTORICAL AND INACTIVE. No dedicated Terraform, AWS, S3 or KMS credentials are required.

Legacy shared terraform-validate/plan/apply.yml, docker-build.yml and production-deploy.yml remain discoverable and unchanged. They are NOT the dedicated path; do not dispatch their cloud operations. The whole repository still contains executable Terraform/AWS tooling. Active dedicated Python entry points import standard-library GitHub/subprocess helpers from infrastructure/automation.py, but do not invoke its state/catalog/plan/apply functions.

Review the local regression evidence and the hosted runs for the exact deployment commit. Environment and runner settings require owner verification.

Runner-selection scope: [GitHub variables reference](https://docs.github.com/en/actions/reference/workflows-and-actions/variables).
