# Sourcing documentaire — ONG / Bailleurs (ZolaOS · République du Congo)

> Généré le 2026-07-03 · Agent : sourcing documentaire ZolaOS  
> Périmètre : agents `projets_ong` (schéma `rag_erp`) et `reporting_bailleurs` (placeholder `rag_legal` → futur `rag_grc`/`rag_ong`)  
> Pays cible : **République du Congo — Brazzaville** · Les standards internationaux sont signalés comme tels  
> PII : NONE (documents publics uniquement)

---

## Légende

| Symbole | Signification |
|---------|---------------|
| 🟢 | Accessible librement, licence claire ou open data, ingestion directe possible |
| 🟠 | Accessible mais licence à clarifier, format sous-optimal, ou version non authoritative |
| 🔴 | Inaccessible / payant / introuvable en accès direct / à vérifier manuellement |

---

## CORPUS 1 — Standards bailleurs / Redevabilité

> **Agent cible** : `reporting_bailleurs`  
> **Schéma RAG** : `rag_legal` (placeholder — futur `rag_grc` / `rag_ong`)  
> **Tags** : `country:cg` + `module:reporting_bailleurs`  
> **Note** : ces standards sont internationaux, non spécifiques à la République du Congo

---

### 1.1 IATI — Standard XML (International Aid Transparency Initiative)

| Champ | Détail |
|-------|--------|
| **Intitulé** | IATI Standard v2.03 — Schémas XML + documentation de référence |
| **URL principale** | https://iatistandard.org/en/iati-standard/203/ |
| **URL schémas XSD** | https://github.com/IATI/IATI-Schemas (branche `version-2.03`) |
| **URL version FR** | https://iatistandard.org/fr/iati-standard/203/ |
| **Format** | Documentation HTML en ligne + schémas XSD téléchargeables via GitHub |
| **Année / version** | v2.03 (publiée 2018, version courante en 2026) |
| **Langue** | Anglais (documentation principale) / Français (listes de codes uniquement, traduit 2018 avec appui du Canada) |
| **Licence / réutilisation** | Open data : IATI recommande CC-BY ou CC0 pour les données publiées. Le standard lui-même indique « data is freely available and open to anyone » — licence exacte du dépôt GitHub à confirmer (fichier LICENSE présent, contenu non visible) |
| **Accessibilité** | Libre, sans authentification |
| **Statut** | 🟢 |
| **Notes ingestion** | Schémas XSD : `git clone https://github.com/IATI/IATI-Schemas`. Documentation HTML : crawler iatistandard.org/fr/iati-standard/203/. NB : le registre IATI a été relancé en décembre 2025. |

---

### 1.2 IATI — Bulk Data Service (données publiées)

| Champ | Détail |
|-------|--------|
| **Intitulé** | IATI Bulk Data Service — fichiers XML de toutes les organisations publiantes |
| **URL** | https://bulk-data.iatistandard.org/ |
| **Format** | ZIP contenant fichiers XML (activités + organisations) + métadonnées JSON |
| **Année / version** | Continu (mis à jour en temps réel) |
| **Langue** | Anglais (structuré XML) |
| **Licence / réutilisation** | Open data (conditions de licence variables par organisation publiante — CC-BY, CC0, ou PDDL pour les membres IATI) |
| **Accessibilité** | Libre, sans authentification |
| **Statut** | 🟢 |
| **Notes ingestion** | Utile pour constituer des exemples de rapports de bailleurs (UE, AFD, USAID, etc.) sur des projets en zone OHADA / Afrique centrale. Filtrer par `recipient-country/@code = "CG"` pour la République du Congo. |

---

### 1.3 PRAG — Guide pratique des procédures contractuelles UE (EuropeAid / INTPA)

