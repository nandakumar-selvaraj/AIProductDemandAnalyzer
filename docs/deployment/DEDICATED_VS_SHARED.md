# Dedicated versus legacy shared deployment

| Area | Active dedicated path | Legacy shared path — not this deployment |
| --- | --- | --- |
| Provisioning | Owner control panel, reviewed manual bootstrap | infrastructure/terraform and shared Terraform workflows |
| Runtime | compose.prod.yml, deploy/single, nginx | compose.production.yml, deploy/ops, Caddy |
| Delivery | single-validate, single-publish-images, single-deploy-production | docker-build, production-deploy |
| GitHub Environment | aiproductdemand-production | production |
| State | Manual owner inventory; no remote Terraform state | Historical S3/KMS state design |
| Backup | Encrypted Restic over pinned SFTP | Legacy shared backup design |

Dedicated infra/terraform, infra/automation.py provisioning commands and archived single-terraform workflows are HISTORICAL AND INACTIVE. Keep source/state; do not execute them or restore archived workflows.

Active entry points infra/ci.py, infra/release_manifest.py and infra/deploy_transport.py call only low-level run/github/verify_run/ci/required helpers from infrastructure/automation.py and deployment guards. Importing that standard-library module does not invoke its Terraform/AWS functions. No active dedicated CLI/credential/backend dependency exists, but source coupling remains and the whole repository is not Terraform-free.

Do not provision both paths. Existing resources/state require owner inventory, not assumed absence. See [final audit](PHASE_5_17_FINAL_VALIDATION.md).
