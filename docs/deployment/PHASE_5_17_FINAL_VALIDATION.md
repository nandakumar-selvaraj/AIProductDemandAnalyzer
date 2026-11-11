# Phase 5.17 final validation — 2026-11-10

## Decision: NO-GO for manual VPS provisioning

Audit target: master b38d84bedac71e7815506c7a3e795c31ffbae21e. Read-only git ls-remote confirmed remote master at this SHA. This working tree changes documentation only; no runtime, security policy, tests or workflows were weakened. No commit/push, cloud resource, GitHub setting, deployment, real administrator or storage deletion was performed.

Do not purchase/provision yet. Resolve the bootstrap lockout/rerun/firewall risks, repair current validation failures and rehearse installation/recovery on disposable local Ubuntu24.04 amd64. Application deployment has additional backup, same-SHA CI, protected approval, fixed-egress, runtime and DNS/TLS gates.

## Findings

| Severity | Finding and evidence | Required resolution |
| --- | --- | --- |
| High | bootstrap-host.sh replaces operator/deployer authorized_keys, disables root SSH and reloads SSH in the same run. KEY-ACCESS-VERIFIED does not demonstrate a second operator session; initial provider access may be root-only. | Separate installation from final hardening; prove second-session key/sudo and out-of-band recovery before disabling initial access. |
| High | Bootstrap reruns retain obsolete/broad UFW allows; default deny does not remove an existing OpenSSH/world-open rule. docker-firewall.sh flushes its live chain before rebuilding it, creating a transient permissive interval on rerun. | Validate/reconcile exact firewall state safely, stage/atomically switch Docker rules, test approved and unapproved sources and reboot. Do not flush the whole firewall. |
| High | Bootstrap overwrites privileged artifacts, sudoers and SSH policy in place; package/config errors can leave partial changes without rollback. Existing user/home/key/symlink state is not comprehensively validated. | Define supported rerun states, root-owned source/path checks, staged validation/atomic writes and tested recovery. Never treat it as generic host migration or key rotation. |
| High | restore-verify.sh leaves prior acceptance receipt on failure; preflight accepts it for35 days and only restic check metadata. Receipt has no snapshot/revision/count binding. | Invalidate acceptance before a drill, bind successful exact snapshot/data evidence, and failure-injection test old-receipt rejection. |
| High | Bootstrap restore only SELECT1; later checks read Alembic/auth tables without expected-value assertions. Backup prunes before newly produced snapshot restore verification; failed dump can still leave a partial snapshot. | Validate expected schema/business data, identify only successful snapshots, decouple authorized retention from backup/verified recovery. |
| High | Current infra safety suite has19 failures: archived dedicated Terraform workflows still expected under .github/workflows; old build/CI expectations remain. | Update contracts to assert archived workflows stay inactive and preserve active publication/deployment/security gates. Do not simply skip failures. |
| Medium | infra/release_manifest.py fails Ruff formatting. | Format and rerun required checks before declaring CI green. |
| Medium | SINGLE_DEPLOY_RUNNER_LABEL must be available during runner selection; earlier docs incorrectly put every variable at Environment scope. | Use repository/organization configuration variable for this nonsecret label; independently verify runner/Environment protections. Documentation corrected. |
| Medium | bash -n deploy/single/*.sh in CI only parses the first file; remaining names become positional arguments. | Loop over scripts in a future reviewed workflow fix; this audit explicitly syntax-checks each file locally. |
| Medium | Backup self-host rejection resolves the local hostname only, which may omit the public IP; separate failure domain is not proven by code. Monitoring starts before backup/TLS setup and initially fails by design. | Verify separate host/storage and test alert delivery plus setup-to-operational transition. |
| Medium | Shared workflows remain active/discoverable and non-dedicated Actions include mutable version tags. | Keep paths separate; never dispatch shared provisioning for this app. Review action pinning separately. |
| Low | Historical runbooks contradicted manual provisioning, SFTP and automatic publication; missing manual guide broke source contracts. | Corrected documentation in this audit; historical source/evidence preserved with explicit inactive banners. |

Root privilege review: bootstrap requires uid0, Ubuntu24.04/amd64, distinct Ed25519 public keys and narrow global IPv4 CIDRs. It installs Docker from a fingerprint-checked vendor key, gives operator deliberate full-root sudo, restricts deployer to a fixed release entrypoint and rejects Docker group membership. These controls are useful but do not prove safe key transition, effective sshd Match precedence, idempotence or recovery. sshd -t is syntax validation, not an access test. No privileged host script was executed.

Firewall review: only nginx exposes80/443 in dedicated Compose; DB uses an internal network and an external persistent volume. No PostgreSQL/Ollama public ports. Docker DNAT is explicitly handled by DOCKER-USER, but real routing/interface/IPv6 and restart behavior remain untested.

Backup review: root-only0600 config/key/password/pin files; authenticated Restic encryption, strict pinned Ed25519 SFTP, pipefail, lock, full-data check during restore and actual pg_restore into network-isolated tmpfs PostgreSQL. These are source observations, not an off-server drill. Preserve production storage; no backup/prune/restore script was run.

## Dependency and workflow audit

PASS (source scope): dedicated single-validate, single-publish-images and single-deploy-production require no Terraform executable/provider/backend, AWS CLI/SDK, S3 or KMS credentials. Runtime uses Docker Compose, GHCR immutable images and encrypted SFTP/Restic.

Imports remain coupled to infrastructure/automation.py: dedicated ci/release_manifest/deploy_transport call only github, run, required, verify_run and ci. guards.py retains historical Terraform constants/policy tests but deployment only invokes workflow/Environment/key guards. No provisioning function runs at import. This is NOT a claim that the whole repository is Terraform/AWS-free: legacy shared workflows and historical provisioning tools remain executable. Dedicated provisioning workflow definitions stay in infra/retired-workflows/*.yml.disabled, outside Actions discovery.

Publication: master push, same-SHA required checks, package-write only in build, digest scans, PostgreSQL16 check and manifest artifact. Release: manual master, schema attestation, successful same-SHA publication artifact, immutable repository allowlist, protected dedicated Environment, independent reviewer/no self-review/no admin bypass/master branch rule, pinned SSH and host preflight. Host code owns migrations, HTTPS health and compatible application rollback. Real GitHub protections and runner isolation were not inspected or modified.

Read-only GitHub connector returned an empty workflow-run list for the target SHA; this is not evidence of successful CI or absence of all checks. No workflow was dispatched. Eleven discoverable workflow YAML files parsed locally; Actionlint remains untested.

## Executed validation

Commands run from repository root unless specified. Python launcher is backend/venv/Scripts/python.exe (Python3.15.1); Ruff from the same venv. Node24.21.0. Local Python differs from production/CI3.13; a production-version run remains required.

| Check / command | Result | Evidence and limitation |
| --- | --- | --- |
| git ls-remote origin refs/heads/master | PASS | Remote master equals b38d84b; initial sandbox DNS failure resolved with read-only approved retry |
| python -m pytest infra/tests infrastructure/tests -q --basetemp=validation/phase517-infra-tmp --tb=line | FAIL | 19 failed,191 passed. Initial run also had2 sandbox temp errors; workspace-temp retry removes those errors, not real failures |
| Backend: python -m pytest tests -q --basetemp=../validation/phase517-backend-unrestricted --tb=short | PASS | 200 passed,1 skipped in40.83s; process-only ENVIRONMENT=test, AUTH_ENABLED=false, synthetic unreachable DATABASE_URL; TEST_DATABASE_URL unset. Authentication tests remain in suite. Opt-in real PostgreSQL integration skipped |
| ruff check infra infrastructure deploy/single deploy/ops backend | PASS | All checks passed |
| ruff format --check infra infrastructure deploy/single deploy/ops backend | FAIL | release_manifest.py would reformat;112 files already formatted |
| Angular npm run lint | PASS | ESLint completed with exit0 outside sandbox; restricted attempt was interrupted |
| Angular npm test -- --watch=false | FAIL |19 Vitest fork-worker startup timeouts; no tests executed. Initial sandbox attempt interrupted after stalling |
| Angular npm test -- --watch=false --runner-config ../validation/phase517-vitest.mjs | PASS | 266 tests in19 files passed in42.35s. Ignored config exports test.maxWorkers=1 only; same suite, no skipping. Default parallel run still failed worker startup |
| Angular npm run build -- --configuration production | PASS | Initial bundle662.77kB; production output dist/ui/browser |
| npm run e2e:typecheck and npm run e2e:list | PASS | Type check and discovery of18 tests; NOT browser execution |
| Dedicated per-file bash -n loop | PASS | Git for Windows Bash parsed every deploy/single/*.sh individually; no script execution |
| Parse .github/workflows/*.yml with PyYAML | PASS |11 active YAML files; not a substitute for Actionlint/security analysis |
| Dedicated Compose config --quiet with example runtime and synthetic digest references | PASS | Docker Compose2.40.3; no daemon/start or credential read |
| python infra/validate.py | PASS | Initial missing-guide failure resolved by new documentation; final Compose/migration/manual-workflow/LF/link contracts pass |
| git diff --check | PASS | No whitespace errors; Git reports expected Windows newline conversion warnings |
| Docker version / engine probe | NOT TESTED (runtime blocked) | CLI present; dockerDesktopLinuxEngine named pipe absent in sandbox and approved unrestricted probe |
| PostgreSQL init/migrations/persistence; Docker integration/health; real browser E2E | NOT TESTED | No disposable Docker engine; do not reuse development DB or synthesize a runtime PASS |
| python infrastructure/check_secrets.py | NOT TESTED (attempt failed) | RuntimeError: Secret scanner could not complete; scanner requires unavailable Docker |
| Actionlint, ShellCheck, Trivy config/current images | NOT TESTED | No native executables found; container route blocked by unavailable engine. No current zero-vulnerability or secret-free claim |
| Ubuntu bootstrap/rerun/reboot, real firewall/SSH recovery, live Restic/SFTP restore | NOT TESTED | Requires isolated host rehearsal and later separately authorized real acceptance |
| Cloud/GitHub settings/DNS/TLS/admin/deployment | NOT TESTED | Intentionally prohibited; no changes made |

Earlier sandbox backend/Angular processes were interrupted and replaced by explicit validation attempts; they are not counted as passes. Historical scan/test reports were marked inactive rather than reused as current evidence. No tests were added, removed or bypassed. Frontend unit validation used a one-worker runner override only; no application configuration was changed.

## Documentation changes and release gates

Updated active GITHUB_ACTIONS, GITHUB_SECRETS, BACKUP_RESTORE, COST_ESTIMATE, ACCEPTANCE, UPCLOUD_SETUP, SSH_SETUP, DEDICATED_VS_SHARED, ARCHITECTURE, TEARDOWN and Phase5.17 index; created UPCLOUD_MANUAL_PROVISIONING and this report. README points to current guidance. Dedicated Terraform/state and earlier reports, plus legacy top-level deployment/backup/state guides, now carry historical/inactive-for-this-path banners.

Before a future GO: fix/retest the High bootstrap findings locally; repair current infrastructure/format checks; retain the passing one-worker Angular evidence and obtain Docker integration/current scans; verify recovery and budget/backup/fixed-egress prerequisites. Real public DNS/TLS/app acceptance follows provision under separate approval, not before it. After approved provisioning stop at IPv4 for the subdomain owner; no automatic application release.

This audit ends here. No provisioning or deployment is authorized.
