#!/bin/bash
set -euo pipefail
umask 077
[[ $(id -u) = 0 && ${1:-} =~ ^[0-9a-f]{8,64}$ ]] || exit 1
[[ $(stat -c '%u:%a' /etc/demand/backup.env) = 0:600 ]] || exit 1
set -a
source /etc/demand/backup.env
source /var/lib/demand/releases/active.env
set +a
[[ $POSTGRES_IMAGE =~ ^ghcr.io/nandakumar-selvaraj/aiproductdemandanalyzer/postgres@sha256:[0-9a-f]{64}$ ]] || exit 1
name="demand-restore-check-$$"
cleanup() { docker rm -f "$name" >/dev/null 2>&1 || true; }
trap cleanup EXIT
# No production network or data volume. Ephemeral filesystem, no public ports.
docker run -d --name "$name" --network none --memory 768m --cpus 0.5 \
  --tmpfs /var/lib/postgresql/data:rw,size=512m -e POSTGRES_HOST_AUTH_METHOD=trust "$POSTGRES_IMAGE" >/dev/null
for attempt in {1..60}; do
  docker exec "$name" pg_isready -U postgres >/dev/null 2>&1 && break
  sleep 2
done
docker exec "$name" createdb -U postgres restore_check
restic dump "$1" demand.dump | docker exec -i "$name" pg_restore -U postgres -d restore_check --no-owner --no-acl --exit-on-error
docker exec "$name" psql -U postgres -d restore_check -v ON_ERROR_STOP=1 \
  -c 'SELECT version_num FROM alembic_version' -c 'SELECT count(*) AS preserved_users FROM auth_users'
logger -t demand-backup 'Isolated restore completed; review schema and business row counts'
