# GitHub production Environment setup

Repository: `nandakumar-selvaraj/AIProductDemandAnalyzer`. Create an Environment named
`production` under Settings → Environments. Environment declarations in YAML do not
configure protections: an automatically created unprotected environment is insufficient.
Select only branch `master`, require an independent reviewer, prevent self-review and
disable administrator bypass. The orchestration script checks these settings and refuses
to operate otherwise. Verify that the repository/account plan supports required reviewers;
do not upgrade billing automatically if unavailable. No default reviewer is invented.

## Environment secrets (enter in GitHub, never paste into this repository)

| Name | Purpose |
|---|---|
| UPCLOUD_TOKEN | Scoped UpCloud API token, read from `${{ secrets.UPCLOUD_TOKEN }}` and passed directly as provider-supported UPCLOUD_TOKEN |
| TF_STATE_ACCESS_KEY_ID / TF_STATE_SECRET_ACCESS_KEY | Separate AWS identity for the dedicated encrypted S3 state/plan bucket and KMS key |
| DEPLOY_SSH_PRIVATE_KEY | Dedicated deployment Ed25519 private key; never the operator key; CI supports a noninteractive key stored only as an encrypted GitHub secret |
| DEPLOY_SSH_KNOWN_HOSTS | Host-key line verified independently through the UpCloud console after provisioning; no automatic ssh-keyscan trust-on-first-use |

No database/JWT/Restic secrets are passed through GitHub or cloud-init in this design.
They remain in root-only host files provisioned explicitly by the operator in Phase 8B.
Backup credentials must differ from both UpCloud and Terraform-state credentials.

## Environment variables (non-secret)

| Name | Value / timing |
|---|---|
| UPCLOUD_ZONE | Verified current UpCloud zone; maps to TF_VAR_zone |
| UPCLOUD_PLAN | Verified current 2 CPU/4 GB target plan; maps to TF_VAR_plan |
| SSH_ALLOWED_CIDRS | JSON list, e.g. `["203.0.113.10/32"]`; use real operator and trusted static runner egress CIDRs, never this documentation address |
| DEPLOY_USER | `deployer` (must match Terraform input/cloud-init) |
| DEPLOY_SSH_PUBLIC_KEY | Public counterpart of the dedicated deployment key |
| OPERATOR_SSH_PUBLIC_KEY | Distinct operator key material, not merely a different comment |
| TF_STATE_BUCKET / TF_STATE_REGION / TF_STATE_KMS_KEY | Dedicated native AWS S3 bucket, AWS region and full KMS key ARN; not UpCloud region/token |
| DEPLOY_HOST | Terraform's public IPv4; leave unset until VPS exists |
| APP_DOMAIN | Lowercase temporary hostname; leave unset until friend creates DNS |
| ACME_EMAIL | Real operator contact email, required for certificate deployment only |
| DEPLOY_RUNNER_LABEL | Optional trusted static-egress runner label; runner must be outside the VPS and permitted by SSH_ALLOWED_CIDRS |
| POSTGRES_RUNTIME_IMAGE | After the first successful image build, pin its postgres digest here; changing the DB digest requires separate maintenance |
| CADDY_RUNTIME_IMAGE | Optional reviewed Caddy digest; defaults to scanning the current official 2-alpine candidate |

Required missing/placeholder values cause failure. Domain/email are deliberately not read
by Terraform workflows. Apply outputs IP and stops; it cannot deploy the application.

Use the existing three CI workflows plus Terraform validation. Image publication waits for
all four on the exact master SHA. `workflow_run` publication accepts only same-repository
master push events; PR/fork completions cannot publish. Actions are commit-pinned, package
write is confined to the build job, and no production deployment runs on push.

GHCR packages must be explicitly made public after owner review or the operator must
configure a narrowly scoped read-only pull identity on the VPS. Publishing a new package
does not automatically make it public. Never forward the Actions write token to the server.

GitHub API access must allow the protected Environment read checks and Actions run/artifact
reads. If those checks fail, fix permissions rather than removing the protection gate.

## SSH runner reachability

GitHub-hosted egress ranges can change. Do not open SSH to 0.0.0.0/0 to make deployment
work. Use an approved static-egress runner/controlled network or redesign the transport
before Phase 8B. Do not install a general-purpose self-hosted Actions runner on the VPS.
The deployment user cannot configure its own network/firewall or modify installed scripts.

The current Environment creation/protection status is recorded in PHASE8A_VALIDATION.md;
workflow files alone are not evidence that live GitHub settings or secrets exist.
