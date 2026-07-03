# Sourcing corpus juridique — Droit national congolais (République du Congo / Brazzaville)

> Droit NATIONAL CG uniquement — OHADA régional EXCLU (sourcé séparément).
> Date de sourcing : 2026-07-03
> Méthode : ~25 recherches web vérifiées (WebSearch + WebFetch) + 3 sous-agents spécialisés.

---

## Tableau de synthèse global

| Agent RAG    | 🟢 Dispo | 🟠 Partiel | 🔴 Introuvable | Note critique |
|--------------|----------|-----------|---------------|---------------|
| `fiscal_cg`  | 2        | 5         | 1             | CGI non consolidé post-2021 en version libre |
| `travail_cg` | 5        | 3         | 1             | Code 1975 + modif. 1996 = droit positif ; refonte en cours |
| `admin_cg`   | 4        | 3         | 1             | Code 2009 dispo ; CCAG absent ; BOAMP payant |

---

## 1. Agent `fiscal_cg` — Fiscalité congolaise

### Sources identifiées

#### SOURCE F1 — Code Général des Impôts, Tome I

| Champ | Valeur |
|---|---|
| **Intitulé exact** | Code général des impôts — Tome 1 |
| **URL page officielle** | https://www.finances.gouv.cg/fr/CGI-tome1_280321 |
| **URL directe PDF** | https://www.finances.gouv.cg/sites/default/files/documents/CGI%20Tome%20I.pdf |
| **Format** | PDF |
| **Fraîcheur** | Version publiée le 28 mars 2021 (intègre LF 2021 ; modifications LF 2022–2025 non consolidées) |
| **Contenu** | Impôts d'État : IRPP, IS, TVA, taxe professionnelle unique, procédures fiscales, impôts locaux |
| **Licence** | Texte réglementaire public — domaine public ; aucune restriction explicite sur le portail |
| **Téléchargement direct** | Oui |
| **Statut** | 🟠 Partiel — version 2021, non à jour des LF 2022–2025 |

---

#### SOURCE F2 — Code Général des Impôts, Tome II

| Champ | Valeur |
|---|---|
| **Intitulé exact** | Code général des impôts — Tome 2 |
| **URL page officielle** | https://www.finances.gouv.cg/fr/CGI-tome2_280321 |
| **URL directe PDF** | https://www.finances.gouv.cg/sites/default/files/documents/CGI%20Tome%20II.pdf |
| **Format** | PDF |
| **Fraîcheur** | 28 mars 2021 (même réserve que Tome I) |
| **Contenu** | Droits d'enregistrement, timbre, IRVM, taxe immobilière |
| **Licence** | Texte réglementaire public — libre diffusion |
| **Téléchargement direct** | Oui |
| **Statut** | 🟠 Partiel — version 2021 uniquement |

---

#### SOURCE F3 — Loi de Finances pour l'année 2025 (LF 2025) ★ PRIORITAIRE

| Champ | Valeur |
|---|---|
| **Intitulé exact** | Loi n° 47-2024 du 30 décembre 2024 portant loi de finances pour l'année 2025 |
| **URL page officielle** | https://www.finances.gouv.cg/fr/loi-de-finances-pour-lann%C3%A9e-2025 |
| **URL directe PDF** | https://www.finances.gouv.cg/sites/default/files/documents/Loi%20de%20finances%202025%20(1).pdf |
| **Format** | PDF |
| **Fraîcheur** | Promulguée le 30 décembre 2024 — texte en vigueur |
| **Contenu clé** | Hausse IS 28 % → 30 %, modifications IRPP, TVA, droits d'accises, nouvelle taxe emballages non récupérables. Budget : 2 550,7 Mds FCFA. |
| **Licence** | Texte réglementaire public — libre |
| **Téléchargement direct** | Oui |
| **Statut** | 🟢 Disponible |

---

#### SOURCE F4 — Journal Officiel (portail SGG) — éditions fiscales

| Champ | Valeur |
|---|---|
| **Intitulé exact** | Journal Officiel de la République du Congo — Portail Secrétariat Général du Gouvernement |
| **URL index** | https://www.sgg.cg/fr/journal-officiel/le-journal-officiel.html |
| **URL recherche** | https://sgg.cg/fr/recherche.html (1 842 résultats indexés, filtrables par année/numéro) |
| **Exemples PDF directs** | `https://www.sgg.cg/JO/2024/congo-jo-2024-25.pdf` · `https://sgg.cg/JO/2026/congo-jo-2026-9.pdf` |
| **Format** | PDF par numéro (archives 1946–2026) |
| **Fraîcheur** | Jusqu'au n° 2026-27 du 2 juillet 2026 |
| **Licence** | Texte officiel public. *Avertissement SGG : seule la version papier fait foi — les PDF ont valeur informative.* |
| **Téléchargement direct** | Oui (PDF individuels par numéro) |
| **Statut** | 🟢 Disponible — source primaire de référence ; crawl nécessaire pour les éditions spéciales LF |

