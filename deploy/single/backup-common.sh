#!/bin/bash
# Sourced only by root-owned backup tools. Never enable shell tracing.
set -euo pipefail
umask 077
[[ $(id -u) = 0 ]] || exit 1
for file in /etc/demand/backup.env /etc/demand/restic-password /etc/demand/backup-key /etc/demand/backup-known-hosts; do
  [[ -f $file && ! -L $file && $(stat -c '%u:%a' "$file") = 0:600 ]] || exit 1
done
unset RESTIC_PASSWORD RESTIC_PASSWORD_COMMAND RESTIC_REPOSITORY_FILE
set -a
# Owner-provided root-only configuration is intentionally not in the checkout.
# shellcheck source=/dev/null
source /etc/demand/backup.env
set +a
[[ $RESTIC_REPOSITORY =~ ^sftp:demand-backup:/[a-zA-Z0-9/_-]+$ ]] || exit 1
[[ $RESTIC_PASSWORD_FILE = /etc/demand/restic-password ]] || exit 1
[[ $BACKUP_HOST =~ ^[0-9]+\.[0-9]+\.[0-9]+\.[0-9]+$ ]] || exit 1
[[ $BACKUP_USER =~ ^[a-z][a-z0-9_-]{0,31}$ ]] || exit 1
export BACKUP_HOST BACKUP_HOST_FINGERPRINT
python3 - <<'PY'
import base64, hashlib, ipaddress, json, os, struct, subprocess
from pathlib import Path
host = ipaddress.IPv4Address(os.environ['BACKUP_HOST'])
assert host.is_global
local = json.loads(subprocess.check_output(["ip", "-j", "-4", "addr", "show"]))
assert str(host) not in {addr["local"] for nic in local for addr in nic["addr_info"]}
lines = Path('/etc/demand/backup-known-hosts').read_text().strip().splitlines()
assert len(lines) == 1
name, kind, key, *comment = lines[0].split()
assert name == str(host) and kind == 'ssh-ed25519'
blob = base64.b64decode(key, validate=True)
assert blob[:4] == struct.pack('>I', 11) and blob[4:15] == b'ssh-ed25519'
assert blob[15:19] == struct.pack('>I', 32) and len(blob) == 51
assert 'SHA256:' + base64.b64encode(hashlib.sha256(blob).digest()).decode().rstrip('=') == os.environ['BACKUP_HOST_FINGERPRINT']
PY
(
  ssh_config=$(mktemp /etc/demand/.backup-ssh.XXXXXXXX)
  trap 'rm -f "$ssh_config"' EXIT
  cat >"$ssh_config" <<EOF
Host demand-backup
  HostName $BACKUP_HOST
  HostKeyAlias $BACKUP_HOST
  User $BACKUP_USER
  IdentityFile /etc/demand/backup-key
  UserKnownHostsFile /etc/demand/backup-known-hosts
  GlobalKnownHostsFile /dev/null
  StrictHostKeyChecking yes
  HostKeyAlgorithms ssh-ed25519
  IdentitiesOnly yes
  BatchMode yes
  PasswordAuthentication no
  KbdInteractiveAuthentication no
  ForwardAgent no
  ForwardX11 no
  ClearAllForwardings yes
  ConnectTimeout 15
EOF
  mv -T -- "$ssh_config" /etc/demand/backup-ssh.conf
)
DEMAND_BACKUP_CONFIG_DIGEST=$(sha256sum /etc/demand/backup.env /etc/demand/backup-known-hosts /etc/demand/restic-password /etc/demand/backup-key | sha256sum | cut -d ' ' -f 1)
export DEMAND_BACKUP_CONFIG_DIGEST
