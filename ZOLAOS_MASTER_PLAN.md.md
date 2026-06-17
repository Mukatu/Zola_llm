# PROMPT D'INITIALISATION DE CONTEXTE : PROJET ZOLAOS
# À l'attention de Claude Code

## 1. RÔLE ET VISION DU PROJET
Tu es l'ingénieur principal en architecture IA et le lead developer de **ZolaOS**. 
ZolaOS est un écosystème multi-agents souverain (Hierarchical Multi-Agent System) conçu pour s'exécuter en priorité localement (sur une infrastructure Asus ROG 128 Go de RAM via Ollama) et capable de basculer (fallback) sur des API externes en cas de haute complexité.
Le but business est de fournir une plateforme d'IA centralisée (via FastAPI) connectable à des applications tierces (Web, Flutter, serveurs locaux) pour le marché africain, avec deux pôles prioritaires : la Santé et le Droit (OHADA), et un avantage compétitif majeur basé sur le traitement des langues locales (Pôle K : Lingala, Swahili, Wolof, etc.).

## 2. ARCHITECTURE DE RÉFÉRENCE DE LA PLATEFORME
Tu dois concevoir et coder le système selon la topologie suivante :
- **ZolaOS Core (Orchestrateur) :** Géré par un modèle lourd (Llama-3-70B en local via Ollama / ou Claude API). Il route les requêtes, gère la sécurité, et fusionne les réponses.
- **Sous-Agents Experts (La Brigade) :** Modèles rapides (Llama-3-8B / Mistral 7B) spécialisés par un System Prompt strict et un accès RAG dédié.
- **Méta-Agents Systèmes :** Agents transversaux (Mémoire partagée, Planification, Traduction, Auto-Correction).
- **Persistance :** Base de données PostgreSQL unique avec l'extension `pgvector` pour la mémoire sémantique, compartimentée par des tags d'accès.

## 3. FEUILLE DE ROUTE CRITIQUE ET PHASES D'EXÉCUTION
Tu dois m'aider à exécuter le projet de manière progressive. Ne passe à une phase que lorsque la précédente est validée et fonctionnelle.

### PHASE 1 : Les Fondations du Système (Mois 1) - [À EXÉCUTER EN PRIORITÉ INDICE 1]
- **Tâche 1.1 :** Configurer l'arborescence du projet (`/agents`, `/tools`, `main.py`, `.env`).
- **Tâche 1.2 :** Écrire la connectivité Python vers Ollama (Endpoints locaux) et l'API Anthropic (Fallback).
- **Tâche 1.3 :** Créer le squelette de l'Orchestrateur central (`main.py` avec FastAPI) capable de classifier une demande (Santé, Droit, Tech, Général) et de retourner un JSON de routage.
- **Tâche 1.4 :** Implémenter les premiers Méta-Agents : Agent Mémoire (liaison PostgreSQL + pgvector) et Agent Planification.

### PHASE 2 : Le MVP Commercial - Santé & Droit (Mois 2 - 3)
- **Tâche 2.1 :** Développer le sous-agent Pharmacologie (Pôle Santé) : système RAG connecté à une base de données de médicaments (CIM-10, posologies, équivalences) avec fonction de vérification de stock.
- **Tâche 2.2 :** Développer le sous-agent OHADA (Pôle Juridique) : système RAG indexant les traités de l'espace OHADA pour la génération automatique de contrats et de protocoles d'accord.
- **Tâche 2.3 :** Sécuriser les outils d'écriture (`Safe Write`) pour que les sous-agents ne modifient pas de fichiers sans validation.

### PHASE 3 : Souveraineté, Localisation (Pôle K) & Mode Hybride (Mois 4)
- **Tâche 3.1 :** Intégrer le Méta-Agent Traduction (Français <-> Lingala, Swahili, Wolof) pour permettre des entrées/sorties multilingues (Text-to-Text et hooks pour le vocal).
- **Tâche 3.2 :** Développer la logique de bascule automatique (Fallback Logic) : Si perte de connexion réseau, isolation 100% locale sur Ollama. Si confiance du modèle local < 80% sur une tâche critique, appel asynchrone à l'API Claude 3.5 Sonnet ou Opus 4.6;

