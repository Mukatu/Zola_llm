# ZolaOS — Addendum V3 : Partenariat Polaris × ZolaOS

**Date** : 2026-05-17 (révisé 2026-05-18 — Annexe Zero Trust Client)
**Statut** : Addendum complémentaire au [`ZOLAOS_MASTER_PLAN_V2.md`](./ZOLAOS_MASTER_PLAN_V2.md) (V2.2 — **intact, conservé comme référence**).
**Objet** : intégrer la vision Polaris (cabinet de conseil opérateur) sans modifier les fondations V2.2.

> **Mise à jour 2026-05-18** : suite à une analyse approfondie des techniques de protection IP face aux IA modernes de reverse engineering, le plan a été **complété par une Annexe Zero Trust Client** (section 11) qui révise la stratégie de protection IP. Les tasks #73 (chiffrement modèles) et #74 (TEE) sont **abandonnées** au profit d'une architecture où les actifs sensibles ne sont jamais déployés chez le client. Voir section 11 ci-dessous.

> Ce document **complète** le plan V2.2 ; il ne le remplace pas. Les 8 pôles ZolaOS restent d'actualité, les phases restent dans l'ordre prévu, l'infra Phase 0/1 reste valide telle quelle. On ajoute ici la dimension business (Polaris comme opérateur commercial) et les adaptations techniques qui en découlent.

---

## 1. Le partenariat structurant

### 1.1. Deux entités, un seul moteur

- **ZolaOS** = la **plateforme technologique** multi-agents souveraine (8 pôles V2.2 inchangés).
- **Polaris** = le **cabinet de conseil opérateur** qui s'appuie sur ZolaOS pour vendre des missions de conseil augmenté à ses clients (entreprises, institutions, ONG).

### 1.2. Pourquoi ce modèle

| Piège évité (SaaS pur) | Force du conseil augmenté |
|------------------------|---------------------------|
| Éducation marché trop longue | Polaris facture des honoraires élevés dès J1 |
| Support technique lourd côté éditeur | Le consultant est l'interface humaine, l'IA en arrière-plan |
| Marges faibles au démarrage | Rivalise immédiatement avec PwC/Deloitte sur la précision et la vitesse |
| Manque d'expérience historique pénalisant | Annulé par la puissance de l'IA spécialisée |

### 1.3. Polaris est le premier opérateur, pas le seul possible

À terme, d'autres cabinets ou opérateurs sectoriels pourraient utiliser ZolaOS (autres pays OHADA, ONG internationales, gouvernements). Le code est conçu **multi-tenant cabinet** dès maintenant.

---

## 2. Topologie Zolabox / Zolacortex

### 2.1. Définitions officielles

| Composant | Lieu | Profil d'usage | Données |
|-----------|------|----------------|---------|
| **Zolabox** | Salle informatique / réseau interne du client | Restreint (1 tenant client, sous-agents standards) | Strictement locales au client |
| **Zolacortex** | Cabinet Polaris | Élargi (cross-tenants via missions, overlays Polaris) | Vue éphémère pendant les missions |

### 2.2. Une seule codebase, deux profils

Pas de fork de code. Variable d'env :

```bash
ZOLAOS_PROFILE=box      # déploiement chez le client
ZOLAOS_PROFILE=cortex   # déploiement chez Polaris
```

Le profil détermine ce qui est exposé/actif :

| Élément | Profil `box` | Profil `cortex` |
|---------|--------------|------------------|
| Routes API gestion missions | ❌ | ✅ |
| Connexion distante aux Box clientes | ❌ | ✅ (pendant mission) |
| Overlays prompts Polaris | ❌ | ✅ |
| OUTPUT_FORMAT structuré strict | optionnel | ✅ obligatoire |
| Génération de rapports `.docx`/`.pdf` | ❌ | ✅ |
| RAG locaux du client | ✅ | ✅ (lu par token éphémère) |

### 2.3. Connexion sécurisée éphémère

Pendant une mission d'audit :

1. **Consentement explicite** du client via interface Zolabox (journalisé).
2. **Token court (JWT)** émis par la Zolabox : scopé sur le tenant client, durée 1-3 h, `mission_id` en claim.
3. Le Cortex interroge les endpoints RAG du client via API authentifiée.
4. **Audit chaîne hash** dans `audit.log` chez le client de chaque requête Cortex (jamais désactivable).
5. Expiration → accès révoqué automatiquement.

