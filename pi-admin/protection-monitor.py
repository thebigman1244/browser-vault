#!/usr/bin/python3
"""Read-only operational checks. Never changes firewall rules or reads VPN keys."""
import hashlib, json, os, pathlib, subprocess, sys, time

BASELINE = pathlib.Path('/etc/browser-vault-protection/baseline.json')
OUTPUT = pathlib.Path('/run/browser-vault-health/status.json')
TABLES = [('inet', 'vault_vpn'), ('bridge', 'vault_l2')]

def run(*args):
    return subprocess.run(args, check=True, capture_output=True, text=True, timeout=4).stdout.strip()

def table_hash(family, name):
    # Stateless output omits live counters; numeric output avoids name lookups.
    text = run('nft', '-s', '-n', 'list', 'table', family, name)
    return hashlib.sha256(text.encode()).hexdigest()

def snapshot():
    return {name: table_hash(family, name) for family, name in TABLES}

def routing_ok():
    rules = json.loads(run('ip', '-j', 'rule', 'show'))
    routes = json.loads(run('ip', '-j', 'route', 'show', 'table', '51820'))
    rule = any(x.get('priority') == 100 and str(x.get('fwmark')) in ('0xb00','2816') and str(x.get('table')) == '51820' for x in rules)
    fallback = any(x.get('type') == 'unreachable' and x.get('dst') == 'default' and x.get('metric') == 32760 for x in routes)
    vpn = any(x.get('dst') == 'default' and x.get('dev') == 'vault-wg' and x.get('metric') == 10 for x in routes)
    return rule and fallback and vpn

def vpn_ok():
    # Only handshake timestamps are queried. Never use wg dump/showconf here.
    times = [int(line.split()[-1]) for line in run('wg', 'show', 'vault-wg', 'latest-handshakes').splitlines()]
    return bool(times) and all(0 <= time.time()-stamp <= 240 for stamp in times)

def proxy_ok():
    return run('docker', 'inspect', 'kasm_proxy', '--format', '{{.State.Running}} {{(index .NetworkSettings.Networks "vault_browsers").IPAddress}}') == 'true 172.30.80.254'

def main():
    if len(sys.argv) > 1:
        if sys.argv[1:] != ['--record-reviewed-baseline']:
            raise SystemExit('Unsupported arguments')
        # Explicit installation-only step after verifying the deployed policy.
        BASELINE.write_text(json.dumps(snapshot())+'\n')
        BASELINE.chmod(0o600)
        return
    checks = {}
    probes = {'firewall':lambda: snapshot() == json.loads(BASELINE.read_text()), 'routing':routing_ok, 'vpn':vpn_ok, 'proxy':proxy_ok}
    for name, probe in probes.items():
        try: checks[name] = bool(probe())
        except Exception: checks[name] = False
    OUTPUT.parent.mkdir(mode=0o755, exist_ok=True)
    temp = OUTPUT.with_suffix('.tmp')
    temp.write_text(json.dumps({'version':1,'checkedAt':int(time.time()*1000),'checks':checks})+'\n')
    temp.chmod(0o644)
    os.replace(temp, OUTPUT)

if __name__ == '__main__': main()