**Note** : Pour récupérer les LF antérieures (2022, 2023, 2024), chercher les éditions spéciales budgétaires (`congo-jo-20XX-YY-sp.pdf`) sur le portail SGG.

---

#### SOURCE F5 — Recueil des textes fiscaux UNICONGO × Sutter & Pearce-Laways (LF 2023)

| Champ | Valeur |
|---|---|
| **Intitulé exact** | Recueil des textes fiscaux à jour avec la Loi de Finances 2023 |
| **URL directe PDF** | https://www.unicongo.cg/wp-content/uploads/2023/10/Recueil-des-textes-fiscaux-a-jour-avec-LF-2023.pdf |
| **URL espace fiscalité** | https://www.unicongo.cg/espace-fiscalite/ |
| **Format** | PDF (4,4 Mo, ~444 pages) |
| **Fraîcheur** | Octobre 2023 — consolidation jusqu'à LF 2023 incluse |
| **Contenu** | CGI Tomes I+II + textes hors code (TVA, fiscalité pétrolière/minière, conventions fiscales, investissements) |
| **Producteur** | UNICONGO + Cabinet Sutter & Pearce-Laways — diffusion gratuite déclarée |
| **Licence** | Libre et gratuite (non officielle — document de travail patronal) |
| **Téléchargement direct** | Oui |
| **Statut** | 🟠 Partiel — meilleure consolidation gratuite disponible, mais arrêtée à LF 2023 |

---

#### SOURCE F6 — PLF 2025 (version projet — exposés de motifs)

| Champ | Valeur |
|---|---|
| **Intitulé exact** | Projet de loi de finances pour l'année 2025 (version v051024) |
| **URL directe PDF** | https://www.finances.gouv.cg/sites/default/files/documents/PLF_2025%20v051024.pdf |
| **Format** | PDF |
| **Fraîcheur** | Octobre 2024 (avant vote parlementaire) |
| **Utilité RAG** | Exposés de motifs + annexes détaillées absentes de la loi promulguée |
| **Licence** | Document gouvernemental public |
| **Téléchargement direct** | Oui |
| **Statut** | 🟠 Partiel — version avant adoption ; complémentaire à F3 |

---

#### SOURCE F7 — DGID (Direction Générale des Impôts et des Domaines)

| Champ | Valeur |
|---|---|
| **Intitulé** | Site officiel DGID — portail de la fiscalité congolaise |
| **URL** | https://dgid.tax/ (alias : http://impots-gouv.cg/) |
| **Contenu attendu** | Instructions d'application, circulaires, formulaires, guides pratiques |
| **Fraîcheur** | Actif (campagne vulgarisation LF 2025 lancée le 6 mai 2025) |
| **Licence** | Texte officiel — libre a priori |
| **Téléchargement direct** | À vérifier — domaine `dgid.tax` inaccessible depuis l'environnement de test externe (ENOTFOUND) |
| **Statut** | 🔴 Inaccessible depuis l'extérieur au moment du test — à re-vérifier depuis réseau congolais ou via VPN |

**Note critique** : Une instruction d'application des dispositions fiscales de la LF 2025 a été produite et vulgarisée début mai 2025 (`finances.gouv.cg/fr/articles/vulgarisation-DGID-LF25_060525`), mais aucun PDF public n'est lié sur le portail. Ce document est probablement disponible à la DGID physiquement ou sur `dgid.tax`.

---

#### SOURCE F8 — CGI consolidé 2024/2025 (Droit-Afrique / LGDJ — payant)

| Champ | Valeur |
|---|---|
| **Intitulé** | Congo — Code général des impôts 2025 (inclut LF n°47-2024) |
| **URL Droit-Afrique** | http://www.droit-afrique.com/boutique/congo-code-general-des-impots/ |
| **URL LGDJ** | https://www.lgdj.fr/congo-code-general-des-impots-2025-9782353083077.html |
| **ISBN** | 9782353083077 |
| **Format** | PDF (édition privée) |
| **Fraîcheur** | 2025 (édition la plus récente intégrant LF 2025) |
| **Licence** | Édition commerciale payante — droits réservés |
| **Téléchargement direct** | Non (payant) |
| **Statut** | 🟠 Partiel — référence consolidée de qualité, mais payante ; à acquérir pour compléter le corpus |

---

### Gap identifié `fiscal_cg`

Aucune source gratuite et accessible ne propose le CGI consolidé intégrant simultanément les LF 2022, 2023, 2024 et 2025. La stratégie d'ingestion devra juxtaposer :
- CGI Tomes I+II (2021, sources F1+F2)
- + Recueil UNICONGO LF2023 (F5) pour la consolidation jusqu'à 2023
- + LF 2025 (F3) pour les dispositions les plus récentes
avec un pipeline de réconciliation des articles modifiés.

---

### Plan d'ingestion `fiscal_cg`

