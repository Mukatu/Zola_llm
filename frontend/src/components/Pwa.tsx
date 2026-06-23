"use client";

import { useEffect } from "react";

/** Enregistre le service worker (PWA offline). */
export function Pwa() {
  useEffect(() => {
    if (typeof navigator !== "undefined" && "serviceWorker" in navigator) {
      navigator.serviceWorker.register("/sw.js").catch(() => {});
    }
  }, []);
  return null;
}
