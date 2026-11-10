#!/bin/bash
set -euo pipefail
[[ $(id -u) = 0 ]] || exit 1
for executable in docker restic curl flock python3; do command -v "$executable" >/dev/null; done
docker compose version >/dev/null
docker info >/dev/null 2>&1
systemctl is-active --quiet docker
systemctl is-enabled --quiet demand-backup.timer
systemctl is-active --quiet demand-monitor.timer
[[ $(sysctl -n net.ipv6.conf.all.disable_ipv6) = 1 ]] || exit 1
for path in / /var/lib/docker; do
  available=$(df -Pk "$path" | awk 'NR==2 {print $4}')
  used=$(df -Pk "$path" | awk 'NR==2 {gsub(/%/,"",$5); print $5}')
  (( available >= 5242880 && used < 85 )) || exit 1
done
[[ $(stat -c '%u:%a' /etc/demand/runtime.env) = 0:600 ]] || exit 1
[[ -f /etc/demand/tls-ready && -s /etc/demand/domain ]] || exit 1
! id -nG deployer | tr ' ' '\n' | grep -qx docker
