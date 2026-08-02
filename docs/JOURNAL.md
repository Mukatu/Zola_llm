# Journal des travaux — ZolaOS

Trace chronologique de ce qui est construit, en cours, et les décisions prises.
Le « quoi/pourquoi » synthétique ; le détail vit dans les `docs/*_ROADMAP.md` et
les messages de commit.

---

## 2026-08-02 — Doc : runbook de déploiement production (cabinet + client)

`docs/DEPLOIEMENT_PRODUCTION.md` (630 l., schéma mermaid) — tutoriel pas-à-pas
ordonné, ancré sur le tooling réel `deploy/` : Étape A Cortex (Polaris) → Étape B
provisionnement client (credential + cert mTLS `issue_box_cert.sh`) → Étape C Zolabox
(sur site, tunnel sortant) + option VM/appliance, vérification bout en bout, exploitation
(backup/update/supervision/révocation), sécurité, checklists go-live.

**4 écarts réels détectés `deploy/` ↔ modèle mTLS** (documentés, à corriger avant pilote) :
1. Cert client mTLS **non câblé côté box** : `TUNNEL_CLIENT_CERT_PATH/KEY` absents de
   `deploy/zolabox/.env.zolabox.example` + aucun volume `.crt/.key` dans le compose box.
2. `TUNNEL_CORTEX_URL` par défaut → `cortex.polaris.cg` (cockpit) au lieu du domaine
   **tunnel** (`CORTEX_TUNNEL_DOMAIN`, porteur du `client_auth` mTLS dans le Caddyfile).
3. `GF_ADMIN_PASSWORD` absent des `.env.*.example` → repli silencieux sur `admin`.
4. Variables d'entitlement (`ENTITLEMENT_*`) non référencées dans le `.env`/`install.sh` box.

## 2026-08-02 — Sécurité : auth exigée sur les lectures GED + garde de login

Deux correctifs suite au constat « on accède à l'app sans se connecter, même en
navigation privée » :

- **Backend (fuite d'autorisation)** : `GET /v1/cortex/ged/{templates,deliverables}`
  et leurs variantes `/{id}` répondaient **200 sans authentification** — seul le profil
  `cortex` était vérifié (dépendance de router), pas l'appelant. Ajout de
  `Depends(authenticate)` sur les 4 lectures. Audit des autres GET cortex : aucune autre
  fuite. Test de régression `tests/test_cortex_ged_authz.py` (401 sans jeton, paramétré).
- **Frontend (garde manquante)** : le shell + l'accueil s'affichaient pour un visiteur
  non authentifié (l'accueil ne fait aucun appel protégé, donc aucune redirection).
  Garde ajoutée dans `ConfigProvider` : une fois la session vérifiée (`me()`), si ni
  cookie ni jeton, on tente l'auto-login dev puis, à défaut, on renvoie vers `/login`
  (compatible mode `-Dev` : le jeton dev court-circuite la redirection).
- Vérifié : lectures GED → 401 sans auth / 200 avec cookies ; `test_cortex_ged` 6/6 ;
  front lint + tsc + 79 vitest verts.

## 2026-08-01 — Documentation : guide utilisateur + doc technique IT

Deux livrables de documentation, couvrant les deux faces (Zolabox + Zolacortex) :

- **`docs/GUIDE_UTILISATEUR.md`** (365 l.) — tutoriel pour les équipes/utilisateurs :
  premiers pas, assistant & modules box, conduite d'une mission de A à Z côté cortex
  (fil rouge), les 7 assistants IA (à quoi ça sert / pas-à-pas / ce que l'IA fait et ne
  fait pas), bonnes pratiques, FAQ, glossaire. Ancré sur le vrai code frontend (Sidebar,
  capabilities, pages cortex). NB : le « mémo réglementaire » s'affiche « Note de
  recherche (IA) » à l'écran — les deux formulations sont données.
- **`docs/DOC_TECHNIQUE_IT.md`** (479 l., 4 schémas mermaid) — doc IT : architecture,
  composants & ports (front 3000 / box 8000 / cortex **8010** / pg 5432 / redis 6379 /
  minio 9000-9001 / LLM 11435), profils & routage, démarrage dev (`dev_up.ps1`),
  configuration (variables), auth/sécurité (login/refresh/CSRF, RBAC, garde-fou
  `api()` 401→me()), données & migrations, RAG, LLM souverain, surfaces IA (`run_draft`),
  exploitation, **déploiement hybride** (bundles réels `deploy/zolabox` & `deploy/zolacortex`,
  mTLS, entitlement RS256), licences. Vérifié contre le code (settings, main, factory…).

## 2026-07-31 — IA : synthèse d'entretien (notes brutes → compte rendu savable)

7ᵉ surface IA, un **3ᵉ mode** au-delà du RAG et de l'extraction : la **structuration
fidèle** de notes fournies. Le consultant colle ses notes d'entretien/réunion ; l'IA
en fait un **compte rendu** professionnel (contexte / points clés / décisions /
prochaines étapes), **enregistré comme livrable** — qui entre dans le circuit GED.

- **Module** `zolaos/ged/synthesis.py` (hors-RAG) : `run_synthesis()` (LLM local) met au
  propre les notes ; garde-fou propre à la reformulation — structure UNIQUEMENT ce qui
  figure dans les notes, n'invente aucune décision/action/date/participant (« — non
  précisé » sinon). `kind` borné (entretien/reunion/atelier/appel) → cadrage du prompt.
- **Endpoint** `POST /v1/cortex/ged/deliverables/synthesis {mission_id, notes, kind?, title?}`
  → `status` (generated → livrable créé / unavailable → rien). 404 mission inconnue.
- **Front** : section « Synthèse d'entretien (IA) » sur `/cortex/livrables` (notes + type +
  titre) → le compte rendu apparaît dans la liste des livrables de la mission.
