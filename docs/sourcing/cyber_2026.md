# Sourcing — corpus cybersécurité (`rag_cyber`)

Catalogue des **sources réelles** à ingérer dans le corpus `rag_cyber` (pôle
Cyber/GRC : durcissement défensif, détection d'anomalies, registre de
conformité). Sourcing du 2026-07-27, par WebSearch/WebFetch vérifiés (chaque
URL a été récupérée et son contenu inspecté — cf. méthode en bas de fichier).

> **Doctrine : socle INTERNATIONAL d'abord, bonus LOCAL congolais ensuite.**
> Le gros du volume vient des référentiels internationaux (NIST, OWASP, MITRE)
> qui couvrent la technique de manière profonde et stable. Le bonus local
> (lois congolaises) ne vise pas l'exhaustivité mais les points où le droit
> national s'impose (obligations légales, autorité compétente).
>
> **Rôle du corpus.** Ce corpus **ne calcule rien** : CYBER-1 (audit de
> durcissement) et CYBER-2 (détection d'anomalies journaux/registre) sont des
> moteurs déterministes qui produisent des constats factuels (port ouvert,
> service exposé, pic anormal d'échecs d'authentification, etc.). Le RAG sert
> uniquement à **citer la norme qui qualifie ce constat** — "recommandation
> NIST SP 800-53 AC-7" en face d'un constat de verrouillage de compte absent,
> "OWASP ASVS V2.2.1" en face d'un défaut de politique de mot de passe. Le
> corpus ne doit jamais devenir la source du chiffre ou du seuil — ça reste le
> rôle des moteurs déterministes (cf. `project_hook_evidence` — hook evidence
> livré le 2026-07-24).
>
> **Règle de non-fabrication.** Toute URL ci-dessous a été récupérée par
> WebFetch et son contenu inspecté (extraction de texte via `pypdf`, pas
> seulement un code HTTP). Quand une source canonique n'a pas pu être
> confirmée ou n'existe pas sous forme ingérable en l'état, elle est marquée
> `pending` avec la raison exacte — jamais d'URL inventée.

---

## 1. Tableau des licences — ce qui rentre, ce qui ne rentre pas

Produit **commercial** (Polaris vend du conseil augmenté via ZolaOS) : la
licence de chaque texte a été vérifiée avant toute décision d'ingestion.

| Source | Licence constatée | Décision |
|---|---|---|
| **NIST** (CSF 2.0, SP 800-53, SP 800-61, SP 800-171) | Œuvre du gouvernement fédéral américain — domaine public (17 U.S.C. §105) | ✅ **Ingérer le texte intégral** |
| **OWASP** (ASVS) | CC BY-SA 4.0 (attribution + partage à l'identique) | ✅ **Ingérer le texte intégral** (attribution obligatoire) |
| **OWASP** (Top 10, Cheat Sheets) | CC BY-SA **3.0** pour le Top 10 (constaté sur owasp.org, pas 4.0) ; contenu publié en pages web/markdown, **aucun PDF officiel compilé** | 🟡 Licence OK, **mais pas de format ingérable** avec l'outillage actuel (cf. §4) |
| **MITRE ATT&CK** (matrice Enterprise, volet défensif) | Terms of Use ATT&CK : réutilisation/distribution avec attribution ; données STIX sous Apache-2.0 (`mitre-attack/attack-stix-data`) | 🟡 Licence OK, **mais données en STIX/JSON, pas en PDF** (cf. §4) |
| **ANSSI** (guide 42 mesures, guide TPE/PME) | Colophon des PDF : *« Licence Ouverte/Open Licence (Etalab — V1) »*. **Mais** les mentions légales de cyber.gouv.fr posent une **exception** : *« l'exploitation commerciale de ces contenus reste soumise à une autorisation préalable de l'ANSSI »* | ⚠️ **Conflit à trancher avant mise en production commerciale** — voir alerte §5 |
| **République du Congo** (Loi 29-2019, Loi 26-2020, Loi 27-2020, Loi 30-2019) | Textes officiels publiés au Journal Officiel — domaine public réglementaire (même statut que les autres textes CG déjà ingérés dans `rag_legal`/`rag_fintech`) | ✅ **Ingérer le texte intégral** |
| **ISO/IEC 27001, 27002** | Norme **propriétaire** — l'ISO vend le texte, pas de mise à disposition gratuite | ❌ **Jamais ingéré** — repère de structure uniquement (numérotation des clauses citée par renvoi, jamais le texte) |
| **CIS Controls / CIS Benchmarks** | CC BY-**NC**-SA — le **Non-Commercial** interdit explicitement l'usage par un produit commercial | ❌ **Jamais ingéré** — repère de structure uniquement, même traitement qu'ISO |

---

## 2. Schéma de tags à appliquer

```
framework:{nist|owasp|attack|anssi|loi2919|loi2620|loi2720|loi3019}
scope:{international|cg}
lang:{en|fr}
domaine:{gouvernance|technique|web|incident|conformite}
type:{referentiel|guide|texte_legal|mapping}
validated:{true|false}
```

- **`scope:`** est le levier du **bonus local** : `scope:international` pour
  le socle NIST/OWASP/MITRE/ANSSI, `scope:cg` pour les 4 lois congolaises.
  Le retriever peut ainsi remonter en priorité le texte local quand il existe
  (ex. obligations de notification de violation → Loi 29-2019 avant NIST
  SP 800-61), et retomber sur le socle international sinon.
- **`lang:`** sert à **privilégier le français à narration égale** : un
  constat technique peut être qualifié aussi bien par NIST (EN) que par
  l'ANSSI (FR) ou une loi CG (FR) ; à pertinence comparable, le prompt doit
  préférer citer la source française pour un rendu naturel en français —
  c'est le rôle de `lang:fr` dans le re-ranking, pas un filtre d'exclusion.
- **`framework:`** a été **étendu** au-delà de l'énumération initiale du
  brief (`anssi|loi2919|arpce`) : le sourcing a mis au jour **3 lois
  congolaises dédiées à la cybersécurité**, pas seulement la loi sur les
  données personnelles (voir §6). `loi2919`, `loi2620`, `loi2720`, `loi3019`
  suivent le même gabarit (`loi` + numéro + année sur 2 chiffres). Le tag
  `arpce` reste réservé au schéma mais **n'a aucune entrée** à ce stade —
  voir alerte §6.
- **`type:mapping`** est prévu pour MITRE ATT&CK (matrice tactiques ×
  techniques), même si aucune entrée manifeste n'existe encore (cf. §4).

---

## 3. Socle international — documents ingérés (`status: ready`)

| Document | URL vérifiée | Pages | Licence | Langue | Note |
|---|---|---|---|---|---|
| **NIST CSF 2.0** (26/02/2024) | [nvlpubs.nist.gov](https://nvlpubs.nist.gov/nistpubs/CSWP/NIST.CSWP.29.pdf) | 32 | Domaine public US | en | Framework de gouvernance du risque cyber (Govern/Identify/Protect/Detect/Respond/Recover) |
| **NIST SP 800-53 Rev. 5** | [nvlpubs.nist.gov](https://nvlpubs.nist.gov/nistpubs/SpecialPublications/NIST.SP.800-53r5.pdf) | 492 | Domaine public US | en | Catalogue de contrôles de sécurité/vie privée — texte de référence pour qualifier un constat CYBER-1 (ex. AC-7 verrouillage de compte, SI-4 surveillance) |
| **NIST SP 800-61 Rev. 3** (04/2025) | [nvlpubs.nist.gov](https://nvlpubs.nist.gov/nistpubs/SpecialPublications/NIST.SP.800-61r3.pdf) | 48 | Domaine public US | en | Remplace la Rev. 2 (Computer Security Incident Handling Guide) — recommandations de réponse à incident alignées CSF 2.0. **Utiliser la Rev. 3, pas la Rev. 2** (texte retiré/superseded, même logique que l'écueil LBC-FT 2016 vs 2024 documenté dans `fintech_reglementaire.md`) |
| **NIST SP 800-171 Rev. 3** (05/2024) | [nvlpubs.nist.gov](https://nvlpubs.nist.gov/nistpubs/SpecialPublications/NIST.SP.800-171r3.pdf) | 120 | Domaine public US | en | Protection des informations non classifiées contrôlées (CUI) en environnement non fédéral — pertinent pour la posture de sous-traitant/fournisseur |
| **OWASP ASVS 5.0.0** (05/2025) | [raw.githubusercontent.com/OWASP/ASVS](https://raw.githubusercontent.com/OWASP/ASVS/v5.0.0/5.0/OWASP_Application_Security_Verification_Standard_5.0.0_en.pdf) | 120 | CC BY-SA 4.0 | en | Verification standard applicatif — sert à qualifier les constats techniques web (authentification, gestion de session, validation d'entrée) |

Toutes les 5 URLs ci-dessus ont été récupérées par WebFetch (HTTP 200,
`application/pdf`) **et** le texte de la première page a été extrait via
`pypdf` pour confirmer l'identité du document (titre visible, texte natif —
pas un scan). Détail par document dans l'historique de la session ; exemple
NIST CSF 2.0 page 1 : *« National Institute of Standards and Technology …
February 26, 2024 … The NIST Cybersecurity Framework (CSF) 2.0 »*.

---

## 4. Socle international — bloqués par l'outillage, pas par la licence

Ces documents ont une licence compatible avec un usage commercial, mais ne
peuvent pas être ingérés avec l'outillage actuel (`ingest_from_manifest.py`
ne connaît que `method: pdf` et `method: hf_dataset` — cf.
`scripts/ingest_from_manifest.py`).

| Document | Pourquoi bloqué | Piste |
|---|---|---|
| **OWASP Top 10** (2021, et une édition 2025 semble en cours — statut final non confirmé) | Aucun PDF officiel compilé n'existe (seul le Top 10:2017 a un PDF archivé sur owasp.org ; 2021 et 2025 sont **web-only**, pages `owasp.org/Top10/2021/...`) | Ingestion par scraping de pages HTML/markdown (`github.com/OWASP/Top10`), pas par `method: pdf`. À construire. |
| **OWASP Cheat Sheet Series** | Diffusée en ~100 fichiers markdown individuels (`github.com/OWASP/CheatSheetSeries`) + site `cheatsheetseries.owasp.org` ; pas de PDF compilé officiel | Même remarque — nécessite un extracteur markdown/HTML dédié, à construire |
| **MITRE ATT&CK** (matrice Enterprise, volet défensif) | Données distribuées en STIX 2.1/2.0 JSON (`github.com/mitre-attack/attack-stix-data`, Apache-2.0), pas en PDF. Le contenu humainement lisible est sur `attack.mitre.org`, un site, pas un document | Nécessite un parseur STIX/JSON dédié (comme `ingest_ohada.py` route un dataset HF, un `ingest_attack.py` pourrait router `attack-stix-data`). À construire — non bloquant pour le lancement du corpus (CSF 2.0 + SP 800-53 couvrent déjà gouvernance/contrôles ; ATT&CK apporterait la dimension "techniques d'attaque" en plus) |

Ces trois entrées figurent dans `ingest_manifest.yml` en `status: pending`
avec une note technique, à la manière de l'entrée `iati_standard` déjà
présente (standard XML sans PDF unique).

---

## 5. ANSSI (France) — ALERTE licence à trancher avant mise en production

| Document | URL vérifiée | Pages | Version |
|---|---|---|---|
| **Guide d'hygiène informatique** (42 mesures) | [messervices.cyber.gouv.fr](https://messervices.cyber.gouv.fr/documents-guides/guide_hygiene_informatique_anssi.pdf) | 72 | v2.0, septembre 2017 (ANSSI-GP-042) |
| **La cybersécurité pour les TPE/PME en 13 questions** | [messervices.cyber.gouv.fr](https://messervices.cyber.gouv.fr/documents-guides/20241212_np_anssi_guide_tpe-pme_v2.pdf) | 37 | v2.5, novembre 2024 (ANSSI-GP-086) |

Les deux PDF ont été récupérés et leur texte extrait (natif, propre — page de
garde et colophon lisibles). **Le colophon de chaque PDF indique** :

> *« Licence Ouverte/Open Licence (Etalab — V1) »*

Ce qui, seul, autoriserait une réutilisation commerciale (c'est tout le
principe d'une licence ouverte Etalab). **Mais** la page des mentions
légales de `cyber.gouv.fr` (consultée séparément) précise :

> *« Les contenus présents sur le site internet de l'agence nationale de la
> sécurité des systèmes d'information sont couverts par la « Licence
> ouverte/open licence », version 1.0, sauf mention explicite. **Par
> exception à la licence précédente, l'exploitation commerciale de ces
> contenus reste soumise à une autorisation préalable** de l'agence
> nationale de la sécurité des systèmes d'information. »*

**Ces deux mentions se contredisent** : le document lui-même ne porte aucune
mention d'exception, mais le site qui l'héberge en revendique une de portée
générale. Faute de pouvoir trancher unilatéralement une question de droit
pour un produit commercial, les deux entrées sont marquées **`status:
pending`** dans le manifeste (texte prêt, `validated:true`, mais ingestion
**suspendue** en attendant confirmation écrite de l'ANSSI ou avis juridique).
Ne pas basculer en `ready` sans lever ce point.

---

## 6. Bonus local — République du Congo : plus riche que prévu

Le brief initial anticipait *« Loi 29-2019 + directives ARPCE + cadre CEMAC à
sourcer »*. Le sourcing a mis au jour un corpus local **plus complet** :
**4 lois congolaises directement dédiées au cyber**, et une clarification
institutionnelle importante.

| Loi | Objet | URL vérifiée | Statut extraction |
|---|---|---|---|
| **Loi n°29-2019** du 10/10/2019 | Protection des données à caractère personnel | [guot.cg](https://guot.cg/docs/texte_certification/Loi%20n%C2%B0%2029-2019%20du%2010%20octobre%202019%20-%20portant%20protection%20des%20donn%C3%A9es%20%C3%A0%20caract%C3%A8re%20personnel.pdf) (identique au JO [sgg.cg 2019-45](https://www.sgg.cg/JO/2019/congo-jo-2019-45.pdf)) | ✅ Texte natif propre, 101 articles extraits et relus (obligations du responsable de traitement, droits des personnes, violations de données, sanctions — art. 98 renvoie explicitement à la « loi portant lutte contre la cybercriminalité ») |
| **Loi n°26-2020** du 05/06/2020 | **Relative à la cybersécurité** — régit le cadre juridique national de sécurité des systèmes d'information et des réseaux de communications électroniques ; définit la cryptologie et son régime | [guot.cg](https://guot.cg/docs/texte_certification/Loi%20n%C2%B0%2026-2020%20du%205%20juin%202020%20-%20relative%20%C3%A0%20la%20cybers%C3%A9curit%C3%A9.pdf) (identique au JO [sgg.cg 2020-23](https://www.sgg.cg/JO/2020/congo-jo-2020-23.pdf)) | ✅ Texte natif propre, 14 pages |
| **Loi n°27-2020** du 05/06/2020 | Portant lutte contre la cybercriminalité (108 articles rapportés — atteintes à la confidentialité/intégrité des SI, interception frauduleuse, infractions sur données personnelles) | [sgg.cg](https://www.sgg.cg/textes-officiels/lois/2020/congo-loi-2020-27.pdf) | ⛔ **Scan pur (0 caractère extrait sur 28 pages)** — confirmé par `pypdf`. Deux miroirs testés (`droit-afrique.com`, `awa-afrika.com`) sont **aussi des scans image** (flux `DCTDecode`/JPEG). OCR requis avant ingestion (même protocole que le LBC-FT 2024 dans `fintech_reglementaire.md` : `scripts/ocr_scan.py --dpi 300`, puis relecture humaine des seuils/peines avant `validated:true`) |
| **Loi n°30-2019** du 10/10/2019 | Portant création de l'**Agence Nationale de Sécurité des Systèmes d'Information** (ANSSI-Congo) — établissement public sous tutelle de la Présidence | Non trouvée en PDF autonome ; présente uniquement dans le Journal Officiel [sgg.cg 2019-42](https://www.sgg.cg/JO/2019/congo-jo-2019-42.pdf) (24 pages), **mêlée** à 2 autres lois sans rapport (accord transport aérien Congo-Burkina Faso, loi d'orientation de la performance de l'action publique) et à des décrets/nominations | 🟡 JO confirmé et texte natif (sommaire lu : *« 10 oct. Loi n° 30-2019 portant création de l'agence nationale de sécurité des systèmes d'information … 1232 »*), mais nécessite une **extraction par plage de pages** pour isoler la loi du reste du JO avant ingestion — point ouvert, non bloquant |

### Correction importante : ARPCE n'est pas l'autorité cyber

Le brief supposait des *« directives ARPCE (régulateur CG) »*. Le sourcing
montre que :

- **ARPCE** (Agence de Régulation des Postes et des Communications
  Électroniques, créée par la loi n°11-2009) est le régulateur **télécoms et
  postal** — identification des abonnés, conformité des opérateurs. Aucun
  texte normatif **spécifiquement cyber** publié par l'ARPCE n'a été trouvé.
- L'autorité cyber dédiée est l'**ANSSI-Congo** (Agence Nationale de Sécurité
  des Systèmes d'Information, loi n°30-2019 ci-dessus), placée sous la
  Présidence de la République. Une coopération ANSSI-Congo × ARPCE a été
  annoncée en 2026 (protection des infrastructures télécoms, gestion
  d'incidents, partage de renseignement), mais ce n'est pas un texte
  normatif ingérable.

Le tag `framework:arpce` est **conservé** dans le schéma pour une future
directive technique ARPCE (sécurité des réseaux, identification), mais
**aucune entrée manifeste n'existe à ce stade** — pas de fabrication d'URL.

### CEMAC — pas de règlement ratifié, seulement un projet non contraignant

Recherche du *« cadre CEMAC cyber »* mentionné comme probablement à sourcer :
seul document trouvé est un **projet de lois types / projet de directives**
produit en 2013 par le projet HIPSSA de l'UIT (Union internationale des
télécommunications) : *« Cybersécurité : Projets de Lois Types de la CEEAC et
projets de Directives de la CEMAC »*
([itu.int](https://www.itu.int/en/ITU-D/Projects/ITU-EC-ACP/HIPSSA/Documents/REGIONAL%20documents/projets_des_lois_types-directives_cybersecurite_CEEAC_CEMAC.pdf),
92 pages, confirmé). C'est un **modèle non contraignant** de 2013 — les
recherches successives (2026) indiquent que la CEMAC/CEEAC *« travaille
activement »* à un cadre harmonisé mais qu'aucun règlement n'est encore
ratifié à ce jour. Statut : `pending`, valeur informative/historique
uniquement — ne pas le présenter comme du droit positif CEMAC.

---

## 7. Ce qui ne sera JAMAIS ingéré (texte intégral)

- **ISO/IEC 27001** (SMSI) et **ISO/IEC 27002** (mesures de sécurité) — normes
  vendues par l'ISO. Le corpus ne doit contenir **aucun extrait de texte** de
  ces normes ; seule la **numérotation des clauses** peut être citée par
  renvoi structurel (ex. "aligné sur la structure ISO 27001 A.9" sans
  reproduire le texte de la clause), à la façon dont un plan de contrôle
  GRC-1 référence une structure sans en recopier le contenu protégé.
- **CIS Controls / CIS Benchmarks** — CC BY-**NC**-SA : le *Non-Commercial*
  interdit expressément la réutilisation par ZolaOS/Polaris (produit
  commercial). Même traitement que l'ISO : repère de structure, jamais de
  texte.

Toute mention future de "CIS Control 5" ou "ISO 27001 A.9.2" dans une
réponse doit provenir d'un **mapping interne** (ex. table de correspondance
NIST CSF ↔ ISO 27001 ↔ CIS, construite à la main, sans reproduire le texte
protégé), jamais d'un chunk RAG portant le texte de la norme elle-même.

---

## 8. Point ouvert : chunker pour les référentiels structurés

`chunker: legal_article` (découpage sur `Article \d+`) est appliqué aux
textes de loi (Loi 29-2019, Loi 26-2020, et futurs 27-2020/30-2019). Il
n'est **pas adapté** à NIST/OWASP, qui sont structurés en sections/sous-
sections numérotées (ex. "3.2 Organizational Profiles", "V2.1.1") plutôt
qu'en articles. Ces documents utilisent donc le chunker par défaut
(découpage par taille), ce qui est sous-optimal : un chunk peut couper au
milieu d'un contrôle ou d'une exigence numérotée. Un chunker `section`/
`heading` (découpage sur la structure de titres du PDF) serait l'idéal — ce
n'est **pas bloquant** pour le lancement du corpus, mais c'est une dette
technique à noter à côté de celle déjà connue sur le reranking hybride
(`project_refonte_citation_doctrine`).

---

## Méthode de vérification (rappel)

Pour chaque URL retenue en `status: ready` : récupération HTTP (WebFetch),
sauvegarde du binaire, puis extraction de texte avec `pypdf` (environnement
`.venv_test` du dépôt) sur la première page au minimum, pour confirmer :
(1) le document est bien celui attendu (titre visible), (2) le texte est
**natif** et non un scan (caractères extraits > 0, pas de charabia). Pour les
lois congolaises, le texte complet a été extrait et relu pour confirmer la
numérotation des articles. Aucune URL de ce document n'a été acceptée sur la
seule foi d'un résultat de recherche — chacune a été ouverte et inspectée.
