# ZolaOS — Frontend (Web PWA)

Next.js 14 (App Router) + TypeScript + Tailwind. Deux surfaces isolées
(**Zolabox** client / **Zolacortex** cabinet) partageant ce codebase ; la
navigation est **pilotée par `/v1/config`** (personnalisation par tenant).

## Démarrage
```bash
cp .env.example .env.local   # NEXT_PUBLIC_API_BASE → API ZolaOS
npm install
npm run dev                  # http://localhost:3000
```

## Surface
`NEXT_PUBLIC_SURFACE=box` (client, défaut) ou `cortex` (cabinet). Builds séparés
(frontière de confiance Zero Trust — pas d'accès croisé aux données).

## Architecture (socle FE-1)
- `src/lib/config.ts` — config tenant (`/v1/config`) : modules, branding, langue.
- `src/lib/capabilities.ts` — manifeste des capacités → navigation + écrans.
- `src/components/` — AppShell (sidebar/top bar pilotés par config), ConfigProvider,
  CapabilityScreen (écran de capacité générique).
- `src/app/` — dashboard, assistant, `c/[capability]` (écran générique).

Principe : **un écran par capacité, généré** depuis le manifeste ; quelques
**phares** (Paie, Compta, CRM, Pilotage) auront une UX dédiée (FE-2). PWA offline
et i18n (FR→Lingala/Kituba) en FE-3.

Cf. `../docs/UX_DESIGN_SPEC.md`, `../docs/FRONTEND_ROADMAP.md`.