- **Validé** en conteneur : notes brutes « RDV Ngoma (DAF Congo Agro), audit OHADA,
  comptable parti, lettre de mission avant vendredi… » → CR fidèle, « Décisions : —
  non précisé », aucun montant inventé, « budget pas encore abordé » repris tel quel.

## 2026-07-31 — IA : alertes marge & sous-facturation (moteur détecte, IA narre)

6ᵉ surface IA, l'illustration la plus pure de la doctrine « le moteur calcule, le LLM
narre » : le **moteur détecte** (déterministe) les missions à risque économique ; l'IA
ne fait que **reformuler/prioriser** en une note de pilotage, sans jamais inventer de
chiffre (elle ne cite que ceux calculés).

- **Module** `zolaos/psa/alerts.py` (déterministe) : `scan_alerts()` émet des alertes
  typées — `marge_negative` (coût > honoraires, high), `marge_faible` (marge % < seuil
  sur mission non naissante, medium), `sous_facturation` (encours approuvé **non facturé**
  ≥ seuil ; high si ≥ 2×). Tri sévérité puis impact. Seuils **gouvernables** :
  `PSA_MARGIN_LOW_PCT` (20), `PSA_WIP_ALERT_XAF` (500 000), `PSA_MIN_HONORAIRES_XAF`
  (100 000). `narrate_alerts()` = note de pilotage (LLM local, contraint aux chiffres).
- **Endpoints** : `GET /v1/cortex/psa/alerts` (admin, déterministe) → alertes + seuils ;
  `POST /v1/cortex/psa/alerts/brief` (admin, CSRF) → `status` (generated/empty/unavailable)
  + `brief`. Encours non facturé = temps `approved`+`billable`+`invoice_id IS NULL`.
- **Front** : page `/cortex/alertes` (tableau trié + seuils actifs + bouton « Note de
  pilotage (IA) »), entrée Sidebar « Alertes marge ».
- **Validé** en conteneur : 4 missions → 3 alertes (petite mission < plancher supprimée,
  WIP 300k < seuil ignoré, marge 13% signalée) ; note IA n'emploie que 1 400 000/-150 000,
  priorise les « high », propose des actions concrètes. Aucun chiffre inventé.

## 2026-07-31 — IA : saisie de temps assistée (récit → lignes proposées)

5ᵉ surface IA, une **capacité nouvelle** (extraction structurée, hors-RAG) : le
consultant décrit sa semaine en langage libre ; l'IA en **extrait** des lignes de
temps (date, durée, activité, mission). Ce sont des **propositions** — rien n'est créé,
le consultant relit/corrige/valide chaque ligne (« je propose, l'humain valide »).
L'IA structure le récit ; les taux/montants restent **déterministes** (figés à la
création réelle selon le grade) — elle ne touche jamais à l'économie.

- **Module** `zolaos/psa/time_assist.py` (hors-RAG) : `suggest_time_entries()` appelle
  le modèle léger local en `json_mode` ; `_parse_entries` **borne/valide** chaque champ
  (durée > 0 et ≤ 24 h, date ISO sinon null, `mission_id` retenu SEULEMENT s'il figure
  dans les missions du consultant → anti-hallucination), cap 30 lignes. Ne lève jamais.
- **Endpoint** `POST /v1/cortex/psa/time-entries/assist {narrative, week_start?}` → `status`
  (suggested/unavailable) + suggestions {entry_date, minutes, hours, activity, billable,
  mission_id, mission_label}. **Ne crée rien.** Résout les missions du consultant courant.
- **Front** : section « Saisie assistée (IA) » sur `/cortex/temps` → tableau éditable de
  propositions ; « Ajouter » crée la ligne via l'endpoint existant, « Ignorer » l'écarte.
- **Validé** en conteneur : récit « Lundi 3h audit ACME, mardi 2h cadrage fiscal… » →
  4 lignes, missions correctement mappées (ACME↔audit, Brasseries↔fiscal), durées exactes
  (3h/2h/1h30/4h). Dates approximatives (limite 8B) → corrigées par le consultant.

## 2026-07-31 — IA : mémo réglementaire savable (recherche → production)

4ᵉ surface IA, le **pont recherche → production** : un consultant pose une **question
réglementaire** sur sa mission ; l'IA rend une **note ancrée et citée**, **enregistrée
comme livrable** (statut draft) — qui entre alors dans le circuit GED (édition, relecture,
statut). Distincte des surfaces de rédaction (pilotée par une question, pas un modèle).

- **Endpoint** `POST /v1/cortex/ged/deliverables/memo {mission_id, question, pole?, title?}`
  (cortex, CSRF) → `status` (generated/abstained/unavailable) + `deliverable` (créé si
  `generated`, sinon `null`) + citations. 404 si mission inconnue. Corpus insuffisant →
  `abstained`, **aucun livrable créé** (rien inventé).
- Réutilise `run_draft` avec un `MEMO_SYSTEM_PROMPT` dédié (## Réponse / ## Fondement /
  ## À vérifier / limites) + `build_memo_query` (la question devient la requête de retrieve
  ET le message). Titre par défaut dérivé de la question (`_memo_title`).
- **Front** : section « Note de recherche (IA) » sur `/cortex/livrables` → la note générée
  apparaît dans la liste des livrables de la mission (rafraîchie).
