// Service Worker for CurrencyTracker PWA
const CACHE_NAME = 'currency-tracker-v1'
const STATIC_ASSETS = [
  '/',
  '/index.html',
  '/manifest.json',
  '/icon-192.png',
  '/icon-512.png',
]

const API_CACHE_NAME = 'currency-tracker-api-v1'
const API_CACHE_DURATION = 5 * 60 * 1000 // 5 minutes

// Install event - cache static assets
self.addEventListener('install', (event) => {
  event.waitUntil(
    caches.open(CACHE_NAME).then((cache) => {
      return cache.addAll(STATIC_ASSETS)
    })
  )
  self.skipWaiting()
})

// Activate event - clean up old caches
self.addEventListener('activate', (event) => {
  event.waitUntil(
    caches.keys().then((cacheNames) => {
      return Promise.all(
        cacheNames
          .filter((name) => name !== CACHE_NAME && name !== API_CACHE_NAME)
          .map((name) => caches.delete(name))
      )
    })
  )
  self.clients.claim()
})

// Fetch event - serve from cache, fallback to network
self.addEventListener('fetch', (event) => {
  const { request } = event
  const url = new URL(request.url)

  // Skip non-GET requests
  if (request.method !== 'GET') {
    return
  }

  // Skip chrome-extension and other non-http requests
  if (!url.protocol.startsWith('http')) {
    return
  }

  // Handle API requests with stale-while-revalidate
  if (url.pathname.startsWith('/api/')) {
    event.respondWith(handleApiRequest(request))
    return
  }

  // Handle static assets with cache-first
  event.respondWith(handleStaticRequest(request))
})

async function handleStaticRequest(request: Request): Promise<Response> {
  const cachedResponse = await caches.match(request)
  if (cachedResponse) {
    return cachedResponse
  }

  try {
    const networkResponse = await fetch(request)
    if (networkResponse.ok) {
      const cache = await caches.open(CACHE_NAME)
      cache.put(request, networkResponse.clone())
    }
    return networkResponse
  } catch {
    // Return offline page for navigation requests
    if (request.mode === 'navigate') {
      return caches.match('/index.html') || new Response('Offline', { status: 503 })
    }
    return new Response('Offline', { status: 503 })
  }
}

async function handleApiRequest(request: Request): Promise<Response> {
  const cache = await caches.open(API_CACHE_NAME)
  const cachedResponse = await cache.match(request)

  // Try network first for fresh data
  try {
    const networkResponse = await fetch(request)
    if (networkResponse.ok) {
      // Cache successful response with timestamp
      const responseToCache = networkResponse.clone()
      const headers = new Headers(responseToCache.headers)
      headers.set('sw-cached-at', Date.now().toString())
      const cachedResponse = new Response(await responseToCache.blob(), {
        status: responseToCache.status,
        statusText: responseToCache.statusText,
        headers,
      })
      await cache.put(request, cachedResponse)
    }
    return networkResponse
  } catch {
    // Network failed, serve from cache if available
    if (cachedResponse) {
      const cachedAt = cachedResponse.headers.get('sw-cached-at')
      const age = cachedAt ? Date.now() - parseInt(cachedAt) : Infinity

      // Add header to indicate stale data
      const headers = new Headers(cachedResponse.headers)
      headers.set('x-cache-status', 'stale')
      headers.set('x-cache-age', Math.round(age / 1000).toString())

      return new Response(await cachedResponse.blob(), {
        status: cachedResponse.status,
        statusText: cachedResponse.statusText,
        headers,
      })
    }

    // No cache available
    return new Response(
      JSON.stringify({ error: 'Offline - no cached data available' }),
      {
        status: 503,
        headers: { 'Content-Type': 'application/json' },
      }
    )
  }
}

// Background sync for failed requests (optional)
self.addEventListener('sync', (event) => {
  if (event.tag === 'sync-alerts') {
    event.waitUntil(syncAlerts())
  }
})

async function syncAlerts(): Promise<void> {
  // Implement background sync for alerts if needed
  console.log('Background sync triggered')
}

// Push notifications (optional)
self.addEventListener('push', (event) => {
  if (!event.data) return

  const data = event.data.json()
  const options = {
    body: data.body,
    icon: '/icon-192.png',
    badge: '/icon-72.png',
    vibrate: [100, 50, 100],
    data: data.data,
    actions: data.actions || [],
  }

  event.waitUntil(
    self.registration.showNotification(data.title, options)
  )
})

self.addEventListener('notificationclick', (event) => {
  event.notification.close()

  if (event.action) {
    // Handle action clicks
    clients.openWindow(event.action)
  } else {
    // Default click - open app
    event.waitUntil(
      clients.matchAll({ type: 'window' }).then((clientList) => {
        for (const client of clientList) {
          if (client.url === '/' && 'focus' in client) {
            return client.focus()
          }
        }
        return clients.openWindow('/')
      })
    )
  }
})