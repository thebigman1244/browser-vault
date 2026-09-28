#!/usr/bin/env bash
set -euo pipefail
# Apply before Docker can restart any container. Established display replies
# remain possible; new connections cannot reach private destinations.
iptables -t mangle -N VAULT-EARLY 2>/dev/null || true
iptables -t mangle -F VAULT-EARLY
iptables -t mangle -A VAULT-EARLY -m conntrack --ctstate ESTABLISHED,RELATED -j RETURN
for cidr in 0.0.0.0/8 10.0.0.0/8 100.64.0.0/10 127.0.0.0/8 169.254.0.0/16 172.16.0.0/12 192.0.0.0/24 192.0.2.0/24 192.168.0.0/16 198.18.0.0/15 198.51.100.0/24 203.0.113.0/24 224.0.0.0/4 240.0.0.0/4; do
  iptables -t mangle -A VAULT-EARLY -d "$cidr" -j DROP
done
iptables -t mangle -A VAULT-EARLY -p tcp -m multiport --dports 80,443 -j RETURN
iptables -t mangle -A VAULT-EARLY -p udp --dport 53 -d 1.1.1.1 -j RETURN
iptables -t mangle -A VAULT-EARLY -p udp --dport 53 -d 9.9.9.9 -j RETURN
iptables -t mangle -A VAULT-EARLY -p tcp --dport 53 -d 1.1.1.1 -j RETURN
iptables -t mangle -A VAULT-EARLY -p tcp --dport 53 -d 9.9.9.9 -j RETURN
iptables -t mangle -A VAULT-EARLY -j DROP
iptables -t mangle -C PREROUTING -i br-vault -j VAULT-EARLY 2>/dev/null || iptables -t mangle -I PREROUTING 1 -i br-vault -j VAULT-EARLY
ip6tables -t mangle -C PREROUTING -i br-vault -j DROP 2>/dev/null || ip6tables -t mangle -I PREROUTING 1 -i br-vault -j DROP
