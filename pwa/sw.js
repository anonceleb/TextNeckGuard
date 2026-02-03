const CACHE_NAME = 'text-neck-v2';
const ASSETS = [
    './',
    './index.html',
    './css/style.css',
    './js/app.js',
    'https://cdn.jsdelivr.net/npm/@mediapipe/pose/pose.js',
    'https://cdn.jsdelivr.net/npm/@mediapipe/camera_utils/camera_utils.js',
    'https://cdn.jsdelivr.net/npm/@mediapipe/drawing_utils/drawing_utils.js'
];

self.addEventListener('install', (event) => {
    event.waitUntil(
        caches.open(CACHE_NAME)
            .then((cache) => cache.addAll(ASSETS))
    );
});

self.addEventListener('fetch', (event) => {
    // Basic network-first strategy
    event.respondWith(
        fetch(event.request)
            .catch(() => caches.match(event.request))
    );
});
