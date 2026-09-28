import { readFile, lstat } from 'node:fs/promises';

export const HEALTH_FILE = '/run/browser-vault-health/status.json';
export const MAX_HEALTH_AGE_MS = 45000;
const keys = ['firewall', 'routing', 'vpn', 'proxy'];

export function protectionStatus(sample, now = Date.now()) {
  const fresh = sample?.version === 1 && Number.isFinite(sample.checkedAt) &&
    sample.checkedAt <= now + 5000 && now - sample.checkedAt <= MAX_HEALTH_AGE_MS;
  const checks = Object.fromEntries(keys.map(key => [key, fresh && sample?.checks?.[key] === true]));
  const ready = fresh && keys.every(key => checks[key]);
  const reason = !fresh ? 'Protection checks are unavailable or out of date. New sessions are paused.' :
    !checks.firewall || !checks.routing ? 'Network protection needs attention. New sessions are paused.' :
    !checks.proxy ? 'The browser display service is not ready. Try again shortly.' :
    !checks.vpn ? 'The VPN has no recent connection. New sessions are paused; the kill switch stays in place.' :
    'Recent VPN handshake, firewall rules and browser routing checked.';
  return { ready, fresh, checkedAt: fresh ? sample.checkedAt : null, checks, reason };
}

export async function readProtection(file = HEALTH_FILE) {
  try {
    const stat = await lstat(file);
    if (!stat.isFile() || stat.uid !== 0 || (stat.mode & 0o022) || stat.size > 8192) return protectionStatus(null);
    return protectionStatus(JSON.parse(await readFile(file, 'utf8')));
  } catch { return protectionStatus(null); }
}
