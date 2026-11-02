FROM postgres:16-alpine@sha256:0cefaabd882e42bcb2a2f3dc56d3ce4770560ba62fd7f197f1a2e008fd5731ab
# Replace the obsolete Go-based privilege switcher with Alpine's maintained native helper.
# Keep PostgreSQL binaries/data layout; adapt only the entrypoint's privilege-drop command.
RUN apk add --no-cache su-exec=0.3-r0 \
    && rm /usr/local/bin/gosu /usr/local/bin/su-exec \
    && grep -q 'exec gosu postgres' /usr/local/bin/docker-entrypoint.sh \
    && sed -i 's/exec gosu postgres/exec su-exec postgres/' /usr/local/bin/docker-entrypoint.sh \
    && test "$(su-exec postgres id -u)" = "$(id -u postgres)"