- **Schéma cible** : `rag_legal`
- **Tags** : `country:cg`, `module:fiscal_cg`, `type:texte_legal`
- **Tags secondaires** : `type:code` (CGI) · `type:loi_finances` (LF annuelles) · `millesime:2021|2023|2025`
- **Politique PII** : NONE — texte public réglementaire sans données personnelles
- **Découpage recommandé** :
  - CGI : découpage par article (level 3 = `Art. XXX`) ; les livres/parties/chapitres comme métadonnées hiérarchiques
  - LF : découpage par article + préambule ; conserver le numéro de loi et l'année fiscale comme metadata
  - Recueil UNICONGO : même granularité, tagger `source:unicongo` pour distinguer de la source officielle
- **Pipeline OCR** : non requis (PDFs textuels natifs confirmés)
- **Remarques** : Versionner explicitement chaque chunk avec `version_texte` (ex. `2021`, `2023`, `2025`) pour permettre le filtrage par année fiscale dans le retriever

---

## 2. Agent `travail_cg` — Droit du travail congolais

### Sources identifiées

#### SOURCE T1 — Code du travail (Loi n° 45-75 du 15 mars 1975) — texte fondateur

| Champ | Valeur |
|---|---|
| **Intitulé exact** | Code du travail de la République du Congo — Loi n° 45-75 du 15 mars 1975 |
| **URL officielle SGG (PDF scan)** | https://www.sgg.cg/codes/congo-code-1975-travail.pdf |
| **URL NATLEX ILO (fiche)** | https://natlex.ilo.org/dyn/natlex2/r/natlex/fe/details?p3_isn=14546 |
| **URL NATLEX ILO (PDF direct)** | https://natlex.ilo.org/dyn/natlex2/natlex2/files/download/14546/COG-14546.pdf |
| **URL UNICONGO (PDF scan, 2024)** | https://www.unicongo.cg/wp-content/uploads/2024/02/code-du-travail2.pdf |
| **Format** | PDF scanné (scan CCITT — texte non extractible sans OCR) |
| **Fraîcheur** | Texte de 1975 (version consolidée non datée sur SGG ; février 2024 sur UNICONGO) |
| **Licence** | Texte réglementaire public congolais — réutilisation libre a priori |
| **Téléchargement direct** | Oui (SGG + UNICONGO) ; PDF NATLEX direct : 403 Forbidden (accéder via la fiche HTML) |
| **Statut** | 🟠 Partiel — texte de référence disponible mais PDF scanné ; OCR obligatoire avant ingestion RAG |

---

#### SOURCE T2 — Loi n° 6-96 du 6 mars 1996 (modification majeure du Code du travail) ★ PRIORITAIRE

| Champ | Valeur |
|---|---|
| **Intitulé exact** | Loi n° 6-96 du 6 mars 1996 modifiant et complétant certaines dispositions de la Loi n° 45/75 instituant un Code du Travail |
| **URL SGG (PDF)** | https://www.sgg.cg/textes-officiels/lois/1996/congo-loi-1996-06.pdf |
| **URL NATLEX ILO (HTML intégral)** | https://www.ilo.org/dyn/natlex/docs/WEBTEXT/43085/64990/F96COG01.htm |
| **URL NATLEX (fiche)** | https://natlex.ilo.org/dyn/natlex2/r/natlex/fe/details?p3_isn=43085 |
| **Format** | PDF (SGG) + HTML texte intégral (ILO NATLEX — idéal RAG) |
| **Fraîcheur** | 1996 — dernière grande révision du code en vigueur |
| **Licence** | Texte réglementaire public — libre |
| **Téléchargement direct** | Oui (SGG PDF) / Oui (HTML ILO directement parseable) |
| **Statut** | 🟢 Disponible — la version HTML ILO est particulièrement favorable au RAG (texte extractible sans OCR) |

---

#### SOURCE T3 — Avant-projet de nouveau Code du travail (en cours de révision)

| Champ | Valeur |
|---|---|
| **Intitulé** | Avant-projet de loi portant Code du travail de la République du Congo |
| **URL** | https://fonction-publique.gouv.cg/fr/code-du-travail |
| **Format** | Page HTML informative — pas de PDF téléchargeable |
| **Fraîcheur** | Examiné en Commission nationale consultative du travail le 12 décembre 2025 — non encore adopté |
| **Licence** | N/A (texte non promulgué) |
| **Téléchargement direct** | Non |
| **Statut** | 🔴 Introuvable en version téléchargeable — processus législatif en cours |

**Note critique** : La loi n° 45-75 et ses modifications (1996) **restent le droit positif en vigueur** jusqu'à adoption du nouveau code. L'agent RAG doit **signaler ce statut transitoire** dans ses réponses sur le droit du travail congolais.

---

#### SOURCE T4 — Décrets d'application récents : SMIG 2024 + Loi retraite 2024