| Champ | Détail |
|-------|--------|
| **Intitulé** | Practical Guide to contract procedures for EU external actions (PRAG) |
| **URL officielle CE** | https://ec.europa.eu/europeaid/funding/about-procurement-contracts/procedures-and-practical-guide-prag_en |
| **URL newsroom INTPA** | https://ec.europa.eu/newsroom/intpa/items/909208/en |
| **URL e-learning FR** | https://learning.europa.eu (cours ID 159 — version française 2025) |
| **URL PDF anglais 2025** | https://ipa-bgrs.mrrb.bg/sites/default/files/documents/2025-02/PRAG_2025_full_version_en.pdf (264 pages, modifié jan. 2025 — à vérifier) |
| **URL ePRAG 2021 FR** | https://intpa-econtent-public.s3.eu-west-1.amazonaws.com/ePrag/2021.0/ePRAG_public_full_fr.pdf |
| **Format** | PDF (version complète anglaise 2025) + cours e-learning en ligne (FR/EN) |
| **Année / version** | Version 2025 (mise à jour jan. 2025, alignement avec le Règlement Financier 2024) |
| **Langue** | **Anglais** (version faisant autorité). Traduction française automatique disponible pour information uniquement — version éditée disponible uniquement jusqu'à l'édition 2021. |
| **Licence / réutilisation** | Document public de la Commission européenne — réutilisation libre sous réserve de mention de source (politique © CE). Pas de licence Creative Commons explicite. |
| **Accessibilité** | Libre (PDF anglais 2025 disponible) ; version FR éditée uniquement jusqu'à 2021 |
| **Statut** | 🟠 |
| **Notes ingestion** | Pour `reporting_bailleurs` : privilégier l'ePRAG 2021 FR (version éditée) + compléter avec version anglaise 2025 pour les mises à jour (passation électronique, eSubmission). Sections clés : marchés de services, subventions (grants), clauses de redevabilité. |

---

### 1.4 OCDE-CAD — Normes et critères d'évaluation de l'aide

| Champ | Détail |
|-------|--------|
| **Intitulé** | Normes du CAD pour une évaluation de qualité (CAD/OCDE) |
| **URL document FR** | https://www.oecd.org/fr/cad/evaluation/37854181.pdf (**403 Forbidden** au moment du sourcing — à vérifier) |
| **URL miroir accessible** | https://consult.africa/wp-content/uploads/2024/09/37854181.pdf |
| **URL critères officiels** | https://www.oecd.org/en/topics/sub-issues/development-co-operation-evaluation-and-effectiveness/evaluation-criteria.html |
| **Format** | PDF |
| **Année / version** | Critères révisés 2019 (6 critères : pertinence, cohérence, efficacité, efficience, impact, durabilité) |
| **Langue** | Français (document 37854181) |
| **Licence / réutilisation** | © OCDE — droit d'auteur standard OCDE. Réutilisation soumise à conditions (non Creative Commons). Consultation libre, reproduction à usage interne ou éducatif généralement tolérée. |
| **Accessibilité** | URL OCDE officielle inaccessible (403) — miroir disponible |
| **Statut** | 🟠 |
| **Notes ingestion** | Utiliser le miroir `consult.africa` (PDF identique). Compléter avec : Glossaire CAD 2e édition (FR/EN/ES) : https://www.oecd.org/content/dam/oecd/en/publications/reports/2023/06/glossary-of-key-terms-in-evaluation-and-results-based-management-for-sustainable-development-second-edition_2767e14e/632da462-en-fr-es.pdf |

---

### 1.5 OCDE-CAD — Glossaire des termes clés en évaluation et GAR (2e éd.)

| Champ | Détail |
|-------|--------|
| **Intitulé** | Glossaire des termes clés en évaluation et gestion axée sur les résultats pour le développement durable (2e édition) |
| **URL PDF direct** | https://www.oecd.org/content/dam/oecd/en/publications/reports/2023/06/glossary-of-key-terms-in-evaluation-and-results-based-management-for-sustainable-development-second-edition_2767e14e/632da462-en-fr-es.pdf |
| **URL page officielle** | https://www.oecd.org/en/publications/glossary-of-key-terms-in-evaluation-and-results-based-management-for-sustainable-development-second-edition_632da462-en-fr-es.html |
| **Format** | PDF trilingue (EN/FR/ES dans un seul fichier) |
| **Année / version** | 2023 (2e édition) |
| **Langue** | Français inclus |
| **Licence / réutilisation** | © OCDE — à vérifier sur la page officielle (la page renvoie 403 ; accès direct au PDF testé non disponible au moment du sourcing) |
| **Accessibilité** | À vérifier — URL directe PDF à tester |
| **Statut** | 🟠 |
| **Notes ingestion** | Source complémentaire essentielle pour les définitions GAR (gestion axée sur les résultats) utilisées dans les rapports bailleurs. |

---

## CORPUS 2 — SYSCOHADA / SYCEBNL : comptabilité ONG/OSBL en zone OHADA

