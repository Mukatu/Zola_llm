# Sourcing documentaire — Agent Pharmacology / Santé
**Schéma cible :** `rag_health`  
**Périmètre géographique :** République du Congo (Brazzaville) — PAS la RDC  
**Tags globaux :** `country:cg` · `module:pharmacology`  
**Politique PII :** NONE (données publiques non nominatives)  
**Date de sourcing :** 2026-07-03  
**Validation requise :** pharmacien habilité avant toute mise en production

---

## Corpus 1 — CIM-10 / ICD-10 (Classification Internationale des Maladies, 10e révision)

### 1A. CIM-10 via l'API OMS (icd.who.int) — voie principale recommandée 🟢

| Champ | Détail |
|---|---|
| **Intitulé exact** | ICD-10 / CIM-10 — Classification statistique internationale des maladies et des problèmes de santé connexes, 10e révision |
| **URL vérifiée** | https://icd.who.int/icdapi (portail API) |
| **Documentation API** | https://icd.who.int/docs/icd-api/APIDoc-Version2/ |
| **Format** | API REST JSON (multilingue, dont français) · ICD-10 versions 2008, 2010, 2016 disponibles |
| **Langue FR** | Supportée via header HTTP `Accept-Language: fr` — confirmé par la documentation v2 |
| **Version / Année** | ICD-10 2016 (dernière mise à jour disponible via API) |
| **Licence** | Licence non-commerciale de recherche OMS — Accords annuels obligatoires |
| **Conditions détaillées** | — Usage interne non-commercial, recherche et analyse statistique uniquement<br>— Rapport annuel à fournir à l'OMS dans les 30 jours suivant chaque année civile d'utilisation<br>— Non-exclusive, non-cessible, non-sous-licenciable<br>— Redistribution externe ou usage commercial : **non autorisé sans accord séparé**<br>— FAQ licence : https://cdn.who.int/media/docs/default-source/publishing-policies/copyright/who-faq-licensing-icd-10.pdf |
| **Inscription** | Gratuite — enregistrement sur https://icd.who.int/icdapi/Account/Register |
| **Volumétrie** | ~14 000+ codes diagnostics (estimation ; ICD-10 complet) |
| **Accessibilité** | Téléchargement direct via API après inscription — pas de CSV natif ; export structuré possible par appels successifs |
| **Tags supplémentaires** | `type:classification` |
| **Statut** | 🟢 **Accessible et vérifiée** |

**Point d'attention licence :** La licence ICD-10 OMS est strictement non-commerciale. Pour ZolaOS en tant que produit SaaS ou commercial, une négociation avec l'OMS est nécessaire, OU basculer sur CIM-11 (voir 1C).

---

### 1B. CIM-10 FR (adaptation ATIH, usage PMSI France) — voie secondaire 🟠

| Champ | Détail |
|---|---|
| **Intitulé exact** | CIM-10 FR 2021 à usage PMSI — Classification statistique internationale des maladies, 10e révision, adaptation France |
| **URL vérifiée** | https://www.atih.sante.fr/cim-10-fr-usage-pmsi (page portail) |
| **PDF** | https://www.atih.sante.fr/sites/default/files/public/content/3963/cim-10fr-2021.pdf |
| **Format ClaML (XML)** | Disponible sur https://www.atih.sante.fr/cim-10-fr-usage-pmsi-au-format-claml (accès 403 au moment du sourcing — à vérifier) |
| **Terminologie (ANS)** | https://smt.esante.gouv.fr/terminologie-cim-10/ |
| **Version / Année** | 2021 (intègre mises à jour OMS 2020 + modifications ATIH 2021) ; 2022 aussi disponible |
| **Contenu** | Versions française ET OMS distinguées par l'élément `variant` dans le ClaML |
| **Licence** | **Non précisée explicitement sur le site ATIH.** Adaptation à usage PMSI France — une demande formelle à l'ATIH est requise pour confirmer les droits de réutilisation hors PMSI (notamment dans une application IA africaine) |
| **Volumétrie** | ~14 000 codes (volumes 1 et 3 inclus dans le PDF de 600+ pages) |
| **Accessibilité** | PDF libre d'accès ; ClaML XML à confirmer (erreur 403) |
| **Tags supplémentaires** | `type:classification` · `source:france-atih` |
| **Statut** | 🟠 **Partiellement accessible — licence à clarifier avant usage** |

---

### 1C. CIM-11 (ICD-11) — alternative ouverte recommandée à terme 🟢

