#!/bin/sh
# Run from the repository root; requires the production env file and running DB.
set -eu
umask 077
directory=${BACKUP_DIRECTORY:-backups}
mkdir -p "$directory"
file="$directory/demand-$(date -u +%Y%m%dT%H%M%SZ).dump"
tmp="$file.partial"
trap 'rm -f "$tmp"' EXIT HUP INT TERM
docker compose --env-file "${COMPOSE_ENV_FILE:-.env.production}" -f compose.production.yml ${COMPOSE_EXTRA_FILE:+-f "$COMPOSE_EXTRA_FILE"} exec -T db \
  sh -c 'pg_dump -U "$POSTGRES_USER" -d "$POSTGRES_DB" -Fc' > "$tmp"
test -s "$tmp"
mv "$tmp" "$file"
printf 'Backup written: %s\n' "$file"
