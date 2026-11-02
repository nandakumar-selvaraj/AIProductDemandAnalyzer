# Cost estimate — checked 2026-11-02

[Official UpCloud pricing](https://upcloud.com/pricing/) lists Starter2vCPU/4GB,30GB storage at EUR12/month, primary IPv4 included. [Deployment guide](https://upcloud.com/docs/guides/deploy-server/) documents included Standard storage for Starter, MaxIOPS for Premium. Configuration uses30GB Standard. Exact plan identifier/account-visible Singapore capacity still require catalog review; no authenticated cloud query run.

| Item | Provisional assumption |
|---|---|
| One Starter VPS/included disk/IPv4 | EUR12/month |
| Hourly equivalent | About EUR0.01786/hour at28-day/672h cap; verify account hourly quote |
| Off-host encrypted backup | Destination/minimum/storage/API/retention charges unselected |
| Encrypted S3/KMS state | Existing approved account assumed; storage/KMS requests additional |
| GHCR/Actions/fixed-egress runner | Existing allowance/runner assumed, extra usage possible |
| AI | Disabled |

EUR12 is a base estimate, not approved total. Taxes, conversion, state, backup and runner costs excluded. Recheck all quotes before spending; pricing page announces November16 changes. No guessed currency conversion.

One app VPS, no managed DB/Kubernetes/load balancer/extra IP/other-demo resources; explicit plan/state/locks/manual operations prevent duplicates and unapproved spend. Stopping VPS does not establish zero charges: disks/backups/IPs/retained services may bill. Inventory before first apply and after teardown.