| Champ | Valeur |
|---|---|
| **Intitulé 1** | Décret n° 2024-2762 portant revalorisation du Salaire Minimum Interprofessionnel Garanti (SMIG) |
| **Intitulé 2** | Loi n° 48-2024 du 30 décembre 2024 fixant l'âge de la retraite des travailleurs soumis au Code du travail |
| **URL index OARH** | https://www.oarh.cg/lois-et-reglements-2/ |
| **URL Journal Officiel SGG** | https://www.sgg.cg/JO/ (éditions 2024-2026 disponibles) |
| **Format** | PDF (Journal Officiel) |
| **Fraîcheur** | 2024 |
| **Licence** | Texte réglementaire public — libre |
| **Téléchargement direct** | Oui (via OARH ou sgg.cg/JO/) |
| **Statut** | 🟢 Disponible |

---

#### SOURCE T5 — Convention collective des Services Pétroliers (2022) + grille 2023

| Champ | Valeur |
|---|---|
| **Intitulé exact** | Convention collective des Entreprises de Services Pétroliers — République du Congo |
| **URL directe OARH** | https://www.oarh.cg/wp-content/uploads/2022/07/Convention-collective-des-Entreprises-de-Services-Petroliers.pdf |
| **URL alternative Liziba** | https://liziba.cg/wp-content/uploads/2021/04/Convention-Collective-des-entreprises-de-services-petroliers.pdf |
| **Grille salariale 2023** | https://www.unicongo.cg/wp-content/uploads/2024/02/Grille-salariale-Petrole-signee-le-23-fevrier-2023-3.pdf |
| **Format** | PDF |
| **Fraîcheur** | Convention : 2022 ; grille salariale : signée le 23 février 2023 |
| **Licence** | Document patronal/syndical public — réutilisation probable libre |
| **Téléchargement direct** | Oui (OARH + Liziba) |
| **Statut** | 🟢 Disponible |

---

#### SOURCE T6 — Convention collective des Hydrocarbures (Recherche & Production) (2022)

| Champ | Valeur |
|---|---|
| **Intitulé exact** | Convention collective des Entreprises de Recherche et d'Exploitation d'Hydrocarbures — République du Congo |
| **URL OARH (index)** | https://www.oarh.cg/convention-collective/ |
| **URL alternative Liziba** | https://liziba.cg/wp-content/uploads/2021/04/Convention-collective-des-dhydrocarbures.pdf |
| **Format** | PDF |
| **Fraîcheur** | 2022 (OARH) / 2021 (Liziba) |
| **Licence** | Document patronal/syndical public |
| **Téléchargement direct** | Oui (deux sources) |
| **Statut** | 🟢 Disponible |

---

#### SOURCE T7 — Convention collective BTP — Bâtiment, Travaux Publics et activités connexes (2022)

| Champ | Valeur |
|---|---|
| **Intitulé exact** | Convention collective de Bâtiment Travaux Publics et des Activités Connexes — République du Congo |
| **URL OARH** | https://www.oarh.cg/wp-content/uploads/2022/07/Convention-Collecticve-de-Batiment-Travaux-Publics-et-des-Activites-Connexes.pdf |
| **URL UNICONGO** | https://www.unicongo.cg/wp-content/uploads/2024/02/Convention-BTP-News.pdf |
| **Format** | PDF (scan, 2,7 Mo) |
| **Fraîcheur** | 2022 |
| **Licence** | Document patronal/syndical public |
| **Téléchargement direct** | Oui (OARH + UNICONGO) |
| **Statut** | 🟢 Disponible |

---

#### SOURCE T8 — Convention collective du Commerce (2021)

| Champ | Valeur |
|---|---|
| **Intitulé exact** | Convention collective du Commerce — République du Congo |
| **URL OARH (index)** | https://www.oarh.cg/convention-collective/ |
| **Protocole grille salariale 2024** | Disponible sur UNICONGO (Auxiliaires de Transports et Assimilés, janvier 2024 — vérifier périmètre) |
| **Format** | PDF |
| **Fraîcheur** | 2021 |
| **Licence** | Document patronal/syndical public |
| **Téléchargement direct** | Oui |
| **Statut** | 🟢 Disponible |

---

#### SOURCE T9 — Portail UNICONGO — 17 conventions collectives sectorielles (index)

| Champ | Valeur |
|---|---|
| **Intitulé** | Conventions collectives sectorielles — Union Patronale et Interprofessionnelle du Congo |
| **URL index** | https://www.unicongo.cg/les-conventions-collectives/ |
| **Nombre de documents** | 17 conventions listées couvrant : agriculture, transports auxiliaires, banques/assurances, BTP, boulangeries, commerce, compagnies aériennes, forestières, hôtellerie, industrie/métallurgie, pêche maritime, pharmacies, personnel domestique, mines, hydrocarbures (versions 2019 & 2023), services pétroliers (2022), TIC, télécommunications |
| **Format** | PDF (tous téléchargeables directement) |
| **Fraîcheur** | 1991–2024 selon secteur |
| **Licence** | Documents patronaux/syndicaux — diffusion libre par UNICONGO |
| **Téléchargement direct** | Oui |
| **Statut** | 🟢 Disponible — index complet et exhaustif pour les 17 secteurs |

