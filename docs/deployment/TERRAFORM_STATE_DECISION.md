> HISTORICAL AND INACTIVE for the Phase 5.17 dedicated manual deployment. Do not execute Terraform, AWS, S3/KMS or teardown instructions below. Preserve existing resources/state. Prior passes are not current evidence. Use [manual provisioning](UPCLOUD_MANUAL_PROVISIONING.md) and [final validation](PHASE_5_17_FINAL_VALIDATION.md).

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

## Shared bucket, separate prefixes (Phase 5.16.1)

Reusing the portfolio bucket with a separate key is acceptable **only** with a dedicated IAM principal whose policy is limited to this project's prefixes and key. With one shared credential, either project could read or overwrite the other's state, and a compromise of one exposes both. A separate bucket is simpler to reason about and costs about the same, so it is preferred when one is being created anyway.

Minimum policy for the dedicated principal (credentials go only into `AIPD_TF_STATE_*` in the `aiproductdemand-production` Environment):

| Purpose | Actions | Resource |
|---|---|---|
| Pre-flight bucket checks (`state_init`) | `s3:GetBucketVersioning`, `s3:GetBucketPublicAccessBlock`, `s3:GetEncryptionConfiguration` | `arn:aws:s3:::BUCKET` |
| Listing (Terraform S3 backend) | `s3:ListBucket`, with condition `s3:prefix` limited to `aiproductdemand/production/*` and `reviewed-plans/aiproductdemand/*` | `arn:aws:s3:::BUCKET` |
| State read/write | `s3:GetObject`, `s3:PutObject` | `arn:aws:s3:::BUCKET/aiproductdemand/production/terraform.tfstate` |
| Lockfile | `s3:GetObject`, `s3:PutObject`, `s3:DeleteObject` | `arn:aws:s3:::BUCKET/aiproductdemand/production/terraform.tfstate.tflock` |
| Reviewed plans | `s3:GetObject`, `s3:PutObject` | `arn:aws:s3:::BUCKET/reviewed-plans/aiproductdemand/*` |
| Encryption | `kms:Encrypt`, `kms:Decrypt`, `kms:GenerateDataKey`, `kms:DescribeKey` | the one KMS key ARN |

No `s3:DeleteObject` on state, no `s3:PutBucket*` and no `kms:*Key*Policy`. The bucket policy should deny non-TLS access and unencrypted puts. Add a lifecycle rule expiring `reviewed-plans/aiproductdemand/` after the review window. Confirm the exact action names against the current Terraform S3 backend and AWS IAM docs before use.

## Not done / still required

* Confirm bucket, region, KMS key ARN and IAM policy exist (`UNVERIFIED`).
* Test the lock with two concurrent plans on first activation.
* Restore drill: restore a prior state version into a scratch key and run a plan with no changes.
* `backend.hcl.example` is unchanged. Any backend change needs a new approval.