- **Valeur prouvée** en conteneur : « obligations de préavis d'un cadre en CDI ? » →
  note `generated`, 8 citations (« préavis 3 mois [2] », convention collective [5]) —
  question ad hoc transformée en artefact de mission durable et cité.
- 4 surfaces IA désormais branchées, toutes via `run_draft` : rédaction de livrable,
  rédaction de proposition, relecture qualité, **mémo réglementaire savable**.

## 2026-07-31 — IA de relecture qualité des livrables (contrôle d'ancrage)

3ᵉ surface IA, **distincte** de la rédaction : au lieu de produire, l'IA **confronte**
un projet de livrable aux textes de référence et rend une revue — sans réécrire.

- **Endpoint** `POST /v1/cortex/ged/deliverables/{id}/review {pole?}` (cortex, lecture
  seule) → `status` (generated/abstained/unavailable) + `review` markdown structuré
  (## Bien étayé [n] / ## À vérifier — non étayé / ## Points manquants) + citations.
  422 si livrable vide. Ne modifie jamais le livrable (version inchangée).
- Réutilise `run_draft` avec un `REVIEW_SYSTEM_PROMPT` dédié + `build_review_query`
  (le contenu du projet est injecté dans la requête, tronqué à ~4000 c pour le contexte).
- **Front** : bouton « Relire (IA) » dans l'éditeur → panneau de revue (lecture seule).
- **Valeur prouvée** en conteneur : un projet affirmant « congés 30 jours » → la revue
  relève que les textes disent « 26 jours ouvrables » [1][2] (détection d'affirmation
  non conforme aux sources). C'est le garde-fou anti-invention côté contrôle.

## 2026-07-31 — IA sur les propositions commerciales (patron réutilisé)

Le patron de rédaction ancrée (livrables) **généralisé** à l'amont : rédiger une
**proposition commerciale** (lettre de mission) pour une opportunité, ancrée corpus,
citée, **sans chiffrer d'honoraires** (le prix reste décision cabinet).

- **Factorisation** : `ged/drafting.run_draft(settings, *, schema, tags, query, system_prompt?)`
  → `DraftOutcome{status, content, citations}` (retrieve + abstention + génération, ne
  lève jamais). `DeliverableDraftAgent` accepte un `system_prompt` (prompt livrable OU
  proposition). `cortex_ged` refactoré pour l'utiliser (DRY).
- **Proposition** : `opportunities.proposal` (markdown ; migration `0070`) + endpoint
  `POST /v1/cortex/pipeline/{id}/proposal/draft {pole?, apply?}` (statut generated/
  abstained/unavailable ; écrit dans l'opportunité si `apply=true`). Prompt dédié
  (`PROPOSAL_SYSTEM_PROMPT`) : structure lettre de mission, **interdit tout montant**.
  `proposal` éditable via `PATCH /v1/cortex/pipeline/{id}`.
- **Front** : zone « Proposition commerciale » sur l'opportunité (textarea + bouton
  « Rédiger la proposition (IA) »).
- Validé en conteneur : « Objet : Proposition commerciale pour un audit de conformité
  sociale — ACME SARL… », ancrée sur 8 extraits, sans prix.

## 2026-07-31 — GED : modèles de livrables & documents produits

Le dernier classique : bibliothèque de **modèles de livrables** (squelettes) + les
**documents** produits par mission (versionnés, à statut). Complète la face production.

- **Modèles** `core.deliverable_templates` (nom, offre, sections `[{title, guidance}]`,
  actif). **Livrables** `core.deliverables` (mission, template optionnel, contenu markdown,
  statut draft→review→final, **version** incrémentée à chaque modif). Migration `0069`.
- **Endpoints** `/v1/cortex/ged` (cortex) : `/templates` (CRUD, mutations **admin**) ;
  `/deliverables` (produits par tout consultant) — création **semée** du squelette du
  modèle (`ged/skeleton.py`, markdown déterministe), liste (sans contenu) / détail (avec),
  édition (version++ au changement de contenu) + transitions de statut. Mutations CSRF.
- **Front** : écran `/cortex/livrables` (bibliothèque de modèles + éditeur de livrables
  par mission) + `lib/cortex-ged.ts` + entrée Sidebar « Livrables ».
- Orienté par 2 sous-agents.

### Rédaction assistée par IA (le « + », branché)

Le contenu d'un livrable peut être **rédigé par l'IA, ancré sur le corpus** — dans le
respect de la doctrine (le LLM narre et **cite**, **abstention** si le corpus ne couvre
pas, **jamais** d'invention de valeurs). Servi **localement**.

- **Agent** `ged/drafting.py` (`DeliverableDraftAgent`) : réutilise le `RAGAgent` public
  (retrieve + garde-fous + citations) avec un prompt de rédaction inline ;
  `requires_citation=True` → l'abstention tombe AVANT toute génération. Pôle → corpus
  (`POLE_SCHEMAS`, heuristique `pole_from_offre`).
- **Endpoint** `POST /v1/cortex/ged/deliverables/{id}/draft` `{pole?, apply?}` → `status`
  ∈ `generated` (projet + citations) / `abstained` (corpus insuffisant → rien) /
  `unavailable` (retrieval/LLM indispo, jamais de 500). Écrit dans le livrable (version++)
  seulement si `apply=true` — **relecture humaine par défaut** (« je cite, je ne tranche pas »).
- **Front** : bouton « Générer un projet (IA) » dans l'éditeur de livrable.
- Validé en conteneur : 8 extraits `rag_legal` → projet rédigé et cité par le LLM local.

## 2026-07-31 — Staffing / plan de charge (prospectif)

La pièce **prévisionnelle** qui manquait : planifier qui travaille sur quoi, quand,
pour quelle capacité. Le pendant *forward* du taux d'occupation (rétrospectif).

- **Modèle** `core.assignments` (affectation consultant × mission × **semaine** = lundi,
  capacité allouée ; unique par trio, upsert à la re-planification). Migration `0068`.
- **Endpoints** `/v1/cortex/staffing` (cortex+admin, mutations CSRF) : upsert affectation
  (semaine normalisée au lundi) ; liste ; suppression ; `GET /load` = **plan de charge**
  (grille consultant × semaine : alloué vs **capacité** hebdo, taux de charge, dispo,
  **sur-affectation**, moyenne).
- **Moteur** `staffing/capacity.py` : lundi de la semaine, capacité (5 j × heures/jour),
  ligne de charge déterministe (alloué/capacité, sur-affectation).
- **Front** : écran `/cortex/staffing` (formulaire d'affectation + **grille de charge**
  colorée par taux) + `lib/cortex-staffing.ts` + entrée Sidebar « Plan de charge ».
- Orienté par 2 sous-agents (tests + front).

## 2026-07-31 — Notes de frais (avec les feuilles de temps)

L'autre engagement du consultant sur une mission : le frais. Miroir des feuilles de
temps, **intégré à la facturation** (débours refacturés) et à la rentabilité (coût).

- **Modèle** `core.expenses` (consultant × mission × jour × montant, catégorie, statut
  draft→submitted→approved/rejected, `invoice_id` de rattachement). Migration `0067`.
- **Endpoints** `/v1/cortex/expenses` (cortex) : saisie/liste/submit (consultant) ;
  approve/reject + synthèse par mission (admin). Catégories fermées
  (transport/hébergement/repas/fournitures/honoraires_tiers/autre).
- **Intégration facturation** : `POST /v1/cortex/invoices` regroupe désormais les temps
  facturables approuvés **ET** les frais facturables approuvés (débours). `amount` =
  honoraires + débours ; le détail liste `entries` **et** `expenses` ; l'annulation
  libère les deux. Les frais non facturables restent un coût, jamais refacturés.
- **Moteur** `psa/expenses.py` (catégories + synthèse : total/facturable/refacturable approuvé).
- **Front** : écran `/cortex/frais` (miroir de `/cortex/temps`) + `lib/cortex-expenses.ts`
  + entrée Sidebar « Notes de frais ». Orienté par 2 sous-agents.

## 2026-07-30 — Pilotage : tableau de bord KPI cabinet (capstone)

Le **capstone** de la chaîne cabinet : une synthèse **transverse en lecture** sur tous
les sous-systèmes. Ne crée rien (pas de modèle/migration) ; agrège sur un mois en
réutilisant les moteurs déterministes déjà éprouvés (`crm`, `psa`).

- **Endpoint** `GET /v1/cortex/dashboard?period=YYYY-MM` (cortex+admin, lecture seule) :
  - **Commercial** : pipeline ouvert (nombre/montant), **prévision pondérée**, taux de conversion.
  - **Production** : missions actives, consultants actifs, heures travaillées/facturables,
    **taux d'occupation**.
  - **Finance** : honoraires du mois, coût, **marge** (+%), **WIP** (approuvé non facturé),
    facturé, encaissé, **créances en cours**.
  Métriques bornées au mois (temps/factures par date) vs snapshots globaux (missions
  actives, WIP, créances, pipeline).
- **Front** : écran `/cortex/pilotage` (3 blocs KPI commercial/production/finance,
  sélecteur de mois) + `lib/cortex-dashboard.ts` + entrée Sidebar « Pilotage ».
- Orienté par 2 sous-agents (test + front).

## 2026-07-30 — CRM : pipeline commercial (amont du cabinet)

L'amont de la chaîne : prospect → opportunité → proposition → **gagné → mission**.
Complète le front, et **referme la boucle** avec la production (temps) et la
facturation (honoraires).

- **Modèle** `core.opportunities` (client tenant OU prospect libre `client_name`, offre,
  montant estimé, étape lead→qualified→proposal→won|lost, probabilité, `mission_id` à la
  conversion). Migration `0066`.
- **Endpoints** `/v1/cortex/pipeline` (cortex) : créer/lister/faire avancer une
  opportunité (propriétaire ou admin ; changer d'étape applique la probabilité par
  défaut) ; `GET /summary` = **pipeline pondéré** (montant × probabilité, par étape +
  prévision + taux de conversion) ; `POST /{id}/convert` = convertit une opportunité
  **gagnée** en `Mission` (le pont CRM → production), **audité** (`opportunity.converted`).
- **Moteur** `crm/pipeline.py` : probabilités par étape + synthèse pondérée déterministe.
- **Front** : écran `/cortex/pipeline` (synthèse + création + pipeline par étape +
  conversion) + `lib/cortex-pipeline.ts` + entrée Sidebar « Pipeline ».
- Orienté par 2 sous-agents (tests + front).

## 2026-07-30 — PSA : facturation d'honoraires (aval du temps)

L'aval direct du PSA : le cabinet **facture son client** à partir des temps
**approuvés**. Distincte de la facturation d'**usage** plateforme (`billing/`,
éditeur→client) — ici c'est **cabinet → son client**, en honoraires.

- **Modèle** `core.invoices` (mission, client, numéro `FACT-YYYY-NNNN`, statut
  draft→issued→paid/cancelled, montant figé) + `time_entries.invoice_id` (rattachement).
  Migration `0065`.
- **Endpoints** `/v1/cortex/invoices` (cortex+admin, mutations CSRF) : création depuis
  les feuilles de temps **facturables approuvées non facturées** d'une mission (les
  regroupe, fige le total, les rattache) ; `issue` (échéance), `pay`, `cancel` (libère
  les saisies) ; `GET /aging` = **échéancier** ventilé par ancienneté (base des
  relances) ; détail avec saisies rattachées. Émission/encaissement/annulation
  **audités** (`audit.log`, verbes `invoice.issued/paid/cancelled`).