**Contact UNICONGO pour accès** : documentation@unicongo.cg | +242 06 621 56 68

---

#### SOURCE T10 — Portail OARH.cg — agrégateur de référence

| Champ | Valeur |
|---|---|
| **Intitulé** | Observatoire Africain des Ressources Humaines — portail droit social Congo |
| **URL conventions** | https://www.oarh.cg/convention-collective/ |
| **URL lois et règlements** | https://www.oarh.cg/lois-et-reglements-2/ |
| **Contenu** | Code du travail + 20 conventions collectives sectorielles + décrets SMIG + textes sécurité/hygiène |
| **Format** | PDF (tous secteurs) |
| **Fraîcheur** | Jusqu'à 2024 |
| **Licence** | Agrégateur public — contenu libre a priori |
| **Téléchargement direct** | Oui |
| **Statut** | 🟢 Disponible — portail le plus complet pour le corpus `travail_cg` |

---

### Alertes critiques `travail_cg`

1. **OCR obligatoire** : La quasi-totalité des PDF (SGG, UNICONGO, OARH) sont des scans CCITT ou JPEG — non indexables sans pipeline OCR (Tesseract + modèle français recommandé).
2. **Code du travail en refonte** : Le nouveau code est en consultation (dec. 2025) — la Loi 45-75 + modif. 1996 restent le droit positif. L'agent RAG doit inclure un avertissement sur ce statut transitoire.
3. **NATLEX ILO — accès 403 sur PDF directs** : Accéder via les fiches HTML ou utiliser les miroirs SGG/UNICONGO.
4. **Meilleur point d'entrée** : Le portail OARH (`oarh.cg`) est le plus complet et pratique : code du travail + 20 conventions + décrets récents en un seul endroit.

---

### Plan d'ingestion `travail_cg`

- **Schéma cible** : `rag_legal`
- **Tags** : `country:cg`, `module:travail_cg`, `type:texte_legal`
- **Tags secondaires** :
  - `type:code` → Code du travail (Loi 45-75 + Loi 6-96)
  - `type:decret` → Décrets SMIG, retraite
  - `type:convention_collective` + `secteur:petrole|btp|commerce|hydrocarbures|...`
- **Politique PII** : NONE — textes publics et documents patronaux/syndicaux
- **Découpage recommandé** :
  - Code du travail : découpage par article après OCR ; préserver la numérotation (articles 1 à N)
  - Conventions collectives : découpage par clause/chapitre ; conserver le titre de section comme métadonnée
  - Décrets : découpage par article ; lier au texte de référence modifié
- **Pipeline OCR** : Obligatoire pour la majorité des sources (Tesseract 5+ avec modèle français, ou EasyOCR)
- **Remarques** : Indexer séparément Code du travail vs conventions collectives ; tagguer le secteur pour permettre le filtrage par secteur d'activité dans le retriever

---

## 3. Agent `admin_cg` — Marchés publics & ARMP

### Sources identifiées

#### SOURCE A1 — Décret n° 2009-156 portant Code des marchés publics ★ TEXTE DE BASE

| Champ | Valeur |
|---|---|
| **Intitulé exact** | Décret n° 2009-156 du 20 mai 2009 portant Code des marchés publics et textes d'application de la République du Congo |
| **URL officielle SGG** | https://www.sgg.cg/codes/congo-code-2009-marches-publics.pdf |
| **URL alternative Liziba** | https://liziba.cg/wp-content/uploads/2020/11/Decret-n%C2%B0-2009-156_2009-Code-marches-publics.pdf |
| **URL alternative ClientEarth** | https://www.clientearth.fr/media/k2jbkt3o/2009-05-20-decret-n-2009-156-du-20-mai-2009-portant-code-des-marches-publics-republique-du-congo-ext-fr.pdf |
| **URL finances.gouv.cg** | https://www.finances.gouv.cg/fr/d%C3%A9cret-n%C2%B02009-156-du-20-mai-2009-portant-code-des-march%C3%A9s-publics |
| **Format** | PDF (114,6 Ko) |
| **Fraîcheur** | 2009 (édition consolidée SGG de mai 2012) |
| **Licence** | Texte réglementaire public — libre diffusion ; aucune licence explicite sur le portail |
| **Téléchargement direct** | Oui (PDF direct SGG) |
| **Statut** | 🟢 Disponible |

**Note** : C'est le corpus de base absolu. Contient code complet + textes d'application dans un seul PDF. Plusieurs sources miroir confirment l'accessibilité.

---

#### SOURCE A2 — Décret n° 2009-157 : Création et organisation de l'ARMP

| Champ | Valeur |
|---|---|
| **Intitulé exact** | Décret n° 2009-157 du 20 mai 2009 portant création, attributions, organisation et fonctionnement de l'Autorité de Régulation des Marchés Publics (ARMP) |
| **URL Liziba** | https://liziba.cg/wp-content/uploads/2020/11/Decret-n%C2%B0-2009-157_2009-Autorite-regulation-marches-publics.pdf |
| **URL SGG** | https://www.sgg.cg/textes-officiels/decrets/2009/ (répertoire — fichier à localiser) |
| **Format** | PDF |
| **Fraîcheur** | 2009 |
| **Licence** | Texte officiel — libre |
| **Téléchargement direct** | Oui (Liziba) |
| **Statut** | 🟢 Disponible |