> **Agent cible** : `projets_ong`  
> **Schéma RAG** : `rag_erp`  
> **Tags** : `country:cg` + `module:projets_ong`  
> **Note** : standard OHADA, applicable en République du Congo (État-partie au Traité OHADA)

---

### 2.1 SYCEBNL — Acte uniforme OHADA (texte officiel)

| Champ | Détail |
|-------|--------|
| **Intitulé** | Acte uniforme relatif au Système comptable des entités à but non lucratif (SYCEBNL) |
| **URL officielle OHADA** | https://www.ohada.org/acte-uniforme-relatif-au-systeme-comptable-des-entites-a-but-non-lucratif/ |
| **URL PDF Journal Officiel OHADA** | https://www.ohada.com/uploads/actualite/6692/SYSCEBNL.pdf (taille : > 10 Mo — confirmer accès) |
| **URL miroir SGG Congo** | https://www.sgg.cg/txts-droit-reg/OHADA-Acte-Uniforme-2022-entites-but-non-lucratif.pdf (taille > 10 Mo) |
| **URL Drive (OHADA.org)** | https://drive.google.com/file/d/1C2btINUksN1MPl1HruTeAuwldZlOe2mu/view?usp=share_link |
| **Format** | PDF |
| **Adoption / publication** | Adopté le 22 décembre 2022 (53e session Conseil des ministres OHADA, Niamey) — JO OHADA n° Spécial du 22/02/2023 |
| **Entrée en vigueur** | **1er janvier 2024** |
| **Langue** | Français |
| **Licence / réutilisation** | Texte législatif officiel — domaine public légal. Aucune licence Creative Commons mais reproductible librement (texte de droit). |
| **Accessibilité** | PDF disponible (fichiers volumineux, > 10 Mo) — miroir SGG Congo confirme disponibilité officielle CG |
| **Statut** | 🟢 |
| **Notes ingestion** | **Source prioritaire pour `rag_erp` / `projets_ong`.** Contient : cadre conceptuel, structure des comptes (plan comptable EBNL), états financiers (bilan, compte de résultat, TAFIRE, notes annexes). Scope : associations, ONG, fondations, coopératives hors AUSCOOP, unités de gestion de projets. 422 pages. |

---

### 2.2 SYCEBNL — Guide d'application officiel OHADA

