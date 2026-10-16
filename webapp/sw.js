/* AbdulmajeedPharma (APH) — offline cache
   يعمل الموقع كتطبيق دون إنترنت بعد أول زيارة، مع استثناءات مهمة:
   • لا يتدخل في أي طلب خارج النطاق (Gemini / OpenAI / raw / jsDelivr)
   • لا يخزّن aph-database.json حتى تبقى المزامنة طازجة دائماً */
const C = 'aph-v5';
const CORE = ['./', './index.html', './drugs-data.js', './aph-cloud.js', './manifest.webmanifest'];

self.addEventListener('install', e => {
  e.waitUntil(
    caches.open(C)
      .then(c => Promise.all(CORE.map(u => c.add(u).catch(() => {}))))
      .then(() => self.skipWaiting())
  );
});

self.addEventListener('activate', e => {
  e.waitUntil(
    caches.keys()
      .then(ks => Promise.all(ks.filter(k => k !== C).map(k => caches.delete(k))))
      .then(() => self.clients.claim())
  );
});

self.addEventListener('fetch', e => {
  if (e.request.method !== 'GET') return;
  let url;
  try { url = new URL(e.request.url); } catch (_) { return; }
  if (url.origin !== self.location.origin) return;          // API calls & sync sources: never cached
  if (url.pathname.indexOf('aph-database.json') !== -1) return; // always fetch fresh
  e.respondWith(
    caches.match(e.request).then(hit => hit || fetch(e.request).then(res => {
      const copy = res.clone();
      caches.open(C).then(c => c.put(e.request, copy)).catch(() => {});
      return res;
    }).catch(() => caches.match('./index.html')))
  );
});
