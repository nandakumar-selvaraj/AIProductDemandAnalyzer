#!/bin/bash
set -euo pipefail
source /opt/demand/backup-common.sh
receipt=/var/lib/demand/backup-restore-verified
[[ ! -L $receipt && $(stat -c '%u:%a' "$receipt") = 0:600 ]] || exit 1
[[ $(cat "$receipt") = "$(backup_config_digest)" ]] || exit 1
age=$(( $(date +%s) - $(stat -c %Y "$receipt") ))
(( age >= 0 && age <= 3024000 )) || exit 1
restic_safe check >/dev/null 2>&1
