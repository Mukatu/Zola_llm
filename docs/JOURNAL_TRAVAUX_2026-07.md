# Journal des travaux — juillet 2026

Documentation des travaux réalisés dans la période (28 commits, `534c141..71627ac`).
Regroupés par chantier. Chaque entrée : **quoi**, **pourquoi**, **où** (fichiers /
commits), et **comment tester**. Tous les lots sont passés par les gates (ruff /
black / pytest côté back ; `tsc` / `eslint` côté front) et, quand pertinent,
prouvés « live » (LLM Ollama + embeddings bge-m3).

---

## 1. Accès à la connaissance & corpus du client

Objectif : faire que l'assistant réponde « **la loi + VOS règles** », en cloisonnant
strictement les données de chaque client.

- **Téléversement contextuel** (`d864a65`) — chaque client dépose ses documents
  (règlement intérieur, contrats, chartes…) dans un corpus RAG **cloisonné par
  tenant** (`rag_tenant`, OCR auto). API `POST /v1/kb/upload`, consultation via la
  Bibliothèque (`/v1/kb`). Migration `0034`.
- **Retrieval-union public + privé** (`d1543ba`) — les agents RAG fusionnent le
  corpus de référence (droit public) **et** le corpus du client, triés par
  similarité. Prouvé : « préavis d'un cadre » → le règlement intérieur du client
  passe **devant** les conventions de branche.
- **Traduction de contrats étrangers** (`09286d6`) — capacité du pôle juridique :
  contrat en langue étrangère (texte ou fichier) → traduction FR fidèle (par blocs,
  détection de langue) → **assimilation** optionnelle dans `rag_tenant`.
  `POST /v1/legal/translate`, `TranslationService`.
- **Isolation multi-tenant sur les 3 axes** :
  - **Requête** : le retrieval-union est borné au tenant **dérivé de l'auth**
    (dépendance `current_tenant`) (`fbf541e`).
  - **Écriture** : upload / suppression / traduction assimilée authentifiées, tenant
    serveur (champ retiré du corps) (`fbf541e`).
  - **Lecture** : la Bibliothèque cloisonne `rag_tenant` (`optional_principal` +
    `_tenant_filter`) ; les corpus de référence restent publics (`3e7aee6`).

**Tester** : `Consultation` → onglet « Mes documents » (téléverser) ; Assistant →
question métier (la réponse cite les docs du client si pertinents).

---

## 2. Pilotage / BI v2 — cockpit décisionnel

- **Cockpit v2** (`91d226b`) — l'écran BI passe d'un mur de chiffres à un cockpit :
  - **Signaux déterministes** dérivés des KPIs du client (trésorerie négative, marge
    faible, DSO élevé, encours > trésorerie…) — `agents/bi/signals.py`.
  - **Échéances réglementaires** indicatives (TVA/CNSS/ITS/IS/DAS1), cadence
    calculée, marquées « à confirmer » — `agents/bi/echeances.py`.
  - **Brief IA narré** + Q&A (`/v1/bi/brief`, `/v1/bi/ask`) ; le LLM narre, ne
    recalcule jamais. Cockpit déterministe `GET /v1/bi/cockpit`.

**Tester** : écran **Pilotage / BI** → « Générer le brief IA ».

---

## 3. Communs de connaissance (niveau 3) — le moteur « perpétuellement plus expert »

Comment l'usage réel améliore le **moteur partagé** sans jamais faire remonter de
donnée privée. Cadrage : `docs/COMMONS_PIPELINE.md` (`c5039f4`).
**6 invariants** : rien de brut ne sort ; anonymisation avant la frontière ;
k-anonymat (k=3) ; opt-in révocable ; validation humaine ; traçabilité anonyme.

- **Phase A — consentement + quarantaine** (`55544d3`, UI `316b4d5`) :
  `store_contribution_optin` (désactivé par défaut, par périmètre), extraction des
  candidats depuis le feedback, **anonymisation locale**, dépôt en quarantaine
  (`store_contrib_candidates`, **sans tenant_id**). Migration `0035`.
- **Phase B — k-anonymat + curation** (`79eb71b`, écran `2e0a25e`) : comptage
  d'**origines distinctes** (`origin_hash` salé, jamais le tenant) ; `is_eligible`
  (pending ET ≥ 3) ; validation/rejet **humain** (scope `commons:curate`) ; écran
  `/curation`. Migration `0036`.
- **Phase C — promotion** (`17024c4`) : les candidats validés entrent dans le corpus
  partagé `rag_commons` (app en **lecture seule**, écriture admin) ; journal d'audit
  **anonyme** ; les agents **consultent `rag_commons`** via le retrieval-union.
  `scripts/promote_commons.py`, migration `0037`. Prouvé live.
