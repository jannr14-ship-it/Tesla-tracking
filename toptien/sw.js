// Toptien service worker: de app werkt offline met de laatst geladen lijsten.
const SHELL = 'toptien-shell-v1';
const DATA = 'toptien-data';
const SHELL_FILES = ['./', './index.html', './manifest.webmanifest', './icon-192.png', './icon-512.png'];

self.addEventListener('install', e => {
  e.waitUntil(caches.open(SHELL).then(c => c.addAll(SHELL_FILES)).then(() => self.skipWaiting()));
});
self.addEventListener('activate', e => {
  e.waitUntil(caches.keys()
    .then(keys => Promise.all(keys.filter(k => k.startsWith('toptien-shell-') && k !== SHELL).map(k => caches.delete(k))))
    .then(() => self.clients.claim()));
});

// Netwerk eerst (verse lijsten), cache als reserve (offline).
async function networkFirst(req, cacheName) {
  const cache = await caches.open(cacheName);
  try {
    const res = await fetch(req);
    if (res && (res.ok || res.type === 'opaque')) cache.put(req, res.clone());
    return res;
  } catch (err) {
    const hit = await cache.match(req, { ignoreSearch: true });
    if (hit) return hit;
    throw err;
  }
}
// Cache eerst, op de achtergrond verversen (lettertypes, plaatjes).
async function staleWhileRevalidate(req, cacheName) {
  const cache = await caches.open(cacheName);
  const hit = await cache.match(req);
  const fresh = fetch(req).then(res => {
    if (res && (res.ok || res.type === 'opaque')) cache.put(req, res.clone());
    return res;
  }).catch(() => hit);
  return hit || fresh;
}

self.addEventListener('fetch', e => {
  const req = e.request;
  if (req.method !== 'GET') return;
  const url = new URL(req.url);
  const inScope = url.href.startsWith(self.registration.scope);
  if (req.mode === 'navigate' && inScope) {
    e.respondWith(networkFirst(req, SHELL).catch(() => caches.match('./index.html')));
  } else if (inScope && /\/data\.json$/.test(url.pathname)) {
    e.respondWith(networkFirst(req, DATA));
  } else if (inScope && /\/img\//.test(url.pathname)) {
    e.respondWith(staleWhileRevalidate(req, DATA));
  } else if (url.hostname === 'fonts.googleapis.com' || url.hostname === 'fonts.gstatic.com') {
    e.respondWith(staleWhileRevalidate(req, SHELL));
  } else if (inScope) {
    e.respondWith(networkFirst(req, SHELL));
  }
});
