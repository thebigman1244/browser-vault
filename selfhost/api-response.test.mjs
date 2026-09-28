import test from 'node:test';
import assert from 'node:assert/strict';
import {readApiResponse} from './api-response.mjs';
test('HTML sign-in never escapes as a JSON syntax error', async()=> {
  await assert.rejects(readApiResponse(new Response('<!DOCTYPE html><html>Sign in</html>', {headers:{'content-type':'text/html'}})), e=>e.needsSignIn && !e.message.includes('Unexpected token'));
});
test('HTML gateway failure explains temporary server unavailability', async()=> {
  await assert.rejects(readApiResponse(new Response('<!DOCTYPE html>', {status:502,headers:{'content-type':'text/html'}})), e=>!e.needsSignIn && /temporarily unavailable/.test(e.message));
});
test('expired Access requests require fresh sign-in', async()=> {
  for(const status of [401,403]) await assert.rejects(readApiResponse(new Response('',{status})), e=>e.needsSignIn);
});
test('valid API responses and structured errors are preserved', async()=> {
  assert.deepEqual(await readApiResponse(Response.json({ready:true})), {ready:true});
  await assert.rejects(readApiResponse(Response.json({error:'Session limit reached'},{status:409})), /Session limit reached/);
});
