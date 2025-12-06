// Service Worker for Cherry Hills Worship Arts PWA
const CACHE_NAME = 'aria-wa-v1';
const STATIC_CACHE = 'aria-static-v1';

// Assets to cache on install
const STATIC_ASSETS = [
  '/',
  '/chat/',
  '/static/css/styles.css',
  '/static/css/fonts.css',
  '/static/favicon.png',
  '/static/manifest.json',
];

// Install event - cache static assets
self.addEventListener('install', (event) => {
  event.waitUntil(
    caches.open(STATIC_CACHE).then((cache) => {
      console.log('Caching static assets');
      return cache.addAll(STATIC_ASSETS.filter(url => !url.includes('undefined')));
    }).catch((error) => {
      console.log('Cache install error:', error);
    })
  );
  self.skipWaiting();
});

// Activate event - clean up old caches
self.addEventListener('activate', (event) => {
  event.waitUntil(
    caches.keys().then((cacheNames) => {
      return Promise.all(
        cacheNames
          .filter((name) => name !== CACHE_NAME && name !== STATIC_CACHE)
          .map((name) => caches.delete(name))
      );
    })
  );
  self.clients.claim();
});

// Fetch event - network first, fallback to cache
self.addEventListener('fetch', (event) => {
  const { request } = event;
  const url = new URL(request.url);

  // Skip non-GET requests
  if (request.method !== 'GET') {
    return;
  }

  // Skip cross-origin requests
  if (url.origin !== location.origin) {
    return;
  }

  // Skip API/dynamic requests (let them go to network)
  if (url.pathname.startsWith('/chat/send/') ||
      url.pathname.startsWith('/api/') ||
      url.pathname.includes('htmx')) {
    return;
  }

  // For HTML pages - network first, cache fallback
  if (request.headers.get('accept')?.includes('text/html')) {
    event.respondWith(
      fetch(request)
        .then((response) => {
          // Clone and cache the response
          const responseClone = response.clone();
          caches.open(CACHE_NAME).then((cache) => {
            cache.put(request, responseClone);
          });
          return response;
        })
        .catch(() => {
          // Fallback to cache
          return caches.match(request).then((cachedResponse) => {
            if (cachedResponse) {
              return cachedResponse;
            }
            // Return offline page if available
            return caches.match('/');
          });
        })
    );
    return;
  }

  // For static assets - cache first, network fallback
  if (url.pathname.startsWith('/static/')) {
    event.respondWith(
      caches.match(request).then((cachedResponse) => {
        if (cachedResponse) {
          return cachedResponse;
        }
        return fetch(request).then((response) => {
          const responseClone = response.clone();
          caches.open(STATIC_CACHE).then((cache) => {
            cache.put(request, responseClone);
          });
          return response;
        });
      })
    );
    return;
  }

  // Default - network first
  event.respondWith(
    fetch(request)
      .then((response) => {
        return response;
      })
      .catch(() => {
        return caches.match(request);
      })
  );
});

// Handle push notifications
self.addEventListener('push', (event) => {
  console.log('Push notification received:', event);

  let data = {
    title: 'Cherry Hills WA',
    body: 'New notification',
    icon: '/static/icons/icon-192x192.png',
    badge: '/static/icons/badge-72x72.png',
    url: '/',
    tag: 'default',
    data: {}
  };

  if (event.data) {
    try {
      const payload = event.data.json();
      data = { ...data, ...payload };
    } catch (e) {
      console.error('Error parsing push data:', e);
      data.body = event.data.text();
    }
  }

  const options = {
    body: data.body,
    icon: data.icon,
    badge: data.badge,
    vibrate: [100, 50, 100, 50, 100],
    tag: data.tag,
    renotify: true,
    requireInteraction: data.requireInteraction || false,
    data: {
      url: data.url,
      ...data.data
    },
    actions: data.actions || []
  };

  event.waitUntil(
    self.registration.showNotification(data.title, options)
  );
});

// Handle notification clicks
self.addEventListener('notificationclick', (event) => {
  console.log('Notification clicked:', event);
  event.notification.close();

  const urlToOpen = event.notification.data?.url || '/';

  // Handle action button clicks
  if (event.action) {
    console.log('Action clicked:', event.action);
    // Could handle different actions here
  }

  event.waitUntil(
    clients.matchAll({ type: 'window', includeUncontrolled: true })
      .then((clientList) => {
        // Check if there's already a window open
        for (const client of clientList) {
          if (client.url.includes(self.location.origin) && 'focus' in client) {
            client.navigate(urlToOpen);
            return client.focus();
          }
        }
        // Open new window if none exists
        if (clients.openWindow) {
          return clients.openWindow(urlToOpen);
        }
      })
  );

  // Track notification click (fire and forget)
  if (event.notification.data?.notificationLogId) {
    fetch('/notifications/clicked/', {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
      },
      body: JSON.stringify({
        log_id: event.notification.data.notificationLogId
      })
    }).catch(() => {});
  }
});

// Handle notification close (dismissed without clicking)
self.addEventListener('notificationclose', (event) => {
  console.log('Notification closed:', event);
});
