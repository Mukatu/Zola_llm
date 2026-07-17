# Sourcing — corpus réglementaire fintech (`rag_fintech`)

Catalogue des **sources réglementaires réelles** à ingérer dans le corpus
`rag_fintech` (pôle fintech : microfinance, LBC-FT, systèmes de paiement, zone
CEMAC / République du Congo).

> **Règle de non-fabrication.** Ce corpus ne doit contenir que des **textes
> officiels obtenus des sources ci-dessous**. Aucun seuil, taux ou ratio
> réglementaire n'est saisi de mémoire. Tant que les textes ne sont pas
> récupérés, seule une **fiche d'orientation** (institutions et périmètres,
> sans valeur chiffrée, `validated:false`) est ingérée.

## Institutions et périmètres

| Institution | Rôle | Périmètre pour le pôle |
|---|---|---|
| **COBAC** — Commission Bancaire de l'Afrique Centrale | Supervision des établissements de crédit et de **microfinance (EMF)** en zone CEMAC | Conditions d'exercice, agrément, ratios prudentiels des EMF |
| **GABAC** — Groupe d'Action contre le Blanchiment d'Argent en Afrique Centrale | Organisme régional type GAFI (LBC-FT) | Obligations de vigilance (KYC), déclaration de soupçon, gel |
| **BEAC** — Banque des États de l'Afrique Centrale | Émission monétaire, **systèmes et services de paiement** | Mobile Money / monnaie électronique, prestataires de paiement |
| **CEMAC / UMAC** | Édiction des règlements communautaires | Cadre LBC-FT, microfinance, paiements |
| **République du Congo** | Droit national applicable | Loi 29-2019 (protection des données), fiscalité EMF |

## Textes de référence à récupérer (portails officiels)

- **Microfinance / EMF** : règlement CEMAC/UMAC/COBAC relatif à l'exercice et au
  contrôle de l'activité de microfinance (famille des règlements EMF).
- **LBC-FT** : règlement CEMAC/UMAC/CM portant prévention et répression du
  blanchiment des capitaux et du financement du terrorisme.
- **Systèmes de paiement** : règlement CEMAC relatif aux services de paiement
  (monnaie électronique, Mobile Money).
- **Données personnelles** : Loi n° 29-2019 (République du Congo).

Portails : BEAC (beac.int), COBAC, Secrétariat CEMAC, GABAC, Journal Officiel CG.

## État au 2026-07-17 — textes récupérés et vérifiés

Les 4 URLs ci-dessous ont été **testées** (HTTP 200, `application/pdf`) et le texte
extrait a été **relu** avant toute décision d'ingestion. Déclarés dans
`ingest_manifest.yml`.

