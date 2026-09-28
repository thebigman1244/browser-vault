import test from 'node:test';
import assert from 'node:assert/strict';
import {securityStatus} from './security.mjs';
const now=Date.now(),id='session';
const sample={version:1,checkedAt:now,sessionId:id,state:'monitoring',files:[{name:'test.exe',sha256:'a'.repeat(64),size:4,status:'flagged',findings:['Test signature'],scannedAt:now},{name:'oversize.zip',sha256:null,size:99999999,status:'not_scanned',findings:['Size limit']}],engine:{available:true,version:'test',definitionsAt:now,definitionsFresh:true}};
test('stale and wrong-session scan results are not shown as current',()=>{
  assert.equal(securityStatus({...sample,checkedAt:now-180001},id,now).fresh,false);
  assert.equal(securityStatus({...sample,checkedAt:now+6000},id,now).fresh,false);
  assert.equal(securityStatus(null,id,now).fresh,false);
  assert.deepEqual(securityStatus(sample,'another-session',now).files,[]);
  assert.equal(securityStatus(sample,null,now).state,'idle');
});
test('flagged, skipped, and unknown scan states remain distinct',()=>{
  const result=securityStatus(sample,id,now);
  assert.equal(result.files[0].status,'flagged');assert.equal(result.files[1].status,'not_scanned');assert.equal(result.files[1].sha256,null);
  assert.equal(securityStatus({...sample,files:[{...sample.files[0],status:'safe'}]},id,now).files[0].status,'error');
});