| Champ | Détail |
|---|---|
| **Intitulé exact** | ICD-11 — Classification internationale des maladies, 11e révision (OMS) |
| **URL vérifiée** | https://icd.who.int/icdapi |
| **Licence** | Creative Commons Attribution-NoDerivs 3.0 IGO (**CC BY-ND 3.0 IGO**) |
| **Conditions détaillées** | — Usage commercial **autorisé**<br>— Dérivés/adaptations des codes : **interdits**<br>— Attribution OMS obligatoire<br>— Inscription API gratuite<br>— Texte licence : https://icd.who.int/en/docs/icd11-license.pdf |
| **Langues** | 10 langues dont **français** (+ 25 traductions en cours) |
| **Format** | API REST JSON — feuilles de calcul, PDF, tables de correspondance dans la zone de téléchargement |
| **Version** | 2026 release (mise à jour annuelle) |
| **Volumétrie** | ~55 000 entités (codes + extensions) |
| **Accessibilité** | Inscription gratuite, téléchargement direct |
| **Tags supplémentaires** | `type:classification` · `source:who-icd11` |
| **Statut** | 🟢 **Recommandée pour usage production — licence ouverte** |

**Recommandation architecturale :** Privilégier **ICD-11** pour `rag_health` (licence CC BY-ND, français natif, API moderne). Conserver CIM-10 uniquement si des formulaires ou protocoles CG référencent explicitement les codes CIM-10.

---

## Corpus 2 — LNME (Liste Nationale des Médicaments Essentiels, République du Congo)

### 2A. LNME CG 7e édition 2016 (OMS AFRO) — seule version nationale disponible 🟠

| Champ | Détail |
|---|---|
| **Intitulé exact** | Liste nationale des médicaments essentiels du Congo, 7e édition — République du Congo (Brazzaville) |
| **URL vérifiée** | https://cdn.who.int/media/docs/default-source/essential-medicines/national-essential-medicines-lists-(neml)/afro_neml/congo_neml_2016.pdf |
| **Autorité émettrice** | Ministère de la Santé et de la Population, République du Congo |
| **Référencée par** | WHO AFRO Repository of National EMLs |
| **Format** | PDF (1,4 Mo) — pas de format tabulaire/CSV disponible |
| **Version / Année** | 7e édition — 2016 (publiée dans le référentiel WHO le 30 juillet 2024) |
| **Licence / Réutilisation** | Document gouvernemental public — pas de clause de licence explicite identifiée. Réutilisation dans un système IA national : à confirmer auprès du Ministère de la Santé CG (contact@sante.gouv.cg) |
| **Versions antérieures** | 1re éd. 1982 ; révisée 2000, 2004, 2006 (4e éd. avec 215 médicaments), puis 7e éd. 2016 |
| **Version récente (post-2016)** | **Aucune trouvée** dans le référentiel WHO, sur sante.gouv.cg, CAMEPS ou DPM Congo — Point de blocage (voir §4) |
| **Volumétrie** | À vérifier dans le PDF — ordre de grandeur : 200-400 médicaments (estimation basée sur les éditions précédentes) |
| **Accessibilité** | Téléchargement direct (URL vérifiée, fichier accessible) |
| **Tags supplémentaires** | `type:formulaire` · `source:msp-cg` |
| **Statut** | 🟠 **Accessible mais potentiellement obsolète (8 ans) — validation pharmacien impérative** |

---

### 2B. WHO EML 24e édition 2025 — repli non-national 🟢 (repli seulement)

> **IMPORTANT : Ce corpus est un REPLI. Il ne remplace pas la LNME nationale CG.** À utiliser uniquement en complément ou en attendant une LNME CG récente.

| Champ | Détail |
|---|---|
| **Intitulé exact** | WHO Model List of Essential Medicines — 24th Edition (2025) |
| **URL vérifiée** | https://www.who.int/groups/expert-committee-on-selection-and-use-of-essential-medicines/essential-medicines-lists |
| **Version électronique** | https://list.essentialmeds.org/ (eEML — base de données interrogeable) |
| **23e édition 2023 (PDF)** | https://www.who.int/publications/i/item/WHO-MHP-HPS-EML-2023.02 |
| **Format** | PDF + base eEML en ligne (interrogeable, pas de téléchargement CSV direct constaté) |
| **Contenu** | 1 200 recommandations, 591 médicaments + 103 équivalents thérapeutiques (23e éd.) ; 24e éd. mise à jour sept. 2025 |
| **Licence** | Document OMS — usage public libre ; conditions de réutilisation à confirmer via https://www.who.int/about/policies/publishing/copyright |
| **Accessibilité** | Téléchargement direct PDF ; eEML accessible sans inscription |
| **Tags supplémentaires** | `type:formulaire` · `source:who-eml` · `scope:non-national` |
| **Statut** | 🟢 **Accessible, licence ouverte** — mais **non-national : doit être clairement étiqueté comme repli** |

---

## 3. Plan d'ingestion — schéma `rag_health`

### CIM-10 / CIM-11

```
Source prioritaire  : CIM-11 via API WHO (CC BY-ND 3.0 IGO)
Source secondaire   : CIM-10 2016 via API WHO (licence non-commerciale, rapport annuel)
Schéma              : rag_health
Tags                : country:cg, module:pharmacology, type:classification, source:who-icd11
Chunking suggéré    : un chunk par code (code + libellé + description + hiérarchie parent)
Langue              : fr (header Accept-Language: fr)
PII                 : NONE
Fréquence MàJ       : annuelle (publication WHO)
Pré-requis          : inscription API icd.who.int (gratuit)
```

