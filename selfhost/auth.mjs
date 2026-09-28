import { createHash, timingSafeEqual } from 'node:crypto';

// Cloudflare mode never falls back to the old access key or an email header.
export async function createAuthenticator(config, testKeys) {
  const mode = config.authMode ?? 'key';
  if (mode === 'key') {
    if (typeof config.accessKey !== 'string' || config.accessKey.length < 32) {
      throw new Error('A random access key of at least 32 characters is required.');
    }
    const digest = createHash('sha256').update(config.accessKey).digest();
    return { mode, async verify(headers) {
      const supplied = typeof headers.authorization === 'string' ? headers.authorization.replace(/^Bearer /, '') : '';
      return timingSafeEqual(createHash('sha256').update(supplied).digest(), digest) ? { mode } : null;
    }};
  }
  if (mode !== 'cloudflare') throw new Error('Unknown authentication mode.');
  const { issuer, audience, email } = config.cloudflareAccess ?? {};
  if (typeof issuer !== 'string' || !/^https:\/\/[a-z0-9-]+\.cloudflareaccess\.com$/.test(issuer) ||
      typeof audience !== 'string' || !audience || typeof email !== 'string' || !email.includes('@')) {
    throw new Error('Cloudflare Access requires the exact team issuer, application audience, and allowed email.');
  }
  const { createRemoteJWKSet, jwtVerify } = await import('jose');
  const keys = testKeys ?? createRemoteJWKSet(new URL(`${issuer}/cdn-cgi/access/certs`), {
    timeoutDuration: 5000, cooldownDuration: 30000, cacheMaxAge: 600000,
  });
  return { mode, async verify(headers) {
    const token = headers['cf-access-jwt-assertion'];
    if (typeof token !== 'string' || token.length > 16384) return null;
    try {
      const { payload } = await jwtVerify(token, keys, {
        issuer, audience, algorithms: ['RS256'],
        requiredClaims: ['exp', 'iat', 'sub', 'email'],
        clockTolerance: 5,
      });
      if (payload.type !== 'app' || typeof payload.sub !== 'string' || !payload.sub ||
          typeof payload.email !== 'string' || payload.email.toLowerCase() !== email.toLowerCase() ||
          typeof payload.iat !== 'number' || payload.iat > Date.now() / 1000 + 5) return null;
      return { mode, email: payload.email, subject: payload.sub };
    } catch { return null; }
  }};
}
