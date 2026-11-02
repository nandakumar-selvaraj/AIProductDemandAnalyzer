# Dedicated versus shared-portfolio infrastructure (Phase 5.16)

Authorized scope: **one UpCloud VPS for AIProductDemandAnalyzer only**. Everything under the "shared" column is outside that scope and must not be run for this project. The default branch is `master` (verified with `git branch -a`).

| Concern | Dedicated (authorized) | Shared portfolio (NOT authorized) |
|---|---|---|
| Terraform root | `infra/terraform` | `infrastructure/terraform` |
| Automation | `infra/automation.py`, `infra/deploy_transport.py`, `infra/guards.py` | `infrastructure/automation.py` (library only for dedicated code) |
| Workflows | `single-terraform-plan/apply/destroy.yml`, `single-deploy-production.yml`, `single-validate.yml` | `terraform-plan.yml`, `terraform-apply.yml`, `production-deploy.yml`, `terraform-validate.yml`, `docker-build.yml` |
| State key | `aiproductdemand/production/terraform.tfstate` | `portfolio/production/terraform.tfstate` |
| Saved-plan prefix | `reviewed-plans/aiproductdemand/<run>/` | `reviewed-plans/<run>/` |
| Concurrency group | `aiproductdemand-terraform-production`, `aiproductdemand-application-production` | `portfolio-terraform-production`, `portfolio-application-production` |
| Compose / host scripts | `compose.prod.yml`, `deploy/single/`, `deploy/postgres/` | `compose.production.yml`, `deploy/ops/` |
| Resources | `upcloud_server.app`, `upcloud_firewall_rules.app` | `upcloud_server.portfolio`, `upcloud_storage.data`, `upcloud_firewall_rules.portfolio` |
| Hostname | `aiproductdemand-prod` | portfolio hostnames |
| GitHub Environment | `aiproductdemand-production` (Phase 5.16.1) | `production` |
| Secrets / state variables | `AIPD_*` (Environment-level only) | `UPCLOUD_TOKEN`, `TF_STATE_*` |

## Shared dependencies that remain (documented risk)

* Resolved in Phase 5.16.1: dedicated workflows use their own Environment, `aiproductdemand-production`, and `AIPD_*` secret names. Dedicated automation rejects `production`, and shared workflows are unchanged.
* Dedicated code still imports `infrastructure/automation.py` for low-level helpers only: `run`, `github`, `state_init`, `catalog`, `verify_run` and `ci`. It owns its Environment check, plan, apply, destroy and metadata. `state_init` is pointed at `infra/terraform` and the dedicated fingerprint.
* Same S3 bucket with separate prefixes is acceptable only with a dedicated IAM principal; see [TERRAFORM_STATE_DECISION.md](TERRAFORM_STATE_DECISION.md).
* `docker-build.yml` is shared and runs on `workflow_run`. The dedicated deployment builds its own images and does not use it.

## Guards (all fail closed; covered by `infra/tests/test_isolation.py`)

* `guards.require_dedicated`: Terraform root, state key, project, environment, hostname and a zone from the code allowlist (`sg-sin1`). `guards.require_environment` and `guards.require_workflow` check the dedicated GitHub Environment and the workflow identity.
* `guards.validate_plan`: exactly one `upcloud_server.app` and one `upcloud_firewall_rules.app` across `resource_changes` and `planned_values`, with exact server values and the exact ordered firewall policy. See [Phase 5.16.1](PHASE_5_16_1_SECURITY_HARDENING.md).
* `guards.plan_object_path`: project-scoped S3 prefix with numeric run id and fixed object names.
* Mutating workflows are `workflow_dispatch` only, bound to the `aiproductdemand-production` Environment with non-cancelling concurrency; no `workflow_run` chaining; the application deploy workflow contains no Terraform and no `UPCLOUD_TOKEN`.
* Shared mutating workflows carry an `OUT OF SCOPE` header comment. Nothing was removed.
