// Service worker ZolaOS — PWA offline-first (souverain, sans dépendance externe).
// Règle : seuls les assets hashés par le build (/_next/static/) sont servis
// cache-first, car leur URL change à chaque contenu. Tout le reste passe au
// réseau d'abord, avec repli sur le cache hors-ligne uniquement — sinon un
// déploiement resterait invisible aux navigateurs déjà venus (bundle figé).
// Incrémenter CACHE à chaque changement de stratégie : « activate » purge les
// caches aux noms différents, c'est le seul mécanisme d'éviction.
const CACHE = "zola-shell-v2";
const PRECACHE = ["/", "/manifest.webmanifest"];
const IMMUTABLE = /^\/_next\/static\//;

self.addEventListener("install", (e) => {
  e.waitUntil(caches.open(CACHE).then((c) => c.addAll(PRECACHE)).then(() => self.skipWaiting()));
});

self.addEventListener("activate", (e) => {
  e.waitUntil(
    caches.keys()
      .then((keys) => Promise.all(keys.filter((k) => k !== CACHE).map((k) => caches.delete(k))))
      .then(() => self.clients.claim()),
  );
});

const putInCache = (req, res) => {
  if (res.ok) {
    const copy = res.clone();
    caches.open(CACHE).then((c) => c.put(req, copy));
  }
  return res;
};

self.addEventListener("fetch", (e) => {
  const req = e.request;
  if (req.method !== "GET") return;
  const url = new URL(req.url);
  if (url.origin !== self.location.origin) return; // l'API (cross-origin) n'est pas mise en cache

  // Assets hashés par le build : immuables, cache-first sans risque de péremption.
  if (IMMUTABLE.test(url.pathname)) {
    e.respondWith(
      caches.match(req).then((r) => r || fetch(req).then((res) => putInCache(req, res))),
    );
    return;
  }

  // Navigations, manifest, icônes, payloads RSC : réseau d'abord. Le cache ne
  // sert qu'de repli hors-ligne, jamais de source de vérité.
  e.respondWith(
    fetch(req)
      .then((res) => putInCache(req, res))
      .catch(() => caches.match(req).then((r) => r || (req.mode === "navigate" ? caches.match("/") : undefined))),
  );
});
