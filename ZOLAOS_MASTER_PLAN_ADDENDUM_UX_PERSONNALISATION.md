# ZolaOS — Addendum : UX / Frontend & Personnalisation par client

**Date** : 2026-06-21
**Statut** : addendum **stratégique** validé. Complète V2.2 + V3 (Polaris) + addendum BI/Commercial/Marketing — ne les remplace pas.
**Décision** : construire **d'abord la couche de personnalisation backend** (ce dépôt) ; **frontend = Web React/Next (PWA offline)**, dans un **dépôt séparé** à venir.

---

## 1. Constat (angle mort)

Tout l'existant est **backend/API** (`/v1`). Le frontend était *anticipé* (`CORS … Web/Flutter`, `:3000`) mais **aucune UI/UX/navigation n'a été conçue**. La **personnalisation par client** n'existe pas (seules les fondations multi-tenant existent : `core.tenants`, `tenant_uuid`, `missions`, profils box/cortex, RBAC tags).

---

## 2. Deux surfaces distinctes

| | **Zolabox (client)** | **Zolacortex (consultant Polaris)** |
|---|---|---|
| Public | Entreprises clientes, **nombreuses et variées** | Consultants du cabinet |
| Personnalisation | **Forte** : modules activés, branding, langue, champs | **Aucune** : interface **uniforme** |
| Orientation | Self-service assisté (poser des questions, générer des docs, consulter le corpus) | Cockpit de **mission** (audits via overlays, génération `.docx`, cross-client via missions) |
| Données | Les siennes (local) | Accès éphémère via missions (Zero Trust) |

**Principe** : la personnalisation est une **configuration déterministe par tenant** (servie par l'API) ; le frontend la **consomme** pour s'afficher. Le consultant a une config **fixe**.

---

## 3. Couche de personnalisation (backend — ce dépôt)

Configuration par tenant (`box`) :
- **Modules activés** (sous-ensemble du catalogue de pôles/modules).
- **Branding** : nom d'affichage, couleur primaire, logo.
- **Langue** (`fr` → `ln`/`kg` en Phase 9).
- **Champs personnalisés** (libellés/métadonnées propres au client).
- **Connecteurs activés**.

Garde-fous :
- `box` = personnalisable ; `cortex` = **config uniforme imposée** (mêmes outils consultant pour tous).
- `modules_actifs` validés contre le **catalogue** (pas de module inconnu).
- RBAC/tenancy existants réutilisés.

Exposé via `GET /v1/config` (le frontend lit la config effective au démarrage).

---

## 4. Frontend (dépôt séparé, à venir) — stack **Web React/Next (PWA)**

- **React/Next** (cohérent avec le CORS `:3000` déjà prévu).
- **PWA offline-first** : impératif contexte CG (coupures électriques, connectivité dégradée — directive §4 du plan).
- Consomme l'API `/v1` (auth JWT/API key existante) + `/v1/config` (personnalisation).
- Deux *builds*/thèmes selon profil : **Zolabox** (personnalisé) et **Zolacortex** (uniforme).
- **Souveraineté** : pas de dépendance SaaS externe ; assets servis localement (Caddy).

> Le frontend visuel n'est pas dans ce dépôt Python ; ce repo fournit l'**API + la config** que le frontend consomme. La **spec d'écrans** détaillée est un livrable dédié (UX-3).

---

## 5. Architecture d'information (esquisse)

**Zolabox (client)** :
- Accueil / tableau de bord (KPIs BI personnalisés aux modules activés)
- Espace par pôle activé (Santé, Droit, ERP, CRM, Marketing…)
- Consultation documentaire (`/v1/kb/*`, cf. data roadmap) — Actes Uniformes, conventions…
- Génération de documents (contrats, devis, contenus)
- Paramètres (branding, langue, champs) — selon droits

**Zolacortex (consultant)** :
- Tableau de missions (créer/révoquer, scope)
- Cockpit d'audit (overlays Polaris) par mission
- Génération de rapports `.docx`
- (uniforme — pas de personnalisation client)

---

## 6. Séquence

1. **(ce dépôt)** Couche personnalisation backend : module + service + `GET /v1/config` + tests. ← **priorité**
2. Spec design frontend détaillée (UX-3, doc).
3. Frontend React/Next PWA (dépôt séparé) — chantier ultérieur.

---

## 7. Hors périmètre (clarté)

- Le **frontend visuel** lui-même (autre stack, autre dépôt).
- Thèmes graphiques détaillés / design system complet → avec le frontend.
- Éditeur d'admin de la personnalisation (UI) → frontend.

---

*Addendum établi le 2026-06-21. Complète V2.2 + V3 + addendum BI/Commercial/Marketing.*
