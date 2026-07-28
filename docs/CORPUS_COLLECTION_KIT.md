# Kit de collecte de corpus — langues africaines (lot L2.1, volet partenariats)

> **Ce document outille la COLLECTE**, pas le sourcing de l'existant. Il part
> du constat posé par `docs/sourcing/african_languages.md` (recherche web
> vérifiée, 2026-07-24) : pour le kituba/munukutuba et le lingala, l'ouvert
> commercialement exploitable est un **désert quasi total** ; pour le wolof,
> il est **pauvre**. Le goulot de la couche 2 (`docs/CHAMPION_ROADMAP.md`,
> lot L2.1) n'est donc pas le pipeline technique (il est conçu, cf. §3) mais
> la **matière première** — d'où ce kit : comment nouer les partenariats qui
> produiront les données qui n'existent nulle part en ouvert.
>
> **État — 2026-07-28 : document de méthode et de partenariat, aucune
> collecte lancée.** Les partenaires cités ont été vérifiés au web (existence,
> mission, coordonnées quand disponibles) ; aucun accord n'est signé, aucune
> donnée n'a été reçue. Ce document sert à préparer les premières prises de
> contact, pas à rendre compte d'un travail déjà fait.

Produit **commercial** (modèle adapté servi **localement** par ZolaOS/
Polaris) : toute donnée collectée doit être utilisable en droits ET en
souveraineté — cf. §4 pour le canevas de licence et les pièges déjà identifiés
(jw.org, NOODL-1.0, CC-BY-NC).

---

## 1. Priorisation — où collecter en premier

**Principe** : la priorité de collecte est **inverse** à la disponibilité de
l'ouvert. Une langue déjà bien dotée (swahili) n'a pas besoin de partenariat
de collecte à ce stade ; une langue désertique (kituba, lingala, wolof) ne
progressera **que** par collecte primaire.

