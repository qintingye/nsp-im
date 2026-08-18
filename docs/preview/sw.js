/* NSP-IM 内网部署 Service Worker · W1-D4
 * 缓存策略: stale-while-revalidate
 * - HTML / SW: network-first (保证更新可见)
 * - data/*.json: stale-while-revalidate (离线可用, 后台拉新)
 */
const CACHE_NAME = 'nspim-preview-w1d4-v1';
const CORE_ASSETS = [
  './',
  './index.html',
  './manifest.json',
  './data/policies.json',
  './data/health.json'
];

self.addEventListener('install', (event) => {
  event.waitUntil(
    caches.open(CACHE_NAME).then((cache) => cache.addAll(CORE_ASSETS))
      .then(() => self.skipWaiting())
  );
});

self.addEventListener('activate', (event) => {
  event.waitUntil(
    caches.keys().then((keys) =>
      Promise.all(keys.filter((k) => k !== CACHE_NAME).map((k) => caches.delete(k)))
    ).then(() => self.clients.claim())
  );
});

self.addEventListener('fetch', (event) => {
  const req = event.request;
  if (req.method !== 'GET') return;

  const url = new URL(req.url);
  const isJson = url.pathname.endsWith('.json');
  const isHtml = req.headers.get('accept')?.includes('text/html') || url.pathname.endsWith('/') || url.pathname.endsWith('/index.html');

  event.respondWith((async () => {
    const cache = await caches.open(CACHE_NAME);
    const cached = await cache.match(req);

    if (isJson) {
      // stale-while-revalidate
      const networkPromise = fetch(req).then((resp) => {
        if (resp.ok) cache.put(req, resp.clone());
        return resp;
      }).catch(() => cached);
      return cached || networkPromise;
    }

    if (isHtml) {
      // network-first
      try {
        const resp = await fetch(req);
        if (resp.ok) cache.put(req, resp.clone());
        return resp;
      } catch (e) {
        return cached || new Response('离线 & 未缓存', { status: 503 });
      }
    }

    // 默认: cache-first
    return cached || fetch(req);
  })());
});

self.addEventListener('message', (event) => {
  if (event.data === 'SKIP_WAITING') self.skipWaiting();
});