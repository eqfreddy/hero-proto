// hero-proto service worker.
//
// Strategy:
//   - Shell assets (HTML/CSS/static icons) → cache-first, revalidate in background.
//   - API calls (/me, /heroes, /battles, /summon, /auth, /arena, /guilds, /raids,
//     /shop, /daily, /admin) → network-only. They're authed + dynamic; caching
//     them would leak stale balances and break multi-device state.
//   - Unknown paths → network-first with a cached fallback for offline.
//
// Cache is versioned; bumping SHELL_VERSION invalidates old entries on activate.

const SHELL_VERSION = "v1";
const SHELL_CACHE = `hp-shell-${SHELL_VERSION}`;

const SHELL_ASSETS = [
  "/app/",
  "/app/static/icons/hero-proto-192.png",
  "/app/static/icons/hero-proto-512.png",
  "/app/manifest.webmanifest",
];

// Paths we never cache — always go to the network. Bypass even in offline mode.
const API_PREFIXES = [
  "/me", "/auth/", "/summon", "/heroes", "/battles", "/gear",
  "/arena", "/daily", "/guilds", "/raids", "/shop", "/admin",
  "/announcements", "/liveops", "/metrics", "/healthz", "/worker/",
];

function isApiRequest(url) {
  const p = new URL(url).pathname;
  return API_PREFIXES.some(prefix => p === prefix || p.startsWith(prefix));
}

self.addEventListener("install", (event) => {
  event.waitUntil(
    caches.open(SHELL_CACHE).then(cache => cache.addAll(SHELL_ASSETS))
      .then(() => self.skipWaiting())
  );
});

self.addEventListener("activate", (event) => {
  event.waitUntil(
    caches.keys().then(keys => Promise.all(
      keys.filter(k => k.startsWith("hp-shell-") && k !== SHELL_CACHE)
          .map(k => caches.delete(k))
    )).then(() => self.clients.claim())
  );
});

self.addEventListener("fetch", (event) => {
  const req = event.request;
  if (req.method !== "GET") return;  // mutations: network only, no cache

  // API passes through — never cache.
  if (isApiRequest(req.url)) return;

  // Shell assets under /app/ — cache-first with background revalidate.
  const url = new URL(req.url);
  if (url.pathname.startsWith("/app/")) {
    event.respondWith(
      caches.match(req).then(cached => {
        const fetchPromise = fetch(req).then(res => {
          if (res && res.status === 200 && res.type === "basic") {
            const clone = res.clone();
            caches.open(SHELL_CACHE).then(c => c.put(req, clone));
          }
          return res;
        }).catch(() => cached);
        return cached || fetchPromise;
      })
    );
    return;
  }
  // Everything else: default fetch. No special handling.
});
