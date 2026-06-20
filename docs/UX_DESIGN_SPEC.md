# ZolaOS — Spécification de conception UX/UI (UX-3)

**Date** : 2026-06-21
**Portée** : architecture d'information, navigation, inventaire d'écrans, parcours, comportement offline et personnalisation — pour le frontend **Web React/Next (PWA offline)**.
**Référence** : `ZOLAOS_MASTER_PLAN_ADDENDUM_UX_PERSONNALISATION.md`. Le frontend consomme l'API `/v1` + `/v1/config`.
**Statut** : spécification (pas de code frontend). Le frontend sera bâti en mono-dépôt (`frontend/` / `apps/web/`).

> ZolaOS = plateforme IA souveraine **multi-secteurs / multi-métiers** pour entreprises et utilisateurs professionnels. Cette spec couvre les **deux surfaces** : **Zolabox** (client) et **Zolacortex** (consultant Polaris).

---

## 1. Principes de conception

1. **Souveraineté & local-first** : PWA installable, fonctionnant **hors-ligne** (coupures électriques / connectivité dégradée — directive plan §4). Aucune dépendance SaaS externe ; assets servis localement (Caddy).
2. **Personnalisation pilotée par config** : l'UI se construit à partir de `GET /v1/config` (modules activés, branding, langue). Aucun écran codé en dur par client.
3. **Multilingue** : FR d'abord, **Lingala / Kituba** prévus (Phase 9) — i18n dès le départ (clés de traduction, pas de texte en dur).
4. **Mobile-first & faible bande passante** : responsive, images légères, lazy-loading, squelettes de chargement, dégradation gracieuse hors-ligne.
5. **Accessibilité** : contraste AA, navigation clavier, cibles tactiles ≥ 44px, libellés ARIA.
6. **Rôles & RBAC** : l'UI n'affiche que ce que les tags RBAC + la config autorisent ; rien de sensible côté client.
7. **Confiance & traçabilité** : citations visibles (RAG), mentions « projet à valider », horodatage/audit visibles sur les actions sensibles (santé/droit/fiscal).
8. **Deux thèmes, un design system** : Zolabox (personnalisable) et Zolacortex (uniforme cabinet) partagent les composants ; seuls les tokens (couleurs/logo) et la navigation diffèrent.

---

## 2. Deux surfaces

| | **Zolabox** (client) | **Zolacortex** (consultant Polaris) |
|---|---|---|
| Build/thème | personnalisé (config tenant) | uniforme (Polaris) |
| Auth | utilisateurs du client | consultants cabinet |
| Navigation | par **modules activés** | par **missions** |
| Donnée | locale (la sienne) | accès éphémère via mission (Zero Trust) |

---

## 3. Design system (tokens & composants)

- **Tokens** : `couleur_primaire` (de la config), neutres, sémantiques (succès/alerte/erreur/info), typo (système, lisible faible résolution), espacement 4px, rayon, ombres légères.
- **Composants de base** : AppShell (header + nav latérale + zone), Card, DataTable (tri/filtre/pagination), Form fields, Badge de sévérité (critical/high/medium/low), Toast, Modal, Skeleton, EmptyState, OfflineBanner, CitationChip, FileDownload (.docx), Chat/Prompt panel, KpiCard, PipelineBoard (kanban).
- **États obligatoires par écran** : chargement (skeleton), vide, erreur, **hors-ligne**, sans-droit (403).

---

## 4. Zolabox — architecture d'information

Navigation latérale **générée depuis `modules_actifs`** (config). Exemple de regroupement :

```
Accueil (Tableau de bord)
Pôles activés ▾
  ├─ Santé        (si sante.*)
  ├─ Droit        (si droit.*)
  ├─ ERP ▾        (si erp.*)
  │    ├─ RH   ├─ Paie   ├─ Finance   ├─ Comptabilité
  ├─ Commercial / CRM   (si commercial.crm)
  ├─ Marketing          (si marketing.*)
Pilotage (BI)            (si bi.pilotage)
Consultation documentaire
Documents générés
Paramètres (selon droits)
```

### 4.1 Inventaire d'écrans Zolabox

| # | Écran | But | Composants clés | API |
|---|-------|-----|-----------------|-----|
| B1 | **Connexion** | Auth utilisateur client | Form, gestion erreurs | auth (JWT/API key) |
| B2 | **Tableau de bord** | Vue d'ensemble (KPIs des modules activés) | KpiCard, alertes, raccourcis | `/v1/config`, BI |
| B3 | **Assistant (chat)** | Poser une question → réponse + **citations** | Prompt panel, CitationChip, refus si hors-corpus | `/v1/query` (router→agent) |
| B4 | **Santé — Pharmacologie** | Conseil posologie/interactions | Réponse + citations LNME/CIM-10 | agent santé |
| B5 | **Droit — Rédaction** | Générer contrat (CDI/CDD, bail OHADA…) | Formulaire paramètres → doc + warnings sécurisation | agent droit (mode rédaction) |
| B6 | **Droit — Contentieux** | Analyse de risque + jurisprudence | Findings, références (articles + arrêts) | overlay/agent analytique |
| B7 | **ERP — RH** | Docs RH, conformité contrat, tri CV | Génération + conformité | agent RH |
| B8 | **ERP — Paie** | Bulletin (calcul **déterministe**) | Formulaire brut → bulletin ; **verrou barème non validé** | moteur paie |
| B9 | **ERP — Finance** | Trésorerie, anomalies | Tableau anomalies (sévérité) + synthèse | agent finance + connecteurs |
| B10 | **ERP — Comptabilité** | Saisie/validation écritures | Éditeur d'écriture + **rapport de validation déterministe** + interprétation fiscale | moteur compta |
| B11 | **CRM — Pipeline** | Opportunités, scoring, relances | PipelineBoard (kanban), LeadScore, relances | moteur/agent CRM |
| B12 | **CRM — Devis** | Créer devis → facture | Formulaire devis, conversion | CRM + compta |
| B13 | **Marketing** | Segments, campagnes, contenu | Segments, **garde consentement**, génération contenu | agent marketing |
| B14 | **Pilotage (BI)** | KPIs cross-métiers + insights | KpiCard, synthèse narrative, Q&A | agent BI |
| B15 | **Consultation documentaire** | Lire Actes Uniformes/CGI/conventions | Recherche, lecture article, citation | `/v1/kb/*` (planifié) |
| B16 | **Documents générés** | Historique des `.docx`/exports | Liste, téléchargement | reports/stockage |
| B17 | **Paramètres** | Branding, langue, modules, champs (selon droits) | Form config | `GET/PUT /v1/config` |
| B18 | **Connecteurs** | Configurer sources (REST/SQL/CSV/Odoo…) | Form connecteur + test | Connector Framework |

