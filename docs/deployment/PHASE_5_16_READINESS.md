# Phase 5.16 deployment readiness report

> **Superseded in part by [Phase 5.16.1](PHASE_5_16_1_SECURITY_HARDENING.md).** Dedicated workflows now use the `aiproductdemand-production` Environment and `AIPD_*` secret and variable names (section F below is historical). Plan policy is now complete-inventory and exact-match, and transport pins a host-key fingerprint. Infrastructure tests: 212 passed.

Scope: source changes, local tests and documentation only. No Terraform plan/apply/destroy, no cloud or AWS call, no GitHub setting change, no production deployment, no administrator creation, no secret read. Local passes are **not** deployment approval.

**Status: BLOCKED for deployment** (owner prerequisites below). **READY FOR REVIEW** as a source change.

## A. Executive summary

Remediated: dedicated/shared isolation is now enforced in code and tests (`infra/guards.py`); saved plans are project-scoped and inspected for resource type, region and public ports; the dedicated build job's CI gate now requires `single-validate.yml`; deploy transport rejects unpinned or non-Ed25519 hosts; shared workflows are marked out of scope; the Terraform state decision and the dedicated/shared map are documented; a Windows-only test failure was fixed.

Still blocked: GitHub Environment protection is unverified; the S3/KMS backend is unconfirmed; the Singapore plan identifier and price are unconfirmed; the fixed-egress runner label and SSH CIDRs are unset; off-host backup was never exercised; Docker, Terraform and Actionlint are unavailable in this session (see matrix).

## B. Repository findings

Default branch: `master` (`git branch -a`). Full mapping: [DEDICATED_VS_SHARED.md](DEDICATED_VS_SHARED.md).

* Dedicated: `infra/terraform`, `infra/*.py`, `single-*.yml`, `compose.prod.yml`, `deploy/single`, `deploy/postgres`.
* Shared (out of scope): `infrastructure/terraform`, `terraform-plan/apply/validate.yml`, `production-deploy.yml`, `docker-build.yml`, `compose.production.yml`, `deploy/ops`.

## C. Security findings

| Sev | Finding |
|---|---|
| High | Dedicated and shared workflows share the `production` Environment and secret names; isolation relied on convention. Mitigated by guards; a separate Environment is still recommended. |
| High | Dedicated build job's CI gate omitted `single-validate.yml` (only the deploy job added it). Fixed. |
| Medium | Plan summary checked only resource addresses, not region or ports. Fixed. |
| Medium | Saved plans lived under an unscoped `reviewed-plans/<run>/`. Fixed. |
| Medium | Transport accepted any non-empty known_hosts. Fixed. |
| Medium | Non-dedicated CI workflows use `@v4` action tags (`backend-ci`, `docker-validation`, `e2e`, `terraform-validate`). They hold no cloud secrets, but SHAs could not be resolved offline. **Open.** |
| Low | The local `backend/.env` enables auth and breaks 9 unit tests unless `AUTH_ENABLED=false`, as in CI. Documentation point only. |

## D. Remediation results

| Issue | Root cause | Files | Evidence | Residual risk | Status |
|---|---|---|---|---|---|
| Isolation | Convention only | `infra/guards.py`, `infra/automation.py`, `infra/tests/test_isolation.py`, shared workflow headers | 84 tests pass | Shared Environment/secrets | Fixed, partial |
| Plan integrity | Weak summary, unscoped prefix | `infra/guards.py`, `infra/automation.py` | Tests for tampered/foreign resources, regions, ports, delete/replace, duplicates, path traversal | Live lineage/serial check relies on Terraform saved-plan behaviour (not live-tested) | Fixed |
| CI gate | Missing check | `single-deploy-production.yml`, `infra/automation.py` (`ci` action) | Test asserts `single-validate.yml` in required list | None | Fixed |
| SSH transport | Unvalidated inputs | `infra/deploy_transport.py` | 8 negative tests | GitHub-hosted runner IPs are not stable; requires a fixed-egress runner (`SINGLE_DEPLOY_RUNNER_LABEL`) | Fixed in code; runner unconfigured |
| Windows test | `str(Path)` separators | `infra/tests/test_single_safety.py` | 2 previously failing tests now pass | None | Fixed |
| Action pinning (non-dedicated) | Tags | not changed | none | See C | Open |

Verified by reading, not changed: ordinary push/PR cannot mutate cloud (only `backend-ci`, `docker-validation`, `e2e`, `*-validate` run on push/PR, none uses cloud secrets; tested). Plan, apply, deploy, rollback and destroy are separate manual dispatches; plan never triggers apply (no `workflow_run`). Dedicated `permissions` are minimal at workflow level (`packages: write` only in the build job).

## E. Terraform state recommendation

Keep **AWS S3 with SSE-KMS and native lockfile locking**, contingent on owner confirmation of an existing bucket or separate approval to create one. Full comparison: [TERRAFORM_STATE_DECISION.md](TERRAFORM_STATE_DECISION.md). Local state is not acceptable for the real deployment.

## F. GitHub Environment readiness

Code (`protected_environment`) fails closed unless all hold; **none verified against GitHub in this phase** (no API access and no setting changes):

