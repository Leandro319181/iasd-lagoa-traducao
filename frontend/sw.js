var CACHE = 'iasd-v4';
var STATIC = ['/', '/static/style.css', '/static/script.js', '/static/manifest.json', '/static/icon.jpg'];

self.addEventListener('install', function (e) {
    e.waitUntil(
        caches.open(CACHE).then(function (cache) {
            return cache.addAll(STATIC);
        })
    );
    self.skipWaiting();
});

self.addEventListener('activate', function (e) {
    e.waitUntil(
        caches.keys().then(function (keys) {
            return Promise.all(
                keys.filter(function (k) { return k !== CACHE; }).map(function (k) {
                    return caches.delete(k);
                })
            );
        })
    );
    self.clients.claim();
});

self.addEventListener('fetch', function (e) {
    var url = e.request.url;
    // Nunca cachear SSE, áudio ou status — esses são sempre ao vivo
    if (url.includes('/events') || url.includes('/audio/') || url.includes('/status') || url.includes('/operator')) {
        return;
    }
    e.respondWith(
        caches.match(e.request).then(function (cached) {
            return cached || fetch(e.request);
        })
    );
});
