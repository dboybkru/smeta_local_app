// Минимальный service worker: network-first для своих GET (навигации/ассеты),
// кэш — только офлайн-фолбэк. /api НЕ кэшируется (всегда свежие данные).
const CACHE = "smetaapp-v1";

self.addEventListener("install", () => self.skipWaiting());
self.addEventListener("activate", (event) => event.waitUntil(self.clients.claim()));

self.addEventListener("fetch", (event) => {
  const req = event.request;
  const url = new URL(req.url);
  if (req.method !== "GET" || url.origin !== self.location.origin || url.pathname.startsWith("/api")) {
    return;
  }
  event.respondWith(
    fetch(req)
      .then((resp) => {
        const copy = resp.clone();
        caches.open(CACHE).then((c) => c.put(req, copy)).catch(() => {});
        return resp;
      })
      .catch(() =>
        caches.match(req).then((c) => c || (req.mode === "navigation" ? caches.match("/") : undefined)),
      ),
  );
});