| Langue | Ouvert dispo (cf. sourcing §3) | Effort de collecte requis | Urgence | Partenaire cible principal |
|---|---|---|---|---|
| **Kituba/munukutuba** (`mkw`) | **Aucun** (désert total confirmé — même le seul texte religieux substantiel est bloqué copyright) | **Très élevé** — tout est à créer : locuteurs, guide de style, corpus de départ | **Impérative — priorité 1** | CERELLO/UMNG (§6.1) ; à défaut, collecte communautaire directe (médias/radios du sud du Congo) |
| **Lingala** (`ln`) | Quasi-désert (quelques Mo Wikipedia/CC-100, insuffisant pour compétence générative) | **Élevé** — texte à créer, seul l'audio (Lacuna Fund) a du volume | **Forte — priorité 2** | CERELLO/UMNG (§6.1) ; presse/radio congolaise (VOA/RFI lingala, sous autorisation) |
| **Wolof** (`wo`) | Pauvre (socle propre mais petit : Kallaama, Wikipedia, FLORES) | **Modéré** — des acteurs commerciaux existent déjà et savent produire du volume | **Modérée — priorité 3** | GALSENAI, Baamtu Datamation (§6.2) |
| **Français (variété Congo)** | Bien doté en français global, **désert sur la couleur locale CG** | **Faible-modéré** — collecte ciblée (presse, administration), pas de langue à construire de zéro | Faible-modérée | CERELLO ; SGG (Journal Officiel, §6.3) ; presse CG |
| **Amharique** (`am`) | Correct en volume (OSCAR 513 Mo, AfriBERTa, MasakhaNEWS AFL-3.0) | Faible pour le volume ; **effort différent = tokenizer** (script Ge'ez, renvoi L2.2) | Faible (collecte) / distincte (technique) | Presse d'État éthiopienne (ENA, Walta) si volume additionnel jugé utile — non prioritaire |
| **Haoussa** (`ha`) | Correct (mC4, CC-100, AfriBERTa, Aya, FLEURS, BibleTTS) | Faible — socle suffisant pour démarrer | Faible | Aucun nécessaire à ce stade ; Masakhane si le volet annoté NC devient nécessaire |
| **Swahili** (`sw`) | Le mieux doté après le français (mC4, Wikipedia 107k articles, Common Voice, AfriSenti) | Faible — socle suffisant pour démarrer | Faible | Aucun nécessaire à ce stade |

**Lecture** : les trois premières lignes (kituba, lingala, wolof) concentrent
100 % de l'effort de partenariat à engager maintenant. Le reste du tableau
existe pour justifier de **ne pas** disperser l'effort dessus.

---

## 2. Types de données à collecter, par utilité pour l'adaptation Llama-3

Conforme à la stratégie déjà actée dans le sourcing (§4.4 de
`african_languages.md`) : **SFT/LoRA d'abord**, continued-pretraining (CPT)
seulement quand le volume le justifie. Les volumes ci-dessous sont des
**ordres de grandeur indicatifs** issus de la pratique du domaine (Aya
Dataset/Collection, Lugha-Llama, convention FLORES-200 à ~2 000 phrases/langue
pour l'éval) — **pas des chiffres garantis**, à recalibrer une fois un premier
lot reçu.

### (a) Paires d'instruction FR↔langue / instruction-réponse en langue — priorité 1

La voie **la plus utile immédiatement** pour du SFT/LoRA sur une langue à
volume monolingue trop faible (kituba, lingala, wolof) : pas besoin d'un
corpus massif, un jeu de quelques milliers de paires bien construites suffit
à démontrer un uplift.

- **Format cible** : `{"instruction": "...", "input": "...", "output": "..."}`
  ou conversationnel `messages: [...]`, en langue cible ou FR↔langue.
- **Sourcing possible** : traduction humaine (locuteur natif) d'un petit set
  d'instructions de référence existant (ex. sous-ensemble Aya déjà disponible
  en FR) ; ou production native (question/réponse rédigée directement en
  kituba/lingala/wolof par un locuteur, pas traduite).
- **Volumes-cibles indicatifs** :
  - Phase amorçage (preuve de concept LoRA) : **1 000 à 3 000 paires** —
    comparable aux volumes par langue mineure observés dans Aya.
  - Phase LoRA robuste : **10 000 à 30 000 paires**, idéalement orientées
    domaines métier ZolaOS (santé, droit OHADA, ERP) plutôt que génériques,
    pour que l'uplift se voie sur les cas d'usage réels du produit.

### (b) Texte monolingue propre — priorité 2 (utile plus tard, CPT)

Utile pour le continued-pretraining, mais **seulement une fois un seuil de
volume franchi** — pour kituba/lingala/wolof ce seuil est aujourd'hui hors de
portée sans collecte massive pluriannuelle (le sourcing L2.1 l'a confirmé :
quelques Mo au mieux). Continuer à accumuler ce texte (transcriptions,
articles, contes/proverbes CERELLO) construit vers ce seuil sans bloquer le
plan SFT.

- **Volumes-cibles indicatifs** : pas de seuil unique fiable pour des langues
  bantoues peu dotées (contrairement à l'anglais/français où des ordres de
  grandeur établis existent) — accumuler par paliers de **quelques dizaines de
  Mo**, réévaluer l'utilité empiriquement (cf. §4.1 sourcing, note sur les
  seuils de dédup calibrés pour l'anglais, non transposables tels quels).
- Le français/swahili ont déjà largement franchi ce seuil via l'ouvert
  (mC4/CC-100/Wikipedia) — pas de collecte monolingue prioritaire pour eux.

### (c) Parallèle FR↔langue — priorité 3 (traduction, éval)

Utile pour l'évaluation (au-delà des ~2 000 phrases FLORES déjà disponibles
par langue) et pour amorcer une traduction pivot (générer des paires
d'instruction (a) par traduction). **Ne remplace pas** (a) ou (b) comme socle
d'entraînement — sert de mesure et de génération assistée.

- **Volumes-cibles indicatifs** : **500 à 1 000 phrases parallèles
  supplémentaires** orientées domaine métier (santé/droit/ERP CG), en
  complément des FLORES-200 génériques, pour une éval qui reflète l'usage
  réel du produit — pas seulement la compréhension générale de la langue.

**Ordre de collecte recommandé** : (a) d'abord et en continu, (c) en parallèle
dès qu'un partenaire locuteur natif est engagé (le même travail de traduction
peut nourrir (a) et (c) simultanément), (b) en accumulation passive de tout ce
qui est produit ou reçu, sans objectif de volume à court terme pour
kituba/lingala/wolof.

---

## 3. Formats et intégration au pipeline

