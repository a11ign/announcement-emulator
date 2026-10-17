const COLLECTOR='http://127.0.0.1:8765/';
const post=(k,b)=>fetch(COLLECTOR+k,{method:'POST',body:JSON.stringify(b)}).catch(()=>{});
post('hello-page',{keys:Object.keys(chrome.automation||{}), proto: chrome.automation? Object.getOwnPropertyNames(Object.getPrototypeOf(chrome.automation)):null});
