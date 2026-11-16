#!/bin/bash
set -euo pipefail
umask 077
[[ $(id -u) = 0 && $# = 0 ]] || exit 1
exec 9>/var/lib/demand/backup.lock
flock -x 9
trap 'if (( $? != 0 )); then /usr/bin/python3 -I /opt/demand/backup_state.py invalidate-restore; fi' EXIT
# shellcheck source=deploy/single/backup-common.sh
source /opt/demand/backup-common.sh
/usr/bin/python3 -I /opt/demand/backup_state.py preflight
