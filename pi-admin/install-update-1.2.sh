#!/bin/bash
set -euo pipefail
source_dir=${1:?Provide the reviewed update directory}
backup=/root/browser-vault-backup-1.2
test -s "$source_dir/selfhost/security.mjs"
test -s "$source_dir/selfhost-dist/index.html"
install -d -m700 "$backup"
if ! test -e "$backup/server.mjs"; then
 cp -a /opt/browser-vault/server.mjs /opt/browser-vault/public "$backup/"
fi
python3 - <<'PY'
import json,time,pathlib
p=json.loads(pathlib.Path('/run/browser-vault-health/status.json').read_text())
assert time.time()*1000-p['checkedAt']<45000 and all(p['checks'].values()), 'Isolation checks must pass before updating.'
PY
install -m644 "$source_dir/selfhost/server.mjs" "$source_dir/selfhost/security.mjs" /opt/browser-vault/
cp -a "$source_dir/selfhost-dist/." /opt/browser-vault/public/
chown -R root:root /opt/browser-vault/public
chmod -R a+rX /opt/browser-vault/public
systemctl restart browser-vault
systemctl is-active browser-vault browser-vault-security.timer
echo BROWSER_VAULT_1_2_INSTALLED
