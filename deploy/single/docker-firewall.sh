#!/bin/bash
set -euo pipefail
[[ $(id -u) = 0 ]] || exit 1
interface=$(ip -4 route show default | awk 'NR==1 {print $5}')
[[ $interface =~ ^[a-zA-Z0-9_-]+$ ]] || exit 1
iptables -N DEMAND-INGRESS 2>/dev/null || true
iptables -F DEMAND-INGRESS
iptables -A DEMAND-INGRESS -m conntrack --ctstate ESTABLISHED,RELATED -j RETURN
for port in 80 443; do
  iptables -A DEMAND-INGRESS -p tcp -m conntrack --ctdir ORIGINAL --ctorigdstport "$port" -j RETURN
done
iptables -A DEMAND-INGRESS -j DROP
iptables -C DOCKER-USER -i "$interface" -j DEMAND-INGRESS 2>/dev/null || iptables -I DOCKER-USER 1 -i "$interface" -j DEMAND-INGRESS