---

#### SOURCE A3 — Décrets d'application 2009-159, 2009-160, 2009-162

| Champ | Valeur |
|---|---|
| **Intitulé 159** | Décret n° 2009-159 portant attributions et organisation de la Direction Générale du Contrôle des Marchés Publics (DGCMP) |
| **Intitulé 160** | Décret n° 2009-160 fixant les modalités d'approbation des marchés publics |
| **Intitulé 162** | Décret n° 2009-162 fixant les seuils et modalités de gestion des cellules de passation |
| **URLs SGG** | `https://www.sgg.cg/textes-officiels/decrets/2009/congo-decret-2009-159.pdf` · `…-160.pdf` · `…-162.pdf` |
| **Format** | PDF (scannés — OCR requis) |
| **Fraîcheur** | 2009 |
| **Licence** | Textes officiels — libres |
| **Téléchargement direct** | Oui (liens directs SGG) |
| **Statut** | 🟢 Disponibles — PDFs binaires confirmés, contenu lisible sous réserve OCR |

---

#### SOURCE A4 — Modifications post-2009 : Décrets 2022-1854 et séries 2023-2024

| Champ | Valeur |
|---|---|
| **Intitulé** | Décret n° 2022-1854 du 12 octobre 2022 modifiant le décret n° 2009-161 (cellule de gestion des marchés) + décrets modificatifs 2023 et 2024 |
| **URL JO SGG 2023** | `https://www.sgg.cg/JO/2023/congo-jo-2023-02.pdf` · `…/congo-jo-2023-30.pdf` |
| **Décret récent 2024** | https://www.sgg.cg/textes-officiels/decrets/2025/congo-decret-2024-577.pdf (publié au JO du 3 juillet 2025) |
| **Format** | PDF |
| **Fraîcheur** | 2022–2025 |
| **Licence** | Texte officiel — libre |
| **Téléchargement direct** | Oui |
| **Statut** | 🟠 Partiel — décrets modificatifs présents sur sgg.cg mais nécessitent un crawl systématique des JO pour recensement exhaustif |

---

#### SOURCE A5 — DAO types ARMP : Fournitures & Services (50-100 MFCFA)

| Champ | Valeur |
|---|---|
| **Intitulé exact** | Document-type d'appel d'offres pour fournitures et services (50–100 millions FCFA) |
| **URL ARMP** | https://armp.cg/download-template.php?id=15 |
| **URL alternative** | https://armp.cg/download-template.php?id=14 |
| **Format** | Word (.docx / .doc) |
| **Fraîcheur** | Janvier 2011 |
| **Contenu** | Avis public, instructions aux candidats, formulaires-types (soumission, BQE, spécifications techniques, qualification, contrat, engagement éthique) |
| **Licence** | Document ARMP officiel — libre a priori |
| **Téléchargement direct** | Oui |
| **Statut** | 🟢 Disponible — note : format Word nécessite conversion PDF/texte avant ingestion |

---

#### SOURCE A6 — DAO type ARMP : Travaux

| Champ | Valeur |
|---|---|
| **Intitulé** | Dossier-type d'appel d'offres pour marchés de travaux |
| **URL ARMP** | https://armp.cg/download-template.php?id=11 |
| **Format** | Word (à confirmer) |
| **Fraîcheur** | Probablement 2011–2013 |
| **Licence** | Document ARMP officiel — libre |
| **Téléchargement direct** | Oui |
| **Statut** | 🟠 Partiel — lien confirmé, contenu non entièrement inspecté |

---

#### SOURCE A7 — Manuel de procédures simplifié CMP (ARMP, 2009/2025)

| Champ | Valeur |
|---|---|
| **Intitulé exact** | Manuel de procédure simplifié du CMP — version 2009 |
| **URL ARMP** | https://armp.cg/markets-manual.php?page=1&lang=fr (page index) |
| **URL téléchargement** | https://armp.cg/download-manual.php?id=3&lang=fr |
| **Format** | PDF (296 Ko) |
| **Fraîcheur** | Version 2009 — mise en ligne actualisée le 19 juillet 2025 (1 840 téléchargements) |
| **Licence** | Document ARMP officiel — libre |
| **Téléchargement direct** | Oui |
| **Statut** | 🟢 Disponible |

---

#### SOURCE A8 — Portail SGG : Codes consolidés (bibliothèque générale)

| Champ | Valeur |
|---|---|
| **Intitulé** | Codes en vigueur — Secrétariat Général du Gouvernement de la République du Congo |
| **URL index** | https://www.sgg.cg/fr/droit-congolais/les-codes-consolides.html |
| **Format** | HTML (index) + PDFs téléchargeables (17 codes) |
| **Fraîcheur** | 2004–2023 selon les codes |
| **Licence** | Textes officiels — réutilisation libre |
| **Téléchargement direct** | Oui |
| **Statut** | 🟢 Disponible |

