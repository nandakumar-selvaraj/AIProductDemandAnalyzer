#!/bin/sh
set -eu
# Fixed interpreter, path and environment. No caller-controlled Compose flags or config.
exec /usr/bin/env -i PATH=/usr/sbin:/usr/bin:/sbin:/bin /usr/bin/python3 -I /opt/demand/release.py
