# SSH and hardening

Windows operator commands (documentation only):

```powershell
ssh-keygen -t ed25519 -C "aiproductdemand-upcloud" -f "$HOME\.ssh\aiproductdemand_upcloud"
Get-Content "$HOME\.ssh\aiproductdemand_upcloud.pub"
```

Protect private key with passphrase/Windows ACLs. Generate a distinct CI key; only public halves enter Terraform. CI private half is protected `DEPLOY_SSH_PRIVATE_KEY`. Never upload a private key to metadata/Terraform.

Cloud-init creates `operator` for manual bootstrap/recovery and `deployer` for restricted CI. Neither joins root-equivalent Docker group. Operator bootstrap sudo is deliberately full-root recovery authority; restrict/audit it. Deployer can invoke only fixed root-owned `demand-release`, has a forced SSH command, no PTY/agent/TCP forwarding and no write access to deployment code/config.

After approved provisioning verify key access in two sessions plus console recovery, inspect `cloud-init status --wait`/logs privately and Docker/Compose versions. Then run:

```sh
sudo /usr/local/sbin/demand-harden-ssh KEY-ACCESS-VERIFIED
sudo sshd -T
```

No generated password is requested; account passwords are locked, root SSH disabled and `ssh_pwauth: false` already disables password login. The manual step verifies key access before installing/reloading explicit final authentication policy. There is no temporary password access. Keep console recovery for key/image failure; never widen SSH automatically.

UpCloud filtering: TCP80/443, TCP22 from 1–20 approved IPv4 /24-or-narrower CIDRs, ICMP diagnostics, final inbound drop. UFW supplements it. No assigned IPv6 and no 5432/8000/8080 public mapping. Use approved isolated fixed-egress runner outside production VPS, add its /32; never all GitHub-hosted addresses or world-open SSH. Verify host key via trusted console and store exact `DEPLOY_SSH_KNOWN_HOSTS`; do not blindly trust ssh-keyscan.
