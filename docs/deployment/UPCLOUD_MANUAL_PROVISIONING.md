# Manual UpCloud provisioning

**NO-GO.** Owner execution requires the full disposable Ubuntu 24.04 amd64 VM rehearsal, reviewed CI evidence and separate approval for the Singapore cost. See the [Phase 5.17.1 report](PHASE_5_17_1_SECURITY_REMEDIATION.md).

## 1. Before spending

1. Inventory existing servers, disks, IPs, legacy Terraform resources and the separate backup destination. If a host already serves this app, stop and reconcile ownership. Preserve historical state.
2. Approve the exact Singapore `sg-sin1` quote for one Ubuntu Server 24.04 LTS amd64 VPS, public IPv4 and encrypted storage. Review the candidate Starter 2 vCPU, 4 GB, 30 GB sizing and include SFTP capacity, transfer costs, taxes and fixed-egress CI. Use an existing approved backup failure domain.
3. Prepare distinct operator and deployer Ed25519 keys. Passphrase-protect the operator key. Prepare operator and runner public IPv4 /32s, or approved public networks /24 or narrower. Confirm the fixed-egress runner is outside the VPS.
4. Rehearse packages, fresh install, repeat preparation, failed preparation, interruption and recovery, SSH through approved and disallowed sources, IPv6 denial, Docker DNAT and restart, and boot persistence. Keep a tested provider-console root recovery method outside the VPS.

## 2. Control panel and initial access

After separate approval, choose the approved plan, Ubuntu template, storage and hostname `aiproductdemand-prod`. Upload only the operator public key for initial provider access. Record the instance, disk and IPv4 in inventory. Stop at the IPv4 for the subdomain owner. [UpCloud server deployment guide](https://upcloud.com/docs/guides/deploy-server/)

Configure the provider firewall with IPv4 TCP 22 restricted to the approved CIDRs, IPv4 TCP 80 and 443, approved diagnostic ICMP and default drop. Use IPv4 only. The provider firewall is stateless. Verify the reviewed rules permit return traffic needed by approved DNS, HTTPS and SFTP egress while the host firewall admits only tracked responses. Test package downloads and inbound access during the isolated rehearsal, and test the provider policy under separate authorization. [UpCloud firewall rules](https://upcloud.com/docs/guides/managing-firewall/)

Obtain the host key and its fingerprint directly from the trusted console.

```bash
ssh-keygen -lf /etc/ssh/ssh_host_ed25519_key.pub
cat /etc/ssh/ssh_host_ed25519_key.pub
```

Use the console-obtained key in a dedicated known-hosts file. Keep the initial SSH session and an authenticated root console open. Stage the reviewed, root-owned checkout under `/root/aipd-reviewed` and the two public keys under `/root`. Verify the commit and ownership of the checkout and all parent directories. Require the stock supported SSH Include layout, installed `sshd`, `sudo` and `iptables-save` utilities, a synchronized clock, unused dedicated account names and homes, and no active legacy firewall or prior container installation. Stop on conflicts.

## 3. Stage A prepares access

From the existing root console or initial root shell, run the following after replacing the example addresses with approved values.

```bash
bash /root/aipd-reviewed/deploy/single/bootstrap-host.sh prepare \
  /root/operator.pub /root/deployer.pub OPERATOR_PUBLIC_IP/32 RUNNER_PUBLIC_IP/32
```

Preparation creates the dedicated accounts, separate primary groups, public keys and validated sudoers file. It preserves the initial SSH daemon configuration and existing recovery access. It prints an expiring challenge and the host key fingerprint. Repeat preparation with identical inputs while staged to issue a new challenge. Complete the other stages within 30 minutes of that challenge, with adequate time for package installation. An interrupted account setup blocks retries until reviewed from the console.

## 4. Stage B proves independent access

Open a **new, non-multiplexed** operator connection from an approved source. Pin the console-obtained host key. Disable connection sharing for this proof.

```bash
ssh -o ControlMaster=no -o ControlPath=none -o StrictHostKeyChecking=yes \
  -o UserKnownHostsFile=./demand-known-hosts -o IdentitiesOnly=yes \
  -i ./operator-key operator@APPROVED_IPV4
```

In that new SSH session, run:

```bash
sudo -n bash /root/aipd-reviewed/deploy/single/bootstrap-host.sh verify CHALLENGE
```

The verifier requires the sudo operator identity and a fresh successful OpenSSH Ed25519 login journal entry tied to the session process, the prepared public key and the approved source address. In the separate authenticated root provider console, run:

```bash
bash /root/aipd-reviewed/deploy/single/bootstrap-host.sh recovery CHALLENGE
```

It requires a local virtual or serial terminal. Keep both verified sessions available. Resolve missing journal entries, absent console access or a host identity mismatch before proceeding.

## 5. Stage C finalizes the host

From the console with both proof records current:

```bash
bash /root/aipd-reviewed/deploy/single/bootstrap-host.sh finalize CHALLENGE
bash /root/aipd-reviewed/deploy/single/bootstrap-host.sh check
```

Finalization is a one-time operation for a fresh host. It rejects existing customized targets, container data and active legacy rule sets. It validates staged candidates, commits only the dedicated nftables table, and loads the firewall before Docker installation can start the daemon. The systemd dependency loads the guard before Docker and its activation socket at boot. The host applies IPv4 default-drop input/forward rules and explicit IPv6 drops. Forwarded ingress must be Docker DNAT from IPv4 ports 80/443 to the exact Nginx ports. Compose binds only those two IPv4 ports. Test DHCP/address renewal, Docker restart, routing and reboot on the disposable VM before provisioning.

The SSH candidate is checked before publication and again before reload using `sshd -t`, `sshd -T -C` and `visudo -c`. Verify another operator login and sudo after reload, reject root SSH and test deployer restrictions. Keep the original sessions open until those checks and console recovery pass.

Use `check` for subsequent inspection. For an approved CIDR change, keep the verified operator source in the complete replacement list and use the root console:

```bash
bash /root/aipd-reviewed/deploy/single/bootstrap-host.sh firewall-update OPERATOR_PUBLIC_IP/32 NEW_RUNNER_PUBLIC_IP/32
```

This removes obsolete entries from the dedicated table in one checked transaction. If interrupted between persisting the candidate and runtime commit, active rules remain a complete policy. Compare `nft list table inet demand_ingress` with `/etc/demand/firewall.nft` at the console before retrying. Coordinate the separately administered provider rules and test the new runner before removing its old route. Changing the verified operator source, migrating an existing Docker host, or changing privileged assets requires separate maintenance.

## 6. Failure recovery and later handoff

A rejected SSH candidate leaves the original running daemon policy. A validation or reload failure after publishing restores the original fragment set when possible. Use the retained console and `/var/lib/demand/sshd-before.conf` plus the original unchanged drop-ins to investigate. A force kill can happen outside cleanup. Review the live and boot configuration from the console, repair it to the known policy, and confirm approved access. Keep narrowly scoped firewall rules and key-only access during recovery. An interrupted finalization leaves `finalize-in-progress.json` and blocks a fresh retry. Review what completed, preserve data, and repair under the owner’s maintenance procedure.

Finalization starts infrastructure services only. After separate runtime authorization, install reviewed GHCR digests and root-private runtime files, arrange [Compose database-only setup](DOCKER_COMPOSE.md), obtain [encrypted backup and isolated restore acceptance](BACKUP_RESTORE.md), configure DNS and [HTTPS](DOMAIN_HTTPS.md), then approve the [application release](GITHUB_ACTIONS.md). Create the production application administrator separately after release using the owner migration service. Dedicated Terraform and its state backend are inactive.
