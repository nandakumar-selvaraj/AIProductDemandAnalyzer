#!/bin/bash
set -euo pipefail
umask 077
[[ $(id -u) = 0 ]] || exit 1
[[ $(stat -c '%u:%a' /etc/demand/backup.env) = 0:600 ]] || exit 1
set -a
source /etc/demand/backup.env
set +a
[[ $RESTIC_REPOSITORY = s3:https://* ]] || exit 1
[[ $(stat -c '%u:%a' "$RESTIC_PASSWORD_FILE") = 0:600 ]] || exit 1
exec 9>/run/demand-backup.lock
flock -n 9
cd /opt/demand
# Custom archive is streamed directly into Restic's client-side authenticated encryption.
docker compose --env-file /etc/demand/runtime.env --env-file /var/lib/demand/releases/active.env -f compose.prod.yml \
  exec -T db pg_dump -U demand_owner -d demand -Fc |
  restic backup --stdin --stdin-filename demand.dump --tag demand-single --quiet
restic check --read-data-subset=10% >/dev/null
restic forget --tag demand-single --keep-daily 7 --keep-weekly 4 --keep-monthly 2 --prune >/dev/null
logger -t demand-backup 'Encrypted off-host backup and repository integrity check completed'