Rappel (`african_languages.md` §4) : le pipeline d'entraînement est **distinct**
du pipeline RAG (`ingest_manifest.yml`). Toute donnée collectée par ce kit
entre dans **`training_manifest.yml`** (structure proposée, pas encore câblée
par un script `scripts/prepare_training_corpus.py`), avec les champs :

```
id, lang, source, url, license, license_class, type, volume, status, note
```

Une donnée issue d'un partenariat (donc sans URL publique) doit en plus
porter :

```
contributor          # nom du partenaire/organisme (ex. CERELLO, GALSENAI)
agreement_id          # référence à l'accord de contribution signé (§4)
contains_personal_data  # bool — déclenche le circuit Loi 29-2019 (§5)
consent_obtained      # bool — traçabilité du consentement (voix, texte attribuable)
```

**Étapes obligatoires avant tout usage en entraînement**, dans l'ordre déjà
posé par le sourcing (§4.1) :

1. **Collecte** — fichier source jamais modifié en place, log de provenance
   horodaté, y compris pour les données reçues par email/partenariat (pas
   seulement les téléchargements HF/Wikimedia).
2. **Normalisation** — UTF-8, NFC, nettoyage HTML/markdown résiduel.
3. **Déduplication near-duplicate** — MinHash/LSH (`text-dedup`) ou patron
   FineWeb ; agnostique à la langue mais seuils non calibrés sur du bantou —
   à valider empiriquement une fois le premier lot partenaire reçu.
4. **Langid** — **jamais fastText `lid.176`** (ne couvre ni le lingala ni le
   kituba). Utiliser **GlotLID** (couverture lingala confirmée, F1 0,9965 ;
   couverture kituba non confirmée — à vérifier) et **AfroLID** (cite
   explicitement le kituba parmi les créoles couverts — probablement le
   signal le plus fiable pour cette langue précise). Faire tourner les deux
   en parallèle sur tout nouveau lot partenaire et comparer.
5. **Filtrage PII/toxicité** — **trou documenté à ne pas masquer** : aucun
   outil mainstream (Presidio, heuristiques BigScience/ROOTS) ne fournit de
   NER pour les langues bantoues. Pour tout corpus kituba/lingala reçu d'un
   partenaire, ce maillon doit être **manuel** (relecture humaine par le
   locuteur natif qui a produit ou validé la donnée) tant qu'un NER dédié
   n'existe pas — voir aussi §5 (double annotation) qui couvre en partie ce
   besoin.
6. **Formatage** — CPT (texte brut concaténé) réservé aux corpus volumineux ;
   SFT (`instruction/input/output`) pour tout le reste, en particulier tout
   ce qui vient de ce kit pour kituba/lingala/wolof (§2a).

---

## 4. Gabarit de licence / accord de contribution (canevas, pas un contrat)

Ce canevas liste les **clauses nécessaires**, pas un texte juridique final —
à faire relire par un juriste avant signature. Objectif : éviter les deux
pièges déjà rencontrés dans le sourcing.

> **Piège 1 — jw.org** : une licence qui semble ouverte peut être assortie
> d'une **interdiction explicite de text-and-data-mining**. Masakhane a
> essuyé un refus formel pour n'avoir pas obtenu ce droit précis. → le
> canevas doit nommer explicitement l'usage : "entraînement d'un modèle de
> langage (fine-tuning, LoRA, continued-pretraining)", pas seulement
> "reproduction" ou "recherche".
>
> **Piège 2 — CC-BY-NC / NOODL-1.0** : une clause non-commerciale ou une
> interdiction nommée "Generative AI" rend la donnée **inutilisable pour un
> produit vendu**, quelle que soit sa qualité. → le canevas doit exclure
> explicitement toute clause NC et obtenir une permission GenAI nommée.

### Clauses à faire figurer

1. **Objet et périmètre** — nature précise des données cédées (texte,
   parole, annotations, transcriptions) et volume/échantillon de référence.
2. **Cadre d'usage explicite** — "entraînement (fine-tuning/LoRA/continued-
   pretraining) d'un modèle de langage, servi **localement** par ZolaOS/
   Polaris, à des fins commerciales" — nommer l'IA générative et le
   déploiement local sans ambiguïté (contre-exemple : jw.org).
3. **Licence concédée** — non-exclusive, mondiale, perpétuelle (ou durée
   longue explicite), incluant le droit de créer et distribuer des **œuvres
   dérivées** (le modèle adapté et ses sorties) — **pas de clause NC**, pas de
   "recherche uniquement".
