"use client";

import { useEffect } from "react";

/**
 * Service worker (PWA offline), en production uniquement : en dev les chunks Next
 * ne sont pas hashés par contenu, donc les mettre en cache fige l'app sur un vieux
 * bundle (HTML neuf + JS périmé = erreurs d'hydratation). En dev on désinstalle
 * tout SW hérité d'un build précédent et on vide ses caches.
 */
export function Pwa() {
  useEffect(() => {
    if (typeof navigator === "undefined" || !("serviceWorker" in navigator)) return;

    if (process.env.NODE_ENV === "production") {
      navigator.serviceWorker.register("/sw.js").catch(() => {});
      return;
    }

    navigator.serviceWorker
      .getRegistrations()
      .then((regs) => Promise.all(regs.map((r) => r.unregister())))
      .catch(() => {});
    if (typeof caches !== "undefined") {
      caches.keys().then((keys) => Promise.all(keys.map((k) => caches.delete(k)))).catch(() => {});
    }
  }, []);
  return null;
}
