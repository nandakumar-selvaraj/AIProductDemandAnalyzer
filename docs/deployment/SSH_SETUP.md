# SSH and hardening

Windows operator commands (documentation only):

```powershell
ssh-keygen -t ed25519 -C "aiproductdemand-upcloud" -f "$HOME\.ssh\aiproductdemand_upcloud"
Get-Content "$HOME\.ssh\aiproductdemand_upcloud.pub"
```

Protect private key with passphrase/Windows ACLs. Generate a distinct CI key; only public halves enter Terraform. CI private half (an unencrypted Ed25519 key, used only by the isolated runner) is Environment secret `AIPD_DEPLOY_SSH_PRIVATE_KEY`. Never upload a private key to metadata/Terraform.

Cloud-init creates `operator` for manual bootstrap/recovery and `deployer` for restricted CI. Neither joins root-equivalent Docker group. Operator bootstrap sudo is deliberately full-root recovery authority; restrict/audit it. Deployer can invoke only fixed root-owned `demand-release`, has a forced SSH command, no PTY/agent/TCP forwarding and no write access to deployment code/config.

After approved provisioning verify key access in two sessions plus console recovery, inspect `cloud-init status --wait`/logs privately and Docker/Compose versions. Then run:

```sh
sudo /usr/local/sbin/demand-harden-ssh KEY-ACCESS-VERIFIED
sudo sshd -T
```

No generated password is requested; account passwords are locked, root SSH disabled and `ssh_pwauth: false` already disables password login. The manual step verifies key access before installing/reloading explicit final authentication policy. There is no temporary password access. Keep console recovery for key/image failure; never widen SSH automatically.

UpCloud filtering: TCP80/443, TCP22 from 1–20 approved IPv4 /24-or-narrower CIDRs, ICMP diagnostics, final inbound drop. UFW supplements it. No assigned IPv6 and no 5432/8000/8080 public mapping. Use approved isolated fixed-egress runner outside production VPS, add its /32; never all GitHub-hosted addresses or world-open SSH. Verify the host key via the trusted console and store the exact `AIPD_DEPLOY_SSH_KNOWN_HOSTS`; do not blindly trust ssh-keyscan.

## Independent host-key verification (after approved provisioning)

1. Open the server's console in the UpCloud control panel (an out-of-band channel, not the SSH path) and run `ssh-keygen -lf /etc/ssh/ssh_host_ed25519_key.pub`. Record the `SHA256:...` value.
2. From the operator workstation, run `ssh-keyscan -t ed25519 <IPv4>` and `ssh-keygen -lf -` on that output. Accept the key **only** if the fingerprint equals the console value. If it doesn't match, stop and treat it as a possible interception.
3. Store the single line `<IPv4> ssh-ed25519 <key>` as `AIPD_DEPLOY_SSH_KNOWN_HOSTS`, and the console fingerprint, as a separate value, as `SINGLE_DEPLOY_HOST_KEY_FINGERPRINT`. Transport rejects the deploy unless both agree and the IP equals `SINGLE_DEPLOY_HOST`.
4. After a rebuild or host-key rotation, repeat these steps. Never update the fingerprint from the same network observation as the key.

Client options force publickey only, with no agent, X11 or port forwarding, no TTY, `StrictHostKeyChecking=yes` and an isolated known-hosts file. On the server side, sshd sets `PasswordAuthentication no`, `KbdInteractiveAuthentication no`, `AuthenticationMethods publickey` and `PermitRootLogin no`. The deployer has `ForceCommand sudo -n /usr/local/sbin/demand-release` and no TCP, stream-local, tunnel or TTY.
