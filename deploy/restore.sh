#!/bin/sh
# Restore ONLY to a new database, leaving the current database unchanged.
set -eu
file=${1:?Usage: sh deploy/restore.sh backup.dump new_database_name}
target=${2:?A NEW database name is required}
case "$target" in ''|*[!a-z0-9_]*) echo 'Use lowercase letters, digits, underscore only'; exit 1;; esac
test -r "$file"
# createdb fails if target already exists; no --clean, --create or drop operations.
docker compose --env-file "${COMPOSE_ENV_FILE:-.env.production}" -f compose.production.yml ${COMPOSE_EXTRA_FILE:+-f "$COMPOSE_EXTRA_FILE"} exec -T db \
  sh -c 'createdb -U "$POSTGRES_USER" -- "$1"' sh "$target"
docker compose --env-file "${COMPOSE_ENV_FILE:-.env.production}" -f compose.production.yml ${COMPOSE_EXTRA_FILE:+-f "$COMPOSE_EXTRA_FILE"} exec -T db \
  sh -c 'pg_restore --exit-on-error --single-transaction --no-owner --no-acl -U "$POSTGRES_USER" -d "$1"' sh "$target" < "$file"
echo 'Restored into new database. Validate it before changing DATABASE_URL.'
