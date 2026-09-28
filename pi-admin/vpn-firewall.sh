#!/bin/bash
set -euo pipefail
# Independent of tunnel state: stopping WireGuard must never restore direct egress.
policy=$(mktemp)
trap 'rm -f "$policy"' EXIT
modprobe nf_conntrack_bridge
if nft list table inet vault_vpn >/dev/null 2>&1; then echo 'delete table inet vault_vpn' >>"$policy"; fi
if nft list table bridge vault_l2 >/dev/null 2>&1; then echo 'delete table bridge vault_l2' >>"$policy"; fi
cat >>"$policy" <<'EOF'
table bridge vault_l2 {
 chain isolate_peers {
  type filter hook forward priority -10; policy accept;
  meta ibrname "br-vault" ether type ip6 counter drop
  meta ibrname "br-vault" ip saddr != 172.30.80.254 ip daddr 172.30.80.0/24 ct direction reply ct state established,related counter accept
  meta ibrname "br-vault" ip saddr != 172.30.80.254 ip daddr 172.30.80.0/24 counter drop
 }
}
table inet vault_vpn {
 set private4 { type ipv4_addr; flags interval; elements = { 0.0.0.0/8,10.0.0.0/8,100.64.0.0/10,127.0.0.0/8,169.254.0.0/16,172.16.0.0/12,192.0.0.0/24,192.0.2.0/24,192.168.0.0/16,198.18.0.0/15,198.51.100.0/24,203.0.113.0/24,224.0.0.0/3 } }
 chain route_browser {
  type filter hook prerouting priority -140; policy accept;
  iifname "br-vault" meta nfproto ipv6 counter drop
  iifname "br-vault" ct direction original meta mark set 0xb00
 }
 chain protect_host {
  type filter hook input priority -20; policy accept;
  iifname "br-vault" ct direction reply ct state established,related accept
  iifname "br-vault" counter reject
 }
 chain protect_forward {
  type filter hook forward priority -20; policy accept;
  iifname "br-vault" ct direction reply ct state established,related accept
  iifname "br-vault" meta nfproto ipv6 counter drop
  iifname "br-vault" ip daddr @private4 counter reject
  iifname "br-vault" oifname != "vault-wg" counter reject
  iifname "br-vault" tcp dport {80,443} counter accept
  iifname "br-vault" ip daddr {1.1.1.1,9.9.9.9} udp dport 53 counter accept
  iifname "br-vault" ip daddr {1.1.1.1,9.9.9.9} tcp dport 53 counter accept
  iifname "br-vault" counter reject
 }
 chain tunnel_nat {
  type nat hook postrouting priority 90; policy accept;
  ip saddr 172.30.80.0/24 oifname "vault-wg" masquerade
 }
 chain tunnel_mss {
  type filter hook forward priority -130; policy accept;
  iifname "br-vault" oifname "vault-wg" tcp flags syn tcp option maxseg size set 1240
 }
}
EOF
nft -c -f "$policy"
nft -f "$policy"
ip route replace unreachable default table 51820 metric 32760
if ! ip rule show | grep -q 'fwmark 0xb00 lookup 51820'; then
 ip rule add pref 100 fwmark 0xb00 lookup 51820
fi
echo VPN_KILL_SWITCH_READY