4. **Attribution** — mention du partenaire dans la documentation/model card
   du modèle adapté (cohérent avec les licences CC-BY déjà retenues dans le
   sourcing).
5. **Garantie de titularité** — le partenaire garantit détenir les droits
   (ou avoir recueilli le consentement des contributeurs/locuteurs) sur les
   données cédées — engage sa responsabilité en cas de contestation tierce.
6. **Conformité Loi 29-2019 (données personnelles)** — si les données
   contiennent de la voix ou du texte attribuable à des personnes physiques :
   clause de consentement éclairé documenté, finalité déclarée, droit
   d'accès/rectification/retrait, et **modalités de suppression** si un
   contributeur se rétracte après cession.
7. **Réciprocité** (à négocier selon partenaire) — accès du partenaire aux
   artefacts produits (ex. modèle fine-tuné pour ses propres besoins de
   recherche), co-mention dans une publication, ou contrepartie financière —
   sans obligation de republier les poids en ouvert.
8. **Confidentialité** — si les données incluent des éléments sensibles
   (santé, données administratives), clause de confidentialité distincte de
   la licence de réutilisation.
9. **Droit applicable** — droit congolais de préférence, cohérent avec
   l'exigence de souveraineté du produit (traitement et hébergement locaux).

**Ne jamais accepter en l'état** (rappel direct des pièges déjà tranchés dans
le sourcing) : une clause NC quelle qu'en soit la forme ; une clause
d'interdiction nommée "IA générative"/"Generative AI" sans levée explicite ;
une absence de mention du cadre d'usage précis (fine-tuning de modèle servi
localement).

---

## 5. Protocole d'annotation / qualité

1. **Locuteurs natifs obligatoires** — toute traduction ou production
   native (§2a) doit être faite ou validée par un locuteur natif de la
   variété **ciblée** (voir piège dialectal ci-dessous), pas par traduction
   automatique seule utilisée comme livrable final (elle peut servir de
   brouillon, jamais de source de vérité non relue).
