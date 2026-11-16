#!/bin/bash
# Replace only our own inet table, atomically, including Docker ingress.
set -euo pipefail
umask 077
[[ $(id -u) = 0 && ( $# = 0 || ( $# = 1 && $1 = --update ) ) ]] || exit 1
exec 9>/var/lib/demand/firewall.lock
flock -x 9
policy=/etc/demand/firewall.nft
candidate=$(mktemp /etc/demand/.firewall-transaction.XXXXXXXX)
desired=$(mktemp /etc/demand/.firewall-policy.XXXXXXXX)
previous=$(mktemp /etc/demand/.firewall-previous.XXXXXXXX)
trap 'rm -f "$candidate" "$desired" "$previous"' EXIT
[[ -f $policy && ! -L $policy && $(stat -c '%u:%a' "$policy") = 0:600 ]] || exit 1
if [[ $# = 1 ]]; then
  cat >"$desired"
  cp -- "$policy" "$previous"
else
  cp -- "$policy" "$desired"
fi
printf 'add table inet demand_ingress\ndelete table inet demand_ingress\n' >"$candidate"
cat "$desired" >>"$candidate"
nft --check --file "$candidate"
# Persist only a checked policy. If killed here, the old rules stay active
# until the next reload or reboot, which both load the checked policy.
if [[ $# = 1 ]]; then
  sync -f "$desired"
  mv -T -- "$desired" "$policy"
  sync -f /etc/demand
fi
if ! nft --file "$candidate"; then
  if [[ $# = 1 ]]; then
    mv -T -- "$previous" "$policy"
    sync -f /etc/demand
  fi
  exit 1
fi
