#!/bin/bash
set -euo pipefail
umask 077
[[ $(id -u) = 0 ]] || exit 1
# The release controller already owns this lock while it invokes us.
if [[ ${1:-} = --release-lock-held ]]; then
  shift
else
  exec 8>/var/lib/demand/releases/operation.lock
  flock -n 8
fi
exec 9>/var/lib/demand/backup.lock
flock -x 9
/usr/bin/python3 -I /opt/demand/backup_state.py invalidate-backup
# shellcheck source=deploy/single/backup-common.sh
source /opt/demand/backup-common.sh
exec /usr/bin/python3 -I /opt/demand/backup_state.py backup "$@"