### 4.2 Parcours type (client)
1. Connexion → B2 (dashboard personnalisé aux modules activés).
2. Question dans l'Assistant (B3) → réponse **citée** ; si hors corpus → refus explicite.
3. Génération d'un contrat (B5) → relecture warnings → export `.docx` (B16).
4. Paie (B8) : si barème non validé → bandeau « simulation, non émis » (verrou déterministe respecté à l'UI).

---

## 5. Zolacortex — architecture d'information (uniforme)

```
Tableau de missions
Mission active ▾
  ├─ Contexte client (scope)
  ├─ Audit (overlays Polaris : RH, Fiscal, Santé, Commercial, Pilotage…)
  ├─ Rapport (.docx)
Bibliothèque méthodologique (cabinet)
```

### 5.1 Inventaire d'écrans Zolacortex

| # | Écran | But | API |
|---|-------|-----|-----|
| C1 | **Connexion consultant** | Auth cabinet | auth |
| C2 | **Missions** | Lister/créer/révoquer missions (scope, durée) | `/v1/cortex/missions` |
| C3 | **Cockpit de mission** | Lancer un audit (overlay) sur le client | overlays + `MissionClient` → `/v1/box/rag/search` |
| C4 | **Résultats d'audit** | Findings structurés (sévérité, références) | overlay output |
| C5 | **Rapport** | Générer + relire le `.docx` cabinet | reports |
| C6 | **Bibliothèque méthodo** | Référentiels cabinet (privés) | privé Polaris |

### 5.2 Parcours type (consultant)
1. Créer une mission (C2) → JWT scope éphémère.
2. Cockpit (C3) : choisir un overlay (ex. Audit‑Fiscal‑OHADA) → requêtes RAG **chez le client** (Zero Trust : seuls des chunks anonymisés transitent).
3. Résultats (C4) → génération du rapport `.docx` (C5).
4. Fin de mission → expiration JWT → accès client coupé.

---

## 6. Personnalisation → UI (mapping config)

| Champ `TenantConfig` | Effet UI |
|----------------------|----------|
| `modules_actifs` | construit la **navigation** et les écrans visibles |
| `branding.nom_affichage` / `couleur_primaire` / `logo_uri` | **thème** (tokens) + en-tête |
| `locale` | langue de l'interface (i18n) |
| `champs_personnalises` | libellés/champs additionnels dans les formulaires |
| `connecteurs_actifs` | sources disponibles dans les écrans data |
| `profil=cortex` | bascule sur la surface **uniforme** (ignore la perso client) |

Au démarrage : `GET /v1/config` → hydrate le store frontend → rend la nav + le thème.

---

## 7. Offline / PWA

- **Service worker** : cache de l'app shell + assets (offline-first).
- **Disponible hors-ligne** : navigation, consultation des données déjà chargées, documents générés en cache, brouillons (file d'attente).
- **Nécessite le réseau** : inférence LLM (sauf si Zolabox locale embarque le modèle), recherche RAG fraîche, génération.
- **File de synchronisation** : actions créées hors-ligne (brouillons, formulaires) rejouées à la reconnexion ; **bandeau OfflineBanner** persistant.
- **Conflits** : stratégie « dernier écrivain gagne » + journal local (jamais de perte silencieuse).

---

## 8. Sécurité & conformité à l'UI

- Citations obligatoires affichées (santé/droit) ; mention **« projet à faire valider »** sur les livrables sensibles.
- **Marketing** : l'UI n'expose pas de ciblage sans consentement (la garde est backend ; l'UI le reflète : compteur éligibles/exclus).
- **Paie/Compta** : afficher l'état **« barème/plan non validé → simulation »** quand le verrou déterministe est actif.
- RBAC : masquer (pas seulement désactiver) ce qui est hors droits ; 403 → EmptyState explicite.
- Aucune donnée client ne sort côté Zolacortex (rappel Zero Trust à l'UI mission).

---

## 9. Hors périmètre de cette spec

- Maquettes visuelles haute-fidélité / design system graphique complet (avec le frontend).
- Choix de librairie de composants (Radix/shadcn, MUI…) — au build.
- Le code frontend lui-même (mono-dépôt `frontend/` à venir).

---

*Spécification UX/UI établie le 2026-06-21. Le frontend (Web React/Next PWA) consommera l'API + `/v1/config`.*
