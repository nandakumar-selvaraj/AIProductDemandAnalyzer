#!/bin/bash
# New server only. No application secrets, domain, credentials or paid AI configuration.
set -euo pipefail
export DEBIAN_FRONTEND=noninteractive
systemctl mask docker.service docker.socket
apt-get update
apt-get install -y ca-certificates curl gnupg python3 restic unattended-upgrades ufw sysstat jq
install -m 0755 -d /etc/apt/keyrings /etc/portfolio/sites /var/lib/portfolio
curl --fail --silent --show-error https://download.docker.com/linux/ubuntu/gpg -o /etc/apt/keyrings/docker.asc
chmod 0644 /etc/apt/keyrings/docker.asc
. /etc/os-release
printf 'deb [arch=%s signed-by=/etc/apt/keyrings/docker.asc] https://download.docker.com/linux/ubuntu %s stable\n' "$(dpkg --print-architecture)" "$VERSION_CODENAME" > /etc/apt/sources.list.d/docker.list
apt-get update
apt-get install -y docker-ce docker-ce-cli containerd.io docker-buildx-plugin docker-compose-plugin
# Dedicated virtio:1 disk. Never format a disk with any detected existing signature.
udevadm settle
test -b /dev/vdb
if ! blkid /dev/vdb >/dev/null 2>&1; then
  test -z "$(wipefs --no-act --noheadings --output TYPE /dev/vdb)"
  mkfs.ext4 -L portfolio-data /dev/vdb
fi
test "$(blkid -s TYPE -o value /dev/vdb)" = ext4
uuid=$(blkid -s UUID -o value /dev/vdb)
printf 'UUID=%s /var/lib/portfolio ext4 defaults,nodev,nosuid 0 2\n' "$uuid" >> /etc/fstab
mount /var/lib/portfolio
install -m 0700 -d /var/lib/portfolio/docker /var/lib/portfolio/releases /etc/portfolio
cat > /etc/docker/daemon.json <<'JSON'
{"data-root":"/var/lib/portfolio/docker","log-driver":"json-file","log-opts":{"max-size":"10m","max-file":"3"},"live-restore":true}
JSON
install -d /etc/systemd/system/docker.service.d
cat > /etc/systemd/system/docker.service.d/storage.conf <<'UNIT'
[Unit]
RequiresMountsFor=/var/lib/portfolio
ConditionPathIsMountPoint=/var/lib/portfolio
UNIT
ufw default deny incoming
ufw default allow outgoing
python3 - "$1" <<'PY'
import ipaddress, json, subprocess, sys
for value in json.loads(sys.argv[1]):
    network = ipaddress.IPv4Network(value, strict=False)
    assert network.prefixlen >= 8
    subprocess.run(['ufw', 'allow', 'from', str(network), 'to', 'any', 'port', '22', 'proto', 'tcp'], check=True)
PY
ufw allow 80/tcp
ufw allow 443/tcp
ufw --force enable
# UFW alone does not filter Docker's forwarded published ports. The cloud firewall is
# authoritative; no application/DB ports are published. Keep iptables integration enabled.
printf 'Unattended-Upgrade::Automatic-Reboot "false";\n' > /etc/apt/apt.conf.d/52portfolio
printf 'APT::Periodic::Update-Package-Lists "1";\nAPT::Periodic::Unattended-Upgrade "1";\n' > /etc/apt/apt.conf.d/20auto-upgrades
for job in backup monitor; do
  cat > "/etc/systemd/system/portfolio-$job.service" <<UNIT
[Unit]
Description=Portfolio $job
After=docker.service
RequiresMountsFor=/var/lib/portfolio
ConditionPathExists=/etc/portfolio/active.json
[Service]
Type=oneshot
EnvironmentFile=-/etc/portfolio/backup.env
ExecStart=/usr/local/lib/portfolio/$job.sh
Nice=10
UMask=0077
UNIT
done
cat > /etc/systemd/system/portfolio-backup.timer <<'UNIT'
[Timer]
OnCalendar=*-*-* 03:15:00 UTC
RandomizedDelaySec=900
Persistent=true
[Install]
WantedBy=timers.target
UNIT
cat > /etc/systemd/system/portfolio-monitor.timer <<'UNIT'
[Timer]
OnBootSec=5m
OnUnitActiveSec=5m
[Install]
WantedBy=timers.target
UNIT
systemctl daemon-reload
systemctl unmask docker.service docker.socket
systemctl enable --now docker.service unattended-upgrades.service sysstat.service portfolio-backup.timer portfolio-monitor.timer
sshd -t
systemctl reload ssh
docker compose version
echo 'Bootstrap complete. No app deployed. Obtain the public IP and arrange DNS before deployment.'