- **Helpers** `psa/invoicing.py` : numérotation séquentielle + tranches d'âge de créance.
- **Front** : écran `/cortex/honoraires` (échéancier + création + liste + cycle) +
  `lib/cortex-invoices.ts` + entrée Sidebar « Honoraires ».
- Orienté par 2 sous-agents (tests + front).

## 2026-07-30 — PSA : socle de l'outillage cabinet (feuilles de temps)

Nouvelle brique : l'**outillage métier interne du cabinet** (ce que tout cabinet de
conseil/audit/expertise utilise), distinct des modules client. On pose le **backbone
PSA** (Professional Services Automation) : feuilles de temps → économie de mission →
taux d'occupation. S'ancre sur les missions/consultants existants.

- **Modèle** `core.time_entries` (consultant × mission × jour × durée, statut
  draft→submitted→approved/rejected, **taux figés à la saisie**) + `users.grade`
  (rattachement au barème). Migration `0064`.
- **Moteur déterministe** (`zolaos/psa/`) : barème d'honoraires par grade (`rates.py`,
  config `PSA_RATE_CARD_JSON`, **prix jamais inventés** — défauts à zéro) ; économie de
  mission (`economics.py` : honoraires/coût/**marge**/WIP, `rejected` exclus) ; taux
  d'occupation (facturable/capacité). Tout en entiers (XAF sans sous-unité).
