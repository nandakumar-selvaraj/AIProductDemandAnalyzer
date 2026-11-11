# Manual provisioning cost and capacity — 2026-11-10

The [official UpCloud calculator](https://calc.upcloud.com/cloud-servers?currency=USD) lists 2-core/4-GB/30-GB Starter at USD14/month with public IPv4 included. This is a public estimate, not an account/region quote or approval. Recheck Singapore availability, taxes, encryption/storage tier and checkout total before authorization. [Configurations](https://upcloud.com/docs/products/cloud-servers/configurations/) identify STARTER-2xCPU-4GB.

| Item | Budget assumption |
| --- | --- |
| One dedicated VPS | Approx. USD14/month before tax; confirm actual quote |
| Separate encrypted SFTP/Restic storage | Unquoted; existing off-server capacity is not presumed free |
| GHCR/Actions and fixed-egress runner | Verify allowances and network/runner charges separately |
| Domain | Friend-provided subdomain pending |
| AI | Disabled, no paid inference activated |
| Dedicated Terraform/S3/KMS state | Inactive; no required state cost in this path |

USD10–20 total is not yet demonstrated; backup, runner and tax may exceed it. This is one app, not tested capacity for three demos. Legacy resources may still bill; inventory separately without deleting them.

Compose memory caps: backend1536MiB, DB768MiB, frontend96MiB, ingress96MiB. Concurrent migration adds another backend-sized limit; restore verification adds768MiB. Limits are not measured use. Reserve OS/Docker memory and avoid migration/restore overlap on4GB. Forecast/data load testing remains required. Keep at least5GiB free and disk usage below85% (host-check gate). Disk must hold DB growth, images, logs and update headroom. Build in CI, not on the VPS; no production Ollama.

Stopping a VPS does not establish zero billing. Do not execute historical teardown instructions.
