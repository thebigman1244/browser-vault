import { mkdir, readdir, readFile, writeFile } from 'node:fs/promises';
import { gzipSync } from 'node:zlib';
import { execFileSync } from 'node:child_process';
import { resolve, relative, join } from 'node:path';
const root = resolve(import.meta.dirname, '..');
async function compress(dir) {
  for (const item of await readdir(dir, {withFileTypes:true})) {
    const path=join(dir,item.name);
    if(item.isDirectory()) await compress(path);
    else if(/\.(js|css|html|svg)$/.test(item.name)) await writeFile(path+'.gz',gzipSync(await readFile(path),{level:9}));
  }
}
await compress(join(root,'selfhost-dist'));
await mkdir(join(root,'dist'), {recursive:true});
execFileSync('tar',['-czf',join(root,'dist','frontend.tar.gz'),'-C',join(root,'selfhost-dist'),'.']);
const files=(await readdir(join(root,'selfhost'))).filter(x=>x.endsWith('.mjs')&&!x.startsWith('vite.')||['package.json','package-lock.json'].includes(x));
execFileSync('tar',['-czf',join(root,'dist','broker.tar.gz'),'-C',join(root,'selfhost'),...files]);
console.log('Built dist/frontend.tar.gz and dist/broker.tar.gz');