- **Endpoints** `/v1/cortex/psa/*` (profil cortex) : saisie/liste/submit des feuilles de
  temps (consultant) ; approve/reject + économie de mission + taux d'occupation + barème
  (admin). Le taux est résolu du grade du consultant et **snapshoté** à la saisie.
- **Front** : écran `/cortex/temps` (ma feuille de temps + vue cabinet économie/occupation)
  + `lib/cortex-psa.ts` + entrée Sidebar « Feuilles de temps ».
- **Doctrine** : le moteur calcule (honoraires, marge, occupation), le LLM narrera ;
  barème = décision du cabinet (config). Orienté par 2 sous-agents (tests + front).

## 2026-07-30 — Durcissement config box (synchro entitlement + RBAC)

Deux suivis résiduels de l'entitlement, réglés (`api/v1/config.py`) :

- **Synchro affichage** : `GET /v1/config` (profil box) filtre désormais `modules_actifs`
  par l'entitlement réel (`resolve_box_modules`) — l'UI n'affiche jamais un module que le
  serveur n'expose pas. Mapping code fin `pole.module` → module vendable dans
  `personalization.CODE_TO_ENTITLEMENT` (santé/droit non soumis = toujours gardés) ;
  enforcement off → aucun filtrage.
- **RBAC sur `PUT /v1/config`** : garde `require_config_editor` (rôle admin/consultant ;
  401 anonyme, 403 client). L'édition de la personnalisation n'est plus ouverte. Override
  de test par défaut dans conftest (admin), + tests dédiés du rejet client/anonyme.

## 2026-07-30 — Usage & facturation par tenant

Base de facturation cabinet. Le metering existant (`core/metering.py`) est **Redis,
éphémère (TTL 40 j), par user_id** → inadapté à la facturation. On ajoute donc du
**durable, par tenant**, sans toucher au chemin chaud du quota.

- **Grand livre durable** `core.usage_daily` (tenant_id, day, requests, tokens ;
  migration `0063`) : upsert `INSERT … ON CONFLICT` (`billing/ledger.py`). Alimenté
  **au mieux** par `require_quota` — hook **opt-in** (`BILLING_LEDGER_ENABLED`, défaut
  False), **session propre**, **fail-open** (signature de la dépendance inchangée, chemin
  metering existant intact).
- **Moteur de tarification** (`billing/pricing.py`) : **mécanisme, pas de prix inventés**.
  Barème par tier (forfait `monthly_base` + `included_requests`, dépassement par tranche
  de 1000) via `BILLING_PRICING_JSON` (défaut = zéros → coût 0). Devise défaut XAF (CEMAC).
- **Vue cortex** `GET /v1/cortex/billing?period=YYYY-MM` (cortex+admin, lecture seule) :
  agrège l'usage du mois par tenant, résout nom+tier (`core.tenants` + licence récente),
  applique le barème, trie par coût ; `GET .../pricing` = barème courant.
- **Front** : écran `/cortex/facturation` (sélecteur de mois, résumé, tableau par tenant +
  détail du coût) + `lib/cortex-billing.ts` + entrée Sidebar « Facturation ».
- **Portée** : couvre l'usage enregistré contre la base de ce déploiement ; la collecte
  inter-box (box → cortex par tunnel) est désormais implémentée (ci-dessous).

### Collecte d'usage inter-box par le tunnel

La box **remonte** son usage local au Cortex par le tunnel (comme le refresh de licence,
sens inverse), pour la facturation des déploiements hybrides.

- **Box** (`tunnel/agent.py`, `_usage_report_loop`, opt-in `USAGE_REPORT_SECONDS`, 0=off) :
  `billing/collector.collect_local_usage` agrège `core.usage_daily` local (totaux du jour +
  veille) et pousse des trames `usage_report` (fire-and-forget). Erreur DB → on saute le
  tour ; WS cassé → la reconnexion relance.