| Control | Status |
|---|---|
| Environment `production` exists | UNVERIFIED |
| Required reviewers set | UNVERIFIED |
| Prevent self-review | UNVERIFIED (needs a second reviewer account) |
| Administrator bypass disabled | UNVERIFIED |
| Deployment branches limited to `master` | UNVERIFIED |
| Availability of these features for this repository's visibility and plan | UNVERIFIED. If unavailable, workflows fail closed and an alternative approval mechanism (separate approver-held dispatch or a second repository) must be chosen |
| Secrets: `UPCLOUD_TOKEN` (set by owner, validity unverified), `TF_STATE_ACCESS_KEY_ID`, `TF_STATE_SECRET_ACCESS_KEY`, `DEPLOY_SSH_PRIVATE_KEY`, `DEPLOY_SSH_KNOWN_HOSTS` | UNVERIFIED |
| Variables: `TF_STATE_BUCKET`, `TF_STATE_REGION`, `TF_STATE_KMS_KEY`, `SINGLE_UPCLOUD_PLAN`, `SINGLE_UPCLOUD_ZONE`, `SINGLE_OPERATOR_PUBLIC_KEY`, `SINGLE_DEPLOY_PUBLIC_KEY`, `SINGLE_SSH_ALLOWED_CIDRS`, `SINGLE_DEPLOY_HOST`, `SINGLE_DEPLOY_RUNNER_LABEL`, `SINGLE_STORAGE_TIER` | UNVERIFIED |

## G. Singapore readiness

Static only: zone default `sg-sin1`, enforced by the `sg-` guard; `server_plan` has no default (owner must approve a live 2 vCPU/4 GB plan ID); firewall allows only 22 (approved CIDRs), 80, 443 and ICMP, with default drop. Terraform validate was **not run** (binary absent).

Live preflight checklist (needs separate approval): confirm zone `sg-sin1` in the account; list plans and pick the 2 vCPU/4 GB plan ID; confirm the Ubuntu 24.04 template and storage encryption support; confirm the price and quota; confirm IPv4 inclusion; then a reviewed plan.

## H. Authentication and admin readiness

Backend suite with `AUTH_ENABLED=false` (CI setting): 200 passed, 1 skipped. Angular: 266 passed. These cover the existing hashing, JWT, session revocation, cookies, CSRF, RBAC and login-throttling tests; no code changes were made and no coverage gaps were added in this phase.

`scripts/manage_users.py` (read): `create` requires `--email` and `--role`; prompts twice without echo, or `--password-stdin`; requires 12+ characters; uses the Argon2 hasher; rejects duplicate emails; `reset-password`, `disable` and `set-role` revoke sessions and API tokens. No default admin exists. It is not invoked by Terraform, cloud-init, Docker startup or CI. The runtime DB role cannot insert users, so the migrate/owner context is used, as in [ADMIN_USER_SETUP.md](ADMIN_USER_SETUP.md) (`... run --rm --no-deps migrate python -m scripts.manage_users create --email <email> --role admin`). Not executed.

## I. Cost assessment

Per existing [COST_ESTIMATE.md](COST_ESTIMATE.md), published (not quoted) pricing: UpCloud 2 vCPU/4 GB with 30 GB storage and IPv4 ~EUR 12/month (recheck, the page announces changes). Additional and unquantified: S3 state and KMS (cents to about USD 1/month, estimate), off-host backup storage (destination not chosen), taxes, a fixed-egress runner, traffic beyond the plan. GHCR/Actions use the existing allowance. No extra services were added by this phase. The cheapest compliant architecture is the single VPS with S3 state. Teardown needs residual-resource and billing checks ([TEARDOWN.md](TEARDOWN.md)).

## J. Validation matrix

| Area | Command | Result |
|---|---|---|
| Infra safety tests | `pytest infra/tests infrastructure/tests -q` | PASS (84) |
| Ruff lint, `infra` and `infrastructure` | `ruff check` | PASS |
| Ruff format | `ruff format infra` | PASS (applied) |
| Workflow YAML parse | `yaml.safe_load` on all workflows | PASS |
| Compose/doc contracts | `python infra/validate.py` | PASS |
| Shell syntax | `bash -n deploy/single/*.sh` | PASS |
| Backend | `pytest -q` with `AUTH_ENABLED=false` | PASS (200, 1 skipped); without it, 9 FAIL due to the local `.env` |
| Angular unit | `npm test` | PASS (266) |
| Angular lint, prod build | not run | NOT TESTED |
| Regex secret scan (substitute) | grep for key/token patterns | PASS (one false positive: the literal header check in `deploy_transport.py`) |
| Secret scanner (`check_secrets.py`) | requires Docker | NOT TESTED |
| Terraform fmt/validate/test, tfsec | `terraform` not installed | NOT TESTED |
| Actionlint | not installed | NOT TESTED |
| Docker builds, Compose, healthchecks, Trivy | Docker daemon not running | NOT TESTED |
| Postgres integration, backup/restore, migration-failure, rollback with containers | needs Docker; rollback/migration-failure unit simulations in `test_single_safety.py` | Unit PASS; container tests NOT TESTED |
| Dependency audit | not run | NOT TESTED |
| Live Terraform, GitHub Environment API, UpCloud catalog, off-host backup | not authorized | BLOCKED |

## K. Deployment authorization checklist (each needs explicit approval, in order)

1. Review and commit this phase's changes.
2. Configure the GitHub Environment protections and secrets, preferably in a dedicated Environment.
3. Choose and confirm the state backend (bucket and KMS key).
4. Live UpCloud catalog and price check (read-only).
5. Reviewed Terraform plan.
6. Terraform apply of that exact plan, which stops at the public IPv4.
7. DNS and domain arrangement by the owner.
8. Off-host backup configuration and restore drill.
9. Application deployment.
10. Manual administrator creation.
11. Production acceptance ([ACCEPTANCE.md](ACCEPTANCE.md)).
12. Rollback, teardown or destroy only on separate request.

PHASE 5.16 STATUS: BLOCKED (owner prerequisites outstanding; source work ready for review)
