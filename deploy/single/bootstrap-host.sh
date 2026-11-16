#!/bin/bash
# Root-owned checkout on the dedicated Ubuntu host.
set -euo pipefail
export PATH=/usr/sbin:/usr/bin:/sbin:/bin
helper="$(dirname -- "$0")/bootstrap_host.py"
[[ ! -L $0 && -f $helper && ! -L $helper ]] || exit 1
exec /usr/bin/python3 -I "$helper" "$@"
