/** @type {import('next').NextConfig} */
const nextConfig = {
  reactStrictMode: true,
  // Répertoire de build isolable : permet de lancer deux serveurs de dev (box +
  // cortex) en parallèle sans qu'ils partagent le même cache .next.
  distDir: process.env.NEXT_DIST_DIR || ".next",
  // Surface ciblée au build : "box" (Zolabox client) | "cortex" (Zolacortex cabinet).
  // Deux apps isolées (Zero Trust) partageant le même codebase.
  env: {
    NEXT_PUBLIC_SURFACE: process.env.NEXT_PUBLIC_SURFACE || "box",
    NEXT_PUBLIC_API_BASE: process.env.NEXT_PUBLIC_API_BASE || "http://localhost:8000",
  },
};

export default nextConfig;
