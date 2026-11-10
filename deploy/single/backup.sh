#!/bin/bash
set -euo pipefail
umask 077
source /opt/demand/backup-common.sh
trap 'logger -p daemon.err -t demand-backup "Backup failed; inspect root-only service status"' ERR
images=/var/lib/demand/releases/active.env
if [[ ${1:-} = --bootstrap ]]; then images=/etc/demand/bootstrap-images.env; fi
[[ $# = 0 || ( $# = 1 && $1 = --bootstrap ) ]] || exit 1
[[ $(stat -c '%u:%a' "$images") = 0:600 ]] || exit 1
exec 9>/run/demand-backup.lock
flock -n 9
cd /opt/demand
# Custom archive is streamed directly into Restic's client-side authenticated encryption.
docker compose --env-file /etc/demand/runtime.env --env-file "$images" -f compose.prod.yml \
  exec -T db pg_dump -U demand_owner -d demand -Fc |
  restic_safe backup --stdin --stdin-filename demand.dump --tag demand-single --quiet
restic_safe check --read-data-subset=10% >/dev/null
restic_safe forget --tag demand-single --keep-daily 7 --keep-weekly 4 --keep-monthly 2 --prune >/dev/null
touch /var/lib/demand/backup-last-success
logger -t demand-backup 'Encrypted off-host backup and repository integrity check completed'
