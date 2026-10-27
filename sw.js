/* 绂荤嚎缂撳瓨锛欻TML 璧?network-first锛堜繚璇佹洿鏂拌兘鐢熸晥锛夛紝闈欐€佽祫婧愯蛋 cache-first锛屾暟鎹?闊抽璧?network-first 骞跺洖濉紦瀛?*/
const CACHE = 'toefl-v3';
const CORE = ['./', './index.html', './manifest.webmanifest'];

self.addEventListener('install', e => {
  e.waitUntil(caches.open(CACHE).then(c => c.addAll(CORE)).then(() => self.skipWaiting()));
});

self.addEventListener('activate', e => {
  e.waitUntil(
    caches.keys()
      .then(keys => Promise.all(keys.filter(k => k !== CACHE).map(k => caches.delete(k))))
      .then(() => self.clients.claim())
  );
});

self.addEventListener('fetch', e => {
  const req = e.request;
  if (req.method !== 'GET') return;
  const url = new URL(req.url);
  if (url.origin !== location.origin) return;

  const isHtml = req.mode === 'navigate' || url.pathname.endsWith('/') || url.pathname.endsWith('.html');
  if (isHtml) {
    // network-first锛氭嬁鍒版柊鐨勫氨鐢ㄦ柊鐨勶紝鏂綉鎵嶇敤缂撳瓨
    e.respondWith(
      fetch(req).then(r => {
        const copy = r.clone();
        caches.open(CACHE).then(c => c.put(req, copy));
        return r;
      }).catch(() => caches.match(req).then(hit => hit || caches.match('./index.html')))
    );
    return;
  }

  // 鍏跺畠璧勬簮锛歝ache-first锛屾湭鍛戒腑鍐嶈姹傚苟鍥炲～
  e.respondWith(
    caches.match(req).then(hit => hit || fetch(req).then(r => {
      if (r && r.status === 200) {
        const copy = r.clone();
        caches.open(CACHE).then(c => c.put(req, copy));
      }
      return r;
    }).catch(() => hit))
  );
});

