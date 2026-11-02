# GitHub Actions

Existing workflows are unchanged. Do not dispatch old shared VPS apply/deploy workflows for this dedicated deployment.

| Workflow | Behavior |
|---|---|
| `single-validate.yml` | Push/PR/manual, no credentials: fmt, backend-disabled init, provider/mock tests, Trivy, actionlint, shell syntax, Ruff, safety/source contracts, secret scan |
| `single-terraform-plan.yml` | Manual protected environment: approved state/catalog checks, encrypted private saved plan and sanitized review summary |
| `single-terraform-apply.yml` | Manual approval: exact plan run, commit/config/lockfile/digest/age/state verification; provision and stop |
| `single-deploy-production.yml` | Manual master: require exact-commit existing backend/Angular/E2E/Docker/infra CI, build/publish backend/frontend/repaired PostgreSQL in GHCR, require PostgreSQL major16 and scan all four runtime digests; separate approved fixed-egress SSH deployment job |
| `single-terraform-destroy.yml` | Manual `aiproductdemand-production` selection; destroy-plan followed by separate dispatch/approval of exact destroy-apply within one hour, with backup/restore/inventory confirmation |

Dedicated jobs run in the **`aiproductdemand-production`** Environment (Phase 5.16.1); shared workflows keep `production`, unchanged. That Environment must require independent reviewers, prevent self-review, disable admin bypass and allow only a custom `master` branch policy.

Before any state, cloud or SSH command, `infra/guards.py` checks three things:

* `DEPLOYMENT_ENVIRONMENT` is the dedicated name (`production` is rejected);
* those protections, through the GitHub API;
* `GITHUB_WORKFLOW_REF` is the operation's own `single-*.yml` on `master`.

YAML cannot create reviewer protection. If the repository's plan lacks support, live operations remain BLOCKED. See the [setup checklist](PHASE_5_16_1_SECURITY_HARDENING.md).

Only build job has package-write permission; deployment has read-only repository/actions/deployment permissions. State credentials are scoped to Terraform jobs. `SINGLE_DEPLOY_RUNNER_LABEL` selects an isolated Linux runner with Python/SSH and approved fixed egress, never the VPS. Missing label selects an intentionally nonexistent runner. Review build digests/schema compatibility before deployment approval. Transport also requires the new single-validate workflow to pass before SSH.

Host receives only digest manifest, never runtime secrets or registry write token. GHCR packages must be reviewed and made public, or host separately configured for read-only pulls. Missing pull access blocks release. Image publication precedes deployment approval but requires manual workflow dispatch.

The approved ingress digest is in `deploy/single/images.json` (current Nginx namespace). The PostgreSQL recipe is `deploy/postgres/Dockerfile`; release/restore allowlists require the repaired project repository. No mutable upstream PostgreSQL/Nginx fallback is used by this dedicated workflow. Existing shared-portfolio workflows remain separate.

Existing data backup, write stop, owner migration, Alembic heads, container and HTTPS checks precede success recording. Prior manifest retained. Migration failure needs manual assessment. See [rollback](ROLLBACK.md).
