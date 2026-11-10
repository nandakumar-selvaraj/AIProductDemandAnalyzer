#!/bin/bash
# Owner-run on a reviewed, dedicated Ubuntu host. Never invoked by Actions.
set -euo pipefail
umask 077
[[ $(id -u) = 0 && $# -ge 4 && $1 = KEY-ACCESS-VERIFIED ]] || exit 1
operator_key=$2
deploy_key=$3
shift 3
source /etc/os-release
[[ $ID = ubuntu && $VERSION_ID = 24.04 && $(dpkg --print-architecture) = amd64 ]] || exit 1
root=$(cd -- "$(dirname -- "$0")/../.." && pwd)
# Validate only public keys and approved network ranges. Never read private keys.
python3 - "$operator_key" "$deploy_key" "$@" <<'PY'
import base64, ipaddress, sys
from pathlib import Path
keys = []
for filename in sys.argv[1:3]:
    parts = Path(filename).read_text().strip().split()
    assert len(parts) in (2, 3) and parts[0] == 'ssh-ed25519'
    key = base64.b64decode(parts[1], validate=True)
    assert key[:19] == b'\0\0\0\x0bssh-ed25519\0\0\0\x20' and len(key) == 51
    keys.append(parts[1])
assert keys[0] != keys[1]
for value in sys.argv[3:]:
    net = ipaddress.IPv4Network(value, strict=True)
    assert net.is_global and net.prefixlen >= 24
assert 0 < len(sys.argv[3:]) <= 20
PY
# Never automatically replace an existing distribution Docker installation.
for package in docker.io docker-compose docker-compose-v2 podman-docker containerd runc; do
  if dpkg-query -W -f='${Status}' "$package" 2>/dev/null | grep -q 'install ok installed'; then
    echo 'Conflicting Docker package: owner must review migration separately' >&2
    exit 1
  fi
done
apt-get update
apt-get install -y ca-certificates curl gnupg openssh-server sudo ufw unattended-upgrades restic certbot python3 systemd-timesyncd
install -d -m 0755 /etc/apt/keyrings
keyfile=$(mktemp)
trap 'rm -f "$keyfile"' EXIT
curl --fail --silent --show-error --proto '=https' --tlsv1.2 https://download.docker.com/linux/ubuntu/gpg -o "$keyfile"
gpg --show-keys --with-colons "$keyfile" | grep -q '^fpr:::::::::9DC858229FC7DD38854AE2D88D81803C0EBFCD88:'
install -m 0644 "$keyfile" /etc/apt/keyrings/docker.asc
echo 'deb [arch=amd64 signed-by=/etc/apt/keyrings/docker.asc] https://download.docker.com/linux/ubuntu noble stable' >/etc/apt/sources.list.d/demand-docker.list
apt-get update
apt-get install -y docker-ce docker-ce-cli containerd.io docker-buildx-plugin docker-compose-plugin
for user in operator deployer; do
  id "$user" >/dev/null 2>&1 || useradd --create-home --shell /bin/bash "$user"
  passwd -l "$user" >/dev/null
  if id -nG "$user" | tr ' ' '\n' | grep -qx docker; then
    echo 'Remove existing Docker membership after owner review' >&2
    exit 1
  fi
  install -d -o "$user" -g "$user" -m 0700 "/home/$user/.ssh"
done
install -o operator -g operator -m 0600 "$operator_key" /home/operator/.ssh/authorized_keys
# Restriction also lives in sshd configuration, where deployer cannot modify it.
{ printf 'restrict '; cat "$deploy_key"; } >/home/deployer/.ssh/authorized_keys
chown deployer:deployer /home/deployer/.ssh/authorized_keys
chmod 600 /home/deployer/.ssh/authorized_keys
for dir in /opt/demand /etc/demand /var/lib/demand /var/lib/demand/releases; do
  [[ ! -L $dir ]] || exit 1
  install -d -o root -g root -m 0700 "$dir"
done
install -m 0600 "$root/compose.prod.yml" /opt/demand/compose.prod.yml
install -m 0600 "$root/deploy/single/release.py" /opt/demand/release.py
for script in backup-common backup-preflight backup restore-verify host-check host-monitor; do
  install -m 0700 "$root/deploy/single/$script.sh" "/opt/demand/$script.sh"
done
install -m 0644 "$root/deploy/single/init-db.sh" /opt/demand/init-db.sh
for config in nginx.stage-a.conf nginx.tls.conf; do
  install -m 0644 "$root/deploy/single/$config" "/opt/demand/$config"
done
[[ -e /opt/demand/nginx.conf ]] || install -m 0644 /opt/demand/nginx.stage-a.conf /opt/demand/nginx.conf
install -m 0700 "$root/deploy/single/release-entry.sh" /usr/local/sbin/demand-release
install -d -m 0755 /var/lib/letsencrypt /etc/letsencrypt/renewal-hooks/deploy
install -m 0700 "$root/deploy/single/renew-certificate.sh" /etc/letsencrypt/renewal-hooks/deploy/demand
cat >/etc/sudoers.d/demand <<'EOF'
operator ALL=(ALL) NOPASSWD: ALL
deployer ALL=(root) NOPASSWD: /usr/local/sbin/demand-release ""
EOF
chmod 0440 /etc/sudoers.d/demand
visudo -cf /etc/sudoers.d/demand
install -d -m 0755 /etc/docker /etc/systemd/journald.conf.d
python3 - <<'PY'
import json
from pathlib import Path
p = Path('/etc/docker/daemon.json')
data = json.loads(p.read_text()) if p.exists() else {}
data.update({'log-driver': 'json-file', 'log-opts': {'max-size': '10m', 'max-file': '3'}, 'ipv6': False})
p.write_text(json.dumps(data) + '\n')
PY
dockerd --validate --config-file /etc/docker/daemon.json
cat >/etc/sysctl.d/90-demand-ipv6.conf <<'EOF'
net.ipv6.conf.all.disable_ipv6=1
net.ipv6.conf.default.disable_ipv6=1
EOF
sysctl --system >/dev/null
ufw default deny incoming
ufw default allow outgoing
for cidr in "$@"; do ufw allow from "$cidr" to any port 22 proto tcp; done
ufw allow 80/tcp
ufw allow 443/tcp
ufw --force enable
# UFW does not protect Docker DNAT. Permit only the two published ingress ports.
install -m 0700 "$root/deploy/single/docker-firewall.sh" /usr/local/sbin/demand-docker-firewall
install -d -m 0755 /etc/systemd/system/docker.service.d
cat >/etc/systemd/system/docker.service.d/demand.conf <<'EOF'
[Service]
ExecStartPost=/usr/local/sbin/demand-docker-firewall
EOF
cat >/etc/apt/apt.conf.d/20auto-upgrades <<'EOF'
APT::Periodic::Update-Package-Lists "1";
APT::Periodic::Unattended-Upgrade "1";
EOF
cat >/etc/systemd/journald.conf.d/demand.conf <<'EOF'
[Journal]
Storage=persistent
SystemMaxUse=200M
EOF
for unit in "$root"/deploy/single/systemd/*; do install -m 0644 "$unit" /etc/systemd/system/; done
cat >/etc/ssh/sshd_config.d/00-demand-manual.conf <<'EOF'
PermitRootLogin no
PasswordAuthentication no
KbdInteractiveAuthentication no
PubkeyAuthentication yes
AuthenticationMethods publickey
AllowUsers operator deployer
AllowAgentForwarding no
X11Forwarding no
MaxAuthTries 3
Match User deployer
  AllowTcpForwarding no
  AllowStreamLocalForwarding no
  PermitTunnel no
  PermitTTY no
  ForceCommand sudo -n /usr/local/sbin/demand-release
Match all
EOF
sshd -t
systemctl daemon-reload
systemctl enable --now docker systemd-timesyncd unattended-upgrades demand-monitor.timer
/usr/local/sbin/demand-docker-firewall
systemctl reload ssh
echo 'Host bootstrap complete. No images, volumes, migrations or application releases started.'
echo 'Review effective SSH/firewall policy. Existing daemon needs an owner-scheduled restart for changed logging settings.'