- **learned_rules — mappings déterministes** (`fc76808`, `8438f45`) : 2ᵉ cible de
  promotion, **générique multi-métier** `(domaine, cle) -> valeur`. Câblé **compta**
  (libellé → compte SYSCOHADA), **achats** (fournisseur → objet), **RH**
  (`rh.classification` : poste → catégorie), **juridique** (`legal.doctype` : type de
  contrat → régime OHADA) (`9837056`). Primitives génériques `POST /v1/commons/correction`
  + `GET /v1/commons/learned`. Migration `0038`.
- **Correctif périmètre** (`8c483c1`) : `scope_allowed` accepte **tout segment** du
  nom d'agent (l'agent RH est `erp.rh` → le périmètre « rh » ne matchait pas).

**Tester** : Compta (« Suggérer comptes » + enregistrer une écriture) ; `Paramètres`
→ « Contribution au moteur commun » (opt-in) ; `/curation` (avec le scope curateur).

---

## 4. Qualité du routage & de l'ancrage (assistant)

Découvert **en test réel** (LLM live) : une question de droit du travail était mal
routée et non ancrée.

- **Routeur v1.2.0** (`8bf99b0`) : frontière `legal`/`erp` resserrée — toute règle /
  droit / obligation du travail → `legal/travail_cg` ; `erp/rh` = exécution interne.
  `RoutingInfo` expose désormais `module`. Prouvé : « préavis licenciement » →
  `legal/travail_cg`, **6 citations**.
- **Réponses sans jargon** (`9e642f3`) : plus de « extraits RAG » dans les réponses
  (« Textes de référence »).
- **Filet structurel** (`20ee212`) : si le routeur ne donne pas de `module`, un
  **agent générique de pôle** (`GenericLegalAgent`/`Erp`/`Health`) interroge tout le
  corpus du pôle (au lieu de l'agent placeholder sans RAG). Prouvé live.

---

## 5. Environnement de développement & exploitation

- **`scripts/dev_up.ps1`** (`f964f2f`) : démarre la stack d'un coup — Docker (app +
  embeddings **bge-m3** montés depuis la copie hôte, RAG hors-ligne), frontend
  pré-authentifié, forge d'un jeton dev. Rappelle les commandes **Ollama** (LLM sur
  le port 11435, modèle `llama3-8b`).
- **Auto-login de dev** (`71627ac`) : **plus besoin de gérer un jeton**.
  `POST /v1/auth/dev-token` (dev only, 404 hors dev) ; le front `api()` **ré-essaie
  sur 401** en récupérant un jeton frais → les jetons expirés se soignent seuls.

**Runbook complet** : cf. mémoire projet / `scripts/dev_up.ps1`. Latence CPU sans
GPU : ~20–50 s par réponse LLM (fonctionnel pour démo).

---

## 6. UX/UI — charte visuelle Polaris

Refonte d'après `Modele_charte_couleur.png` + `polaris_logo_horizontal.png` :
**bleu nuit + vert forêt/menthe, touche orange pour l'action**.

- **Palette & shell** (`03ff5cb`, logo `16b3cb1`) : tokens CSS (primaire = orange
  `#E8763A`, ink bleu nuit, + `navy`/`mint`/`forest`) ; TopBar & Sidebar bleu nuit,
  pastille active orange, signature « Propulsé par Polaris ».
- **Équilibre couleur** (`95c315a`, `885397c`, `0297f5c`) : **orange = action
  seulement** (CTA, nav active, dock, bulles user) ; **vert = identité** (tuiles
  d'icônes `bg-mint/25 text-forest`, titres de section, **onglets actifs** en
  `bg-forest`).
- **Lecteur de documents** (`4341bbb`, `de6335e`) : le `<pre>` brut → typographie de
  lecture (serif justifié + césure, titres de section en vert forêt, articles
  détachés via `structureText`). Deep-link `?schema=&source_uri=` (références
  partageables).
- **Composant `<Prose>`** (`885397c`) + **Markdown** (`0297f5c`) : typographie de
  lecture réutilisable (gras/italique/code/listes à puces vertes/titres) appliquée
  **partout** (Assistant, contrats, traductions, brief BI, Documents…). Code et JSON
  restent en monospace.

**Tester** : rafraîchir `localhost:3000` (auto-login) → Assistant (Markdown),
Consultation (lecteur), onglets verts.

---

## État & suites

- **Isolation multi-tenant** : complète (requête + écriture + lecture).
- **Communs niveau 3** : pipeline complet (A→C), 2 cibles (`rag_commons` sémantique +
  `learned_rules` déterministe), 4 métiers déterministes câblés.
- **Reste optionnel** : schéma physique `contrib_staging` (quarantaine en table core
  aujourd'hui) ; distribution multi-déploiement automatisée ; retrofit des libs front
  à `fetch` direct vers `api()` (auto-heal auth) ; module **Fintech #39**.
