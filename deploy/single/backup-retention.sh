#!/bin/bash
# Review-only proposal. Snapshot deletion and pruning require separate owner maintenance.
set -euo pipefail
umask 077
[[ $(id -u) = 0 && $# = 0 ]] || exit 1
exec 9>/var/lib/demand/backup.lock
flock -x 9
# shellcheck source=deploy/single/backup-common.sh
source /opt/demand/backup-common.sh
exec /usr/bin/python3 -I /opt/demand/backup_state.py retention-plan