| Texte | Source | Extraction | État |
|---|---|---|---|
| Règl. **01/17/CEMAC/UMAC/COBAC** (27/09/2017) — exercice et contrôle de la **microfinance** | [sgg.cg](https://www.sgg.cg/txts-droit-reg/cemac-reglement-2017-01-exercice-controle-microfinance.pdf) | texte natif, corps propre (seule la page de garde est un scan illisible) | ✅ **ingéré** — 36 chunks, `validated:true` |
| Règl. **02/24/CEMAC/UMAC/CM** (2024) — **LBC-FT** | [gabac.org](https://gabac.org/textes-organiques/) | couche texte présente mais **corrompue** | ⛔ bloqué |
| Règl. **04/18/CEMAC/UMAC/COBAC** (21/12/2018) — services de paiement | [beac.int](https://www.beac.int/systemes-paiement/instructions-circulaires-reglements/) | scan pur, 0 caractère | ⛔ bloqué (OCR) |
| Règl. **03/CEMAC/UMAC/CM** (21/12/2016) — systèmes, moyens et incidents de paiement | [beac.int](https://www.beac.int/systemes-paiement/instructions-circulaires-reglements/) | scan pur, 0 caractère | ⛔ bloqué (OCR) |

### Le texte LBC-FT à jour est celui de 2024, pas celui de 2016

Le règlement n°01/CEMAC/UMAC/CM du 11/04/2016 (largement référencé, et disponible en
clair sur sgg.cg) a été **révisé** par le règlement **n°02/24/CEMAC/UMAC/CM**, publié
par le GABAC. Ingérer la version 2016 comme référence courante ferait citer à
l'assistant un texte abrogé — sur du KYC/AML, c'est une faute de conformité.

### Pourquoi le LBC-FT 2024 n'est pas ingéré malgré une couche texte

`pypdf` en extrait 203 000 caractères, mais c'est le produit d'un **mauvais OCR
d'origine**, dégradé sur toute la longueur — et **les nombres sont détruits** :

> `déclarer à I'ANIF les sornmes … présence d'au moins ,, ..iæ.r aËini`

Un seuil de déclaration océrisé de travers est **plus dangereux qu'un corpus vide** :
il produit une réponse fausse d'apparence sourcée, que le garde-fou d'ancrage ne peut
pas rattraper (il ne détecte que l'absence de source, pas sa corruption).

> **Piège outillage.** `ingest_pdf.py` ne bascule sur l'OCR que si l'extraction rend
> moins de `_MIN_TEXTE` (400) caractères. Il détecte le texte **absent**, jamais le
> texte **corrompu** — le PDF 2024 franchirait le seuil et polluerait le corpus en
> silence. **Toujours relire un échantillon du texte extrait avant d'ingérer.**

### Pour débloquer les 3 textes restants

1. **Obtenir l'OCR.** Le `Dockerfile` installe déjà `tesseract-ocr`,
   `tesseract-ocr-fra` et `poppler-utils`, mais l'image en service date d'avant cet
   ajout (`which tesseract` → absent). À noter, le `pip install … pytesseract
   pdf2image || true` du Dockerfile **masque son propre échec**.

   > **La reconstruction est bloquée sans `HF_TOKEN`.** Le `Dockerfile` (l. 84-89)
   > télécharge bge-m3 (~2,3 Go) au build **sans filet** (pas de `|| true` sur cette
   > étape) : sans token, le Hub bride les requêtes anonymes et le build cale puis
   > échoue. Aucun `HF_TOKEN` n'est présent dans l'environnement.
   >
   > **Contournement sans reconstruire** (utilisé le 2026-07-17) : `apt-get`
   > fonctionne dans un conteneur jetable lancé en root, ce qui suffit à océriser
   > hors image :
   > ```
   > docker compose run --rm --no-deps --user root \
   >   -v <repo>/scripts:/app/scripts:ro -v <repo>/data/fintech/ocr:/out app \
   >   sh -c "apt-get update -qq && apt-get install -y -qq tesseract-ocr \
   >          tesseract-ocr-fra poppler-utils && pip install -q pytesseract pdf2image \
   >          && python scripts/ocr_scan.py <url> /out/<nom>.txt --dpi 300"
   > ```
   > Bakage bge-m3 : inutile en dev — `docker-compose.local.yml` monte déjà le modèle
   > depuis l'hôte (`/opt/bge-m3`). Il ne compte que pour l'image de production.

2. **OCRiser** les scans : `scripts/ocr_scan.py <url|fichier> <sortie.txt> --dpi 300`.
   Le script réocérise **depuis les images de page**, en ignorant la couche texte
   existante (indispensable pour le PDF 2024, dont la couche est corrompue), et rend
   un **taux de mots français reconnus** — sous ~25 %, le texte est inexploitable.
3. **Faire relire les seuils par un humain** avant de passer `validated:true`. L'OCR
   se trompe précisément là où ça coûte le plus cher : les chiffres.

À noter : `gabac.org` renvoie **HTTP 500** sur le User-Agent du script
(`Mozilla/5.0 (ZolaOS ingestion bot)`). Un UA de navigateur complet + un `Referer`
passent, sans qu'il soit besoin de masquer l'identité de l'outil.

## Convention d'ingestion

- Schéma : `rag_fintech`. Tags : `country:cg`, `country:cemac`, `module:<domaine>`
  (`microfinance`, `lbcft`, `paiements`, `data`), `source:<institution>`, et
  `validated:true|false`.
- Chaque texte porte `source_uri` = URL officielle ; `source_id` = référence du
  texte. Métadonnée `validated:true` **uniquement** pour un texte officiel vérifié.
- Ingestion : `python scripts/ingest_fintech.py` (traite `data/fintech/`).