### PHASE 4 : Expansion B2B - ERP, Banque & Fintech (Mois 5 - 6)
- **Tâche 4.1 :** Déployer le Pôle ERP (Sous-agents RH pour le tri de CV et conformité des contrats de travail, sous-agent Finance pour l'analyse des flux de trésorerie).
- **Tâche 4.2 :** Implémenter le sous-agent Scoring Crédit & KYC pour les structures de microfinance et systèmes de Mobile Money.

### PHASE 5 : Developper un agent comme Claud mythos (Mois 7+)
- **Tâche 5.1 :** Renseigne toi sur les capacités necessaire pour nous permmetre de gérer des problématiques de cyberdéfense complexes et de manière autonome.

### PHASE 6: Industrialisation & Scalabilité (Mois 8+)
- **Tâche 6.1 :** Sécuriser l'ensemble contre les injections de prompts (Méta-Agent Supervision).
- **Tâche 6.2 :** Conteneuriser l'architecture complète avec Docker pour permettre une réplication facile sur des serveurs physiques locaux en Afrique.

## 4. TES DIRECTIVES DE TRAVAIL (INSTRUCTIONS POUR CLAUDE CODE)
1. **Raisonnement explicite :** Avant de générer du code ou de modifier un fichier, utilise ton mode "Thought" pour analyser l'impact sur l'architecture globale de ZolaOS.
2. **Modularité stricte :** Tout code doit être modulaire. Ne mélange pas la logique de l'orchestrateur avec le code d'un outil ou d'un sous-agent. Tout doit être découplé.
3. **Sécurité :** Ne propose aucune commande bash destructrice. Valide toujours les scripts de connexion aux bases de données.
4. **Orientation Business :** Garde en tête que chaque ligne de code doit servir à rendre l'application robuste pour des conditions réelles sur le terrain (gestion de la latence, coupures réseau, clarté des réponses pour les utilisateurs finaux).

5. **Points d'attention dans la logique de travail :** ┌────────┬───────────────────────────┬────────────────────────────────────────────────────────────────────
  │ Modèle │            ID             │                                  Usage
  ├────────┼───────────────────────────┼────────────────────────────────────────────────────────────────────
  │ Haiku  │ claude-haiku-4-5-20251001 │ Tâches mécaniques : tests, lint, docs, grep, refactoring simple
  ├────────┼───────────────────────────┼────────────────────────────────────────────────────────────────────
  │ Sonnet │ claude-sonnet-4-6         │ Implémentation standard : features, debug, revue de code
  ├────────┼───────────────────────────┼────────────────────────────────────────────────────────────────────
  │ Opus   │ claude-opus-4-7           │ Décisions architecturales : design système, sécurité, refactoring m
  └────────┴───────────────────────────┴────────────────────────────────────────────────────────────────────

Affiche-moi un résumé de ta compréhension de ce plan d'action et dis-moi ce que tu en penses et surtout quelles seraient les points d'amelioration?




  1. Droit des affaires

  - OHADA : les 9 Actes uniformes (sociétés commerciales, sûretés, procédures collectives, transport, comptable     
  SYSCOHADA, arbitrage, recouvrement, commercial général, coopératives). Sources libres : ohada.org, ohada.com.
  - Jurisprudence : CCJA (Cour Commune de Justice et d'Arbitrage), Tribunal de Commerce de Brazzaville.
  - Référentiels : RCCM (Registre du Commerce), formulaires CFE (Centre de Formalités des Entreprises).

  2. Droit du travail et social (national congolais)

  - Code du travail congolais : Loi n° 45/75 du 15 mars 1975, fortement modifié — récupérer la version consolidée à 
  jour.
  - Conventions collectives : par secteur (commerce, hydrocarbures, bâtiment, banque…) — souvent peu numérisées, à  
  digitaliser.
  - CNSS Congo : barèmes de cotisations, prestations, formulaires d'affiliation, déclarations DGE/DTE.
  - CIPRES : règles harmonisées sous-régionales.
  - Inspection du travail : circulaires et procédures.

  3. Droit fiscal (national)

  - Code Général des Impôts (CGI) congolais, dernière LF (Loi de Finances annuelle).
  - DGID : doctrine administrative, formulaires (DSF, déclarations TVA mensuelles, IS, IRPP, retenues à la source). 
  - Conventions fiscales : Congo–France, Congo–autres (éviter double imposition).
  - TVA congolaise : 18,9 % (taux normal), régimes spécifiques.

  4. Droit pénal des affaires et anti-blanchiment

  - Code pénal congolais + dispositions OHADA pénales.
  - ANIF (Agence Nationale d'Investigation Financière) : obligations déclaratives LAB-FT.
  - COBAC : normes bancaires (pour Phase 5 Fintech).

  5. Données personnelles

  - Loi n° 29-2019 du 10 octobre 2019 (protection des données à caractère personnel).
  - ARPCE : régulateur, formalités de déclaration/autorisation.
  - C'est le texte de référence pour la conformité Santé + ERP + Fintech. Plus contraignant que beaucoup ne le      
  pensent.

  6. Santé

  - Code de la santé publique congolais.
  - DPML (Direction de la Pharmacie, du Médicament et des Laboratoires) : autorisations de mise sur le marché, liste
   nationale des médicaments essentiels (LNME).
  - Ordre national des Pharmaciens du Congo : déontologie.
  - CIM-10 (OMS, libre) — référentiel international, à compléter par les particularités locales (médicaments        
  génériques disponibles localement, antipaludéens, etc.).

  7. Propriété intellectuelle

  - OAPI / Accord de Bangui révisé : marques, brevets, dessins, droits d'auteur.
  - Pas de droit national distinct — l'OAPI fait office.

  8. Comptabilité

  - SYSCOHADA révisé (référentiel comptable OHADA, applicable directement au Congo) : plan comptable, états
  financiers, normes.
  - Spécificités : déclarations à la DGID en parallèle.

  9. Banque & paiement

  - BEAC : règles monétaires zone CEMAC, change.
  - MTN Mobile Money Congo + Airtel Money Congo : API et conditions d'intégration (Phase 5).
  - Banques locales : LCB Bank, BGFI Congo, Ecobank Congo, UBA Congo… pour intégrations comptes (futur).

  10. Spécificités infrastructure terrain

  - Électricité : coupures fréquentes → renforcement de l'argument local-first + plan de reprise sur
  onduleur/groupe.
  - Connectivité : 4G correcte à Brazzaville et Pointe-Noire, dégradée ailleurs → confirme le fallback API
  désactivé.
  - Langues : français (officielle), lingala (Brazzaville/Nord), kituba/munukutuba (Pointe-Noire/Sud) — à intégrer  
  dans le Pôle K (Phase 9 ex-8) avec priorité lingala et kituba (Wolof retiré de la liste prioritaire : c'est       
  sénégalais).


 1. Le pôle Droit est trop étroit — il faut le restructurer

  OHADA = droit des affaires de 17 États d'Afrique francophone. Important, mais loin de couvrir le besoin réel. Le
  pôle Droit doit s'organiser en modules :

  ┌─────────────────────────┬───────────────────────────────────────────────────┬───────────────────────────────┐   
  │         Module          │                    Couverture                     │            Sources            │   
  ├─────────────────────────┼───────────────────────────────────────────────────┼───────────────────────────────┤   
  │ Droit des affaires      │ Actes uniformes (sociétés, sûretés, procédures    │ Traités OHADA (libres de      │   
  │ (OHADA)                 │ collectives…)                                     │ droits)                       │   
  ├─────────────────────────┼───────────────────────────────────────────────────┼───────────────────────────────┤   
  │ Droit du travail        │ Contrats, licenciement, conventions collectives   │ Codes nationaux (RDC,         │   
  │                         │ par pays                                          │ Sénégal, CI…)                 │   
  ├─────────────────────────┼───────────────────────────────────────────────────┼───────────────────────────────┤   
  │ Droit social / sécu     │ CNSS/CNPS, cotisations, prestations               │ Textes nationaux              │   
  ├─────────────────────────┼───────────────────────────────────────────────────┼───────────────────────────────┤   
  │ Droit fiscal            │ IS, IR, TVA, déclarations, contentieux            │ Codes fiscaux par pays        │   
  ├─────────────────────────┼───────────────────────────────────────────────────┼───────────────────────────────┤   
  │ Droit civil             │ Famille, succession, baux civils                  │ Codes civils nationaux        │   
  ├─────────────────────────┼───────────────────────────────────────────────────┼───────────────────────────────┤   
  │ Droit pénal des         │ Blanchiment, abus de biens, fraude                │ Codes pénaux + OHADA pénal    │   
  │ affaires                │                                                   │                               │   
  ├─────────────────────────┼───────────────────────────────────────────────────┼───────────────────────────────┤   
  │ Propriété               │ OAPI / ARIPO (marques, brevets, droits d'auteur)  │ Accords OAPI                  │   
  │ intellectuelle          │                                                   │                               │   
  ├─────────────────────────┼───────────────────────────────────────────────────┼───────────────────────────────┤   
  │ Données personnelles    │ RGPD-équivalents (RDC, Sénégal, Bénin, CI…)       │ Lois nationales en            │   
  │                         │                                                   │ construction                  │   
  └─────────────────────────┴───────────────────────────────────────────────────┴───────────────────────────────┘   

  Conséquence pratique :
  - Chaque module = un sous-corpus RAG dédié (rag_legal_ohada, rag_legal_labor_<pays>, rag_legal_tax_<pays>…), pas  
  un seul rag_legal indifférencié.
  - Approche progressive : MVP = OHADA + droit du travail RDC (ou Sénégal). Extension pays par pays, module par     
  module.
  - Le sourcing des textes nationaux est plus délicat : disponibilité numérique inégale, mises à jour fréquentes.   
  Plan d'ingestion à formaliser.

  ---
  2. Le stack technique — audit honnête

  PostgreSQL + pgvector

  Verdict : ✅ bon choix pour le MVP, à surveiller à l'échelle.
  - Forces : ACID, transactions multi-schémas, JSON natif, mature, opensource, un seul système à exploiter.
  - Limites connues : sur > 5–10 M de vecteurs par index, pgvector (même avec HNSW depuis 0.5) reste plus lent      
  qu'une base vectorielle dédiée. La latence de recherche peut doubler ou tripler.
  - Plan B : Qdrant (Rust, HNSW natif, opensource, self-hosted) si la volumétrie explose. Postgres reste la source  
  de vérité relationnelle, Qdrant prend juste la couche vectorielle.

  Ce qui manque dans le stack actuel

  ┌──────────────────────────────────────────────────────────────┬──────────────────────────────┬──────────────┐    
  │                            Besoin                            │      Techno recommandée      │    Phase     │    
  │                                                              │                              │   d'intro    │    
  ├──────────────────────────────────────────────────────────────┼──────────────────────────────┼──────────────┤    
  │ Cache (réponses, sessions)                                   │ Redis                        │ Phase 1      │    
  ├──────────────────────────────────────────────────────────────┼──────────────────────────────┼──────────────┤    
  │ Queue / tâches async (indexation, embeddings, jobs           │ Dramatiq ou RQ               │ Phase 2      │    
  │ nocturnes)                                                   │ (Redis-backed)               │              │    
  ├──────────────────────────────────────────────────────────────┼──────────────────────────────┼──────────────┤    
  │ Stockage objet (PDFs, CVs, contrats)                         │ MinIO (S3-compatible)        │ Phase 2      │    
  ├──────────────────────────────────────────────────────────────┼──────────────────────────────┼──────────────┤    
  │ Reverse proxy + TLS auto                                     │ Caddy ou Traefik             │ Phase 0      │    
  ├──────────────────────────────────────────────────────────────┼──────────────────────────────┼──────────────┤    
  │ Métriques                                                    │ Prometheus + Grafana         │ Phase 0      │    
  ├──────────────────────────────────────────────────────────────┼──────────────────────────────┼──────────────┤    
  │ Logs agrégés                                                 │ Loki (plus léger qu'ELK)     │ Phase 0–1    │    
  ├──────────────────────────────────────────────────────────────┼──────────────────────────────┼──────────────┤    
  │ Migrations DB                                                │ Alembic (SQLAlchemy)         │ Phase 0      │    
  ├──────────────────────────────────────────────────────────────┼──────────────────────────────┼──────────────┤    
  │ Validation / DTOs                                            │ Pydantic v2                  │ Phase 0      │    
  └──────────────────────────────────────────────────────────────┴──────────────────────────────┴──────────────┘    

  Ollama

  Verdict : ✅ pour le MVP. Limite : single-node, throughput modeste sur 70B.
  - Plan B pour la prod : vLLM (plus rapide, batching dynamique, mais plus complexe à exploiter). À évaluer Phase 6.

  FastAPI + Pydantic + Python

  ✅ Standard de facto. Rien à débattre.

  ---
  3. Connecteurs ERP — l'approche actuelle est trop limitative

  Tu as raison : se limiter à Odoo/ERPNext cale le produit. Proposition : Connector Framework générique.

  Architecture proposée

  zolaos/connectors/
  ├── base.py              # Interface abstraite ERPConnector
  ├── odoo.py              # via XML-RPC ou JSON-RPC
  ├── erpnext.py           # via REST API
  ├── sap.py               # via OData ou BAPI
  ├── sage.py              # via API ou ODBC
  ├── generic_rest.py      # REST configurable (OpenAPI)
  ├── generic_soap.py      # SOAP / WSDL
  ├── generic_sql.py       # accès DB direct via SQLAlchemy
  ├── csv_excel.py         # ingestion fichiers + watcher dossier
  ├── webhook.py           # entrée par webhooks
  └── custom_sdk/          # SDK + docs pour clients développant leur propre connecteur

  Principes

  - Interface unique : tout connecteur expose list_employees(), read_invoice(), push_journal_entry(), etc. Le       
  sous-agent ERP n'a pas à savoir s'il parle à Odoo ou à un système maison.
  - Mapping déclaratif : un fichier YAML par connecteur déclare la correspondance des champs (employee.full_name →  
  person.nom_complet). Pas de code à écrire pour un mapping simple.
  - Auth pluggable : API key, OAuth2, basic, certificats, IP allowlist.
  - SDK client : pour les systèmes faits maison, le client implémente une classe CustomConnector(BaseConnector) avec
   5-6 méthodes, et ZolaOS le découvre via un fichier de configuration.

  Impact sur le plan : Phase 4 (ERP) inclut la livraison du framework + 2-3 connecteurs (Odoo, REST générique, CSV).
   Les autres sont ajoutés au gré des clients.

  ---
  4. Pôle Conformité / GRC

  Recommandation : un pôle dédié, pas une section de l'ERP.

  Pourquoi :
  - Transversal : touche Santé (HIPAA-like), Droit, ERP, Fintech (KYC/AML), Cyber. Si on l'enferme dans ERP, on     
  duplique la logique partout.
  - Stakeholders distincts : DPO, RSSI, compliance officer, commissaire aux comptes — pas les mêmes utilisateurs que
   la compta.
  - Cycle réglementaire propre : la veille des changements de loi obéit à son propre rythme.

  Composition du pôle GRC

  ┌────────────────────────┬────────────────────────────────────────────────────────────────────────────────────┐   
  │       Sous-agent       │                                        Rôle                                        │   
  ├────────────────────────┼────────────────────────────────────────────────────────────────────────────────────┤   
  │ Audit légal            │ Vérifie conformité (OHADA, droit du travail, RGPD-équivalent…)                     │   
  ├────────────────────────┼────────────────────────────────────────────────────────────────────────────────────┤   
  │ Gestion des risques    │ Identifie + scoring (opérationnel, juridique, financier, cyber), plan              │   
  │                        │ d'atténuation                                                                      │   
  ├────────────────────────┼────────────────────────────────────────────────────────────────────────────────────┤   
  │ Reporting              │ Génère rapports CNPS, fisc, banque centrale, autorité données                      │   
  │ réglementaire          │                                                                                    │   
  ├────────────────────────┼────────────────────────────────────────────────────────────────────────────────────┤   
  │ Veille réglementaire   │ Surveille évolutions textes, alerte sur impacts                                    │   
  ├────────────────────────┼────────────────────────────────────────────────────────────────────────────────────┤   
  │ Contrôle interne       │ Vérifie séparation des tâches, traçabilité, anomalies                              │   
  └────────────────────────┴────────────────────────────────────────────────────────────────────────────────────┘   

  Placement dans la roadmap

  S'appuie sur Droit (corpus juridique) + ERP (données métier). Donc Phase 5 logique : après ERP, avant Fintech (qui
   en bénéficie pour KYC/AML). Renumérotation à prévoir.

  ---
  5. Sandbox d'exécution — comparaison

  ┌────────────────┬───────────────────────────────────┬───────────────────┬───────────────────────────────────┐    
  │    Critère     │          Docker éphémère          │     firejail      │              gVisor               │    
  ├────────────────┼───────────────────────────────────┼───────────────────┼───────────────────────────────────┤    
  │ Plateforme     │ Windows / Mac / Linux             │ Linux only        │ Linux only                        │    
  ├────────────────┼───────────────────────────────────┼───────────────────┼───────────────────────────────────┤    
  │ Isolation      │ Namespaces + cgroups              │ Namespaces +      │ Kernel user-space (Sentry) = fort │    
  │                │                                   │ seccomp           │                                   │    
  ├────────────────┼───────────────────────────────────┼───────────────────┼───────────────────────────────────┤    
  │ Maturité       │ ★★★★★                             │ ★★                │ ★★★ (Google interne, GKE Sandbox) │    
  │ écosystème     │                                   │                   │                                   │    
  ├────────────────┼───────────────────────────────────┼───────────────────┼───────────────────────────────────┤    
  │ Overhead       │ Faible (mais Docker Desktop sur   │ Très faible       │ Modéré (10–30 % sur I/O lourd)    │    
  │                │ Win = WSL2, ~1 Go RAM)            │                   │                                   │    
  ├────────────────┼───────────────────────────────────┼───────────────────┼───────────────────────────────────┤    
  │ Bonne pratique │ --rm --network none --read-only   │ Profils           │ Drop-in replacement runC          │    
  │                │ --user 1000                       │ prédéfinis        │ (--runtime=runsc)                 │    
  ├────────────────┼───────────────────────────────────┼───────────────────┼───────────────────────────────────┤    
  │ Cas d'usage    │ Dev tooling, CI, code "interne"   │ Apps desktop      │ Code non confiance                │    
  │ idéal          │ semi-confiance                    │ Linux             │ (multi-tenants, plugins externes) │    
  ├────────────────┼───────────────────────────────────┼───────────────────┼───────────────────────────────────┤    
  │ Risque escape  │ Existe (kernel partagé)           │ Plus élevé (moins │ Faible (syscalls interceptés)     │    
  │                │                                   │  audité)          │                                   │    
  └────────────────┴───────────────────────────────────┴───────────────────┴───────────────────────────────────┘    

  Ma recommandation pour ZolaOS

  - Phase 3 (MVP Code Agent) : Docker éphémère avec config durcie (--rm, --network none, --read-only, user non-root,
   limites cgroup). Familier, cross-OS (utile pour ton poste de dev Windows), suffisant car le code exécuté est     
  celui de ton projet, pas du code étranger.
  - Phase 7 (Industrialisation, si plugins/clients tiers) : passer à gVisor quand on commence à exécuter du code    
  venu de l'extérieur (marketplace, clients qui poussent leurs scripts). Plug compatible Docker (--runtime=runsc) → 
  migration peu coûteuse.

  firejail écarté : Linux-only, donc ne marche pas sur ton poste Windows.

  ---
  6. Repo / Embedding / Pilotes — explications

  Repo

  ┌───────────────────┬───────────────────────────────────┬──────────────────────────────────────┬─────────────┐    
  │      Option       │               Pour                │                Contre                │    Coût     │    
  ├───────────────────┼───────────────────────────────────┼──────────────────────────────────────┼─────────────┤    
  │ GitHub privé      │ Actions, écosystème, Copilot,     │ Code sur serveurs US → friction      │ Gratuit / 4 │    
  │                   │ sécurité éprouvée                 │ souveraineté                         │  $/u        │    
  ├───────────────────┼───────────────────────────────────┼──────────────────────────────────────┼─────────────┤    
  │ Gitea self-hosted │ Souveraineté totale, opensource   │ Ops à gérer, CI moins riche (Gitea   │ Infra seule │    
  │                   │ MIT, léger                        │ Actions correct)                     │             │    
  ├───────────────────┼───────────────────────────────────┼──────────────────────────────────────┼─────────────┤    
  │ GitLab CE         │ Très complet (CI, registry,       │ Gourmand en RAM (~4 Go mini)         │ Infra seule │    
  │ self-hosted       │ issues, wiki)                     │                                      │             │    
  └───────────────────┴───────────────────────────────────┴──────────────────────────────────────┴─────────────┘    

  Recommandation pragmatique : démarrer GitHub privé pour la vélocité (Actions, écosystème, intégrations), migrer   
  vers Gitea self-hosted en Phase 7 (industrialisation) sur le serveur local. Règle pendant tout le projet : rester 
  portable (pas de GitHub-specific dans le code, Actions documentées comme équivalent à des scripts shell).

  Embedding

  Trois candidats sérieux pour le multilingue FR + africain :

  ┌───────────────────────┬────────┬──────────┬─────────┬────────────────────────────────────────────────────────┐  
  │        Modèle         │ Params │ Contexte │ Langues │                      Spécificités                      │  
  ├───────────────────────┼────────┼──────────┼─────────┼────────────────────────────────────────────────────────┤  
  │ bge-m3 (recommandé)   │ 568 M  │ 8 192    │ 100+    │ Dense + sparse + multivector, excellent en             │  
  │                       │        │          │         │ multilingue, MIT                                       │  
  ├───────────────────────┼────────┼──────────┼─────────┼────────────────────────────────────────────────────────┤  
  │ multilingual-e5-large │ 560 M  │ 512      │ 94      │ Solide mais contexte court                             │  
  ├───────────────────────┼────────┼──────────┼─────────┼────────────────────────────────────────────────────────┤  
  │ jina-embeddings-v3    │ 570 M  │ 8 192    │ 89      │ Très bon, mais licence CC-BY-NC (non commercial sans   │  
  │                       │        │          │         │ payer)                                                 │  
  └───────────────────────┴────────┴──────────┴─────────┴────────────────────────────────────────────────────────┘  

  Verdict : bge-m3 sans hésitation. Contexte 8K = on indexe des chunks de 1 000 tokens sans souffrir, multivector   
  excellent pour les requêtes nuancées, licence MIT, et la couverture multilingue inclut les bases dont le Pôle K a 
  besoin (via XLM-R en sous-bassement).

  Réserve : pour les langues locales spécifiquement (Lingala, Wolof), bge-m3 sera moyen et il faudra évaluer +      
  potentiellement fine-tuner. C'est exactement ce que prévoit la Phase 8 (Pôle K).

  Pilotes — profils cibles

  ┌───────┬─────────────────────────────────────────────────────────┬───────────────────────────────────────────┐   
  │ Pôle  │                      Cible idéale                       │                   Pitch                   │   
  ├───────┼─────────────────────────────────────────────────────────┼───────────────────────────────────────────┤   
  │ Santé │ Pharmacie d'officine ou polyclinique 10–50 lits,        │ Pilote 3 mois gratuit contre feedback     │   
  │       │ Kinshasa ou Dakar, pharmacien/DG ouvert à l'IA          │ structuré + droit d'usage anonymisé       │   
  ├───────┼─────────────────────────────────────────────────────────┼───────────────────────────────────────────┤   
  │ Droit │ Cabinet d'avocats 2–5 associés, spécialisé OHADA +      │ Licence pilote gratuite 6 mois contre cas │   
  │       │ droit du travail, jeune (< 45 ans)                      │  anonymisés pour enrichir corpus          │   
  ├───────┼─────────────────────────────────────────────────────────┼───────────────────────────────────────────┤   
  │ ERP   │ PME 20–100 salariés, secteur services ou négoce, ayant  │ Intégration pilote 6 mois, mesure KPI     │   
  │       │ déjà un ERP (Odoo/maison) ou en cherchant un            │ réduction temps de traitement             │   
  └───────┴─────────────────────────────────────────────────────────┴───────────────────────────────────────────┘ 