**Codes adjacents pertinents pour `admin_cg`** :
- Code du domaine de l'État (2004) : `congo-code-2004-domaine-etat.pdf`
- Code de l'urbanisme et de la construction (2019) : `congo-code-2019-urbanisme-construction.pdf`

---

#### SOURCE A9 — BOAMP (Bulletin Officiel d'Annonces des Marchés Publics)

| Champ | Valeur |
|---|---|
| **Intitulé exact** | Bulletin Officiel d'Annonces des Marchés Publics — République du Congo |
| **URL ARMP** | https://armp.cg/download-bulletin.php?id=10&lang=fr |
| **Format** | PDF (numéros périodiques) |
| **Fraîcheur** | Publication active 2024-2025 |
| **Licence** | Publication officielle ARMP — 1 500 FCFA/numéro ou abonnement |
| **Téléchargement direct** | Non — accès payant |
| **Statut** | 🔴 Non librement accessible — payant ; pertinent pour avis d'appel d'offres en cours mais hors périmètre RAG sans accord ARMP |

---

### Lacune critique `admin_cg` — CCAG absent

Aucun Cahier des Clauses Administratives Générales (CCAG) spécifique au Congo-Brazzaville n'a été trouvé en accès libre. Les DAO types ARMP (A5/A6) constituent le substitut partiel. Statut : **à vérifier** auprès de l'ARMP directement (contact@armp.cg).

---

### Plan d'ingestion `admin_cg`

- **Schéma cible** : `rag_legal`
- **Tags** : `country:cg`, `module:admin_cg`, `type:texte_legal`
- **Tags secondaires** :
  - `type:code` → Décret 2009-156 (Code des marchés publics)
  - `type:decret` → Décrets d'application 2009-157 à 2009-162 + modificatifs 2022-2024
  - `type:dao_type` → DAO Fournitures, DAO Travaux, Manuel ARMP
  - `type:code_annexe` → Code domaine de l'État, Code urbanisme
- **Politique PII** : NONE — textes publics réglementaires et documents administratifs types
- **Découpage recommandé** :
  - Code des marchés publics : par article (chunking niveau article) ; titres/chapitres comme métadonnées
  - DAO types : par section (Instructions aux candidats / Formulaires / Clauses contractuelles)
  - Décrets : par article ; lier au texte de référence modifié avec `modifie_decret:2009-156`
- **Pipeline OCR** : Requis pour les décrets 2009-159 à 2009-162 (scans binaires)
- **Format Word** : Les DAO ARMP sont en `.docx` — conversion python-docx → texte avant vectorisation
- **Remarques** :
  - Distinguer `type:loi|decret` (base légale) vs `type:dao_type` (instruments pratiques)
  - Crawl annuel recommandé des JO SGG pour détecter les décrets modificatifs
  - Surveiller une éventuelle réforme du code de 2009 (aucune annoncée à ce jour)

---

## Tableau récapitulatif global des sources