### 2.4. Apprentissage Fédéré (à concevoir Phase 4+)

Les Zolabox déployées chez plusieurs clients s'enrichissent mutuellement par échange de **gradients mathématiques chiffrés et anonymes** (jamais les données brutes). Préserve le secret des affaires.

Pistes techniques à évaluer : PySyft, Flower, OpenFL. Décision lors du démarrage du chantier dédié.

---

## 3. Mapping des offres Polaris vers les pôles ZolaOS

> Les "offres" Polaris ne sont **pas** de nouveaux pôles techniques. Ce sont des **packagings commerciaux** qui mobilisent un ou plusieurs des 8 pôles ZolaOS V2.2 existants.

### 3.1. Offre **Conseil RH & Conformité**

| Aspect | Détail |
|--------|--------|
| Pôles ZolaOS mobilisés | **Droit** (modules : Travail CG, Social CG) + **GRC** |
| Sous-agents génériques | `agents/legal/travail_cg.py`, `agents/legal/social_cg.py` (CNSS/CIPRES), `agents/grc/conformite.py` |
| Overlay Polaris | `agents/polaris/conformite_rh.py` (nom officiel : `ZolaCortex-Conformite-RH`) |
| Sources RAG | Code du Travail CG 45/75, Conventions Collectives Nationales, **Jurisprudences Cour Suprême / CCJA** |
| OUTPUT_FORMAT (4 champs obligatoires) | `CLAUSE OU SITUATION ANALYSÉE` / `RISQUE JURIDIQUE & PRUD'HOMMAL` / `RÉFÉRENCE LÉGALE` / `NOTE DE SÉCURISATION POLARIS` |
| Chunking spécialisé | Segmentation **par clause juridique** (Période d'essai, Non-concurrence, Rémunération, Préavis…) |
| Rapport généré | Matrice de Vulnérabilité Contractuelle + Fiches de Remédiation Légale + Protocole de Clôture de Risque |
| PII redaction | Stricte (noms, prénoms, adresses, numéros ID, salaires en tranches) |
| Spec détaillée | [`ZolaOS_Agent_Conformite_RH.docx`](./ZolaOS_Agent_Conformite_RH.docx) |

### 3.2. Offre **Fiscalité Opérationnelle**

| Aspect | Détail |
|--------|--------|
| Pôles ZolaOS mobilisés | **Droit** (modules : Fiscal CG, Affaires OHADA) + **ERP** (Comptabilité SYSCOHADA, Fiscalité CG) |
| Sous-agents génériques | `agents/legal/fiscal_cg.py`, `agents/legal/ohada.py`, `agents/erp/compta_syscohada.py` |
| Overlay Polaris | `agents/polaris/fiscal_ohada.py` (nom officiel : `ZolaCortex-Fiscal-OHADA`) |
| Sources RAG | CGI local, **Acte Uniforme OHADA portant organisation de la sûreté et du droit commercial**, **SYSCOHADA révisé** |
| OUTPUT_FORMAT (4 champs obligatoires) | `DESCRIPTION DU RISQUE / DE L'ANOMALIE` / `RÉFÉRENCE LÉGALE` / `IMPACT FINANCIER ESTIMÉ (FCFA)` / `ACTION CORRECTIVE RECOMMANDÉE PAR POLARIS` |
| Chunking spécialisé | Segmentation **par bloc d'écritures comptables** (Date / Compte / Libellé / Débit / Crédit) — pas générique caractères |
| Format ingestion | XLSX / CSV (Grand Livre, balance générale) en plus de PDF/MD/TXT |
| Rapport généré | Synthèse Exécutive (gains immédiats) + Section Conformité Fiscale (risques classés Élevée/Moyenne/Faible) + Section Optimisation Cash-Flow |
| PII redaction | Anonymisation des tiers (clients/fournisseurs → hash type `FR_84920`) avant analyse |
| Spec détaillée | [`ZolaOS_Agent_Fiscalite_Ohada.docx`](./ZolaOS_Agent_Fiscalite_Ohada.docx) |

### 3.3. Offre **Gestion de Trésorerie**

| Aspect | Détail |
|--------|--------|
| Pôles ZolaOS mobilisés | **ERP** (Finance, cash-flow) + **Fintech** (prévisions, scoring) |
| Sous-agents génériques | `agents/erp/finance.py`, `agents/erp/tresorerie.py` (à créer), `agents/fintech/scoring.py` |
| Overlay Polaris | `agents/polaris/tresorerie.py` (à spécifier — pas de doc détaillé encore) |
| Sources RAG | SYSCOHADA (cycles encaissement), données logistique transit/fret EU-Afrique, taux de change BEAC |
| OUTPUT_FORMAT | À spécifier (probable : `RISQUE TRÉSORERIE` / `IMPACT FCFA` / `RECOMMANDATION POLARIS` / `CALENDRIER ACTION`) |
| Chunking spécialisé | Segmentation par cycle (encaissement / décaissement / cycles fournisseurs) |
| Rapport généré | Calendrier de libération de trésorerie + Optimisations de cycles + Alertes |
| Spec détaillée | À produire (TODO) |

### 3.4. Offre **Audit Santé** (cliniques, polycliniques, pharmacies)

| Aspect | Détail |
|--------|--------|
| Pôles ZolaOS mobilisés | **Santé** (pharmacologie, CIM-10/LNME) + **GRC** (conformité DPML) |
| Sous-agents génériques | `agents/health/pharmacology.py`, `agents/health/diagnosis.py`, `agents/grc/conformite_santé.py` |
| Overlay Polaris | `agents/polaris/audit_sante.py` (à spécifier ultérieurement) |
| Sources RAG | **CIM-10** (OMS), **LNME congolaise** (DPML), bonnes pratiques OMS Afrique |
| OUTPUT_FORMAT | À spécifier (probable : `ANOMALIE/RISQUE` / `RÉFÉRENCE OMS/DPML` / `IMPACT PATIENT/LÉGAL` / `ACTION CORRECTIVE`) |
| Statut | **Pas dépriorité** — pôle Santé reste prioritaire Phase 2 |

### 3.5. Offre **Cyber-défense**

| Aspect | Détail |
|--------|--------|
| Pôles ZolaOS mobilisés | **Cyber** (défensif uniquement, jamais offensif) + **GRC** (conformité Loi 29-2019) |
| Sous-agents génériques | `agents/cyber/defense.py`, `agents/grc/conformite_data.py` |
| Overlay Polaris | `agents/polaris/cyber_defense.py` |
| Sources RAG | Loi 29-2019 CG (données personnelles), guides ANSSI/CERT, MITRE ATT&CK (volet défensif) |

### 3.6. Offre **Audit Institutions Gouvernementales** (segment nouveau)

| Aspect | Détail |
|--------|--------|
| Pôles ZolaOS mobilisés | **GRC** (étendu : audit institutionnel, marchés publics, transparence) + **Droit** (administratif — module à ajouter) |
| Sous-agents génériques | `agents/grc/audit_institutionnel.py` (nouveau), `agents/legal/admin_cg.py` (nouveau) |
| Overlay Polaris | `agents/polaris/audit_gouv.py` |
| Sources RAG | Code des marchés publics CG, Lois de Finances, **Cour des Comptes** (rapports publics), guides ARMP |
| Particularités | Sensibilité politique élevée → renforcement audit hash + neutralité éditoriale obligatoire |

### 3.7. Offre **ONG / Bailleurs internationaux** (segment nouveau)

| Aspect | Détail |
|--------|--------|
| Pôles ZolaOS mobilisés | **GRC** (reporting bailleurs, anti-blanchiment, KYC donateurs) + **ERP** (gestion financière simplifiée, reporting projets) |
| Sous-agents génériques | `agents/grc/reporting_bailleurs.py` (nouveau), `agents/erp/projets_ong.py` (nouveau) |
| Overlay Polaris | `agents/polaris/ong_compliance.py` |
| Sources RAG | Standards IATI, guides ONU/UE/Banque Mondiale, GAFI (anti-blanchiment) |

### 3.8. Pôles transverses (utilisés par toutes les offres)

| Pôle | Usage transverse |
|------|------------------|
| **Engineering / Code Agent** | Outillage interne ZolaOS, génération de scripts d'ingestion sur mesure pour chaque mission, intégrations clients |
| **Pôle K** (langues locales) | Activation cross-pôles en **dernière phase** (Phase 9) — pertinent pour tous les clients qui interagissent en Lingala/Kituba |

### 3.9. Récap pôles ZolaOS et leurs usages Polaris

```
┌────────────────┬──────────────────────────────────────────────────────────┐
│ Pôle ZolaOS    │ Offres Polaris qui le mobilisent                         │
├────────────────┼──────────────────────────────────────────────────────────┤
│ Santé          │ Audit Santé (cliniques/pharmas)                          │
│ Droit (8 mod)  │ RH, Fiscal, Audit Gouv, ONG (selon module)               │
│ ERP            │ Fiscal, Trésorerie, ONG                                  │
│ GRC            │ RH, Audit Santé, Cyber, Audit Gouv, ONG (TRANSVERSAL)    │
│ Engineering    │ Outillage interne, dev sur mesure                        │
│ Fintech        │ Trésorerie, scoring                                      │
│ Cyber          │ Cyber-défense                                            │
│ K              │ Phase finale, transverse                                 │
└────────────────┴──────────────────────────────────────────────────────────┘
```

---

## 4. Adaptations techniques transversales (à intégrer)

### 4.1. PII redaction OBLIGATOIRE et pré-ingestion

**Changement vs V2.2** : la PII redaction était prévue Phase 2 comme **module activable** par flag. Elle devient un **prérequis bloquant** du pipeline RAG pour tous les pôles sensibles (santé, RH, fiscal).

Implémentation :
- Module `src/zolaos/security/pii.py` (déjà prévu task #52) **renforcé**
- Hook obligatoire dans `src/zolaos/rag/ingest.py` : `ingest_text()` exige `pii_redaction_policy: PIIRedactionPolicy` non None pour les schémas sensibles
- Politiques par domaine :
  - **Fiscal** : tiers (noms clients/fournisseurs) → hash type `FR_84920`
  - **RH** : noms/prénoms/adresses/numéros ID → masquage ; salaires → tranches
  - **Santé** : noms patients + numéros assurés → masquage ; pathologies → conservées (utiles au RAG)
- Politique `PIIRedactionPolicy.NONE` autorisée uniquement pour les corpus **publics** (CIM-10, OHADA actes uniformes, codes officiels)

### 4.2. OUTPUT_FORMAT structuré strict (overlays Polaris)

Pattern à généraliser :
- Chaque overlay Polaris définit un schéma Pydantic de sortie (4 champs typés).
- Le sous-agent appelle le LLM avec `json_schema=PolarisOutput.model_json_schema()` (le fix JSON strict de Phase 1.5 est réutilisé tel quel).
- Validation Pydantic stricte du LLM → garantit le format livré au consultant.

### 4.3. Chunking spécialisé par domaine

Le `src/zolaos/rag/chunking.py` actuel (sliding window tokens) reste valide pour le générique. À ajouter :

| Chunker spécialisé | Domaine | Stratégie |
|--------------------|---------|-----------|
| `AccountingChunker` | Compta (Grand Livre) | Bloc d'écritures (Date / Compte / Libellé / Débit / Crédit) |
| `LegalClauseChunker` | Contrats juridiques | Une clause par chunk (Période d'essai, Non-concurrence, …) |
| `LegalArticleChunker` | Textes juridiques (CGI, OHADA) | Un article par chunk avec contexte titre/section |
| `MedicalCaseChunker` | Dossiers médicaux | Un dossier patient = 1+ chunks selon longueur |

### 4.4. Formats d'ingestion étendus

`_load_text` actuel : TXT/MD/PDF. À ajouter :
- **XLSX/CSV** : pour Grand Livre, balance générale, exports RH (openpyxl + pandas, à pinner CPU-only)
- **DOCX** : pour contrats, règlements intérieurs (python-docx)
- **HTML/XML** : pour scraping ciblé (sites juridiques officiels)

### 4.5. Génération de rapports `.docx` / `.pdf`

- Module `src/zolaos/reports/` (nouveau)
- Templates Jinja2 + python-docx (génération `.docx`) ou WeasyPrint (génération `.pdf` depuis HTML)
- 1 template par offre Polaris (Synthèse Exécutive Fiscal, Matrice RH, Calendrier Trésorerie, etc.)
- Profil Cortex uniquement (les Box clientes ne génèrent pas de rapport — c'est l'analyse Polaris qui produit le livrable)

### 4.6. Tenancy à 2 niveaux

| Niveau | Exemple | Capacité |
|--------|---------|----------|
| Tenant **cabinet** | Polaris | Cross-clients via missions ; voit ses propres données métier (CRM clients, missions, livrables) |
| Tenant **client** | "SARL Brazza Trading" | Vue isolée stricte sur ses propres données |

Modèle SQL : ajouter `tenant_type` (`cabinet` | `client`) et `parent_tenant_id` (pour relier les clients à leur cabinet de référence). Tags RBAC enrichis :
- `tenant:cabinet:polaris`
- `tenant:client:brazza_trading_001`
- `mission:m_2026_05_17_a`

### 4.7. Mission éphémère (modèle de données)

Nouvelle table `core.missions` :
```sql
CREATE TABLE core.missions (
    id UUID PRIMARY KEY,
    cabinet_tenant_id UUID NOT NULL,
    client_tenant_id UUID NOT NULL,
    offre VARCHAR(64) NOT NULL,     -- "conformite_rh", "fiscal_ohada", etc.
    consultant_user_id UUID NOT NULL,
    started_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    expires_at TIMESTAMPTZ NOT NULL,
    revoked_at TIMESTAMPTZ NULL,
    status VARCHAR(16) NOT NULL DEFAULT 'active'  -- active|expired|revoked|completed
);
```

JWT mission injecte `mission_id` en claim. Toute requête Cortex → Box vérifie la mission active et non expirée.

---

## 5. Extensions par segment clientèle

### 5.1. Institutions gouvernementales (nouveau)

Renforcements :
- Module **Droit administratif CG** dans pôle Droit (à ajouter)
- Sous-agent `agents/grc/audit_institutionnel.py`
- Sources RAG : Code des marchés publics, Cour des Comptes, ARMP, Lois de Finances
- Sensibilité politique : audit hash renforcé, neutralité éditoriale, refus de réponse politiquement orientée

### 5.2. ONG / Bailleurs internationaux (nouveau)

- Sous-agent `agents/grc/reporting_bailleurs.py`
- Sous-agent `agents/erp/projets_ong.py`
- Sources RAG : standards IATI, guides ONU/UE/Banque Mondiale, GAFI
- Multi-langue prioritaire (FR + EN au minimum) — anticipation Pôle K

### 5.3. Médecine (déjà prévu V2.2, Phase 2)

Inchangé. Pilotes terrain prévus : polyclinique/pharmacie d'officine à Brazzaville ou Pointe-Noire.

---

## 6. Adaptation de la roadmap (sans casser ce qui est en cours)

### 6.1. Ce qui ne change pas

- **Phase 0 (close)** : socle technique transverse
- **Phase 1 (close)** : fondations système (orchestrateur, RAG infra, audit, sécurité)
- **Phase 2 (en cours)** : MVP Santé + Droit OHADA + Travail CG + Fiscal CG
- **Ordre des phases V2.2** : préservé (Pôle K en dernier)

### 6.2. Tasks Phase 2 à enrichir (vs liste actuelle #48-54)

| Task # | Adaptation |
|--------|-----------|
| #48 Pharmacologie | Reste prioritaire. Ajouter chunker `MedicalCaseChunker` + PII redaction santé. |
| #49 Droit OHADA | OK. Sources : ajouter Acte Uniforme sûreté + droit commercial. Output format strict 4 champs. |
| #50 Droit travail CG | OK. Sources : ajouter Conventions Collectives + Jurisprudences Cour Suprême. Chunker `LegalClauseChunker` pour contrats. |
| #51 Droit fiscal CG | OK. Ajouter SYSCOHADA révisé + chunker `AccountingChunker`. Ingestion XLSX (Grand Livre). |
| #52 PII redaction | **Repositionné en prérequis bloquant**, plus une option. Hook obligatoire dans `ingest_text`. |
| #53 Eval framework | OK. Ajouter datasets de test pour OUTPUT_FORMAT structuré. |
| #54 Router sous-pôles legal | OK. Étendre aux modules santé (pharmacology/diagnosis) et erp (compta/finance). |

### 6.3. Nouvelles tasks à créer pour Polaris (sans démarrer Phase 3+)

| ID prévu | Bloc | Quand |
|----------|------|-------|
| Polaris-1 | Profil `ZOLAOS_PROFILE=box|cortex` + dispatch routes | Phase 2 bis |
| Polaris-2 | Overlays `agents/polaris/*` (Conformite-RH, Fiscal-OHADA, …) | Phase 2 bis (en parallèle des sous-agents) |
| Polaris-3 | Module `src/zolaos/reports/` (templates Jinja2 + python-docx) | Phase 2 bis |
| Polaris-4 | Chunkers spécialisés (`AccountingChunker`, `LegalClauseChunker`, etc.) | Phase 2 bis |
| Polaris-5 | Loaders étendus (XLSX/CSV/DOCX) dans `ingest._load_text` | Phase 2 bis |
| Polaris-6 | Tenancy 2 niveaux (`tenant_type`, `parent_tenant_id`) | Phase 2 bis |
| Polaris-7 | Table `core.missions` + JWT mission claim | Phase 2 bis |
| Polaris-8 | Connexion sécurisée éphémère Cortex → Box (API + token) | Phase 3 |
| Polaris-9 | Module Droit administratif CG (segment gouvernement) | Phase 4 |
| Polaris-10 | Sous-agents ONG (`reporting_bailleurs`, `projets_ong`) | Phase 4 |
| Polaris-11 | Apprentissage Fédéré (PoC) | Phase 4-5 |

> "Phase 2 bis" = chantier transverse intégré à Phase 2, pas une nouvelle phase. Mêmes pilotes terrain.

---

## 7. KPI ajustés (vs plan V2.2)

| KPI Phase 2 V2.2 | Évolution Polaris |
|------------------|-------------------|
| Hallucination rate < 5 % in-domain | Inchangé |
| Latence p95 < 3 s | Inchangé pour routage ; e2e Strix Halo accepté jusqu'à 8 s en réalité (cf. `project_latency_gpu_constraint.md`) |
| 2 pilotes actifs ≥ 50 requêtes/sem | **1er pilote = Polaris lui-même** (consultants utilisent Cortex sur cas test) + 1 client réel (cabinet d'avocats, polyclinique ou PME) |
| 3 modules juridiques en production | Inchangé (OHADA, Travail CG, Fiscal CG) |
| **Nouveau** : conformité OUTPUT_FORMAT 100 % des appels overlays Polaris | — |
| **Nouveau** : rapport `.docx` généré et validé sur 1 mission test | — |

---

## 8. Décisions tranchées (en plus du V2.2)

1. **Zolabox** et **Zolacortex** = noms officiels des deux profils de déploiement.
2. **Une seule codebase ZolaOS** — pas de fork. Profil via env var.
3. **Polaris est un opérateur du pattern multi-tenant cabinet**, pas un cas unique. Le code reste générique.
4. **Les 8 pôles V2.2 sont préservés** — les "offres Polaris" sont des packagings commerciaux par-dessus.
5. **PII redaction = prérequis bloquant** pour les pôles sensibles (santé, RH, fiscal), pas une option.
6. **OUTPUT_FORMAT structuré** = obligatoire pour tous les overlays Polaris (profil Cortex).
7. **Apprentissage Fédéré** reste à concevoir, planifié Phase 4-5.
8. **Nouveau segment "Secteur Public + ONG"** intégré comme extension de GRC + Droit administratif (à venir).

---

## 9. Références

- Plan originel : [`ZOLAOS_MASTER_PLAN_V2.md`](./ZOLAOS_MASTER_PLAN_V2.md)
- Stratégie globale Polaris : [`Polaris_ZolaOS_Strategie_Globale.docx`](./Polaris_ZolaOS_Strategie_Globale.docx)
- Spec agent Fiscal : [`ZolaOS_Agent_Fiscalite_Ohada.docx`](./ZolaOS_Agent_Fiscalite_Ohada.docx)
- Spec agent RH : [`ZolaOS_Agent_Conformite_RH.docx`](./ZolaOS_Agent_Conformite_RH.docx)
- Architecture & vision produit : [`gemini-code-1779020165723.md`](./gemini-code-1779020165723.md)
- Rapport progression : [`docs/PHASE_1_REPORT.md`](./docs/PHASE_1_REPORT.md)
- Mémoires liées : `project_polaris_partnership.md`, `project_zolabox_zolacortex_topology.md`, `project_zolaos_vision.md`, `project_zero_trust_client_architecture.md`

---

## 11. ANNEXE — Architecture Zero Trust Client (révision 2026-05-18)

### 11.1. Contexte du pivot

La stratégie initiale de protection IP (section 4 et tasks #70-74) prévoyait quatre niveaux :
1. Séparation physique build box/cortex (FAIT)
2. Garde-fou applicatif sur les prompts cabinet (FAIT)
3. Obfuscation Cython/Nuitka
4. Chiffrement modèles + licence en ligne
5. TEE (Intel SGX, AMD SEV-SNP)

Une analyse approfondie des techniques de **reverse engineering assisté par IA en 2026** (Ghidra+LLM, decomp.ai, virtualisation custom type VMProtect/Themida) a montré que :

- La compilation simple Cython/Nuitka est cassée par les LLM en jours.
- VMProtect/Themida résistent mieux mais sont conçus pour C/C++, mal adaptés à un orchestrateur Python+FastAPI, et **ne protègent pas les prompts** qui doivent transiter en clair vers le LLM.
- Les attaques par **extraction de prompt LLM** (Carlini 2023, Zou 2024) volent les prompts via l'inférence, indépendamment de toute obfuscation de code.
- Le coût d'opportunité (6 mois × experts sécurité) pour un résultat partiel n'est pas justifié.

**Conclusion** : on ne peut pas vraiment protéger des actifs qu'on livre. Donc on ne les livre pas.

### 11.2. Principe

**Les actifs sensibles ne sont jamais déployés chez le client.** La Zolabox installée chez l'entreprise cliente ne contient :
- ✅ Les sous-agents génératifs V2.2 avec **prompts publics** uniquement
- ✅ Le pipeline RAG + données client (chiffrées at-rest standard)
- ✅ Un Llama-3-8B générique pour les usages locaux (prompts publics)
- ❌ **Aucun overlay Polaris**
- ❌ **Aucun prompt cabinet**
- ❌ **Aucun modèle fine-tuné Congo**
- ❌ **Aucun template de rapport `.docx` cabinet**

### 11.3. Flux d'une mission d'audit Polaris

```
1. Consultant Polaris crée une mission via POST /v1/cortex/missions (sur Cortex)
   → JWT mission émis, durée 1-3 h, scope_tags = ce que la mission peut interroger

2. Pendant la mission, le consultant utilise un overlay Polaris (ex: ZolaCortex-Conformite-RH)
   instancié CHEZ POLARIS (profil cortex obligatoire)

3. L'overlay appelle MissionClient.rag_search() qui POST sur /v1/box/rag/search
   de la Zolabox du client :
   - JWT mission vérifié côté Box (signature + DB + non expiré + non révoqué)
   - Intersection scope_tags appliquée (impossible de sortir du périmètre)
   - retrieve() local renvoie N chunks (déjà anonymisés via PII redaction
     pré-ingestion : tiers en hash FR_xxxxx, salaires en tranches, etc.)
   - Audit hash inviolable enregistré chez le client

4. La Zolabox renvoie au Cortex : uniquement les CHUNKS RAG ANONYMISÉS
   (pas de prompt cabinet impliqué côté Box, pas d'inférence LLM sur Box)

5. Le Cortex (chez Polaris) :
   - Reconstruit le prompt complet (prompt secret cabinet + chunks reçus + question)
   - Appelle son llama-server LOCAL (côté Polaris, GPU dédié)
   - Récupère le JSON OUTPUT_FORMAT structuré
   - Génère le rapport .docx via les templates cabinet
   - Remet le livrable au consultant

6. Mission terminée → JWT expire → accès Box révoqué automatiquement
```

### 11.4. Garanties

| Actif | Lieu de stockage | Accessible au client root ? |
|---|---|---|
| Prompts cabinet Polaris | Disque chez Polaris uniquement | ❌ Non |
| Modèles fine-tunés Congo (futurs) | Disque chez Polaris uniquement | ❌ Non |
| Templates rapport `.docx` cabinet | Disque chez Polaris uniquement | ❌ Non |
| llama-server tourant les overlays | Process chez Polaris uniquement | ❌ Non |
| Données brutes du client | Chez le client | ✅ Oui (c'est SES données) |
| Chunks RAG indexés du client | Chez le client | ✅ Oui |
| Chunks transitant pendant les missions | Transit Cortex → Box → réponse | Anonymisés via PII redaction |
| Code Python sous-agents V2.2 | Chez le client (image box) | ✅ Lisible (mais bonnes pratiques publiques) |

### 11.5. Argument commercial

Polaris peut dire à un client : *« Vos données ne quittent pas vos murs. Pendant nos missions d'audit, nous interrogeons votre Zolabox pour des extraits anonymisés ; nos méthodologies cabinet et nos modèles spécialisés restent strictement chez nous. Vous gardez un audit hash immuable et inviolable de chaque accès. »*

C'est plus défendable que « on a chiffré le code ».

### 11.6. Impact sur les tasks

- ✅ #70 (garde-fou applicatif) — déjà fait, conservé comme défense en profondeur
- ✅ #71 (strip box au build) — déjà fait, **central** à l'archi Zero Trust
- ⏳ #72 (obfuscation Nuitka) — conservée comme défense en profondeur sur le code générique restant
- ❌ #73 (chiffrement modèles + licence en ligne) — **fermée** (obsolète)
- ❌ #74 (TEE) — **fermée** (obsolète)
- ⏳ #75 (formalisation Zero Trust dans le code) — en cours
- ⏳ #76 (test E2E flux Zero Trust) — à faire

### 11.7. Mémoire de référence

`project_zero_trust_client_architecture.md` — détail technique complet de l'architecture.

---

## 12. ANNEXE — Modèle de licence (acté 2026-05-19)

### 12.1. Décision

ZolaOS adopte un modèle **open-core** :

- **Cœur public ZolaOS** sous **GNU Affero General Public License v3 ou ultérieure**
  (`SPDX-License-Identifier: AGPL-3.0-or-later`)
- **Composants propriétaires Polaris** (overlays cabinet, prompts secrets,
  templates rapports `.docx`, modèles fine-tunés Congo) restent **non distribués**
  (secret des affaires, protégé via l'archi Zero Trust)
- **Double licence commerciale** négociable pour les organisations qui ne
  peuvent pas se conformer à l'AGPL (contact : `licensing@polaris.cg`)

### 12.2. Pourquoi AGPL v3

| Critère | AGPL v3 |
|---|---|
| Protection contre fork commercial fermé | ✅ clause "use over network" §13 force la publication des modifs |
| Cohérence souveraineté & auditabilité | ✅ code livré au client = code lisible 100 % |
| Crédibilité d'éditeur sérieux | ✅ standard de GitLab CE, Sentry, Nextcloud, Mattermost |
| Compatibilité avec mode mission Polaris | ✅ les overlays ne sont pas distribués → clause AGPL non concernée |

Alternatives écartées :
- MIT/Apache 2.0 (trop permissif)
- GPL v3 sans Affero (ne protège pas l'usage réseau)
- Propriétaire pur (contredit souveraineté/auditabilité)

### 12.3. Llama-3 conservé

Décision : on garde **Llama-3 (8B + 70B)**. Conséquences :

- ✅ Pas de bascule de framework
- ⚠️ Attribution "Built with Llama" obligatoire dans la doc/UI client
- ⚠️ Tout modèle fine-tuné Congo (Phase 5+) reste sous Llama 3 Community License
- ⚠️ Pas de revendication de propriété exclusive sur les modèles dérivés
- ✅ Clause MAU >700M sans impact pour Polaris

Bascule possible vers Mistral 7B ou Qwen 2.5 (Apache 2.0) si la propriété exclusive des modèles devient critique.

### 12.4. Artefacts livrés à la racine du repo

| Fichier | Rôle |
|---|---|
| `LICENSE` | En-tête court + SPDX + référence + section composants propriétaires + double licence |
| `NOTICE` | Attribution Llama 3 + autres composants Apache 2.0 |
| `THIRD_PARTY_LICENSES.md` | Recensement exhaustif des deps avec leurs licences et obligations |
| `infra/scripts/fetch_full_license.sh` | Télécharge le texte AGPL v3 officiel depuis gnu.org dans `LICENSE.AGPL-3.0` |
| `pyproject.toml` | `license = AGPL-3.0-or-later` + classifiers PEP 621 |
| `README.md` | Badge + résumé du modèle open-core |

### 12.5. Démarches juridiques en parallèle

À mener avec un cabinet OHADA/numérique :

| Démarche | Organisme | Délai estimé |
|---|---|---|
| Dépôt marques **ZolaOS**, **Polaris**, **Zolabox**, **Zolacortex** | OAPI (Yaoundé) | 6 semaines |
| Enregistrement code source (preuve d'antériorité) | BCDA (Brazzaville) | 1-2 semaines |
| Rédaction **EULA Zolabox** + **DPA** (Loi 29-2019) + **Lettre de mission type** | Cabinet OHADA/numérique | Avant 1er pilote |
| **CGV Polaris** (juridiction CG Brazzaville) | Idem | Avant 1er pilote |
| Statut juridique Polaris (SARL OHADA ?) | Notaire + cabinet | Avant 1er client |

### 12.6. Mémoire de référence

`project_licensing_model.md` — décision détaillée et obligations.

