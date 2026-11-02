#!/bin/bash
set -euo pipefail
[[ $(id -u) = 0 && ${1:-} = KEY-ACCESS-VERIFIED ]] || exit 1
# Execute from a verified operator key session, retaining a second session + console recovery.
cat >/etc/ssh/sshd_config.d/00-demand-verified.conf <<'EOF'
PasswordAuthentication no
KbdInteractiveAuthentication no
PermitRootLogin no
PubkeyAuthentication yes
EOF
chmod 600 /etc/ssh/sshd_config.d/00-demand-verified.conf
sshd -t
systemctl reload ssh
sshd -T | sed -n '/^passwordauthentication /p; /^permitrootlogin /p'
