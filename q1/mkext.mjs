import {generateKeyPairSync, createHash} from 'node:crypto';
import {writeFileSync} from 'node:fs';
const {publicKey} = generateKeyPairSync('rsa',{modulusLength:2048});
const der = publicKey.export({type:'spki',format:'der'});
const id = [...createHash('sha256').update(der).digest().subarray(0,16)].map(b=>String.fromCharCode(97+(b>>4))+String.fromCharCode(97+(b&15))).join('');
writeFileSync('ext/manifest.json', JSON.stringify({
  manifest_version:3, name:'ae-spike-tree', version:'0.0.1', key:der.toString('base64'),
  permissions:['automation','tabs'],
  host_permissions:['<all_urls>'],
  background:{service_worker:'bg.js'}
},null,2));
writeFileSync('ext-id.txt', id);
console.log(id);
