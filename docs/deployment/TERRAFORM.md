> HISTORICAL AND INACTIVE for the Phase 5.17 dedicated manual deployment. Do not execute Terraform, AWS, S3/KMS or teardown instructions below. Preserve existing resources/state. Prior passes are not current evidence. Use [manual provisioning](UPCLOUD_MANUAL_PROVISIONING.md) and [final validation](PHASE_5_17_FINAL_VALIDATION.md).

# Terraform and secure state

Root `infra/terraform`: Terraform 1.17.1, provider exactly 5.48.0, committed official checksums. One `upcloud_server.app` (encrypted persistent boot disk included), one `upcloud_firewall_rules.app`. No extra server, IP, database, load balancer, managed backup or Kubernetes. Labels identify project/environment; provider tags also have access-control meaning, so descriptive labels are used.

Required: `server_plan`, `ssh_public_key`, distinct `deploy_ssh_public_key`, `ssh_allowed_cidrs`. Defaults: `project_name=aiproductdemand`, `environment=production`, `upcloud_zone=sg-sin1`, `server_hostname=aiproductdemand-prod`, `server_timezone=Etc/UTC`, `boot_storage_tier=standard`. Outputs: IPv4, hostname, UUID, SSH instructions only.

```sh
terraform -chdir=infra/terraform fmt -check -recursive
terraform -chdir=infra/terraform init -backend=false -input=false -lockfile=readonly
terraform -chdir=infra/terraform validate
terraform -chdir=infra/terraform test
```

Tests use mock providers. Ordinary cloud-backed planning is not an offline test; validation never proves a real plan safe.

An existing separately approved AWS S3 bucket is mandatory: versioned, all public access blocked, TLS-only policy, SSE-KMS specified key, restricted IAM prefixes, audit logging, S3 `.tflock` locking. Workflow checks versioning/public block/KMS settings; operator verifies policies, IAM and recovery access. Nothing provisions this backend. No local-state fallback is enabled.

State key is `aiproductdemand/production/terraform.tfstate`, separate from shared portfolio. Scope IAM Get/Put to state, Get/Put/Delete to its lock, reviewed plans to `reviewed-plans/aiproductdemand/` (project-scoped since Phase 5.16), and appropriate KMS operations. Ordinary CI should not delete state. Protect versions/backups and expire private saved plans under reviewed retention. Never publish state/plans as Actions artifacts.

Phase 5.16.1 plan policy (`infra/guards.py`) checks both `resource_changes` and `planned_values`, including no-op resources and rejecting child modules. It requires exactly `upcloud_server.app` and `upcloud_firewall_rules.app` and an exact match on:

* zone (code allowlist `sg-sin1`), plan, hostname and labels;
* encrypted 30 GB Ubuntu 24.04 boot storage with the approved tier;
* password login disabled and one public IPv4 interface;
* the complete ordered firewall rule list derived from the approved SSH CIDRs.

Unknown security-critical values fail closed. Destroy has a separate delete-only policy. Saved-plan metadata binds the Environment, prefix, state key and state lineage/serial.

Workflow concurrency, backend lock and saved-plan state lineage/serial checks prevent concurrent writes. Commit/config/backend fingerprint, lockfile hash, plan hash, trusted workflow run and age are checked. Normal plans reject deletes/replacements/unrecognized resources. Apply uses the exact saved plan. Normal plans expire after 24 hours; destroy after one hour.

After approval only, fill ignored `backend.hcl` from example and use process credentials: `terraform init -backend-config=backend.hcl`. Runtime secrets never enter Terraform/cloud-init/plan. Git ignores state, backup files, plans, real tfvars/backend/env/private keys.

Recovery: stop writers, preserve current encrypted version/audit, verify lineage/serial and cloud inventory, review known-good version with two people, restore through approved backend procedure and run fresh reviewed plan. Never force-unlock until lock owner is dead; never use old state to hide drift/recreate an existing server.

Without approved S3/KMS, live work is BLOCKED. Alternative encrypted/locked backend requires reviewed workflow/backend changes and explicit approval, not silent local state.