2. **Double annotation** — pour tout lot de paires d'instruction ou de
   corpus annoté, faire produire/valider par deux locuteurs indépendants et
   mesurer l'accord inter-annotateur ; en cas de désaccord, arbitrage par un
   troisième relecteur (rôle que pourrait jouer CERELLO en tant
   qu'institution académique).
3. **Guide de style par langue** — document court et versionné fixant :
   orthographe retenue, gestion du code-switching français/langue locale
   (fréquent en usage réel au Congo), registre (formel/familier), et
   convention de translittération si pertinent.
4. **Gestion des variantes dialectales — piège déjà identifié à ne pas
   reproduire** :
   - **Kituba/munukutuba ≠ kikongo** (`kon`/`kg`) : la quasi-totalité des
     ressources "proches" trouvées sur le web couvrent le kikongo, pas le
     kituba véhiculaire du sud du Congo qui est la cible réelle. Tout guide
     de style et tout partenaire doivent confirmer explicitement travailler
     sur le **kituba/munukutuba**, pas le kikongo.
   - **Lingala** : distinguer lingala parlé/véhiculaire (Kinshasa/Brazzaville)
     et lingala littéraire/liturgique (souvent la seule forme écrite
     disponible, ex. Bible) — le second n'est pas représentatif du registre
     conversationnel cible du produit.
   - **Wolof** : variantes régionales (wolof urbain de Dakar vs wolof rural)
     — préciser la variété visée dans tout accord avec GALSENAI/Baamtu.
5. **Conformité Loi 29-2019** — dès qu'une donnée est attribuable à une
   personne physique (voix enregistrée, texte signé, réponse d'enquête) :
   consentement éclairé documenté par écrit avant collecte, finalité
   explicite (entraînement d'un modèle IA commercial servi localement),
   droit de retrait, minimisation (ne collecter que ce qui est nécessaire),
   et sécurisation du stockage (cohérent avec l'architecture Zero Trust
   Client déjà actée pour ZolaOS — les données brutes ne doivent pas
   transiter par une infrastructure tierce non maîtrisée).

**Point ouvert à noter** : à ce jour, aucun organe de contrôle équivalent à
une CNIL n'a été identifié avec certitude pour l'application opérationnelle
de la Loi 29-2019 (l'ANSSI-Congo, vérifiée existante, a un mandat
**cybersécurité** — loi distincte n°30-2019 — pas un mandat de protection des
données personnelles à proprement parler). À vérifier auprès d'un juriste
local avant tout accord impliquant des données personnelles à grande échelle.

---

## 6. Plan de collecte phasé et partenaires cibles (vérifiés au web, 2026-07-28)

### 6.1 CERELLO / Université Marien Ngouabi — partenaire prioritaire (kituba, lingala, français CG)

**Vérifié** : CERELLO (Centre de Recherches en Linguistique et Langues
Orales) existe, lancé le 21/07/2026 à l'Université Marien Ngouabi
(Brazzaville), initié par le Pr Yvon Pierre Ndongo Ibara. Site : cerello.org
(non résolu en accès direct au moment de la vérification — passer par la
page institutionnelle umng.cg). Contact confirmé : **cerello@umng.cg**,
01 Avenue Bayardelle, Poto-Poto, Brazzaville, (+242) 06 958 86 97 / 05 047 77
19. Le centre couvre cinq parcours (FLASH + École Normale Supérieure) et
annonce quatre axes, dont un axe **"traitement automatique des langues"**
portant un projet nommé **"Cartographie linguistique du Congo (CLC)"**, et
mentionne la collecte de "paroles spontanées, contes, proverbes, chansons,
devinettes" en langues congolaises — **aucun corpus publié à ce jour**
(confirmé par le sourcing initial et recoupé à cette vérification).

**Ce qu'on lui demande** :
- Confirmer si le projet CLC a déjà une collecte de terrain en cours
  (kituba/munukutuba, lingala) exploitable, même brute et non nettoyée.
- Proposer un partenariat de production ciblée : paires d'instruction FR↔
  kituba et FR↔lingala (§2a), avec un petit groupe d'étudiants/chercheurs
  locuteurs natifs rémunérés pour la tâche, sous l'accord de contribution du
  §4.
- Solliciter CERELLO comme **arbitre de qualité** (double annotation, guide
  de style) plutôt que seulement comme fournisseur de volume — rôle
  académique naturel.
- Étendre à terme au français Congo (presse/administration) une fois le
  volet kituba/lingala engagé — cohérent avec la doctrine "finir un module
  avant le suivant".

### 6.2 GALSENAI et Baamtu Datamation — wolof

**Vérifiés** : GalsenAI (galsen.ai) est une communauté sénégalaise IA/data
active, porteuse du **projet Waxal** (plateforme de commandes vocales en
langues locales sénégalaises — wolof, pulaar, sérère, mandinka, diola,
soninké) et de datasets HF sous l'organisation `galsenai` (dont
`galsenai/wolof_corpus`, **52 706 lignes / 4,79 Mo, licence non affichée,
README vide** — confirmé lors de cette vérification, cohérent avec la
réserve déjà posée dans le sourcing). Baamtu Datamation est une société
sénégalaise de data/IA confirmée, à l'origine des défis **AI4D Baamtu
Datamation** sur Zindi (ASR wolof, transport public) et de jeux TTS wolof
(deux locuteurs, >20 000 phrases chacun) — société **commerciale**, pas une
communauté bénévole.

**Ce qu'on leur demande** :
- **GALSENAI** : clarifier par écrit la licence de `galsenai/wolof_corpus`
  (README vide à ce jour) avant tout usage ; explorer une collaboration sur
  des paires d'instruction FR↔wolof issues du projet Waxal (déjà orienté
  commandes/instructions, proche du besoin SFT).
- **Baamtu Datamation** : ouvrir une discussion **commerciale** (pas
  seulement un partenariat ouvert) — c'est une société de data engineering,
  probable disposition à un engagement payant pour produire un lot dédié de
  paires FR↔wolof orientées métier (santé/droit/ERP), avec clauses du §4
  explicitement négociées (droit IA générative, pas de NC).

### 6.3 Masakhane — négociation ciblée, pas collecte primaire

**Vérifié** : communauté grassroots confirmée (masakhane.io, >2000 membres,
Slack actif, GitHub `masakhane-io`), mission NLP africain "par des Africains,
pour des Africains". Tous ses corpus de tâches annotées (MasakhaNER,
MasakhaNEWS sauf amharique, MAFAND-MT, MasakhaPOS) sont **CC-BY-NC-4.0** —
non utilisables commercialement en l'état.

