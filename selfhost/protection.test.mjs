import test from 'node:test';
import assert from 'node:assert/strict';
import { protectionStatus, MAX_HEALTH_AGE_MS } from './protection.mjs';
import { websiteUrl, sessionMinutes, displaySettings } from './session-policy.mjs';
const now = 1000000;
const good = { version:1, checkedAt:now, checks:{firewall:true,routing:true,vpn:true,proxy:true} };
test('launch checks fail closed for absent, stale, future, malformed and incomplete reports', () => {
  for (const report of [null,{}, {...good,version:2}, {...good,checkedAt:now-MAX_HEALTH_AGE_MS-1}, {...good,checkedAt:now+6000}, {...good,checks:{firewall:true}}]) {
    assert.equal(protectionStatus(report, now).ready, false);
  }
  assert.equal(protectionStatus(good,now).ready,true);
});
test('each failed check prevents launch without calling a stale check healthy', () => {
  for (const key of Object.keys(good.checks)) assert.equal(protectionStatus({...good,checks:{...good.checks,[key]:false}},now).ready,false);
  assert.ok(Object.values(protectionStatus(good,now+MAX_HEALTH_AGE_MS+1).checks).every(x=>x===false));
});
test('URL policy blocks private, encoded loopback, IPv6, credentials and non-web schemes', () => {
  for (const url of ['http://192.168.1.1','http://127.1','http://2130706433','http://0x7f000001','http://[::1]','http://[::ffff:192.168.1.1]','http://printer.local.','http://router','http://100.100.100.100','http://172.16.0.1','http://169.254.169.254','http://user:secret@example.com','file:///etc/passwd','https://example.com:8080']) assert.throws(()=>websiteUrl(url),url);
  assert.equal(websiteUrl('example.org/path'),'https://example.org/path');
  assert.equal(websiteUrl(''), 'about:blank');
});
test('server enforces a bounded choice of session duration', () => {
  for (const minutes of [5,15,30]) assert.equal(sessionMinutes(minutes),minutes);
  for (const value of [0,31,Infinity,'30',null]) assert.throws(()=>sessionMinutes(value));
});
test('display options cannot inject arbitrary container settings', () => {
  assert.equal(displaySettings('smooth').KVNC_ENCODING_MAX_FRAME_RATE,'30');
  assert.equal(displaySettings('smooth').KVNC_DESKTOP_ALLOW_RESIZE,undefined);
  assert.deepEqual(displaySettings('native'),{});
  assert.throws(()=>displaySettings('-AcceptCutText=1'));
});
