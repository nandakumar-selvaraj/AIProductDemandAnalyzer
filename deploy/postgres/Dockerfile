FROM postgres:16-alpine@sha256:81e77a4833487b8132fe4b00bedd39dc3f74b8641e387f19312a48f7de218c2e
# Replace the obsolete Go-based privilege switcher with Alpine's maintained native helper.
# Keep PostgreSQL binaries/data layout; adapt only the entrypoint's privilege-drop command.
RUN apk add --no-cache su-exec=0.3-r0 \
    && rm /usr/local/bin/gosu /usr/local/bin/su-exec \
    && grep -q 'exec gosu postgres' /usr/local/bin/docker-entrypoint.sh \
    && sed -i 's/exec gosu postgres/exec su-exec postgres/' /usr/local/bin/docker-entrypoint.sh \
    && test "$(su-exec postgres id -u)" = "$(id -u postgres)"
