export function sessionMinutes(value = 30) {
  if (![5, 15, 30].includes(value)) throw new Error('Choose a session length of 5, 15 or 30 minutes.');
  return value;
}

export function displaySettings(mode = 'smooth') {
  if (!['smooth','native'].includes(mode)) throw new Error('Choose Smooth or Full window display.');
  return mode === 'smooth' ? {
    KVNC_ENCODING_MAX_FRAME_RATE:'30',
    KVNC_ENCODING_RECT_ENCODING_MODE_MIN_QUALITY:'4', KVNC_ENCODING_RECT_ENCODING_MODE_MAX_QUALITY:'7'
  } : {};
}

export function websiteUrl(value) {
  if (!value) return 'about:blank';
  if (typeof value !== 'string' || value.length > 4096) throw new Error('Enter a website URL shorter than 4,096 characters.');
  let url;
  try { url = new URL(value.includes('://') ? value : 'https://' + value); }
  catch { throw new Error('Enter a valid website address.'); }
  if (!['https:', 'http:'].includes(url.protocol) || url.username || url.password) throw new Error('Only HTTP and HTTPS addresses without embedded credentials are allowed.');
  if (url.port && !['80', '443'].includes(url.port)) throw new Error('Only standard website ports 80 and 443 are allowed.');
  const host = url.hostname.toLowerCase().replace(/\.$/, '');
  let blocked = host.includes(':') || !host.includes('.') || /\.(local|localhost|internal|lan|home)$/.test(host);
  if (/^\d+\.\d+\.\d+\.\d+$/.test(host)) {
    const [a,b,c] = host.split('.').map(Number);
    blocked ||= a === 0 || a === 10 || a === 127 || a >= 224 ||
      (a === 100 && b >= 64 && b <= 127) || (a === 169 && b === 254) ||
      (a === 172 && b >= 16 && b <= 31) || (a === 192 && (b === 168 || (b === 0 && (c === 0 || c === 2)))) ||
      (a === 198 && (b === 18 || b === 19 || (b === 51 && c === 100))) || (a === 203 && b === 0 && c === 113);
  }
  if (blocked) throw new Error('Local-network and IPv6 addresses are blocked in Browser Vault. Enter a public website.');
  return url.href;
}
