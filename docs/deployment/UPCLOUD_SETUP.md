# UpCloud setup — separate approval required

No UpCloud credentials were read, no live plan was run and no cloud resource was modified.

1. Review architecture, cost, state and GitHub protections. Select this dedicated root only; do not also provision shared-portfolio infrastructure.
2. Inventory existing servers/storage and all relevant state. Reconcile/import an existing deployment rather than creating duplicates. Use only dedicated state key `aiproductdemand/production/terraform.tfstate`.
3. Verify Singapore `sg-sin1`, account-visible 2 vCPU / 4 GB plan and capacity. `server_plan` has no assumed default. Candidate Starter uses included 30 GB Standard storage; Premium needs a revised quote/tier.
4. Verify public template `Ubuntu Server 24.04 LTS (Noble Numbat)`, encryption and plan/tier compatibility. Offline provider validation cannot prove account/zone availability.
5. Configure distinct operator/deployer public keys, narrow SSH CIDRs and protected configuration. Existing credential name is `UPCLOUD_TOKEN`.
6. Obtain explicit authorization before manual live planning; review the exact private encrypted plan, commit/digest, resource count, region, image, storage, price and firewall.
7. Obtain separate authorization/environment approval before apply. Stop at IPv4 output and send it to subdomain owner. No automatic application deployment.
8. Verify console recovery, cloud-init/key access; harden SSH, then perform separately approved runtime/volume/backup/DNS/TLS setup and application deployment.

Official sources checked 2026-11-02: [server schema](https://registry.terraform.io/providers/UpCloudLtd/upcloud/5.48.0/docs/resources/server), [firewall schema](https://registry.terraform.io/providers/UpCloudLtd/upcloud/5.48.0/docs/resources/firewall_rules), [UpCloud deployment guide](https://upcloud.com/docs/guides/deploy-server/). The documented Ubuntu template is used; live account catalog and regional capacity remain an approval gate.
