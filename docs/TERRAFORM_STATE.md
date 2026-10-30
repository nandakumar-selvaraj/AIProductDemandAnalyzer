# Private remote state and reviewed plans

Use a separately administered **native AWS S3** bucket with versioning, all four Block
Public Access flags, bucket-owner-enforced ownership, HTTPS-only policy, default SSE-KMS
encryption and a dedicated KMS key. No bucket/key/account is created by this repository.
Approve any AWS storage/request/KMS costs separately; check current regional pricing and
retention volume. UpCloud API tokens cannot authenticate to this backend.

Create the bucket/key through an approved administrative process, not the VPS module.
Use separate state credentials scoped to this bucket/key. Populate GitHub Environment
variables and secrets described in GITHUB_PRODUCTION_ENVIRONMENT.md. Native S3 lockfiles
are enabled (`use_lockfile=true`) and Terraform is version constrained/locked. Do not
substitute an arbitrary S3-compatible endpoint: its conditional-write/locking, versioning
and encryption semantics have not been validated here.

Object layout:

```text
portfolio/production/terraform.tfstate
portfolio/production/terraform.tfstate.tflock
reviewed-plans/<github-plan-run-id>/reviewed.tfplan
reviewed-plans/<github-plan-run-id>/metadata.json
```

Identity permissions: bucket List/GetLocation/GetVersioning/GetEncryptionConfiguration/
GetPublicAccessBlock; state object Get/Put; lock object Get/Put/Delete; reviewed-plan
prefix Get/Put; KMS Encrypt/Decrypt/GenerateDataKey/DescribeKey for that key only. Enforce
TLS and the intended KMS key in bucket policy; deny public/cross-account access. State
identity has no server/backup access. Allow plan cleanup only to a separate administrator
or bucket lifecycle policy. Enable account audit logging using the approved cloud policy.

Keep recoverable state versions; restrict deleting noncurrent versions. Apply an approved
lifecycle to reviewed-plan objects (for example 7 days, with bounded noncurrent versions);
the automation rejects plans older than 24 hours even while encrypted objects remain.
Review KMS/key deletion safeguards: losing a key makes state/plan recovery impossible.

`terraform init` receives only bucket/key/region/KMS configuration; credentials come from
AWS_* environment variables. Init checks versioning, public-access blocking and default
KMS encryption. Lockfile/provider hashes are checked for Linux/Windows. Never enable
TF_LOG/TF_LOG_PROVIDER or inject TF_CLI_ARGS in credentialed jobs.

Plan uses real read-only provider refresh under the backend lock but never applies.
Only resource addresses/actions, allowlisted public plan/zone/storage settings and plan SHA256 are printed; delete/replacement actions
are rejected. Raw JSON/binary plans, backend cache and state are never Actions artifacts.
Saved plans may still contain sensitive provider data, so encryption/access controls are
mandatory. Plan metadata binds commit, input fingerprint and provider lockfile checksum.

Apply requires the successful plan run ID, exact master SHA, reviewed SHA256, unchanged
configuration and age <24h. Do not advance master between plan approval and apply; if it
changes, create/review a new plan. The saved-plan apply checks stale state rather than
quietly replanning, and shares a global non-cancelling workflow concurrency group with plan.

Recovery: stop other writers, confirm no active operation before any force-unlock, obtain
the intended S3 version through a restricted operator, record lineage/serial and reconcile
with actual UpCloud resources. Do not blindly replace state, force-push it or delete a lock.
If Terraform writes emergency local state after a backend failure, treat it as a secret,
recover it privately and never upload it as a GitHub artifact or commit it.

Reference: [HashiCorp S3 locking and versioning](https://developer.hashicorp.com/terraform/language/backend/s3).
