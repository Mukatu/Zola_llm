# Sourcing documentaire — Jurisprudence & Doctrine
## ZolaOS · République du Congo (Brazzaville) · Périmètre OHADA

> **Date de recherche :** 2026-07-03  
> **Périmètre géographique :** République du Congo (CG), droit OHADA applicable  
> **Usage cible :** Ingestion RAG dans le schéma `rag_legal` de ZolaOS  
> **Langue de travail :** Français  

---

## Table des matières

1. [Corpus 1 — Jurisprudence CCJA (OHADA)](#corpus-1--jurisprudence-ccja-ohada)
2. [Corpus 2 — Jurisprudence nationale Cour Suprême du Congo](#corpus-2--jurisprudence-nationale-cour-suprême-du-congo)
3. [Corpus 3 — Doctrine administrative / DGID](#corpus-3--doctrine-administrative--dgid)
4. [Discipline de tagging et schéma d'ingestion](#discipline-de-tagging-et-schéma-dingestion)
5. [Synthèse et risques](#synthèse-et-risques)

---

## Corpus 1 — Jurisprudence CCJA (OHADA)

### Source 1.A — HuggingFace : `Maathis-com/ohada-ccja-corpus`

| Champ | Valeur |
|---|---|
| **Intitulé** | OHADA-CCJA Court Decisions Corpus |
| **URL** | https://huggingface.co/datasets/Maathis-com/ohada-ccja-corpus |
| **Éditeur** | Maathis (Foutse Yuehgoh) |
| **Format** | Parquet (Hugging Face Datasets) |
| **Volumétrie** | **4 059 décisions uniques** (1997–2023, 26 ans de jurisprudence CCJA) |
| **Licence** | **CC-BY 4.0** (les décisions CCJA sont des documents publics ; la valeur ajoutée structurée est sous CC-BY) |
| **Champs disponibles (17 colonnes)** | `case_id`, `case_number`, `date`, `year`, `legal_domain` (16 catégories), `case_type`, `jurisdiction`, `formation`, `plaintiff`, `defendant`, `articles_cited`, `dispute_summary`, `reasoning`, `ruling`, `full_text`, `source` |
| **Période** | 1997–2023 |
| **Accessibilité** | Public, téléchargement direct via HuggingFace Hub |
| **PII** | Aucune (données judiciaires publiques) |

**Statut : 🟢 PRIORITAIRE**

**Atouts :**
- Corpus le plus structuré disponible en open data pour la CCJA
- 17 colonnes dont `dispute_summary`, `reasoning`, `ruling` : idéal pour RAG ciblé
- Licence CC-BY 4.0 sans ambiguïté : attribution requise, usage commercial et IA autorisés
- Format Parquet natif, directement ingérable

**Risques :**
- Couvre 1997–2023 uniquement : les décisions 2024–2026 sont absentes
- Auteur indépendant (Maathis), non institutionnel : vérifier la fidélité au texte source
- Validation juriste OHADA obligatoire avant toute production

**Écosystème connexe (même auteur) :**

| Dataset | URL | Description | Licence |
|---|---|---|---|
| `ohada-actes-uniformes` | https://huggingface.co/datasets/Maathis-com/ohada-actes-uniformes | 9 Actes Uniformes, 3 126 articles, graphe législatif | CC-BY 4.0 |
| `ohada-ccja-graph` | https://huggingface.co/datasets/Maathis-com/ohada-ccja-graph | Graphe cas-loi : 11 131 nœuds, 33 408 arêtes | À vérifier |
| `ohada_graph` | https://huggingface.co/datasets/Maathis-com/ohada_graph | Graphe général | À vérifier |
| `uriel/Maathis_Ohada_dataset` | https://huggingface.co/datasets/uriel/Maathis_Ohada_dataset | Miroir partiel (1 180 lignes), licence non spécifiée | ⚠️ À vérifier |

---

### Source 1.B — Juricaf (AHJUCAF) — Décisions CCJA

| Champ | Valeur |
|---|---|
| **Intitulé** | Base Juricaf — Jurisprudence CCJA |
| **URL** | https://juricaf.org/recherche/+/facet_pays:OHADA |
| **Éditeur** | AHJUCAF (Association des Hautes Juridictions de Cassation francophones), soutenu par l'OIF |
| **Format** | HTML (pages web), API non publique — export XML sur demande |
| **Volumétrie** | **1 325 décisions CCJA** indexées sur Juricaf |
| **Licence** | **ODbL 1.0** (Open Database Licence) — accès libre ; usage commercial autorisé sous conditions d'attribution et partage à l'identique |
| **Conditions de réutilisation** | Réutilisation autorisée sous ODbL 1.0. Export XML structuré disponible sur demande au secrétariat AHJUCAF. Droit sui generis AHJUCAF sur la base (structure). |
| **Accessibilité** | Accès web gratuit ; scraping possible mais contacter AHJUCAF pour export massif |
| **PII** | Aucune (décisions publiques) |

**Statut : 🟠 SECONDAIRE** (complément utile, volumétrie moindre que 1.A)

**Atouts :**
- Licence ODbL claire et reconnue
- Inclut des décisions CCJA tenues en séance à Brazzaville (ex. nov. 2013)
- Plateforme institutionnelle stable (depuis 2005)

**Risques :**
- 1 325 décisions seulement vs 4 059 sur HuggingFace : recouvrement partiel
- Format HTML uniquement en accès direct : structuration requise avant ingestion
- ODbL impose "share-alike" sur la base dérivée — à documenter dans l'architecture ZolaOS
- Pas de disposition explicite sur l'entraînement IA : contacter AHJUCAF

**Contact export XML :** Via formulaire https://juricaf.org/contact

---

### Source 1.C — OHADA.com (UNIDA) — Base jurisprudentielle

| Champ | Valeur |
|---|---|
| **Intitulé** | Jurisprudence OHADA — OHADA.com |
| **URL** | https://www.ohada.com/documentation/jurisprudence.html |
| **Éditeur** | UNIDA (Association pour l'Unification du Droit en Afrique) |
| **Format** | HTML, téléchargement PDF individuel gratuit |
| **Volumétrie** | **4 126 décisions** (dont ~1 147 CCJA + décisions cours nationales OHADA) |
| **Licence** | ⚠️ **©2026 — Tous droits réservés** — Aucune licence ouverte déclarée |
| **Accessibilité** | Accès web gratuit, téléchargement PDF gratuit par décision |
| **PII** | Aucune |

**Statut : 🟠 COMPLÉMENTAIRE** (utile pour enrichissement ponctuel, pas d'ingestion en masse)

**Atouts :**
- Décisions commentées par des spécialistes OHADA (valeur doctrinale)
- Inclut décisions Brazzaville : 56 décisions filtrées sur `ville=brazzaville`
- Large couverture nationale (17 États membres)

**Risques :**
- **Absence de licence ouverte : "Tous droits réservés"** — risque juridique élevé pour ingestion RAG automatisée
- Pas de CGU explicites pour l'usage IA — contact UNIDA obligatoire avant ingestion
- Format PDF non structuré : extraction NLP requise
- Pas d'API ni export en masse

**Action requise :** Contacter UNIDA (ohada.com) pour demander une autorisation explicite de réutilisation à des fins de RAG interne.

---

### Source 1.D — ohada.org (Secrétariat Permanent CCJA) — Recueils officiels

| Champ | Valeur |
|---|---|
| **Intitulé** | Recueil de Jurisprudence CCJA (numéros N°1–N°36) |
| **URL** | https://www.ohada.org/en/ohada-case-law/ |
| **Éditeur** | Secrétariat Permanent OHADA / CCJA |
| **Format** | PDF (recueils numérotés) — certains payants depuis N°27 (via thebookedition.com) |
| **Volumétrie** | Non publiée globalement. Recueil N°36 le plus récent (2026) |
| **Licence** | ⚠️ Pas de licence ouverte déclarée. Document institutionnel officiel. |
| **Accessibilité** | Accès partiel — anciens numéros libres, récents payants |
| **PII** | Aucune |

**Statut : 🟠 RÉFÉRENCE** (source officielle pour validation, pas pour ingestion en masse)

**Atouts :**
- Source officielle CCJA : fait foi pour valider la fidélité des autres corpus
- Bibliothèque numérique : https://biblio.ohada.org/

**Risques :**
- Numéros récents (N°27+) payants
- Absence de licence ouverte
- Format PDF non structuré

---

### Source 1.E — Jurisprudence-OHADA.com (IDEF / SIRE OHADA)

| Champ | Valeur |
|---|---|
| **Intitulé** | Jurisprudence-OHADA — Base IDEF |
| **URL** | https://jurisprudence-ohada.com/ |
| **Éditeur** | IDEF (Institut pour le Développement de l'Expertise Juridique) / SIRE OHADA |
| **Format** | HTML (résumés + décisions) |
| **Volumétrie** | Non publiée (volumétrie non accessible en page d'accueil) |
| **Licence** | ⚠️ Non spécifiée |
| **Accessibilité** | Apparemment libre, sans inscription obligatoire visible |
| **PII** | Aucune |

**Statut : 🔴 À VÉRIFIER** (licence absente, volumétrie inconnue)

**Action requise :** Contacter jurisprudence@sire-ohada.com pour demander volumétrie et conditions de réutilisation.

---

## Corpus 2 — Jurisprudence nationale Cour Suprême du Congo

### Source 2.A — Juricaf — Cour Suprême du Congo (RC)

| Champ | Valeur |
|---|---|
| **Intitulé** | Jurisprudence nationale — Congo (Brazzaville), toutes juridictions |
| **URL** | https://juricaf.org/recherche/+/facet_pays:Congo |
| **Éditeur** | AHJUCAF (voir Source 1.B) |
| **Format** | HTML + export XML sur demande |
| **Volumétrie totale Congo** | **131 décisions** réparties comme suit : |
| — Cour suprême | 60 décisions (principalement 2022–2024, Première Chambre Civile) |
| — Cour d'appel | 50 décisions |
| — Tribunal de commerce de Brazzaville | 21 décisions (dont certaines dès 2009) |
| **Licence** | **ODbL 1.0** (même conditions que Source 1.B) |
| **Accessibilité** | Accès web gratuit ; export XML sur demande AHJUCAF |
| **Chambres visibles** | Première Chambre Civile confirmée ; Chambre pénale (déc. 2005) ; Chambres réunies (déc. 2002) ; chambre commerciale (présence à vérifier via filtres Juricaf) |
| **PII** | Aucune |

**Statut : 🟠 UTILE** (faible volumétrie mais données réelles et structurées)

**Atouts :**
- Seule source structurée avec licence claire pour la jurisprudence nationale CG
- Inclut le Tribunal de commerce de Brazzaville — pertinent pour litiges OHADA locaux
- Mise à jour périodique (décisions jusqu'en mars 2024 confirmées)

**Risques :**
- **Volumétrie très faible (131 décisions total)** : corpus insuffisant seul pour le RAG
- Chambres sociale et commerciale de la Cour Suprême sous-représentées voire absentes
- Format HTML uniquement : preprocessing nécessaire
- ODbL share-alike (voir Source 1.B)

**Stratégie recommandée :** Utiliser comme corpus d'ancrage local CG, combiné avec la jurisprudence CCJA pour l'enrichissement.

---

### Source 2.B — OHADA.com — Brazzaville (filtré)

| Champ | Valeur |
|---|---|
| **Intitulé** | OHADA.com — Jurisprudence Brazzaville |
| **URL** | https://www.ohada.com/documentation/jurisprudence.html?ville=brazzaville |
| **Éditeur** | UNIDA (voir Source 1.C) |
| **Volumétrie** | **56 décisions** (essentiellement Cour d'Appel de Brazzaville, 2012–2013) |
| **Licence** | ⚠️ Tous droits réservés (voir Source 1.C) |
| **Format** | HTML + PDF individuel |

**Statut : 🔴 SOUS CONDITION** (licence non ouverte, faible volumétrie)

---

### Source 2.C — Site officiel Cour Suprême CG

| Champ | Valeur |
|---|---|
| **Intitulé** | Cour Suprême de la République du Congo — site officiel |
| **URL** | https://gouvernement.cg/la-cour-supreme/ |
| **Éditeur** | Gouvernement du Congo |
| **Volumétrie** | Non publiée (pas de base de données en ligne identifiée) |
| **Licence** | ⚠️ À vérifier |
| **Accessibilité** | Page institutionnelle uniquement — aucune base jurisprudentielle accessible en ligne identifiée lors de la recherche |

**Statut : 🔴 LACUNE** (pas de base jurisprudentielle publique numérique identifiée)

**Action requise :** Contacter directement le greffe de la Cour Suprême (BP 597, Brazzaville, tél. +242 814517) ou M. Armand Noël MOUHINGOU (contact AHJUCAF) pour demander accès à des décisions numériques.

---

## Corpus 3 — Doctrine administrative / DGID

### Source 3.A — Ministère des Finances du Congo — Portal documentaire

| Champ | Valeur |
|---|---|
| **Intitulé** | Documentation fiscale — Ministère des Finances, Budget et Portefeuille Public |
| **URL principale** | https://www.finances.gouv.cg/fr/documentation |
| **URL DGID** | https://www.finances.gouv.cg/fr/direction-g%C3%A9n%C3%A9rale-des-imp%C3%B4ts-et-des-domaines |
| **Éditeur** | République du Congo — Ministère des Finances |
| **Format** | PDF (téléchargement libre sur le portail) |
| **Documents identifiés** | CGI Tome I (PDF, mis à jour 28/03/2021) ; Lois de finances annuelles ; Décrets, arrêtés, circulaires, notes de service ; Conventions fiscales internationales |
| **Licence** | ⚠️ Textes officiels gouvernementaux — domaine public présumé mais non déclaré explicitement |
| **Accessibilité** | Accès libre sur le portail, téléchargement direct PDF |
| **PII** | Aucune |

**Statut : 🟠 UTILE** (textes de référence indispensables, mais doctrine administrative stricto sensu limitée)

**Documents clés disponibles :**
- Code Général des Impôts Tome I : https://www.finances.gouv.cg/sites/default/files/documents/CGI%20Tome%20I.pdf
- CGI 2025 (mis à jour par loi n°47-2024 du 30 déc. 2024) — édition LGDJ disponible commercialement
- Recueil des textes fiscaux 2023 (Unicongo/Cabinet Sutter & Pearce) : https://www.unicongo.cg/wp-content/uploads/2023/10/Recueil-des-textes-fiscaux-a-jour-avec-LF-2023.pdf
- Dispositions fiscales Loi de Finances 2025 (commentaire Deloitte) : https://blog.avocats.deloitte.fr/congo-brazzaville-les-principales-mesures-importantes-de-la-loi-de-finances-pour-2025/

**Atouts :**
- Textes officiels gratuits en PDF
- CGI structuré en deux tomes (impôts directs + enregistrement/timbre)
- Loi de finances 2025 (loi n°47-2024) disponible

**Risques :**
- **Absence de rescrits fiscaux (prises de position formelles) en ligne** : la DGID du Congo ne publie pas de doctrine administrative formalisée à l'instar du BOFIP français
- CGI Tome I disponible en ligne daté de 2021 — version 2024/2025 nécessite achat de l'édition LGDJ
- Site impots-gouv.cg inaccessible lors de la recherche (timeout DNS)
- Circulaires et instructions internes non publiées en ligne de manière systématique

---

### Source 3.B — DGID — Site officiel (inaccessible à la vérification)

| Champ | Valeur |
|---|---|
| **Intitulé** | DGID — Direction Générale des Impôts et des Domaines |
| **URL** | http://impots-gouv.cg/ |
| **Statut lors de la recherche** | ⚠️ **INACCESSIBLE** (timeout DNS lors de la vérification le 2026-07-03) |
| **Contenu attendu** | Formulaires fiscaux, communications, instructions |

**Statut : 🔴 À VÉRIFIER** (URL à re-tester ultérieurement)

---

### Source 3.C — Vulgarisation fiscale et doctrine commentée (sources tierces)

| Champ | Valeur |
|---|---|
| **Intitulé** | Recueil textes fiscaux 2023 (Unicongo / Sutter & Pearce) |
| **URL** | https://www.unicongo.cg/wp-content/uploads/2023/10/Recueil-des-textes-fiscaux-a-jour-avec-LF-2023.pdf |
| **Éditeur** | Unicongo (Union patronale congolaise) + Cabinet Sutter & Pearce |
| **Format** | PDF |
| **Volumétrie** | Recueil compilé (LF 2023 incluse) |
| **Licence** | ⚠️ Document patronal — droits à vérifier pour réutilisation RAG |

**Statut : 🟠 COMPLÉMENTAIRE** (utile pour contexte, droits à clarifier)

---

## Discipline de tagging et schéma d'ingestion

### Principe fondamental

> **Une décision de justice n'est pas une norme.** Le texte de loi (Acte Uniforme OHADA, CGI, loi nationale) **prime toujours**. La jurisprudence *illustre* l'application d'une norme dans un contexte factuel ; elle ne la remplace pas. Tout résultat produit par ZolaOS sur la base de jurisprudence doit porter une mention explicite de ce statut.

### Schéma de tags obligatoires

```yaml
# Champs obligatoires pour toute pièce du schéma rag_legal
type:          "jurisprudence" | "doctrine" | "texte_legal"
country:       "cg"   # République du Congo — TOUJOURS pour le périmètre ZolaOS
juridiction:   string  # ex. "CCJA", "Cour_Suprême_CG", "Cour_Appel_Brazzaville", 
                       #     "Tribunal_Commerce_Brazzaville", "DGID"
date:          "YYYY-MM-DD"  # date de la décision ou du texte
reference:     string  # numéro d'arrêt, numéro de loi, référence OHADATA, etc.
legal_domain:  string  # ex. "droit_commercial", "droit_social", "droit_fiscal",
                       #     "droit_civil", "acte_uniforme_AUPC", "acte_uniforme_AUS"
source_url:    string  # URL vérifiée de la source originale
licence:       string  # ex. "CC-BY-4.0", "ODbL-1.0", "tous_droits_reserves", "domaine_public"
validated:     boolean # false par défaut ; true uniquement après validation juriste OHADA
```

### Tags complémentaires recommandés

```yaml
pii:           false    # Les décisions judiciaires publiques ne contiennent pas de PII identifiantes
language:      "fr"
acte_uniforme: string   # ex. "AUPC", "AUS", "AUC", "AUSCGIE" (pour la jurisprudence OHADA)
instance:      string   # "premier_degre" | "appel" | "cassation" | "arbitrage"
ohada_member:  boolean  # true si décision rendue dans un État membre OHADA
```

### Séparation `type:jurisprudence` vs `type:doctrine` vs `type:texte_legal`

| Type | Définition | Exemples | Poids interprétatif |
|---|---|---|---|
| `texte_legal` | Norme opposable (loi, décret, Acte Uniforme) | CGI, Actes Uniformes OHADA, Constitution CG | **Prioritaire — fait foi** |
| `jurisprudence` | Décision de justice appliquant une norme | Arrêt CCJA, décision Cour Suprême CG | Illustratif — contexte d'application |
| `doctrine` | Interprétation administrative ou académique | Instructions DGID, circulaires, commentaires UNIDA | Indicatif — aide à l'interprétation |

### Règle de présentation dans les réponses ZolaOS

Toute réponse de l'agent juridique qui s'appuie sur de la jurisprudence DOIT :
1. Citer le `texte_legal` applicable en premier
2. Mentionner la jurisprudence comme **illustration** uniquement
3. Porter la mention : *"Cette analyse s'appuie sur des décisions de justice à titre illustratif. Le texte de loi applicable prime. Une validation par un juriste qualifié en droit OHADA est requise avant toute décision."*

### Plan d'ingestion — Schéma `rag_legal`

```sql
-- Table principale (PostgreSQL)
CREATE TABLE rag_legal (
    id          UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    type        TEXT NOT NULL CHECK (type IN ('texte_legal', 'jurisprudence', 'doctrine')),
    country     TEXT NOT NULL DEFAULT 'cg',
    juridiction TEXT,
    date        DATE,
    reference   TEXT,
    legal_domain TEXT,
    titre       TEXT,
    contenu     TEXT NOT NULL,
    source_url  TEXT,
    licence     TEXT,
    validated   BOOLEAN DEFAULT FALSE,
    pii         BOOLEAN DEFAULT FALSE,
    language    TEXT DEFAULT 'fr',
    embedding   VECTOR(1024),  -- bge-m3 (Phase 2 ZolaOS)
    metadata    JSONB,
    created_at  TIMESTAMPTZ DEFAULT NOW()
);

-- Index recommandés
CREATE INDEX idx_rag_legal_type    ON rag_legal(type);
CREATE INDEX idx_rag_legal_domain  ON rag_legal(legal_domain);
CREATE INDEX idx_rag_legal_date    ON rag_legal(date);
CREATE INDEX idx_rag_legal_country ON rag_legal(country);
CREATE INDEX idx_rag_legal_embed   ON rag_legal USING ivfflat (embedding vector_cosine_ops);
```

### Ordre de priorité d'ingestion recommandé

1. **P0 — Textes légaux** : CGI CG 2024/2025 + 9 Actes Uniformes OHADA (Source `ohada-actes-uniformes`, CC-BY 4.0)
2. **P1 — Jurisprudence CCJA structurée** : `Maathis-com/ohada-ccja-corpus` (4 059 décisions, CC-BY 4.0)
3. **P2 — Jurisprudence nationale CG** : Juricaf Congo (131 décisions, ODbL 1.0)
4. **P3 — Doctrine administrative** : Circulaires/instructions DGID (après autorisation / vérification domaine public)
5. **P4 — Enrichissement** : OHADA.com + Jurisprudence-OHADA.com (sous réserve d'autorisation)

---

## Synthèse et risques

### Tableau récapitulatif

| # | Source | Type | Volumétrie | Licence | Statut |
|---|---|---|---|---|---|
| 1.A | HuggingFace `ohada-ccja-corpus` | Jurisprudence CCJA | **4 059 décisions** | CC-BY 4.0 | 🟢 |
| 1.B | Juricaf — CCJA | Jurisprudence CCJA | 1 325 décisions | ODbL 1.0 | 🟠 |
| 1.C | OHADA.com (UNIDA) | Jurisprudence CCJA + nationale | 4 126 décisions | ©️ Tous droits réservés | 🟠 |
| 1.D | ohada.org (recueils) | Jurisprudence CCJA officielle | ~36 numéros | Non déclarée | 🟠 |
| 1.E | Jurisprudence-OHADA.com | Jurisprudence CCJA | Inconnue | Non déclarée | 🔴 |
| 2.A | Juricaf — Congo national | Jurisprudence CG | **131 décisions** | ODbL 1.0 | 🟠 |
| 2.B | OHADA.com Brazzaville | Jurisprudence CG | 56 décisions | ©️ Tous droits réservés | 🔴 |
| 2.C | Cour Suprême CG officielle | Jurisprudence CG | Non publié | À vérifier | 🔴 |
| 3.A | finances.gouv.cg | Doctrine / textes fiscaux | CGI + circulaires | Domaine public (présumé) | 🟠 |
| 3.B | impots-gouv.cg (DGID) | Doctrine administrative | Inconnu | À vérifier | 🔴 |
| 3.C | Unicongo / Sutter & Pearce | Doctrine commentée | Recueil 2023 | À clarifier | 🟠 |

### Sources 🟢 : Action immédiate possible

- **`Maathis-com/ohada-ccja-corpus`** : Télécharger via `datasets.load_dataset("Maathis-com/ohada-ccja-corpus")`, ingérer avec tags `type:jurisprudence`, `country:cg`, `juridiction:CCJA`, `licence:CC-BY-4.0`, `validated:false`.
- **`Maathis-com/ohada-actes-uniformes`** : Même procédure pour `type:texte_legal` — 3 126 articles des Actes Uniformes.

### Sources 🟠 : Actions à engager

| Source | Action |
|---|---|
| Juricaf (CCJA + Congo) | Contacter AHJUCAF pour export XML en masse. Documenter la contrainte ODbL share-alike dans l'architecture ZolaOS. |
| OHADA.com | Contacter UNIDA pour demander une autorisation explicite de réutilisation RAG interne. |
| finances.gouv.cg | Télécharger CGI Tome I PDF (2021) + compléter avec édition 2025. Vérifier si les lois de finances annuelles sont sous domaine public officiel. |
| Unicongo/Sutter & Pearce | Demander autorisation à Unicongo pour usage RAG interne. |

### Sources 🔴 : Lacunes critiques identifiées

1. **Doctrine administrative DGID** : Absence complète de rescrits/prises de position formelles en ligne. Le Congo n'a pas de BOFIP équivalent. Contournement : utiliser les circulaires téléchargeables + compléter par droit comparé OHADA (Bénin a publié sa doctrine fiscale 2023 — cf. recherche).

2. **Jurisprudence nationale CG — Chambres sociale et commerciale** : Très faible couverture sur Juricaf (60 décisions Cour Suprême, principalement civile). Contacter le greffe de la Cour Suprême CG directement.

3. **Jurisprudence post-2023** : Ni HuggingFace ni Juricaf ne couvrent 2024–2026 de manière complète. Mettre en place une veille CCJA via RSS Juricaf.

### Principaux risques licence

| Risque | Sources concernées | Mitigation |
|---|---|---|
| "Tous droits réservés" sans licence ouverte | OHADA.com (1.C), OHADA.org (1.D), Jurisprudence-OHADA.com (1.E) | Ne pas ingérer sans autorisation écrite préalable |
| ODbL share-alike | Juricaf (1.B, 2.A) | Documenter l'obligation de redistribution si la base dérivée est partagée |
| Absence de clause IA dans ODbL 1.0 | Juricaf | Contacter AHJUCAF pour clarification usage entraînement/inférence |
| Textes officiels CG : domaine public non formalisé | finances.gouv.cg (3.A) | Utiliser les textes publiés au Journal Officiel CG (présomption domaine public) — vérifier loi sur l'accès à l'information |
| Corpus non audité par juriste | Tous | **Validation juriste OHADA obligatoire avant mise en production** |

### Recommandation de validation

> Avant toute mise en production de l'agent juridique ZolaOS, un **juriste qualifié en droit OHADA** doit :
> 1. Auditer un échantillon représentatif du corpus ingéré (50 décisions minimum)
> 2. Vérifier la fidélité du corpus HuggingFace aux décisions sources officielles
> 3. Valider le schéma de tagging `type:jurisprudence` vs `type:texte_legal`
> 4. Confirmer que les réponses de l'agent respectent la hiérarchie des normes
> 5. Mettre à `validated:true` uniquement les pièces vérifiées

---

*Document généré le 2026-07-03 — Ne pas commettre — Recherche web (environ 20 requêtes effectuées)*
