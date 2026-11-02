# Terraform state decision record (Phase 5.16)

Status: **recommendation only. No backend was created, initialized or migrated.** Terraform is pinned to 1.17.1 and the UpCloud provider to 5.48.0.

| Criterion | A. AWS S3 + KMS (current design) | B. Alternative remote backend | C. Local state |
|---|---|---|---|
| Availability | **Unverified.** No S3 bucket or KMS key is known to exist; the repository assumes an approved existing one | Needs a new account or service and workflow changes | Always available |
| Locking | Native `use_lockfile = true` (S3 conditional writes, no DynamoDB). Declared in `versions.tf` | HCP Terraform and GCS lock natively. UpCloud Managed Object Storage works with the S3 backend, but conditional-write/lock support is **unverified** and needs a live test | None across machines |
| Encryption | SSE-KMS enforced and checked by `state_init` | Varies by provider | Only if the operator disk is encrypted |
| Versioning / recovery | Bucket versioning, checked before every run | Provider dependent | Manual copies only |
| IAM least privilege | Prefix-scoped (state key, lock, `reviewed-plans/aiproductdemand/`, one KMS key) | Provider dependent | None |
| GitHub-hosted runners | Works; credentials in Environment secrets | Works | **Incompatible**: state disappears with the runner |
| Setup effort | Existing bucket: low. New bucket: moderate and needs a separate approval | New code and review | None |
| Recurring cost | Cents per month for one small state object plus KMS key and requests (about USD 1 per key per month). **Estimate only; verify on the AWS pricing pages** | Free tier or plan fee, **unverified** | None |
| Main risk | Extra external dependency; blast radius of the AWS credential | Unreviewed workflow changes | Loss or corruption, no concurrency protection, no audit trail |

## Recommendation

**Option A: keep the AWS S3 backend with native lockfile locking**, but only after the owner confirms one of these:

1. An existing private, versioned, TLS-only bucket with SSE-KMS and the least-privilege IAM described in `TERRAFORM.md`.
2. Separate explicit approval to create that bucket and key.

Reasons: the workflows already verify versioning, public-access block and KMS on every run, the saved-plan protocol depends on the same bucket, and no code changes are needed. Option B needs new reviewed code and has unverified lock semantics. Option C is allowed only for a supervised, offline dry run and must never be used for the real deployment. There is no silent fallback; the backend block has no local default.

## Not done / still required

* Confirm bucket, region, KMS key ARN and IAM policy exist (`UNVERIFIED`).
* Test the lock with two concurrent plans on first activation.
* Restore drill: restore a prior state version into a scratch key and run a plan with no changes.
* `backend.hcl.example` is unchanged. Any backend change needs a new approval.
