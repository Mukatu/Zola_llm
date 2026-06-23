# Feuille de route — Frontend (Web React/Next PWA)

**Date** : 2026-06-22
**Stack** : Next.js 14 (App Router) + TypeScript + Tailwind CSS + PWA. Mono-dépôt `frontend/`.
**Référence** : `docs/UX_DESIGN_SPEC.md`, `docs/PRODUCT_STRATEGY.md` (un moteur, deux faces), Zero Trust (deux apps isolées).

## Principes
- **Nav pilotée par `/v1/config`** (modules activés, branding, langue) — rien codé en dur par client.
- **Cadre d'écran de capacité** : un écran générique généré par capacité + quelques **phares** sur mesure.
- **Fluide & moderne** : transitions, skeletons, command palette ⌘K, responsive mobile-first.
- **PWA offline-first** (contexte coupures). **Souverain** : aucune dépendance SaaS externe.
- **Deux surfaces isolées** : Zolabox (client) / Zolacortex (cabinet) — builds séparés, pas d'accès croisé.

## Jalons
- **FE-1 (socle)** : projet Next + design system + ConfigProvider + client API + AppShell (sidebar/top bar pilotés par config) + dashboard + Assistant + cadre d'écran de capacité générique. ← *en cours*
- **FE-2** : écrans phares (Paie, Compta, CRM kanban, Pilotage/BI) + rendu de sortie par schéma.
- **FE-3** : Consultation documentaire (KB), Documents, Paramètres, i18n complet, offline/sync + service worker.
- **FE-4** : Zolacortex (cockpit missions) — surface cabinet, isolée (Zero Trust).

## Hors périmètre (pour l'instant)
- Authentification réelle (brancher sur l'API auth existante en FE-2/3).
- Design system graphique exhaustif (itératif).

## Statut (2026-06-23) — FE-1 → FE-4 ✅
- **FE-1/2** socle + écran de capacité pour toutes les capacités. ✅
- **Écrans riches** (FE↔BE) : Paie, Compta, Supply, Achats, HSE, Facility, CRM (kanban), BI (dashboard), Finance + génératifs Code, Droit, Marketing. ✅
- **FE-3** : PWA offline (service worker) + Paramètres (PUT /v1/config) + transverses (Documents, KB). ✅
- **FE-4** : surface cabinet **Zolacortex** (cockpit missions : liste/création/révocation + cockpit, isolée Zero Trust ; overlays propriétaires non exposés côté public). ✅
- Qualité : job CI frontend (typecheck + lint + build). Reste : Vitest (logique pure), branchement auth, i18n Lingala/Kituba.
