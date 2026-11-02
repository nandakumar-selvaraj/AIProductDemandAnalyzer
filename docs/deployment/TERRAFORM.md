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

State key is `aiproductdemand/production/terraform.tfstate`, separate from shared portfolio. Scope IAM Get/Put to state, Get/Put/Delete to its lock, reviewed plans to `reviewed-plans/`, and appropriate KMS operations. Ordinary CI should not delete state. Protect versions/backups and expire private saved plans under reviewed retention. Never publish state/plans as Actions artifacts.

Workflow concurrency, backend lock and saved-plan state lineage/serial checks prevent concurrent writes. Commit/config/backend fingerprint, lockfile hash, plan hash, trusted workflow run and age are checked. Normal plans reject deletes/replacements/unrecognized resources. Apply uses the exact saved plan. Normal plans expire after 24 hours; destroy after one hour.

After approval only, fill ignored `backend.hcl` from example and use process credentials: `terraform init -backend-config=backend.hcl`. Runtime secrets never enter Terraform/cloud-init/plan. Git ignores state, backup files, plans, real tfvars/backend/env/private keys.

Recovery: stop writers, preserve current encrypted version/audit, verify lineage/serial and cloud inventory, review known-good version with two people, restore through approved backend procedure and run fresh reviewed plan. Never force-unlock until lock owner is dead; never use old state to hide drift/recreate an existing server.

Without approved S3/KMS, live work is BLOCKED. Alternative encrypted/locked backend requires reviewed workflow/backend changes and explicit approval, not silent local state.
