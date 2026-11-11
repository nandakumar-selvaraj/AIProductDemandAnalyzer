> HISTORICAL AND INACTIVE for the Phase 5.17 dedicated manual deployment. Do not execute Terraform, AWS, S3/KMS or teardown instructions below. Preserve existing resources/state. Prior passes are not current evidence. Use [manual provisioning](UPCLOUD_MANUAL_PROVISIONING.md) and [final validation](PHASE_5_17_FINAL_VALIDATION.md).

# Phase 5.16.1: Final security hardening

Scope: source changes and local validation only. No Terraform plan/apply/destroy, no UpCloud or AWS call, no GitHub setting change, no workflow dispatch, no secret read, no administrator creation, no deployment. Default branch re-verified as `master`.

**Source status: READY FOR REVIEW. Live deployment: BLOCKED** (see [Remaining blockers](#remaining-blockers)).

## 1. Vulnerabilities found in the Phase 5.16 implementation

| # | Severity | Finding | Root cause |
|---|---|---|---|
| V1 | High | Dedicated workflows ran in the shared `production` GitHub Environment, and dedicated automation called the shared `protected_environment()`, which validates `production`. | Dedicated code reused the shared module by monkeypatching instead of owning its own boundary. |
| V2 | High | Dedicated workflows read generic secret names (`UPCLOUD_TOKEN`, `TF_STATE_*`). A repository- or organization-level secret with the same name would be used silently if the Environment lacked it. | GitHub resolves secrets Environment → repository → organization; generic names allow fallback. |
| V3 | High | Plan validation accepted any `sg-*` zone, did not check the server plan, hostname, labels, storage, login or interfaces, and only checked resources with changes. `no-op` resources and `planned_values` were not inspected; a missing `zone` passed. | Address-only policy over `resource_changes`. |
| V4 | High | Firewall check only rejected 0.0.0.0 SSH and non-22/80/443 TCP. UDP, IPv6, broad rules, a missing default drop and widened SSH ranges passed. | Deny-list instead of exact-policy comparison. |
| V5 | Medium | Unknown-until-apply values (`after_unknown`) were ignored. | Policy read only `after`. |
| V6 | Medium | Saved-plan metadata did not bind the Environment, plan prefix, state key or state lineage/serial. Destroy apply reimplemented the checks separately. | Metadata schema from the shared module. |
| V7 | Medium | Known-hosts check accepted any Ed25519-looking entry for the IP, multiple lines, and an unchecked key body; the private key check was a header string match. | Shape-only validation. |
| V8 | Medium | Workflows defaulted `SINGLE_UPCLOUD_ZONE` and `SINGLE_STORAGE_TIER` (`|| 'sg-sin1'`, `|| 'standard'`). | Convenience fallbacks. |
| V9 | Low | Initial sshd drop-in relied on cloud-init `ssh_pwauth: false` for password denial and did not disable stream-local forwarding or tunnels for `deployer`. | Defence-in-depth gap. |

## 2. Changes

| Area | Change | Files |
|---|---|---|
| Environment | Dedicated workflows use `aiproductdemand-production` and set `DEPLOYMENT_ENVIRONMENT`. `guards.require_environment` rejects `production` and any other name, then checks via the GitHub API: the Environment exists, admin bypass is off, required reviewers are set with `prevent_self_review`, the custom branch policy is exactly `master`, and protected-branches mode is off. `guards.require_workflow` requires `GITHUB_WORKFLOW_REF` to be the operation's own `single-*.yml` on `master` in this repository. Both run before any state, cloud or SSH command (tested). Shared `infrastructure/automation.py` is unchanged. | `infra/guards.py`, `infra/automation.py`, `infra/deploy_transport.py`, `single-*.yml` |
| Secrets | Dedicated secrets are `AIPD_*`; state variables are `AIPD_TF_STATE_*`. Test: dedicated workflows reference no other secret or variable names, and shared workflows reference no `AIPD_` names. | workflows, `infra/tests/test_isolation.py` |
| Fallbacks | Zone and storage-tier fallbacks removed. The only `||` left is the runner label, which falls back to a deliberately nonexistent runner (fail closed). | workflows |
| Plan policy | `guards.validate_plan` checks both `resource_changes` and `planned_values.root_module` (child modules are rejected). It requires exactly `upcloud_server.app` and `upcloud_firewall_rules.app` (managed, unindexed, not deposed, no module address, no duplicates). Normal actions are limited to `create`, `update` or `no-op`. Every resource, including `no-op`, is validated in both representations. | `infra/guards.py` |
| Server | Exact match on zone (in the code allowlist `{sg-sin1}`), plan, hostname, the full labels map, `firewall = true`, one `template` (Ubuntu 24.04 string, 30 GB, approved tier, `encrypt = true`), one `login` (`create_password = false`, `password_delivery = none`), and one `network_interface` (`public`, `IPv4`). Any `storage_devices` are rejected. Security-critical fields marked unknown in `after_unknown` are rejected. | `infra/guards.py` |
| Firewall | The ordered rule list must equal the policy generated from the approved CIDRs: SSH 22/tcp per CIDR (network to broadcast address, the same as `cidrhost(…,0)` and `cidrhost(…,-1)`), 80/tcp, 443/tcp, IPv4 ICMP, inbound drop, outbound accept. All 13 rule fields are compared; unknown rule fields are rejected. | `infra/guards.py` |
| SSH CIDRs | JSON list of 1–20 distinct, strict, public IPv4 networks, each /24 or narrower (mirrors `variables.tf`, plus a public-address check). | `infra/guards.py` |
| Destroy | Separate policy: only `delete` of approved resources, at least one, and no remaining planned resources. `guards.authorize_destroy` requires the backup confirmation, `DESTROY_TARGET = aiproductdemand-production` and the exact reviewed commit. | `infra/guards.py`, destroy workflow |
| Plan integrity | Dedicated `plan()` and `apply()` replace the shared ones. Metadata has an exact key set: commit, run id, digest, configuration fingerprint (including `DEPLOYMENT_ENVIRONMENT`), lockfile hash, mode, state lineage/serial, Environment, prefix and state key. Apply recomputes all of these, checks the producing run (workflow file, commit, branch, repository), and rejects plans older than 24 h (normal) or 1 h (destroy) or dated in the future. Raw state is read only to extract lineage/serial and is never stored or printed. | `infra/automation.py`, `infra/guards.py` |
| SSH transport | The private key is parsed as an unencrypted, single-key OpenSSH Ed25519 structure. Known hosts must be exactly one `IP ssh-ed25519 <key>` line for the exact `DEPLOY_HOST`, whose SHA256 fingerprint equals `SINGLE_DEPLOY_HOST_KEY_FINGERPRINT`, an independently verified variable. The client forces publickey only, with no agent, X11, port forwarding or TTY. | `infra/guards.py`, `infra/deploy_transport.py` |
| sshd | `PasswordAuthentication no`, `KbdInteractiveAuthentication no`, `AuthenticationMethods publickey`. The deployer additionally gets `AllowStreamLocalForwarding no` and `PermitTunnel no`; a new Terraform mock-test assertion covers this. | `infra/terraform/cloud-init.yml.tftpl`, `infra/terraform/tests/single.tftest.hcl` |

## 3. Required regression coverage

All 28 required cases are implemented with synthetic plans, mocked GitHub responses and synthetic SSH structures (`infra/tests/test_plan_policy.py`, `infra/tests/test_isolation.py`):

* **Environment, branch and workflow (1–5):** shared or other Environment; dedicated accepted; wrong branch; missing reviewers; admin bypass.
* **Identity, state and prefix (6–8):** Terraform root, state key, plan prefix.
* **Region (9–11):** wrong, missing or empty, and unknown region.
* **Server (12–14):** VPS plan, additional VPS, storage.
* **Firewall (15–20):** 5432, unrestricted SSH, UDP, IPv6, missing default drop, invalid CIDRs.
* **Plan integrity (21–25):** replacement, tampering, unknown or missing values, nested module, unauthorized destroy.
* **Transport (26):** invalid host key.
* **Workflow crossing (27–28):** shared workflow identity rejected by dedicated automation, and shared paths and resources rejected in dedicated workflows and plans.

A test also proves that running with the shared Environment makes no API, state or cloud call.

## 4. Remote state assessment

The recommendation is unchanged: S3 with SSE-KMS and `use_lockfile = true`. See [TERRAFORM_STATE_DECISION.md](TERRAFORM_STATE_DECISION.md), now including the shared-bucket analysis and the minimum IAM policy. **Remote state: UNCONFIGURED.** No bucket or key is known to exist, and nothing was initialized.

## 5. Authentication and admin (re-verified by reading code and running tests; no changes)

* Argon2id via `argon2-cffi` (`Type.ID`, t=3, m=64 MiB, p=2) with a dummy-hash timing equaliser and rehash-on-login.
* JWT decode requires `sub`, `jti`, `iat`, `nbf`, `exp`, `iss` and `aud`; API tokens use a distinct audience.
* Cookies are `HttpOnly`, `SameSite=Strict`, and `Secure` in production.
* CSRF: Origin allowlist plus a session-bound `X-CSRF-Token`.
* Login and readiness rate limits (429).
* Database-backed session and token revocation, applied on reset, disable and role change.
* No default administrator; no hardcoded passwords found.
* Migration `0002_authentication` revokes all `auth_users` privileges from `demand_app` and grants only `SELECT` plus `UPDATE(password_hash)`. Therefore only the owner-credentialed `migrate` service can create users. The `migrate` service has no ENTRYPOINT override, so `docker compose … run --rm --no-deps migrate python -m scripts.manage_users create --email <email> --role admin` (see [ADMIN_USER_SETUP.md](ADMIN_USER_SETUP.md)) runs the script with `MIGRATION_DATABASE_URL`. Not executed.

## 6. Validation results (2026-11-02, Windows host, Docker daemon not running)

| Check | Command | Result |
|---|---|---|
| Infrastructure tests | `python -m pytest infra/tests infrastructure/tests -q` (venv: pytest 8.4.2, PyYAML 6.0.3, Ruff 0.14.3) | PASS: 212 passed (194 dedicated, 18 shared) |
| Ruff lint | `ruff check infra infrastructure deploy/single` | PASS |
| Ruff format | `ruff format --check infra deploy/single infrastructure` | PASS |
| Source contracts and YAML parse | `python infra/validate.py` | PASS |
| Backend | `AUTH_ENABLED=false venv/Scripts/python -m pytest -q` (in `backend/`) | PASS: 200 passed, 1 skipped (opt-in PostgreSQL integration) |
| Backend auth subset | same, `-k "auth or token or session or csrf or role or login"` | PASS: 42 passed |
| Angular unit | `npm test -- --watch=false` (in `ui/`) | PASS: 266 passed, 19 files |
| Angular lint | `npm run lint` (in `ui/`) | PASS (exit 0) |
| Terraform fmt/init/validate/test | not installed on host; Docker unavailable | NOT TESTED. The new `single.tftest.hcl` assertion is unexecuted |
| Actionlint | not installed; Docker unavailable | NOT TESTED |
| Trivy config and secret scan (`infrastructure/check_secrets.py`) | requires Docker | NOT TESTED |
| Compose config, image builds, container tests, backup/restore | requires Docker | NOT TESTED |
| Angular production build | not run this phase | NOT TESTED |
| Live GitHub Environment, state backend, UpCloud catalog | not authorized | BLOCKED |

Re-run the NOT TESTED rows in `single-validate.yml` on the pushed commit or with Docker running before any approval.

## Remaining blockers

1. Create and protect the `aiproductdemand-production` Environment (checklist below). **CONFIGURATION REQUIRED.**
2. An approved S3 bucket and KMS key, plus a dedicated IAM principal. **UNCONFIGURED.**
3. Confirm the Singapore plan identifier, price and capacity. **NOT STARTED.**
4. A fixed-egress self-hosted runner and its /32 in `SINGLE_SSH_ALLOWED_CIDRS`.
5. Verify the host-key fingerprint through the UpCloud console after provisioning.
6. Terraform, Actionlint, Trivy and Docker checks on the final commit.
7. Off-host backup destination and restore drill.
8. The exact-match policy uses the attribute names from `main.tf` (UpCloud provider 5.48.0 schema) but has only been tested against synthetic plan JSON. The first real reviewed plan may fail closed if the provider renders a value differently, for example a template UUID after creation, or empty strings versus null for unset firewall fields (nulls are already normalised). Any adjustment must be a reviewed code change, never a relaxation by variable.

## Manual GitHub setup checklist (owner; nothing was configured automatically)

**Plan limitations (per GitHub's "Managing environments for deployment" docs; re-check the current page):** Environments with required reviewers, self-review prevention and admin-bypass control are available for **public** repositories on all plans. For **private or internal** repositories, Environments and branch policies need GitHub Pro, Team or Enterprise, and required reviewers need GitHub Enterprise. This repository's visibility and plan were **not verified** in this session.

If required reviewers are unavailable, the automation fails closed and stays BLOCKED; it does not degrade. Acceptable alternatives, each needing a separate decision:

* (a) Make the repository public if that is acceptable.
* (b) Upgrade the plan.
* (c) Run Terraform from an operator workstation under a two-person procedure: a reviewed PR, a second person verifying the plan hash, and the same `infra/guards.py` checks run locally. This requires reviewed code changes.

Steps, in **Settings → Environments → New environment**:

1. Name it exactly `aiproductdemand-production`.
2. **Required reviewers:** at least one person other than the dispatcher. Enable **Prevent self-review**.
3. Turn off **Allow administrators to bypass configured protection rules**.
4. **Deployment branches and tags:** *Selected branches and tags*, add one branch rule, exactly `master`, with no wildcard and no tags.
5. **Environment secrets** (Environment-level only; never repository or organization level):
   * `AIPD_UPCLOUD_TOKEN`
   * `AIPD_TF_STATE_ACCESS_KEY_ID`
   * `AIPD_TF_STATE_SECRET_ACCESS_KEY` (dedicated IAM principal)
   * `AIPD_DEPLOY_SSH_PRIVATE_KEY` (unencrypted OpenSSH Ed25519 deployer key; used only by the runner)
   * `AIPD_DEPLOY_SSH_KNOWN_HOSTS` (single line `IP ssh-ed25519 KEY`)
6. **Environment variables:**
   * `AIPD_TF_STATE_BUCKET`, `AIPD_TF_STATE_REGION`, `AIPD_TF_STATE_KMS_KEY`
   * `SINGLE_UPCLOUD_ZONE` (`sg-sin1`)
   * `SINGLE_UPCLOUD_PLAN`
   * `SINGLE_STORAGE_TIER` (`standard` or `maxiops`)
   * `SINGLE_OPERATOR_PUBLIC_KEY`, `SINGLE_DEPLOY_PUBLIC_KEY`
   * `SINGLE_SSH_ALLOWED_CIDRS` (JSON list)
   * `SINGLE_DEPLOY_HOST`
   * `SINGLE_DEPLOY_HOST_KEY_FINGERPRINT` (`SHA256:…`)
   * `SINGLE_DEPLOY_RUNNER_LABEL`
7. Confirm that no repository- or organization-level secret named `AIPD_*` exists.
8. Leave the shared `production` Environment unchanged. The existing `UPCLOUD_TOKEN` there is not used by dedicated workflows; you have to add the token to the new Environment yourself (no value was read or copied).
9. Protect the `master` branch (PR review, required status checks including `single-validate.yml`).

## Next approval-gated steps (in order)

1. Review and commit this change, push, and confirm that `single-validate.yml` and the other CI workflows pass.
2. Complete the GitHub checklist and confirm that the protections are visible.
3. Approve or confirm the state backend and the dedicated IAM principal.
4. Run a read-only UpCloud catalog and price check.
5. Dispatch `single-terraform-plan.yml` and review it.
6. Separately approve `single-terraform-apply.yml` for that exact plan.
7. Verify the host key through the console and set the fingerprint variable.
8. Arrange DNS.
9. Run a backup and restore drill.
10. Deploy.
11. Create the administrator manually.
12. Run the acceptance checklist.

Phase 5.17 is not started.
