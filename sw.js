/**
 * sw.js — Service Worker для PWA «Утрау».
 * Кэш статики (cache-first), HTML/JSON network-first, обработка push.
 */
const CACHE_VERSION = 'utrau-v2-2026-07-24';
const STATIC_CACHE = 'utrau-static-' + CACHE_VERSION;
const RUNTIME_CACHE = 'utrau-runtime-' + CACHE_VERSION;
const BASE = '/DaniilK-utrau/';

const STATIC_ASSETS = [
  BASE + 'manifest.json',
  BASE + 'apple-touch-icon.png',
  BASE + 'icon-192.png',
  BASE + 'icon-512.png',
];

self.addEventListener('install', (event) => {
  event.waitUntil(
    caches.open(STATIC_CACHE)
      .then((c) => c.addAll(STATIC_ASSETS.map((u) => new Request(u, { cache: 'reload' }))))
      .then(() => self.skipWaiting())
      .catch((e) => console.warn('[sw] install', e))
  );
});

self.addEventListener('activate', (event) => {
  event.waitUntil(
    caches.keys().then((keys) =>
      Promise.all(keys.filter((k) => k.startsWith('utrau-') && !k.endsWith(CACHE_VERSION)).map((k) => caches.delete(k)))
    ).then(() => self.clients.claim())
  );
});

self.addEventListener('fetch', (event) => {
  const req = event.request;
  const url = new URL(req.url);
  if (req.method !== 'GET' || url.origin !== self.location.origin) return;
  if (url.pathname.endsWith('/api_url.json')) {
    event.respondWith(fetch(req, { cache: 'no-store' }).catch(() => caches.match(req)));
    return;
  }
  const accept = req.headers.get('accept') || '';
  if (accept.includes('text/html') || url.pathname.endsWith('.html') || url.pathname.endsWith('.json')) {
    event.respondWith(networkFirst(req));
    return;
  }
  // Данные отчётов (data/*.js) — network-first: свежие цифры важнее офлайна.
  // Иначе cache-first ниже замораживает .js навсегда и дашборды не обновляются.
  if (url.pathname.includes('/data/') || url.pathname.endsWith('_data.js')) {
    event.respondWith(networkFirst(req));
    return;
  }
  if (url.pathname.match(/\.(png|jpg|jpeg|webp|svg|woff2?|ttf|css|js)$/)) {
    event.respondWith(cacheFirst(req));
    return;
  }
});

async function networkFirst(req) {
  try {
    const fresh = await fetch(req);
    if (fresh && fresh.ok) { const c = await caches.open(RUNTIME_CACHE); c.put(req, fresh.clone()); }
    return fresh;
  } catch (e) {
    const cached = await caches.match(req);
    if (cached) return cached;
    return new Response(
      '<!doctype html><meta charset="utf-8"><title>Офлайн</title>' +
      '<style>body{background:#080c08;color:#eeeae4;font-family:system-ui;text-align:center;padding:80px 24px;}' +
      'h1{font-weight:300;}a{color:#4fb8b0;}</style><h1>📡 Нет связи</h1>' +
      '<p>Данные обновятся, как появится сеть.</p><p><a href="' + BASE + 'reports.html">← На главную</a></p>',
      { headers: { 'Content-Type': 'text/html; charset=utf-8' }, status: 200 }
    );
  }
}
async function cacheFirst(req) {
  const cached = await caches.match(req);
  if (cached) return cached;
  try {
    const fresh = await fetch(req);
    if (fresh && fresh.ok) { const c = await caches.open(RUNTIME_CACHE); c.put(req, fresh.clone()); }
    return fresh;
  } catch (e) { return new Response('Offline', { status: 503 }); }
}

self.addEventListener('push', (event) => {
  let data = {};
  try { data = event.data ? event.data.json() : {}; }
  catch (e) { data = { title: 'Утрау', body: event.data ? event.data.text() : 'Новое уведомление' }; }
  const title = data.title || 'Утрау';
  const options = {
    body: data.body || '',
    icon: data.icon || BASE + 'icon-192.png',
    badge: data.badge || BASE + 'icon-192.png',
    tag: data.tag || 'utrau-default',
    data: { url: data.url || BASE + 'reports.html' },
    requireInteraction: data.critical === true,
    timestamp: Date.now(),
  };
  event.waitUntil(self.registration.showNotification(title, options));
});

self.addEventListener('notificationclick', (event) => {
  event.notification.close();
  const target = (event.notification.data && event.notification.data.url) || BASE + 'reports.html';
  event.waitUntil(
    self.clients.matchAll({ type: 'window', includeUncontrolled: true }).then((clients) => {
      for (const c of clients) {
        if (c.url.includes(BASE) && 'focus' in c) { c.navigate(target); return c.focus(); }
      }
      if (self.clients.openWindow) return self.clients.openWindow(target);
    })
  );
});
