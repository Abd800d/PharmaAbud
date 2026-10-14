/* APH offline cache — يعمل التطبيق دون إنترنت بعد أول زيارة */
const C='aph-v3';
const CORE=['./','./index.html','./drugs-data.js','./manifest.webmanifest'];
self.addEventListener('install',e=>{e.waitUntil(caches.open(C).then(c=>c.addAll(CORE)).then(()=>self.skipWaiting()))});
self.addEventListener('activate',e=>{e.waitUntil(self.clients.claim())});
self.addEventListener('fetch',e=>{
  if(e.request.method!=='GET')return;
  e.respondWith(
    caches.match(e.request).then(hit=>hit||fetch(e.request).then(res=>{
      const copy=res.clone();caches.open(C).then(c=>c.put(e.request,copy)).catch(()=>{});return res;
    }).catch(()=>caches.match('./index.html')))
  );
});