| Champ | Détail |
|-------|--------|
| **Intitulé** | Guide d'application du Système comptable des entités à but non lucratif (SYCEBNL) |
| **URL PDF** | https://www.ohada.org/wp-content/uploads/2023/04/SYCEBNL-GUIDE-D-APPLICATION.pdf |
| **Format** | PDF (6,3 Mo) |
| **Année / version** | 2023 (publié avant l'entrée en vigueur jan. 2024) |
| **Langue** | Français |
| **Licence / réutilisation** | Document officiel OHADA — reproductible à usage interne. Aucune licence explicite mentionnée. |
| **Accessibilité** | Libre (URL directe PDF fonctionnelle) |
| **Statut** | 🟢 |
| **Notes ingestion** | Guide pratique d'implémentation complémentaire à l'Acte uniforme. Contient des exemples de comptabilisation, des tableaux de passage, des explications pédagogiques. À ingérer en tandem avec le texte de l'AU. |

---

### 2.3 SYCEBNL — Publication OHADA « Pratiques comptables EBNL dès 2024 »

| Champ | Détail |
|-------|--------|
| **Intitulé** | Les Pratiques de la Comptabilité des entités du secteur à but non lucratif dans les pays OHADA dès 2024 : Associations, Ordres professionnels et Projets de développement |
| **URL** | https://www.ohada.com/actualite/7057/publication-ohada-les-pratiques-de-la-comptabilite-des-entites-du-secteur-a-but-non-lucratif-dans-les-pays-ohada-des-2024-associations-ordres-professionnels-et-projets-de-developpement.html |
| **Format** | Page web (publication OHADA.com) |
| **Année / version** | 2024 |
| **Langue** | Français |
| **Licence / réutilisation** | À vérifier |
| **Accessibilité** | Page web accessible |
| **Statut** | 🟠 |
| **Notes ingestion** | Source secondaire utile — précisions sur les projets de développement (UGP) comme entités soumises au SYCEBNL. À croiser avec le texte officiel. |

---

### 2.4 AUSCOOP — Acte uniforme sur les sociétés coopératives (OHADA)

| Champ | Détail |
|-------|--------|
| **Intitulé** | Acte uniforme relatif au droit des sociétés coopératives (AUSCOOP) |
| **URL officielle OHADA** | https://www.ohada.com/textes-ohada/actes-uniformes.html (liste complète des AU) |
| **Format** | PDF |
| **Adoption** | 15 décembre 2010, Lomé |
| **Langue** | Français |
| **Licence / réutilisation** | Texte législatif — domaine public légal |
| **Accessibilité** | Accessible via la liste des AU sur ohada.com |
| **Statut** | 🟢 |
| **Notes ingestion** | Complémentaire au SYCEBNL pour les coopératives. L'AUSCOOP régit la structure juridique ; le SYCEBNL leur fournit le cadre comptable (coopératives non financières). Déjà couvert dans le corpus OHADA de base — référencer ici par cohérence `projets_ong`. |

---

## CORPUS 3 — Cadres nationaux République du Congo (suivi ONG)

> **Agent cible** : `projets_ong`  
> **Schéma RAG** : `rag_erp`  
> **Tags** : `country:cg` + `module:projets_ong`  
> **Note** : spécifique République du Congo (Brazzaville)

---

### 3.1 Loi du 1er juillet 1901 relative au contrat d'association (héritée)

| Champ | Détail |
|-------|--------|
| **Intitulé** | Loi du 1er juillet 1901 relative au contrat d'association (applicable en République du Congo) |
| **Statut au Congo** | Texte colonial français maintenu en vigueur après l'indépendance (1960) ; base légale principale des associations et ONG en République du Congo à ce jour |
| **URL texte** | à vérifier — disponible via légifrance.gouv.fr mais version Congo non spécifique ; portail `sgg.cg` n'a pas de version nationale révisée identifiée |
| **Format** | Texte de loi |
| **Année** | 1901 (maintenu) |
| **Langue** | Français |
| **Licence / réutilisation** | Domaine public (texte législatif) |
| **Accessibilité** | 🟠 — aucun texte spécifiquement congolais consolidé localisé ; absence d'une loi nationale propre confirmée |
| **Statut** | 🟠 |
| **Notes ingestion** | **Lacune documentaire identifiée.** La République du Congo applique toujours la loi de 1901 héritée de la colonisation. Il n'a pas été trouvé de loi nationale spécifique et consolidée sur les associations/ONG publiée sur `sgg.cg`. Une proposition de loi déterminant le régime des associations a été débattue (signalée en 2016 par des ONG comme restrictive), sans adoption confirmée à ce jour. |

---

### 3.2 Journal Officiel de la République du Congo (SGG)

| Champ | Détail |
|-------|--------|
| **Intitulé** | Journal Officiel de la République du Congo — Secrétariat Général du Gouvernement |
| **URL portail** | https://www.sgg.cg/ |
| **URL exemples JO 2024** | https://www.sgg.cg/JO/2024/congo-jo-2024-42.pdf |
| **Format** | PDF par numéro de JO |
| **Langue** | Français |
| **Licence / réutilisation** | Textes officiels — domaine public légal |
| **Accessibilité** | Libre (PDF accessibles par numéro) |
| **Statut** | 🟠 |
| **Notes ingestion** | **Surveillance active recommandée.** Le JO publie les déclarations d'associations enregistrées et les textes réglementaires. À surveiller pour : (a) toute loi nationale sur les associations/ONG adoptée ; (b) décrets sur les coopératives. Pas d'index structuré/API — accès manuel par numéro. |

---

### 3.3 Portail LIZIBA — Base de données légale CG

| Champ | Détail |
|-------|--------|
| **Intitulé** | LIZIBA — Base de données légale et réglementaire de la République du Congo |
| **URL** | https://liziba.cg/en/cadre-legal-et-reglementaire-2/ |
| **Format** | Base de données web |
| **Langue** | Français / Anglais |
| **Licence / réutilisation** | À vérifier |
| **Accessibilité** | Accessible — mais **ne contient pas de section dédiée aux ONG/associations** (vérifié lors du sourcing) |
| **Statut** | 🔴 |
| **Notes ingestion** | Non prioritaire pour le corpus ONG. Utile pour les textes commerciaux et fiscaux applicables aux projets (droit des affaires CG). |

---

## Récapitulatif — Plan d'ingestion

### Pour l'agent `projets_ong` → schéma `rag_erp`

| Priorité | Source | Tags | Format |
|----------|--------|------|--------|
| P1 | SYCEBNL — Acte uniforme OHADA (§2.1) | `country:cg` · `module:projets_ong` · `source:ohada` | PDF (422 p.) |
| P1 | SYCEBNL — Guide d'application OHADA (§2.2) | `country:cg` · `module:projets_ong` · `source:ohada` | PDF (6,3 Mo) |
| P2 | AUSCOOP — Acte uniforme coopératives (§2.4) | `country:cg` · `module:projets_ong` · `source:ohada` | PDF |
| P3 | SYCEBNL — Publication pratiques 2024 (§2.3) | `country:cg` · `module:projets_ong` | Web |
| P4 | JO Congo / SGG (§3.2) | `country:cg` · `module:projets_ong` | PDF (surveillance) |

### Pour l'agent `reporting_bailleurs` → schéma `rag_legal` (placeholder)

| Priorité | Source | Tags | Format |
|----------|--------|------|--------|
| P1 | IATI Standard v2.03 — schémas XSD (§1.1) | `country:cg` · `module:reporting_bailleurs` · `source:iati` · `scope:international` | XSD + HTML |
| P1 | ePRAG 2021 FR — procédures contractuelles UE (§1.3) | `country:cg` · `module:reporting_bailleurs` · `source:eu` · `scope:international` | PDF |
| P2 | OCDE-CAD — Normes évaluation (§1.4) | `country:cg` · `module:reporting_bailleurs` · `source:ocde` · `scope:international` | PDF |
| P2 | OCDE-CAD — Glossaire GAR 2e éd. (§1.5) | `country:cg` · `module:reporting_bailleurs` · `source:ocde` · `scope:international` | PDF trilingue |
| P3 | IATI Bulk Data Service — exemples rapports (§1.2) | `country:cg` · `module:reporting_bailleurs` · `source:iati` · `scope:international` | XML (filtré CG) |

---

## Synthèse finale

### Sources 🟢 — Ingestion directe possible (4)

| # | Source | Raison |
|---|--------|--------|
| 1 | IATI Standard v2.03 + Bulk Data Service | Open data, libre, schémas XSD + XML téléchargeables |
| 2 | SYCEBNL — Acte uniforme OHADA | Texte officiel PDF accessible (miroir SGG Congo disponible) |
| 3 | SYCEBNL — Guide d'application OHADA | PDF direct fonctionnel (6,3 Mo), libre d'accès |
| 4 | AUSCOOP — AU Coopératives OHADA | Texte officiel accessible via ohada.com |

### Sources 🟠 — Accessibles avec réserve (4)

| # | Source | Raison |
|---|--------|--------|
| 5 | PRAG 2025 (UE) | Version FR éditée limitée à 2021 ; version EN 2025 disponible ; e-learning non téléchargeable |
| 6 | OCDE-CAD normes + Glossaire GAR | URL OCDE officielle en 403 ; contenu accessible via miroirs ; licence © à clarifier |
| 7 | Loi 1901 associations (CG) | Texte hérité, pas de version nationale consolidée publiée ; lacune documentaire réelle |
| 8 | JO Congo / SGG | PDF accessibles mais pas d'index structuré, surveillance manuelle requise |

### Sources 🔴 — Non exploitables pour l'ingestion (1)

| # | Source | Raison |
|---|--------|--------|
| 9 | LIZIBA CG | Aucune section ONG/associations — hors scope pour ce corpus |

### Lacune documentaire majeure identifiée

**La République du Congo ne dispose pas de loi nationale propre et publiée sur les ONG/associations accessible en ligne.** Le cadre légal repose sur la loi coloniale de 1901. Une proposition de loi signalée en 2016 n'a pas abouti à ce jour (confirmation non trouvée). À surveiller via le JO du SGG (`sgg.cg`). Pour les besoins de ZolaOS, l'agent `projets_ong` s'appuiera sur le SYCEBNL/OHADA (comptabilité) et les procédures pratiques de création (ministère de l'Intérieur CG) en attendant un texte national consolidé.

---

*Sourcing réalisé avec ~18 requêtes web (WebSearch + WebFetch). Aucune URL inventée — toutes vérifiées ou signalées « à vérifier ».*
