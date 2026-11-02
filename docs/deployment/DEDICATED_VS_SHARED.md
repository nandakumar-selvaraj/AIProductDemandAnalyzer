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

## Shared dependencies that remain (documented risk)

* Both families use the GitHub Environment named `production` and the same secret names (`UPCLOUD_TOKEN`, `TF_STATE_*`). Isolation therefore depends on code guards, not on separate secrets. Preferred hardening (owner action): a distinct Environment (for example `aiproductdemand-production`) holding only this project's secrets.
* Dedicated code imports `infrastructure/automation.py` as a library (protected-environment check, saved-plan protocol). Dedicated entrypoints rebind its Terraform root, summary, plan-object path, workflow list and fingerprint (see `configure()`); tests assert this.
* `docker-build.yml` is shared and runs on `workflow_run`. The dedicated deployment builds its own images and does not use it.

## Guards (all fail closed; covered by `infra/tests/test_isolation.py`)

* `guards.require_dedicated`: Terraform root, state key, project, environment, hostname and a `sg-*` zone.
* `guards.validate_plan`: exactly one `upcloud_server.app` and one `upcloud_firewall_rules.app`; rejects other resources, indexed/data/duplicate resources, non-Singapore zones, public ports other than 22/80/443, world-open SSH and, outside destroy, any delete/replace.
* `guards.plan_object_path`: project-scoped S3 prefix with numeric run id and fixed object names.
* Mutating workflows are `workflow_dispatch` only, bound to the `production` Environment with non-cancelling concurrency; no `workflow_run` chaining; the application deploy workflow contains no Terraform and no `UPCLOUD_TOKEN`.
* Shared mutating workflows carry an `OUT OF SCOPE` header comment. Nothing was removed.
