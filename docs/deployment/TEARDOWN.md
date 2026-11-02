# Manual teardown — not executed

1. Obtain explicit teardown authorization/production selection; record UUIDs from state/cloud inventory, confirm dedicated app rather than shared VPS.
2. Block writes, final encrypted off-host backup, isolated restore, record evidence/snapshot retention/password escrow. Protect release manifests/schema/runtime recovery config. Approve data-loss/DNS decisions.
3. Review code change removing prevent_destroy ONLY from dedicated server. Destroy plan intentionally fails until removed. Retain provider/state key.
4. Dispatch single-terraform-destroy.yml: destroy-plan, exact reviewed commit, production, OFFHOST-RESTORE-VERIFIED. Reviewer must inspect evidence; string is only an attestation.
5. Review exact encrypted destroy plan/digest/commit, attached boot-storage deletion and inventory. Separately dispatch destroy-apply with environment approval within1h. State serial/lineage/config/lockfile/hash must match; no silent replan.
6. Inspect billable orphan storage/snapshots/backups/templates/extra or floating IPs and prior unmanaged services. Terraform absence does not prove billing stopped; review cloud usage.
7. Remove DNS/revoke CI/disable runner usage only as separately approved. Retain/expire backup/state under policy. External state/KMS/backup services are not deleted by this root and may retain costs.

Never destroy from PR/push/merge/timer, failed deployment recovery or ordinary update. Never use volume prune/down -v. Preserve encrypted recovery audit.
