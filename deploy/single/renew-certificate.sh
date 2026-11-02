#!/bin/bash
set -euo pipefail
umask 077
[[ $(id -u) = 0 && -n ${RENEWED_LINEAGE:-} ]] || exit 1
domain=$(cat /etc/demand/domain)
[[ $RENEWED_LINEAGE = "/etc/letsencrypt/live/$domain" ]] || exit 1
install -d -o root -g 101 -m 0750 /etc/demand/tls
install -o root -g 101 -m 0644 "$RENEWED_LINEAGE/fullchain.pem" /etc/demand/tls/fullchain.pem.new
install -o root -g 101 -m 0640 "$RENEWED_LINEAGE/privkey.pem" /etc/demand/tls/privkey.pem.new
mv /etc/demand/tls/fullchain.pem.new /etc/demand/tls/fullchain.pem
mv /etc/demand/tls/privkey.pem.new /etc/demand/tls/privkey.pem
cd /opt/demand
images=/var/lib/demand/releases/active.env
[[ -f $images ]] || images=/etc/demand/bootstrap-images.env
dc=(docker compose --env-file /etc/demand/runtime.env --env-file "$images" -f compose.prod.yml)
"${dc[@]}" exec -T nginx nginx -t
"${dc[@]}" exec -T nginx nginx -s reload
logger -t demand-tls 'Renewed certificate installed and Nginx reloaded'
