// Network-first with cache fallback: always fresh when online, fully usable offline.
const CACHE = "broker-exam-v1";
const SHELL = ["./", "./index.html", "./data/bank.js", "./manifest.json", "./icons/icon-180.png", "./icons/icon-192.png"];

self.addEventListener("install", e => {
  e.waitUntil(caches.open(CACHE).then(c => c.addAll(SHELL)).then(() => self.skipWaiting()));
});
self.addEventListener("activate", e => e.waitUntil(self.clients.claim()));
self.addEventListener("fetch", e => {
  if (e.request.method !== "GET") return;
  e.respondWith(
    fetch(e.request, {cache: "no-cache"})  // revalidate with server so new question-bank builds arrive immediately
      .then(res => {
        if (res.ok || res.type === "opaque") { const copy = res.clone(); caches.open(CACHE).then(c => c.put(e.request, copy)); }
        return res;
      })
      .catch(() => caches.match(e.request, {ignoreSearch: true}).then(r => r || caches.match("./index.html")))
  );
});