**Ce qu'on lui demande** : pas une collecte, une **négociation de
relicensing** ciblée et de faible ampleur — en particulier MasakhaNEWS
lingala (870 phrases, BBC/VOA, déjà annotées et de bonne qualité) : demander
une licence commerciale limitée ou une exception écrite pour ce sous-
ensemble précis, en expliquant le cadre d'usage (modèle servi localement,
pas de revente des données elles-mêmes) — coût de négociation faible pour un
gain de qualité réel sur le lingala, langue en désert.

### 6.4 Common Voice (Mozilla) — canal à moyen terme, pas immédiat

**Vérifié** : processus d'ajout de langue documenté (`LANGUAGE.md`,
`COMMUNITIES.md` sur github.com/common-voice/common-voice) : demande de
langue → traduction de l'interface (Pontoon) → collecte de phrases →
lancement → contribution vocale communautaire → validation → publication
trimestrielle sous CC0 (compatible commercial sans réserve). Lingala et
kituba ne sont **pas** des locales actives à ce jour (confirmé par le
sourcing initial).

**Ce qu'on lui demande** : lancer une demande de locale kituba/lingala en
s'appuyant sur CERELLO comme coordinateur communautaire local (rôle que le
processus Common Voice attend explicitement) — démarche à **faible coût**
mais à **rendement lent** (mois, dépend du volontariat) : à traiter comme
canal complémentaire, pas comme solution au désert actuel.

### 6.5 État congolais — rôle réel à clarifier (correction par rapport à la piste initiale)

**Vérifié** : l'ANSSI-Congo existe bien (Agence Nationale de Sécurité des
Systèmes d'Information, Brazzaville, créée par la **loi n°30-2019**, distincte
de la loi n°29-2019 sur les données personnelles), mais son mandat est la
**cybersécurité nationale**, pas la collecte ou la mise à disposition de
corpus linguistiques ou administratifs. **Ce n'est donc pas le bon
interlocuteur pour de la donnée texte** — correction à noter par rapport à
la piste envisagée initialement.

Deux pistes plus pertinentes identifiées à cette vérification :
- **SGG (Secrétariat Général du Gouvernement, sgg.cg)** héberge le Journal
  Officiel (textes de loi, actes administratifs) en PDF — source potentielle
  de français administratif "couleur Congo", **à vérifier avant usage** :
  statut de droits des publications officielles non confirmé formellement
  (à traiter avec la même rigueur que les autres cases "ambiguë" du
  sourcing, pas présumé libre de droits sans vérification).
- **Presse congolaise** (Agence Congolaise d'Information/ACI, Journal de
  Brazza, Congo-B) — contenu utile pour le français CG et pour du lingala
  journalistique, mais **sous droit d'auteur classique** : nécessite un
  accord de reprise explicite, pas un scraping (même logique que
  l'interdiction jw.org — l'absence de mention TDM n'équivaut pas à une
  autorisation).

**Ce qu'on leur demande** (SGG, ACI, presse) : autorisation écrite de
réutilisation à des fins d'entraînement IA, sous les clauses du canevas §4 —
démarche administrative, pas technique, à engager en parallèle du volet
kituba/lingala mais avec une urgence moindre (le français CG est en priorité
4, cf. §1).

---

## 7. Synthèse — ordre d'action recommandé

1. **CERELLO** (§6.1) — premier contact (email `cerello@umng.cg`), c'est le
   seul partenaire qui couvre à la fois kituba (priorité 1) et lingala
   (priorité 2), avec un ancrage institutionnel qui facilite un accord de
   contribution propre dès le départ.
2. **Masakhane — MasakhaNEWS lingala** (§6.3) — négociation ciblée à faible
   coût (870 phrases déjà annotées) pendant que la collecte primaire avec
   CERELLO démarre en parallèle ; ne pas attendre l'un pour l'autre.
3. **GALSENAI / Baamtu** (§6.2) — en parallèle, wolof étant en priorité 3
   mais avec des interlocuteurs déjà organisés (association active,
   société commerciale) qui répondront probablement plus vite qu'une
   collecte de terrain kituba/lingala à construire de zéro.

Common Voice (§6.4) et le volet français CG/État (§6.5) sont **à préparer**
mais pas à prioriser dans les premières semaines — rendement plus lent ou
urgence moindre au regard du tableau de priorisation (§1).
