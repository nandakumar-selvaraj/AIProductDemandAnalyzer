# Phase 8A infrastructure preparation

Prepared and validated locally, 2026-10-30. A local commit was explicitly requested after
review. No Terraform apply/destroy, paid resource creation, UpCloud deployment, production
credential generation or push was performed.

## Layout

- `infrastructure/terraform/`: Terraform 1.17.1, official UpCloud provider 5.48.0 lock,
  Ubuntu 24.04 LTS, one configurable VPS, encrypted persistent storage, IPv4, ordered
  firewall rules, cloud-init and public connection outputs. No domain input exists.
- `infrastructure/automation.py`: fail-closed Environment checks, catalog/state checks,
  sanitized plan review, encrypted saved-plan storage, exact-plan apply and SSH release
  orchestration. `images.py` gates release manifests on exact-image vulnerability scans.
- `.github/workflows/terraform-{validate,plan,apply}.yml`, `docker-build.yml`,
  `production-deploy.yml`: separate validation, review, provisioning and deployment.
- `deploy/ops/`: immutable-image Compose overlay, one shared Caddy, restricted root-owned
  release entrypoint, encrypted off-host backups, restore rehearsal and monitoring.

See [GitHub setup](GITHUB_PRODUCTION_ENVIRONMENT.md), [state setup](TERRAFORM_STATE.md),
[provisioning/deployment](UPCLOUD_RUNBOOK.md) and [hostname lifecycle](TEMPORARY_SUBDOMAIN.md).

## Security and failure boundaries

The deploy SSH identity is not in the Docker or sudo-admin group. Its sole passwordless
sudo command is the installed root-owned release entrypoint, which accepts a small JSON
contract, approved repositories and full digests. A distinct operator key has root-equivalent
administrative access. Both keys are public Terraform inputs; private keys never enter
Terraform, tfvars or cloud-init. Password/root SSH login is disabled. SSH source CIDRs
are explicit IPv4 ranges; GitHub-hosted runner IPs are not assumed to be stable.

Only Caddy publishes 80/443. Its sole added capability is NET_BIND_SERVICE, required by
the official image's file capability/low ports; all other capabilities are dropped and
no-new-privileges/read-only root are retained. APIs/frontends use an app-specific edge
network. The DB/migration service remain on a private internal network. Future demos get
separate networks, volumes and credentials; no other demo/server is created here.

Raw plans and state are never Actions artifacts. A plan is encrypted in the private state
bucket and bound to commit, configuration fingerprint, provider lock and SHA256, with a
24-hour approval lifetime. Apply accepts that saved plan only; Terraform additionally
checks stale state under its backend lock. Both Terraform workflows share a non-cancelling
concurrency group. Deletion/replacement plans are rejected, and server/data resources
have prevent_destroy. Application deploy/rollback has a separate workflow + host lock.

Every release requires four successful push workflows on the same master commit, then
scans all four runtime images before publishing a non-secret digest manifest. Failed scans
produce no verified release artifact. Published candidates are not automatically deployed.
Deploy requires the successful build-run identity, protected production approval, exact DNS,
verified SSH host key, private host configuration, encrypted backup and a successful restore
before migration. App rollback never downgrades schemas, deletes volumes or silently
reverts PostgreSQL. A failed migration/deploy remains visible and needs operator action.

## Resource/cost review

Start catalog review at 2 vCPU/4 GB RAM; plan and zone have no vendor-specific default.
The configuration requests a 25 GB boot disk plus a separate 40 GB encrypted data disk
(configurable). Review the entire regional compute + disk + IPv4 + off-host backup +
state/KMS + GitHub usage quote against the shared $10–$20 budget before authorizing apply.
Included plan storage does not imply the extra disk is free. No current price is hardcoded.
If the quote exceeds budget, stop and change the reviewed design/plan; do not silently buy.
Three light apps' documented container ceilings leave limited headroom on 4 GB; build on
CI and serialize heavy imports/migrations. No production Ollama or paid inference is enabled.

Local timers check CPU load, available RAM, free disk, readiness, certificate lifetime and
backup age; failures appear in journald/systemd and workflow summaries. These are local
checks, not an external notification or uptime guarantee. Before launch, assign an operator
to review failures and configure an approved off-host alert path; no paid monitoring is added.

## Verification record

See the current [validation report](PHASE8A_VALIDATION.md). Terraform mock tests do not
prove actual UpCloud capacity, account permissions, boot/disk device order or cloud-init
execution. Trivy currently reports no high/critical findings for this module, but its
UpCloud-specific coverage is limited: custom safety tests and manual review remain necessary.
Real remote state, real authenticated plan, approval gates, VPS boot, external DNS/TLS and
off-host disaster recovery must be verified only in an explicitly authorized next phase.

Sources: [official UpCloud provider](https://registry.terraform.io/providers/UpCloudLtd/upcloud/latest/docs),
[UpCloud token authentication](https://upcloud.com/docs/guides/managing-api-tokens/),
[Terraform S3 backend](https://developer.hashicorp.com/terraform/language/backend/s3),
[GitHub environment protections](https://docs.github.com/en/actions/reference/workflows-and-actions/deployments-and-environments).
