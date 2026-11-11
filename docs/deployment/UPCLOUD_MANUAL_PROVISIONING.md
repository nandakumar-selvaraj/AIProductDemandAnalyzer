# Manual UpCloud provisioning — owner execution only

Status: NO-GO pending [Phase 5.17 findings](PHASE_5_17_FINAL_VALIDATION.md). These are future owner steps, not permission to spend or execute. This audit creates no resources, administrators, volumes, certificates or GitHub settings. Do not run bootstrap while the SSH/rerun findings remain open.

## 1. Before spending

1. Review the final report; resolve bootstrap and validation blockers and rehearse on a disposable LOCAL Ubuntu24.04 amd64 VM with console access. Test first run, rerun, injected failure and console recovery.
2. Inventory existing UpCloud servers/disks/IPs, legacy Terraform-managed resources and backup destinations. If this app already has a host, stop and reconcile ownership. Never provision both shared and dedicated paths. Preserve all historical state.
3. Obtain explicit owner approval of current Singapore sg-sin1 quote: one Ubuntu Server24.04 LTS amd64 machine, candidate2vCPU/4GB/30GB Starter, public IPv4, approved encrypted storage, no extra resources. Confirm budget including separate backup capacity and fixed-egress runner. No Terraform backend, API token, AWS, S3 or KMS is required.
4. Prepare distinct operator and deployer Ed25519 keys locally; protect operator private key with passphrase. Only public keys go to the server. Record operator public IPv4 /32 and isolated runner egress /32 (at most20 approved global IPv4 CIDRs, /24 or narrower). Never allow world-open SSH.
5. Establish and test an out-of-band recovery method with the provider. Opening a web console alone is not enough: after accounts are password-locked, confirm how recovery/rescue access works without SSH. Keep recovery instructions and access outside the VPS.

## 2. Owner control-panel operation — separate authorization

Use [UpCloud deployment guide](https://upcloud.com/docs/guides/deploy-server/). In the control panel review existing inventory, choose sg-sin1, exact approved plan/template/storage and hostname aiproductdemand-prod. Upload only the operator public key, select key-based access, and do not paste private keys, runtime secrets or historical cloud-init. Confirm the final price and exactly one server before the owner clicks Deploy.

Configure [UpCloud firewall](https://upcloud.com/docs/guides/managing-firewall/) before exposing services: inbound TCP22 only from approved operator/runner CIDRs, TCP80/443 public IPv4, required diagnostic ICMP, then inbound drop; outbound allowed for approved package/GHCR/ACME/SFTP access. Verify rule order and firewall enabled. Assign no public IPv6; do not open5432,8000,8080,8443 or11434. If the panel cannot stage firewall restrictions before creation, review its safe provisioning procedure before continuing.

Record server UUID, disk UUID, region, plan, price and IPv4 in the owner's inventory. STOP at IPv4. Inform the subdomain owner yourself; wait for the A record. Do not deploy the app or create application administrators.

## 3. Trusted access and source preparation — after separate approval

From trusted provider console, record:

```bash
ssh-keygen -lf /etc/ssh/ssh_host_ed25519_key.pub
cat /etc/ssh/ssh_host_ed25519_key.pub
```

Construct a workstation known-hosts file containing IPv4 plus that public host key. Compare fingerprint independently before SSH; never accept a network-only ssh-keyscan result as proof.

Workstation example (replace paths/IP with owner-reviewed values):

```bash
ssh -o StrictHostKeyChecking=yes -o UserKnownHostsFile=./demand-known-hosts -i ./operator-key root@APPROVED_IPV4
```

Use the initial image account documented by the provider if different. Keep original SSH and trusted console open. Stage a reviewed checkout/archive under /root/aipd-reviewed and the two public keys under /root. Verify its exact reviewed commit/hash; do not download and pipe scripts into sudo.

Root shell preflight, read-only:

```bash
id -u
cat /etc/os-release
dpkg --print-architecture
sshd -t
sshd -T
ufw status numbered
ip -4 route
getent passwd operator deployer
getent group docker
test -d /root/aipd-reviewed/deploy/single
bash -n /root/aipd-reviewed/deploy/single/bootstrap-host.sh
```

Require uid0, Ubuntu24.04, amd64, known user/home ownership, no conflicting Docker packages, no broad pre-existing UFW/SSH rules. Stop on differences. Review existing services/data; this installer is not a host migration tool.

## 4. Bootstrap hold gate and eventual command

Current bootstrap overwrites authorized_keys and reloads restrictive SSH without proving a new operator session. KEY-ACCESS-VERIFIED is only an attestation. Reruns accumulate firewall allow rules, overwrite root-owned artifacts and do not atomically recover configuration failures. Do not execute as-is on the paid host until the audit findings are remediated and rehearsed.

After that remediation, the intended interface is:

```bash
# FUTURE ONLY: keep tested recovery console and old session open.
bash /root/aipd-reviewed/deploy/single/bootstrap-host.sh KEY-ACCESS-VERIFIED   /root/operator.pub /root/deployer.pub OPERATOR_PUBLIC_IP/32 RUNNER_PUBLIC_IP/32
```

The two keys must differ. Verify a second operator SSH login and sudo -n true before closing initial access or disabling root access. If the implementation cannot separate key installation/verification from final SSH hardening, STOP; do not compensate by claiming the attestation was satisfied.

Inspect effective policy for operator and deployer, not syntax alone:

```bash
sshd -t
sshd -T -C user=operator,host=localhost,addr=OPERATOR_PUBLIC_IP
sshd -T -C user=deployer,host=localhost,addr=RUNNER_PUBLIC_IP
visudo -c
ufw status numbered
iptables -S DOCKER-USER
iptables -S DEMAND-INGRESS
docker version
docker compose version
systemctl is-active docker
sysctl net.ipv6.conf.all.disable_ipv6
```

Require root/password/interactive SSH disabled, operator key access working, deployer forced-command/no forwarding/no TTY, neither user in docker group, only22 from approved sources and80/443 exposed. Test from allowed and disallowed source networks. Check Docker filtering again after a reviewed daemon restart/reboot; bootstrap currently does not restart an existing daemon for changed logging configuration.

## 5. Failure and rerun recovery

Keep the original shell/console open. If sshd -t fails, do not reload. If access fails, use the already tested provider recovery channel; restore the owner-saved known-good SSH/sudo/firewall configuration, validate syntax and reopen only the exact approved operator source. Do not flush firewalls, enable password/world-open root login, delete disks or reprovision as a shortcut. If no tested recovery method exists, do not begin.

Before any rerun compare installed keys/configuration, retain root-only copies and plan a maintenance window. Do not use bootstrap as key rotation, firewall CIDR removal, package migration or release update. Current rerun safety has not passed a real host test.

## 6. Stop and later handoff

Host preparation does not start app images, migrations or administrators. Record proof of access, firewall, clock/updates, Docker and recovery; stop for owner review. Domain/DNS/TLS and runtime setup require separate approval.

Later order: approved GHCR digests and root-only runtime files; [Compose](DOCKER_COMPOSE.md) external volume/database-only setup; [encrypted SFTP backup and isolated restore](BACKUP_RESTORE.md); enable verified backup timer; friend-provided A record with no stale AAAA; [HTTPS](DOMAIN_HTTPS.md); protected [application release](GITHUB_ACTIONS.md); external acceptance. Never create a receipt/TLS marker to bypass failed checks. Admin creation is a separate owner operation after deployment, not bootstrap.

No active dedicated step uses Terraform, AWS or S3. Archived dedicated instructions are historical and inactive. Legacy shared workflows must not be dispatched.