- **Cortex** (`tunnel/channel.py` + `billing/collector.ingest_reported_usage`) : `serve`
  reconnaît `usage_report` et persiste **sous l'identité AUTHENTIFIÉE de la box**
  (`self._tenant_id`, jamais le tenant du payload) via `set_usage_durable` (**écrase** les
  totaux du jour = idempotent, pas de double-comptage sur ré-rapport).
- La vue `/cortex/billing` agrège alors l'usage réel des boxes clientes.
- Tests `tests/test_usage_collection.py` (SET vs ADD, collecte, ingestion + jour invalide,
  canal, boucle désactivée).

## 2026-07-29 — Journal d'audit du cabinet

Trace horodatée des actions **sensibles** de l'exploitant cortex. **Zéro
réinvention** : au lieu d'une table parallèle, on écrit dans le journal **canonique
`audit.log`** (schéma `audit`, chaîne de hachage `payload_hash`/`prev_hash`/`row_hash`
+ triggers d'immuabilité, cf. `infra/postgres/02_audit_log.sql`) — déjà utilisé pour
les accès RAG et les missions.

- **Enregistreur** (`zolaos/audit/recorder.py`, `record_audit`) : insert dans
  `audit.log` (catégorie `security`, event=verbe, actor=principal, tenant=cible si
  tenant, payload=summary+détail) dans la **même transaction** que l'action.
- **Instrumentation** des endpoints cortex sensibles : licences (émission/révocation),
  comptes (création/màj/reset mdp — jamais le mot de passe), credential de box
  (émission/révocation), création de client. Les missions écrivaient déjà nativement.
- **Consultation** (`GET /v1/cortex/audit`, cortex+admin, lecture seule) : lit
  `audit.log`, catégories **gouvernance** par défaut (security/config/auth, écarte le
  bruit RAG), filtres event/acteur/tenant + `category=all`. `GET .../actions` = catalogue.
- **Accès lecture** : `zolaos_app` n'avait qu'INSERT sur `audit.log` ; migration `0062`
  = `GRANT SELECT` (l'immuabilité reste garantie par les triggers, pas par le refus de
  lecture — lire n'altère rien).
- **Front** : écran `/cortex/audit` (filtres + liste anté-chrono, résumé + détail
  repliable) + `lib/cortex-audit.ts` + entrée Sidebar « Journal d'audit ».

## 2026-07-29 — Cockpit de supervision (fleet)

La page « exploitation » qui manquait à cortex : vue d'ensemble des boxes clientes.
Agrège ce qui était éparpillé — connexion du **tunnel** (`REGISTRY`), **licence** +
expiration (`license_grants`), provisioning de box, **missions** actives.

- **Backend** (`api/v1/cortex_fleet.py`, `GET /v1/cortex/fleet`, cortex+admin, lecture
  seule) : par tenant client → statut licence dérivé (active/expired/revoked/none) +
  `days_left`, `box_connected` (`str(id) in REGISTRY`), `box_provisioned`, missions
  actives ; **résumé** (clients, en ligne, actives, expirant bientôt, expirées/révoquées,
  sans licence). Requêtes bornées : DISTINCT ON pour la licence la plus récente, count
  groupé pour les missions (pas de N+1). Param `expiring_days` (défaut 30).
- **Front** : écran `/cortex/supervision` (bandeau de résumé + tableau des boxes,
  badges de statut, alerte « expire bientôt ») + `lib/cortex-fleet.ts` + entrée Sidebar
  « Supervision » (admin).

## 2026-07-29 — Cockpit cortex de gestion des entitlements

Pendant **cabinet** de l'entitlement vérifié côté box : Polaris **émet, liste,
révoque et (re)livre** les licences de modules par tenant, depuis un cockpit monté
**profil cortex uniquement**, rôle **admin**. Détail : `docs/LICENSING.md`.

- **API** (`api/v1/cortex_entitlements.py`, `/v1/cortex/entitlements`) : `GET /catalogue`
  (tiers+modules pour le formulaire), `GET ""` (liste + statut dérivé), `POST ""`
  (émet = signe RS256 + persiste), `GET /{id}` (détail + jeton), `GET /tenant/{id}/active`
  (jeton vivant = socle du refresh tunnel), `POST /{id}/revoke`.
- **Persistance** (`core.license_grants`, migration `0061`) : métadonnées + jeton signé,
  **côté cortex uniquement** (la box ne voit jamais cette table). Statut **dérivé**
  (revoked > expired > active), jamais dénormalisé. **Renouvellement remplace** : émettre
  révoque les licences actives antérieures du tenant → une seule vivante.
- **Clé privée d'émission** (`ENTITLEMENT_PRIVATE_KEY`, cortex only, jamais sur une box) :
  le cockpit est le seul détenteur ; absente → `503` (pas d'émission non signée).
- **Sécurité** : profil cortex + scope `admin:users` + CSRF sur mutations ; validation
  stricte (tier/catalogue, modules ∈ MODULES, tenant type client).
- **Tests** : `tests/test_cortex_entitlements.py` — émission **vérifiable par la clé
  publique** (chaîne de confiance de bout en bout : cortex signe → box vérifie),
  renouvellement, rejets 422/503, garde admin+CSRF, révocation + livraison, 404 en box.
- **Front** (`frontend/`) : section **Licence de modules** sur la fiche client
  (`/cortex/clients/[id]`, à côté du provisioning Zolabox — la licence est par client).
  Client typé `lib/cortex-entitlements.ts` + composant `EntitlementCard` : statut/badge,
  formulaire tier (select) + modules (cases, celles du tier verrouillées) + jours,
  aperçu des modules effectifs, émission → jeton copiable, livraison du jeton vivant,
  révocation, historique. `tsc`/lint/build/vitest verts (test 404→null du client).
- **Refresh par tunnel** : la box **tire** sa licence sur son WebSocket **sortant**
  (plus de dépôt manuel). Côté cortex, `channel.serve` traite un `license_pull` →
  résout `active_license_for_tenant` (`licensing/delivery.py`) → renvoie `(statut, jeton)`.
  Côté box, `agent._refresh_loop` (initial + périodique, `ENTITLEMENT_REFRESH_SECONDS`,
  0=off) reçoit la trame `license` et `_apply_license` **écrit** le jeton (atomique) sur
  `active`, **retire** le fichier sur `revoked`/`expired` (→ fail-closed), no-op sur `none`.
  Tests `tests/test_tunnel_license.py` (14). Suite **754 passed**.
- **Application à chaud** — *révocation immédiate sans redémarrage* : au montage figé
  s'ajoute un état vivant (`licensing/state.py`, `EntitlementState` sur `app.state`) +
  une **garde runtime** (`api/entitlement_gate.py`, `require_module`) posée sur chaque
  module monté → **404** dès qu'un module quitte le jeu courant. L'agent tunnel (même
  process) appelle `refresh()` après une trame `license` → effet immédiat. Endpoint
  `GET`/`POST /v1/box/entitlement[/refresh]` (statut + forçage ops). Sens sûr :
  **réduction/révocation = immédiat** ; **extension** (module neuf) = au redémarrage.
  Tests `tests/test_entitlement_hot.py` (7). Suite **761 passed**.
- **Suivis** : synchro `GET /v1/config` sur l'entitlement ; RBAC sur `PUT /v1/config`.

## 2026-07-29 — Licence commerciale & distribution des modules (entitlement)

Correction d'un défaut **critique** (signalé « lamentable ») : `modules_actifs` était
(1) **cosmétique** (endpoints ouverts quoi qu'il arrive), (2) **éditable par le client**
(`PUT /v1/config`, aucun RBAC), (3) non persisté, (4) hors contrôle vendeur. Un client
« Compta » avait en réalité toute la box.

- **Entitlement signé Polaris** (`src/zolaos/licensing/`) : grant **RS256 asymétrique** —
  Polaris signe (clé privée), la box **vérifie** (clé publique), **ne peut pas forger**
  (prouvé en test). Modèle **HYBRIDE** : `tier` (starter/business/full) + `modules` à la
  carte. `effective_modules = tier ∪ options`, borné au catalogue.
- **Application AU MONTAGE** (`main.py`) : un module non couvert n'est **même pas monté**
  (404, absent de l'OpenAPI) — pas juste masqué. Enforcement **opt-in**
  (`ENTITLEMENT_ENFORCED`, défaut False → tout monté, dev/tests inchangés) ; **fail-closed**
  si licence absente/expirée en mode enforcé. Livraison **fichier signé et/ou refresh tunnel**.
- **Config verrouillée** (`config.py`) : `modules_actifs` **retiré** de `ConfigUpdate` — le
  client ne peut plus s'octroyer de modules ; il ne garde que la vraie personnalisation.
- **Outillage vendeur** : `scripts/gen_entitlement_keys.py` (paire RSA), `scripts/issue_license.py`
  (Polaris émet une licence signée). Runbook `docs/LICENSING.md`. Tests : infalsifiabilité,
  expiration, altération, fail-closed, montage réel (starter → seul erp monté). 17 + config réécrit.
- **Décisions actées** : packaging hybride, livraison fichier+tunnel, enforcement au montage.
- **Suivis** : refresh/révocation via tunnel cortex ; cockpit cortex pour gérer les entitlements
  par tenant ; synchro affichage `GET /v1/config` sur l'entitlement ; RBAC sur `PUT /v1/config`.

## 2026-07-28 — Champion souverain : premier sprint (couches 1 & 2)

Décision : bâtir le **champion IA souverain africain** (cf. `docs/CHAMPION_ROADMAP.md`).
Verdict d'archi : **ne pas réécrire** le moteur (déjà découplé) ; ajouter deux plans
(produit-moteur C1, données/entraînement C2) reliés par le volant de données.

Cadrage acté : portée **continentale** (français CG, lingala, kituba, swahili, wolof,
haoussa, amharique…) ; sourcing **ouvert depuis zéro** ; base **Llama-3** adaptée (LoRA).

- **L1.1 — Profil `engine` headless** — *fait* (`b88015c`). Nouveau
  `ZOLAOS_PROFILE="engine"` exposant la surface générique seule
  (`/v1/query`, `/query/stream`, `/agents` + auth + health) ; les routers verticaux/UI
  (config, feedback, kb, legal, commons) et les blocs box/cortex sont gatés hors `engine`.
  Box/cortex inchangés. `tests/test_engine_profile.py` (3 tests, isolation de surface).
- **L2.1 — Sourcing corpus langues africaines** — *fait* (`2724879`). `docs/sourcing/african_languages.md`.
  **Fait stratégique** : swahili/haoussa/amharique ont du volume ouvert commercial-clean ;
  **lingala/wolof très pauvres**, **kituba = désert total** (zéro corpus ouvert) → pour ces
  langues, **partenariats + collecte primaire** obligatoires (pas d'ouvert à ingérer).
  Pièges honnêtes : jw.org interdit le TDM ; PII sans NER bantou ; langid via GlotLID/AfroLID
  (fastText ne couvre pas lingala/kituba). Design pipeline + `training_manifest.yml` + réfs tokenizer.
- **Sprint parallèle — LIVRÉ** (6 agents simultanés, suite **681 passed**) :
  - **L1.2** (`0c4f8e0`) adaptateur **OpenAI-compatible** `/v1/chat/completions` (drop-in), tous profils.
  - **L1.3** (`0c4f8e0`) **metering + quotas/jour par clé** (Redis), `require_quota` sur query/stream/chat, **fail-open**.
  - **L1.6** (`973583a`) **harnais d'éval moteur** (routage/ancrage/abstention, 20 cas, gated LLM).
  - **L2.2** (`4d28ea1`) **tokenizer bantou** : fertility Llama-3 fr 1.67 / sw 2.60 / wo·ln 2.71 / kituba 3.00
    (+60-80 % tokens) → **garder Llama-3, différer l'extension de vocab** (corpus absent). Réf. InkubaLM/Lelapa.
  - Câblage `main.py`/`settings.py` fait à la convergence (montage OpenAI + settings quotas), zéro conflit.
  - **Correction (best practice, zéro réinvention)** : **L1.5 (volant de données/COMMONS) était DÉJÀ implémenté**
    (2026-07-07, `src/zolaos/commons/`, 13 tests verts) — la roadmap/mémoire le disaient « à coder » à tort. Corrigé.
  - **L2.4 — éval africaine** — *fait* (`fbf5e2a`) : harnais **chrF** ; FLORES-200 gated → repli **UDHR Art. 1**
    (domaine public), 15 paires FR↔{sw,ln,wo,ha,am}, 19 tests, live gated. Le mètre-étalon AVANT l'entraînement.
  - **L1.4 — packs juridiction** — *fait* (`4cf6785`) : registre `config/jurisdictions.yaml` + résolution hybride
    (X-Country/query → pays du principal → défaut) + `/v1/jurisdictions`. Injection tags retrieval = suivi L1.4b.
  - **Kit de collecte corpus** — *fait* : `docs/CORPUS_COLLECTION_KIT.md` (priorisation déserts kituba/lingala/wolof,
    types de données, canevas licence, protocole annotation, partenaires **vérifiés au web**). Outille le vrai goulot.
  - **Reste** : **couche 1 COMPLÈTE** (product-ready). Couche 2 = **data/GPU-gated** — L2.3 (SFT/LoRA), L2.5
    (registre+service), L2.6 (volant→entraînement) attendent le **corpus collecté**. **Prochaines actions = NON-code** :
    1. contacter CERELLO (`cerello@umng.cg`, seul sur kituba+lingala) ; 2. relicensing MasakhaNEWS-lingala ;
    3. GALSENAI/Baamtu pour le wolof. Cf. `docs/CORPUS_COLLECTION_KIT.md`.

## 2026-07-28 — Assistant code souverain (produit client tech, profil box)

Produit : assistant de codage exécuté **sur la box du client**, code jamais sorti.
Modèle **Qwen2.5-Coder-32B** local (dérogation actée à « stack Llama »). Détail :
`docs/CODE_ASSISTANT.md`, `project_code_assistant_souverain`.

- **P1** (`cb647de`) : schéma `rag_code` (cloisonné tenant, sensible), CodeAgent RAG-ancré,
  CodeChunker (par symboles), indexeur CLI, endpoints `/v1/code/{ask,status}`.
- **P2** (`52e28df`) : indexation **incrémentale** (hash + `--since` git + purge suppressions,
  `index_repo()`), endpoint `POST /v1/code/index` (tâche de fond).
- **P3** (`4737f25`) : **sandbox d'exécution** jetable durcie (conteneur `--network none`,
  non-root, read-only, cap-drop, limites, timeout) + `POST /v1/code/run`, **off par défaut**.
- Runbook (`c2889e0`) ; overlay Polaris code-review repointé sur `rag_code` (privé `7b93a06`).

Suite complète : **629 passed**.

## 2026-07-27 — Corpus cyber (`rag_cyber`)

Doctrine « international d'abord, congolais en bonus ». Détail : `docs/sourcing/cyber_2026.md`,
`project_rag_corpus_status`.

- Schéma + sourcing + mécanisme générique `prefer_tags` (préférence `lang:fr` sans exclure l'anglais).
- **Ingestion** (`60f73a6`) : ~5200 chunks — NIST (1019), OWASP Top10/ASVS/CheatSheets (1609),
  MITRE ATT&CK défensif (2382), 4 lois CG (193, `lang:fr`, `validated:false`+`ocr:true`).
  ANSSI laissé `pending` (conflit licence commerciale — décision juridique).

---

## Journal des décisions (durables)

- **Ne PAS réécrire le moteur** pour le champion : il est découplé, on ajoute des plans. (2026-07-28)
- **Base modèle africain = Llama-3** adaptée par LoRA ; sourcing ouvert ; portée continentale. (2026-07-28)
- **Qwen2.5-Coder-32B** pour l'assistant code (exception à « stack Llama » : qualité code = valeur). (2026-07-28)
- **Sandbox code** : option (a) socket Docker + flag off par défaut ; durcir (b)/(c) avant GA. (2026-07-28)
- **Souveraineté** : service LLM **local uniquement**, jamais d'API cloud (fallback API désactivé).
- **Doctrine** : « le moteur calcule, le LLM narre » ; abstention si non validé.
- **Corpus légal océrisé** : toujours `validated:false` + `ocr:true` (relecture humaine des chiffres avant `true`).
