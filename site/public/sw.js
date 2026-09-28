// Offline support. After one visit the site opens without a network connection, and
// Python works offline too once its packages have been downloaded once.
// - page navigations: network first, cached index.html as fallback;
// - versioned files (build assets, Pyodide core, the tsfm_rc wheel, published result
//   versions, CDN packages whose URL contains the Pyodide version): cache first;
// - other data files and the results index: network first, cache as fallback.
// Supabase requests are never cached.
const CACHE = "tsfm-rc-v1";
const IMMUTABLE = [/^\/assets\//, /^\/pyodide\/v[^/]+\//, /^\/py\/[0-9a-f]{12}\//, /^\/data\/results\/[^/]+\/[0-9a-f]{12}\//];

self.addEventListener("install", (event) => {
  event.waitUntil(caches.open(CACHE).then((c) => c.addAll(["/", "/index.html"])).then(() => self.skipWaiting()));
});

self.addEventListener("activate", (event) => {
  event.waitUntil(
    caches.keys().then((keys) => Promise.all(keys.filter((k) => k !== CACHE).map((k) => caches.delete(k)))).then(() => self.clients.claim()),
  );
});

async function cacheFirst(req) {
  const cache = await caches.open(CACHE);
  const hit = await cache.match(req);
  if (hit) return hit;
  const res = await fetch(req);
  if (res.ok) cache.put(req, res.clone());
  return res;
}

async function networkFirst(req, fallbackUrl) {
  const cache = await caches.open(CACHE);
  try {
    const res = await fetch(req);
    if (res.ok) cache.put(fallbackUrl ?? req, res.clone());
    return res;
  } catch (e) {
    const hit = await cache.match(fallbackUrl ?? req);
    if (hit) return hit;
    throw e;
  }
}

self.addEventListener("fetch", (event) => {
  const req = event.request;
  if (req.method !== "GET") return;
  const url = new URL(req.url);
  if (url.hostname.endsWith("supabase.co")) return;
  if (url.hostname === "cdn.jsdelivr.net" && url.pathname.startsWith("/pyodide/v")) {
    event.respondWith(cacheFirst(req));
    return;
  }
  if (url.origin !== self.location.origin) return;
  if (req.mode === "navigate") {
    event.respondWith(networkFirst(req, "/index.html"));
    return;
  }
  if (IMMUTABLE.some((re) => re.test(url.pathname))) {
    event.respondWith(cacheFirst(req));
    return;
  }
  event.respondWith(networkFirst(req));
});
