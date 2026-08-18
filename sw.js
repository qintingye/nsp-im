/* NSP-IM Service Worker · W3-D4
 *
 * 设计目标：
 * 1. 版本号机制：构建时注入 BUILD_ID；新 SW 安装后通过 postMessage 通知所有 client
 *    "有新版本，是否刷新？"，由前端 Toast 弹"更新可用"
 * 2. 数据更新通知：data/policies.json stale-while-revalidate 拉新成功后，
 *    通过 BroadcastChannel('nspim-data') 通知前端"数据已更新"，前端自动 re-render
 * 3. 离线 fallback：HTML 请求失败时返回 /offline.html（带"网络中断 + 显示缓存数据"）
 * 4. 分级缓存策略：
 *    - HTML: network-first（保证更新可见）+ cache fallback
 *    - JSON data: stale-while-revalidate（离线可用 + 后台拉新）
 *    - icons/fonts: cache-first（永久资源）
 *    - 其他: try cache, fallback network
 *
 * 注意：这里硬编码版本号用于本地预览/内网部署。生产环境应由 build 脚本注入。
 */
const SW_VERSION  = '3.4.0-w3d4';
const CACHE_NAME  = `nspim-v${SW_VERSION}`;
const DATA_CHANNEL = 'nspim-data';
const UPDATE_CHANNEL = 'nspim-update';

// 核心静态资源（install 阶段全部预缓存）
const CORE_ASSETS = [
  './',
  './index.html',
  './manifest.json',
  './offline.html',
  './icons/icon-192.png',
  './icons/icon-512.png',
  './icons/icon-512-maskable.png',
  './icons/apple-touch-icon.png',
  './fonts/NotoSansSC-subset.woff2'
];

// 匹配路径
const isHtmlPath = (path) =>
  path === '/' || path.endsWith('/index.html') || path.endsWith('.html');
const isJsonData = (path) =>
  path.endsWith('/data/policies.json') ||
  path.endsWith('/data/health.json') ||
  path.endsWith('.json');
const isStaticAsset = (path) =>
  path.startsWith('/icons/') || path.startsWith('/fonts/');

// ----- install: 预缓存核心资源 + skipWaiting -----
self.addEventListener('install', (event) => {
  event.waitUntil(
    caches.open(CACHE_NAME)
      .then((cache) => cache.addAll(CORE_ASSETS))
      .then(() => self.skipWaiting())
      .catch((err) => {
        console.warn('[SW] install cache.addAll 部分失败（offline.html/fonts 可能未就绪），继续:', err);
        return self.skipWaiting();
      })
  );
});

// ----- activate: 清旧缓存 + claim 所有 client + 通知新版本 -----
self.addEventListener('activate', (event) => {
  event.waitUntil((async () => {
    const keys = await caches.keys();
    await Promise.all(
      keys.filter((k) => k !== CACHE_NAME).map((k) => caches.delete(k))
    );
    await self.clients.claim();
    // 通知所有已打开的 client：SW 已更新
    const clients = await self.clients.matchAll({ includeUncontrolled: true });
    clients.forEach((c) => c.postMessage({
      channel: UPDATE_CHANNEL,
      type: 'SW_UPDATED',
      version: SW_VERSION
    }));
  })());
});

// ----- fetch: 分级缓存策略 -----
self.addEventListener('fetch', (event) => {
  const req = event.request;
  if (req.method !== 'GET') return;

  const url = new URL(req.url);
  // 只处理同源
  if (url.origin !== self.location.origin) return;

  const path = url.pathname;

  // HTML：network-first
  if (isHtmlPath(path)) {
    event.respondWith(handleHtml(req));
    return;
  }
  // JSON data：stale-while-revalidate + 通知前端
  if (isJsonData(path)) {
    event.respondWith(handleData(req));
    return;
  }
  // 静态资源：cache-first
  if (isStaticAsset(path)) {
    event.respondWith(handleStatic(req));
    return;
  }
  // 其他：cache-first with network fallback
  event.respondWith(handleOther(req));
});

// ----- 各策略实现 -----

async function handleHtml(req) {
  const cache = await caches.open(CACHE_NAME);
  try {
    const resp = await fetch(req);
    if (resp.ok) {
      cache.put(req, resp.clone());
      // HTML 是新版本入口 → 通知前端
      broadcastUpdate('HTML_UPDATED');
    }
    return resp;
  } catch (e) {
    const cached = await cache.match(req);
    if (cached) return cached;
    const offline = await cache.match('./offline.html');
    return offline || new Response('离线 & 未缓存', { status: 503 });
  }
}

async function handleData(req) {
  const cache = await caches.open(CACHE_NAME);
  const cached = await cache.match(req);
  const networkPromise = fetch(req)
    .then((resp) => {
      if (resp.ok) {
        cache.put(req, resp.clone());
        // 数据已更新 → 通知前端
        broadcastData('DATA_UPDATED', req.url);
      }
      return resp;
    })
    .catch(() => cached);
  return cached || networkPromise;
}

async function handleStatic(req) {
  const cache = await caches.open(CACHE_NAME);
  const cached = await cache.match(req);
  if (cached) return cached;
  try {
    const resp = await fetch(req);
    if (resp.ok) cache.put(req, resp.clone());
    return resp;
  } catch (e) {
    return cached || new Response('', { status: 504 });
  }
}

async function handleOther(req) {
  const cache = await caches.open(CACHE_NAME);
  const cached = await cache.match(req);
  if (cached) return cached;
  try {
    const resp = await fetch(req);
    if (resp.ok) cache.put(req, resp.clone());
    return resp;
  } catch (e) {
    return new Response('Network error', { status: 504 });
  }
}

// ----- 广播工具 -----

function broadcastData(type, url) {
  try {
    const bc = new BroadcastChannel(DATA_CHANNEL);
    bc.postMessage({ type, url, at: Date.now() });
    bc.close();
  } catch (e) {
    // BroadcastChannel 不支持时回退到 client.postMessage
    self.clients.matchAll({ includeUncontrolled: true }).then((clients) => {
      clients.forEach((c) => c.postMessage({ channel: DATA_CHANNEL, type, url }));
    });
  }
}

function broadcastUpdate(type) {
  self.clients.matchAll({ includeUncontrolled: true }).then((clients) => {
    clients.forEach((c) => c.postMessage({
      channel: UPDATE_CHANNEL,
      type,
      version: SW_VERSION
    }));
  });
}

// ----- 接收前端消息 -----
self.addEventListener('message', (event) => {
  const data = event.data;
  if (!data) return;
  if (data === 'SKIP_WAITING') self.skipWaiting();
  if (data === 'GET_VERSION') {
    event.source && event.source.postMessage({
      channel: UPDATE_CHANNEL,
      type: 'VERSION',
      version: SW_VERSION
    });
  }
});