| ID | Domaine | Intitulé | Source | Format | Fraîcheur | Libre | DL direct | Statut |
|----|---------|----------|--------|--------|-----------|-------|-----------|--------|
| F1 | fiscal | CGI Tome I | finances.gouv.cg | PDF | 2021 | Oui | Oui | 🟠 |
| F2 | fiscal | CGI Tome II | finances.gouv.cg | PDF | 2021 | Oui | Oui | 🟠 |
| F3 | fiscal | Loi de finances 2025 (n°47-2024) | finances.gouv.cg | PDF | 30/12/2024 | Oui | Oui | 🟢 |
| F4 | fiscal | Journal Officiel SGG (portail) | sgg.cg | PDF | 1946–2026 | Oui* | Oui | 🟢 |
| F5 | fiscal | Recueil textes fiscaux LF2023 | unicongo.cg | PDF | 10/2023 | Oui | Oui | 🟠 |
| F6 | fiscal | PLF 2025 (projet) | finances.gouv.cg | PDF | 10/2024 | Oui | Oui | 🟠 |
| F7 | fiscal | DGID (circulaires/instructions) | dgid.tax | HTML | 2025 | — | Non | 🔴 |
| F8 | fiscal | CGI consolidé 2025 (éditeur privé) | droit-afrique.com | PDF | 2025 | Non | Non | 🟠 |
| T1 | travail | Code du travail Loi 45-75 | sgg.cg / unicongo.cg | PDF scan | 1975/2024 | Oui | Oui | 🟠 |
| T2 | travail | Loi 6-96 (modif. code travail) | sgg.cg / ilo.org | PDF+HTML | 1996 | Oui | Oui | 🟢 |
| T3 | travail | Avant-projet nouveau code travail | fonction-publique.gouv.cg | HTML | 2025 | — | Non | 🔴 |
| T4 | travail | Décrets SMIG 2024 + Retraite 2024 | oarh.cg / sgg.cg | PDF | 2024 | Oui | Oui | 🟢 |
| T5 | travail | Conv. collective Services Pétroliers | oarh.cg / liziba.cg | PDF | 2022/2023 | Oui | Oui | 🟢 |
| T6 | travail | Conv. collective Hydrocarbures | oarh.cg / liziba.cg | PDF | 2022 | Oui | Oui | 🟢 |
| T7 | travail | Conv. collective BTP | oarh.cg / unicongo.cg | PDF | 2022 | Oui | Oui | 🟢 |
| T8 | travail | Conv. collective Commerce | oarh.cg | PDF | 2021 | Oui | Oui | 🟢 |
| T9 | travail | 17 conventions UNICONGO (index) | unicongo.cg | PDF | 1991–2024 | Oui | Oui | 🟢 |
| T10 | travail | Portail OARH (agrégateur) | oarh.cg | PDF | 2024 | Oui | Oui | 🟢 |
| A1 | admin | Décret 2009-156 Code marchés publics | sgg.cg / liziba.cg | PDF | 2009/2012 | Oui | Oui | 🟢 |
| A2 | admin | Décret 2009-157 ARMP | liziba.cg | PDF | 2009 | Oui | Oui | 🟢 |
| A3 | admin | Décrets 2009-159/160/162 | sgg.cg | PDF scan | 2009 | Oui | Oui | 🟢 |
| A4 | admin | Décrets modificatifs 2022-2024 | sgg.cg JO | PDF | 2022–2025 | Oui | Oui | 🟠 |
| A5 | admin | DAO type Fournitures ARMP | armp.cg | Word | 2011 | Oui | Oui | 🟢 |
| A6 | admin | DAO type Travaux ARMP | armp.cg | Word | 2011 | Oui | Partiel | 🟠 |
| A7 | admin | Manuel procédures CMP ARMP | armp.cg | PDF | 2009/2025 | Oui | Oui | 🟢 |
| A8 | admin | Codes SGG (domaine État, urbanisme) | sgg.cg | PDF | 2004–2023 | Oui | Oui | 🟢 |
| A9 | admin | BOAMP (bulletin annonces MP) | armp.cg | PDF | 2024–2025 | Non | Non | 🔴 |

*Version électronique informative uniquement selon mention légale SGG ; seule la version papier fait foi.

---

## Points de vigilance transversaux

### 1. Absence de licence Creative Commons explicite
Les portails sgg.cg, finances.gouv.cg et armp.cg ne publient aucune licence Creative Commons ou équivalente. Les textes officiels congolais sont par nature dans le **domaine public réglementaire**, mais une confirmation formelle est recommandée avant toute diffusion commerciale via ZolaOS. Contacter : journal.officiel@sgg.cg.

### 2. OCR requis pour la majorité des PDF scannés
La Loi 45-75, les décrets 2009, et la plupart des conventions collectives sont des scans CCITT/JPEG. Pipeline recommandé : **Tesseract 5+ avec modèle français** ou EasyOCR. À prévoir dans l'ingestion pipeline avant vectorisation.

### 3. Version papier vs version électronique (SGG)
La mention légale du SGG précise que *« seule la version papier de l'édition ordinaire du Journal Officiel fait foi »*. Les PDF ont valeur informative. L'agent RAG devra **avertir l'utilisateur** de consulter la version papier pour tout acte juridique officiel.

### 4. Droit transitoire (Code du travail)
La Loi 45-75 et ses modifications 1996 restent le droit positif en vigueur. L'avant-projet de nouveau code du travail (Dec. 2025) n'est pas encore adopté. À surveiller.

### 5. Gap fiscal post-2021
Aucun CGI consolidé gratuit n'intègre les LF 2022 + 2023 + 2024 + 2025. Stratégie : juxtaposition CGI 2021 + LF annuelles + Recueil UNICONGO 2023.

---

## Sources de référence par portail

| Portail | URL | Contenu | Périmètre |
|---------|-----|---------|-----------|
| Finances.gouv.cg | https://www.finances.gouv.cg/ | CGI, LF annuelles, DGCMP | fiscal_cg + admin_cg |
| SGG.cg | https://www.sgg.cg/ | Journal Officiel, 17 codes consolidés | Tous agents |
| ARMP.cg | https://armp.cg/ | Marchés publics, DAO types, BOAMP | admin_cg |
| UNICONGO.cg | https://www.unicongo.cg/ | Textes fiscaux, 17 conventions collectives | fiscal_cg + travail_cg |
| OARH.cg | https://www.oarh.cg/ | Code travail, 20 conventions, décrets | travail_cg |
| Liziba.cg | https://liziba.cg/ | Décrets marchés publics, conventions | admin_cg + travail_cg |
| ILO NATLEX | https://natlex.ilo.org/ | Code travail (HTML + PDF) | travail_cg |
| DGID.tax | https://dgid.tax/ | Instructions fiscales DGID | fiscal_cg |
