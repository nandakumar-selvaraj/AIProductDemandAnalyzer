#!/bin/bash
set -euo pipefail
trap 'touch /var/lib/demand/attention-required; logger -p daemon.err -t demand-monitor "Host or backup unhealthy; owner attention required"' ERR
/opt/demand/host-check.sh
[[ -f /var/lib/demand/backup-last-success ]]
age=$(( $(date +%s) - $(stat -c %Y /var/lib/demand/backup-last-success) ))
(( age >= 0 && age < 93600 ))
systemctl is-failed --quiet demand-backup.service && exit 1
/opt/demand/backup-preflight.sh
logger -t demand-monitor 'Host capacity and backup checks passed'
