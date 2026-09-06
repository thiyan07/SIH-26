self.addEventListener('install', (e) => self.skipWaiting())
self.addEventListener('activate', (e) => self.clients.claim())
self.addEventListener('fetch', (e) => {
  // Cache-first for static, network-first for API
  if (e.request.url.includes('/locations/search') || e.request.url.includes('/analysis')) {
    e.respondWith(fetch(e.request).catch(() => caches.match(e.request)))
    return
  }
  e.respondWith(caches.match(e.request).then(r => r || fetch(e.request)))
})