### LNME CG / WHO EML

```
Source nationale    : LNME CG 7e éd. 2016 (PDF WHO AFRO)
Repli non-national  : WHO EML 24e éd. 2025 (eEML)
Schéma              : rag_health
Tags (LNME CG)      : country:cg, module:pharmacology, type:formulaire, source:msp-cg
Tags (WHO EML)      : country:cg, module:pharmacology, type:formulaire, source:who-eml, scope:non-national
Chunking suggéré    : un chunk par entrée médicament (DCI + forme + dosage + classe ATC + indication)
Pipeline            : extraction PDF → OCR si nécessaire → normalisation → ingestion
PII                 : NONE
Validation requise  : pharmacien avant ingestion (données cliniques)
```

---

## 4. Points de blocage et actions requises

### Blocage majeur — LNME CG post-2016 introuvable

La recherche exhaustive (WHO AFRO repository, sante.gouv.cg, CAMEPS, DPM Congo, Santé Tropicale, WorldCat) n'a **pas permis de localiser une LNME CG plus récente que 2016**. Le référentiel WHO confirme que la version 2016 est la seule soumise par le Congo.

**Actions à mener :**
1. **Contacter directement** le Ministère de la Santé et de la Population CG : contact@sante.gouv.cg
2. **Contacter la DPM Congo** (Directorate of Pharmacy and Medicine) : infodpmcongo@dpmcongo.org · +242 06 630 03 23
3. **Contacter la CAMEPS** : info@cameps.cg · +242 05 510 00 89
4. **Contacter le Secrétariat EML OMS** : emlsecretariat@who.int (demander si une version post-2016 a été soumise mais non encore publiée)
5. Si aucune version récente n'existe, envisager de **travailler avec un pharmacien congolais** pour annoter/mettre à jour la version 2016 avant ingestion.

### Blocage secondaire — Licence ICD-10 pour usage commercial

Si ZolaOS est déployé en mode SaaS ou commercialisé, la licence non-commerciale OMS pour ICD-10 est incompatible. **Solution recommandée :** migrer vers CIM-11 (CC BY-ND 3.0 IGO, usage commercial autorisé).

### Blocage secondaire — Format LNME CG (PDF uniquement)

La LNME 2016 est disponible en PDF uniquement. Un pipeline OCR + extraction structurée sera nécessaire avant ingestion dans `rag_health`. Qualité de l'extraction à valider.

### À vérifier

- Licence de réutilisation du PDF LNME CG auprès du Ministère de la Santé CG (document gouvernemental, pas de clause explicite identifiée)
- Accès au format ClaML ATIH CIM-10 (erreur HTTP 403 lors du sourcing — à retenter ou contacter ATIH)
- Existence d'un catalogue CAMEPS structuré (1 500+ produits référencés selon leur site — potentiellement plus récent que la LNME 2016)

---

## 5. Synthèse — tableau de bord

| # | Source | Statut | Format | Licence | Blocage |
|---|---|---|---|---|---|
| 1A | CIM-10 via API WHO (FR) | 🟠 | API JSON | Non-commerciale OMS | Usage commercial interdit |
| 1B | CIM-10 FR ATIH 2021 | 🟠 | PDF + ClaML(?) | À clarifier | Hors périmètre PMSI |
| 1C | **CIM-11 via API WHO (FR)** | 🟢 | API JSON | CC BY-ND 3.0 IGO | Aucun — **RECOMMANDÉE** |
| 2A | **LNME CG 7e éd. 2016** | 🟠 | PDF | Gouvernemental (à confirmer) | Obsolescence + format PDF |
| 2B | WHO EML 24e éd. 2025 (repli) | 🟢 | PDF + eEML | OMS (usage public) | Non-national — repli seulement |

**Verdict global :**
- CIM : **CIM-11** est la voie recommandée (🟢) — licence ouverte, français natif, API moderne.
- LNME : **blocage partiel** (🟠) — la version 2016 est accessible mais potentiellement obsolète ; aucune version plus récente n'est localisable via des sources ouvertes. Contact direct avec les autorités CG est indispensable avant d'utiliser ce corpus en production.
- **Validation par un pharmacien** est obligatoire pour les deux corpus avant tout déploiement (directive projet).

---

*Sources consultées : OMS/WHO (icd.who.int, cdn.who.int, who.int/standards), ATIH (atih.sante.fr), LIRMM BioPortal (bioportal.lirmm.fr), Ministère Santé CG (sante.gouv.cg), DPM Congo (dpmcongo.org), CAMEPS (cameps.cg), Santé Tropicale (santetropicale.com), WHO AFRO nEML repository.*
