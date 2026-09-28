import test from 'node:test';
import assert from 'node:assert/strict';
import { generateKeyPair, SignJWT } from 'jose';
import { createAuthenticator } from './auth.mjs';

const { privateKey, publicKey } = await generateKeyPair('RS256');
const config = { authMode: 'cloudflare', accessKey: 'x'.repeat(48), cloudflareAccess: {
  issuer: 'https://test-team.cloudflareaccess.com', audience: 'test-audience', email: 'owner@example.com',
}};
const auth = await createAuthenticator(config, publicKey);
const now = Math.floor(Date.now() / 1000);
async function token(overrides = {}, key = privateKey) {
  return new SignJWT({ iss: config.cloudflareAccess.issuer, aud: 'test-audience', sub: 'user-id',
    email: 'owner@example.com', type: 'app', iat: now, exp: now + 300, ...overrides })
    .setProtectedHeader({ alg: 'RS256' }).sign(key);
}
test('accepts a signed token for the configured owner and application', async () => {
  assert.equal((await auth.verify({ 'cf-access-jwt-assertion': await token() })).email, 'owner@example.com');
});
test('rejects old access keys, email-only headers, missing and malformed tokens', async () => {
  for (const headers of [{}, {authorization: `Bearer ${config.accessKey}`},
    {'cf-access-authenticated-user-email':'owner@example.com'}, {'cf-access-jwt-assertion':'bad'}]) {
    assert.equal(await auth.verify(headers), null);
  }
});
test('rejects the wrong signer, audience, issuer, identity, token type, and timestamps', async () => {
  const other = await generateKeyPair('RS256');
  assert.equal(await auth.verify({'cf-access-jwt-assertion': await token({}, other.privateKey)}), null);
  for (const overrides of [{aud:'other'}, {iss:'https://other.cloudflareaccess.com'},
    {email:'other@example.com'}, {type:'org'}, {exp:now-60}, {nbf:now+60},
    {iat:now+60}, {sub:''}, {exp:undefined}]) {
    assert.equal(await auth.verify({'cf-access-jwt-assertion': await token(overrides)}), null);
  }
});
test('fails closed on incomplete Cloudflare or unknown auth configuration', async () => {
  await assert.rejects(createAuthenticator({authMode:'cloudflare'}));
  await assert.rejects(createAuthenticator({authMode:'unknown'}));
});
test('legacy key mode remains available only when explicitly selected or unconfigured', async () => {
  const keyAuth = await createAuthenticator({accessKey:'k'.repeat(48)});
  assert.equal(await keyAuth.verify({authorization:'Bearer wrong'}), null);
  assert.equal((await keyAuth.verify({authorization:`Bearer ${'k'.repeat(48)}`})).mode, 'key');
});
