#!/usr/bin/env bash
set -euo pipefail
# Dedicated browser bridge: ingress replies are allowed; new connections to the
# VM, other containers, link-local metadata endpoints, and private LANs are not.
docker network inspect vault_browsers >/dev/null 2>&1 || docker network create --driver bridge --subnet 172.30.80.0/24 --opt com.docker.network.bridge.name=br-vault vault_browsers >/dev/null
iptables -N VAULT-EGRESS 2>/dev/null || true
iptables -F VAULT-EGRESS
iptables -A VAULT-EGRESS -m conntrack --ctstate ESTABLISHED,RELATED -j RETURN
for cidr in 0.0.0.0/8 10.0.0.0/8 100.64.0.0/10 127.0.0.0/8 169.254.0.0/16 172.16.0.0/12 192.0.0.0/24 192.0.2.0/24 192.168.0.0/16 198.18.0.0/15 198.51.100.0/24 203.0.113.0/24 224.0.0.0/4 240.0.0.0/4; do
  iptables -A VAULT-EGRESS -d "$cidr" -j REJECT
done
# Restrict browser egress to web traffic and public DNS.
iptables -A VAULT-EGRESS -p tcp -m multiport --dports 80,443 -j RETURN
iptables -A VAULT-EGRESS -p udp --dport 53 -d 1.1.1.1 -j RETURN
iptables -A VAULT-EGRESS -p udp --dport 53 -d 9.9.9.9 -j RETURN
iptables -A VAULT-EGRESS -p tcp --dport 53 -d 1.1.1.1 -j RETURN
iptables -A VAULT-EGRESS -p tcp --dport 53 -d 9.9.9.9 -j RETURN
iptables -A VAULT-EGRESS -j REJECT
iptables -C DOCKER-USER -i br-vault -j VAULT-EGRESS 2>/dev/null || iptables -I DOCKER-USER 1 -i br-vault -j VAULT-EGRESS
iptables -C FORWARD -i br-vault -j VAULT-EGRESS 2>/dev/null || iptables -I FORWARD 1 -i br-vault -j VAULT-EGRESS
iptables -C INPUT -i br-vault -m conntrack --ctstate ESTABLISHED,RELATED -j ACCEPT 2>/dev/null || iptables -I INPUT 1 -i br-vault -m conntrack --ctstate ESTABLISHED,RELATED -j ACCEPT
iptables -C INPUT -i br-vault -j REJECT 2>/dev/null || iptables -A INPUT -i br-vault -j REJECT
# No IPv6 route for browser workloads; defense in depth if IPv6 is enabled later.
ip6tables -C FORWARD -i br-vault -j REJECT 2>/dev/null || ip6tables -I FORWARD 1 -i br-vault -j REJECT
ip6tables -C INPUT -i br-vault -j REJECT 2>/dev/null || ip6tables -I INPUT 1 -i br-vault -j REJECT
