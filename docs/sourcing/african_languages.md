# Sourcing — corpus d'ENTRAÎNEMENT langues africaines (adaptation Llama-3, lot L2.1)

> **Ce document n'est pas du sourcing RAG.** Il qualifie des corpus destinés à
> **fine-tuning / LoRA / continued-pretraining** d'une base **Llama-3** (couche 2
> de `docs/CHAMPION_ROADMAP.md`, lot L2.1). Le RAG (citation de sources au moment
> de la réponse) reste couvert par `docs/sourcing/*.md` existants et
> `ingest_manifest.yml` — ce sont deux pipelines distincts, deux manifestes
> distincts (voir §5.2).

> **État — 2026-07-24 : sourcing initial réalisé (recherche web vérifiée,
> aucune ingestion/entraînement lancé).** Périmètre couvert : français,
> lingala, kituba/munukutuba (priorité 1 — bassin Congo), swahili (priorité 2),
> wolof, haoussa, amharique (priorité 3). **Verdict transversal, à ne pas
> édulcorer** : le français est bien doté, le swahili est correct, le haoussa
> et l'amharique sont corrects avec des réserves de script/licence, le wolof
> est pauvre, et **le lingala comme le kituba/munukutuba sont quasiment un
> désert de données ouvertes exploitables commercialement** — voir §3.2/§3.3.
> Rien n'a été ingéré dans un manifeste d'entraînement réel à ce stade (le
> manifeste §5.2 est une **proposition de structure**, pas encore peuplé et
> exécuté).

Produit **commercial** (le modèle adapté sera servi par une entreprise, ZolaOS/
Polaris) : chaque licence ci-dessous a été vérifiée avec le même niveau
d'exigence que `docs/sourcing/cyber_2026.md` — seul compte le verdict
**usage commercial oui/non**, pas la simple existence d'une licence "ouverte".
Toute source non confirmée directement est marquée **à vérifier** ; aucune URL
ni aucun chiffre n'est inventé.

---

## 1. Tableau des licences transversal — familles de sources réutilisées à travers les langues

| Famille de source | Licence constatée | Verdict commercial |
|---|---|---|
| **Wikipedia dumps** (toutes langues) | CC-BY-SA 4.0 + GFDL | ✅ Compatible (attribution ; zone grise théorique du *share-alike* appliqué à un modèle fine-tuné, mais pratique de facto de tous les grands LLM ouverts) |
| **FLORES-200** (Meta/NLLB) | CC-BY-SA 4.0 | ✅ Compatible — mais **volume d'éval seulement** (~2 000-3 000 phrases/langue), jamais une base d'entraînement à soi seul |
| **mC4** (`allenai/c4`) | ODC-BY | ✅ Compatible avec attribution (a servi à mT5/BLOOM) — **meilleure source volumétrique quand elle existe** pour la langue visée |
| **AfriSenti** (Masakhane) | CC-BY-4.0 | ✅ Compatible — seule ressource Masakhane à licence permissive constatée |
| **Aya Dataset / Aya Collection** (Cohere For AI) | Apache-2.0 | ✅ Compatible — instruction-tuning, 65-101 langues, part par langue à vérifier au cas par cas |
| **AfriBERTa corpus** (castorini) | Apache-2.0 / MIT selon la page | ✅ Compatible — 11 langues (swahili, haoussa, amharique inclus ; **lingala/kituba absents**) |
| **ALFFA** | MIT | ✅ Compatible — corpus de parole (swahili, wolof) |
| **Kallaama** (wolof) | CC-BY-4.0 | ✅ Compatible |
| **Lacuna Fund / Mendeley** (lingala, orienté RDC) | CC-BY-4.0 | ✅ Compatible — **audio**, pas de texte |
| **Common Voice** (Mozilla) | CC0 | ✅ Compatible sans réserve — mais absent pour lingala/kituba/wolof |
| **Amharic News Text Classification** (IsraelAbebe) | MIT | ✅ Compatible |
| **Zindi/Zenodo Swahili News** | CC-BY-4.0 | ✅ Compatible |
| **MasakhaNER / MasakhaNEWS / MAFAND-Lafand-MT / MasakhaPOS** (Masakhane) | **CC-BY-NC-4.0** (sauf exceptions ponctuelles taguées AFL-3.0 sur certaines pages — incohérence constatée, à traiter avec prudence, cf. §3.5-3.7) | ❌ **NON commercial en l'état** — corpus de la meilleure qualité (annoté humainement) mais bloqué pour un produit vendu, sauf négociation directe avec Masakhane |
| **OSCAR** | Métadonnées CC0, texte brut = copyright des sites sources (Common Crawl) | 🟡 **Ambigu** — pratique de facto (tous les grands LLM l'utilisent) mais réserve juridique réelle sur le texte sous-jacent, jamais tranchée par OSCAR lui-même |
| **CC-100** | Non spécifiée, hérite des conditions Common Crawl | 🟡 **Ambigu**, même réserve qu'OSCAR |
| **JW.org / Bible NWT / JW300** | Copyright des sociétés bibliques ; jw.org **interdit explicitement le text-and-data-mining** dans son avis de copyright | ❌ **NON — bloqué, pas seulement par la licence mais par une clause anti-TDM explicite.** Masakhane a essuyé un refus formel de permission et a abandonné JW300 (retiré d'OPUS). À proscrire du pipeline, quelle que soit la tentation (souvent le seul corpus parallèle dense pour une langue peu dotée) |
| **NOODL-1.0** (jeux TTS Mozilla Data Collective : lingala, kituba, TWB Voice haoussa) | Licence propriétaire spécifique | ❌ **NON — interdit nommément l'usage « Generative AI » sans permission écrite** du détenteur, quel que soit le pays de l'utilisateur |
| **TWB Voice 1.0 Hausa** | CC-BY-NC-4.0 | ❌ NON commercial |

---

## 2. Schéma de tags proposé pour le manifeste d'entraînement

```
lang:{fr|ln|mkw|ktu|sw|wo|ha|am}         # ISO/glottocode — mkw=kituba CG, ktu=kituba RDC
family:{romance|bantu|niger-congo|afro-asiatic}
script:{latin|ethiopic}
type:{monolingual|parallel|instruction|speech}
license_class:{open_commercial|ambiguous_pending_legal|non_commercial|blocked}
status:{ready|pending|blocked}
```

`license_class` fait le tri que `status` seul ne fait pas : un corpus peut être
`status: ready` techniquement (URL valide, volume confirmé) mais
`license_class: ambiguous_pending_legal` (OSCAR/CC-100) ou `non_commercial`
(Masakhane NC) — dans les deux cas, **ne pas router vers l'entraînement d'un
modèle vendu** sans décision juridique explicite, même règle que l'alerte
ANSSI dans `docs/sourcing/cyber_2026.md`.

---

## 3. Par langue

### 3.1 Français

| Source | Licence | Verdict | Volume | Type |
|---|---|---|---|---|
| Wikipedia FR (dumps.wikimedia.org) | CC-BY-SA 4.0 + GFDL | ✅ | ~2,6 M articles | monolingue |
| OSCAR-2301 (fr) | ambigu (§1) | 🟡 pending légal | ~138 Go / ~32,7 Mds tokens | monolingue |
| mC4 (fr) | ODC-BY | ✅ | sous-ensemble des 6,3 T tokens globaux | monolingue |
| CC-100 (fr) | ambigu (§1) | 🟡 pending légal | ~27 Go (estimation) | monolingue |
| FLORES-200 (`fra_Latn`) | CC-BY-SA 4.0 | ✅ | ~2 000 phrases | parallèle (éval) |

**Spécifique français Congo/Afrique centrale** : quasiment rien d'exploitable
en corpus. BDLP Congo-Brazzaville (bdlp.org) = dictionnaire de ~850
particularismes lexicaux, **pas un corpus**. Une thèse HAL (tel-05067607, français
parlé au Congo) = corpus oral d'une douzaine de locuteurs, volume négligeable,
pas de licence ouverte. **CERELLO** (Centre de linguistique, Université Marien
Ngouabi, lancé le 21/07/2026) est un acteur institutionnel à surveiller — **aucun
corpus publié à ce jour**.

**Verdict** : bien doté en français global (Wikipedia FR = brique la plus sûre
juridiquement). La couleur « français du Congo » n'existe dans aucun corpus
ouvert et devra venir d'une **collecte propre** (presse CG, administration,
CERELLO en partenariat).

### 3.2 Lingala (`lin`/`ln`)

| Source | Licence | Verdict | Volume | Type |
|---|---|---|---|---|
| MasakhaNEWS | CC-BY-NC-4.0 | ❌ NON commercial | 870 phrases (BBC/VOA) | classification annotée |
| SIB-200 (`Davlan/sib200`) | CC-BY-SA-4.0 | ✅ | 1 004 phrases | classification (dérivé FLORES) |
| FLORES-200 (`lin_Latn`) | CC-BY-SA 4.0 | ✅ | ~2 000 phrases | parallèle (éval) |
| CC-100 (ln) | ambigu | 🟡 | **~2,3 Mo compressé** (anecdotique) | monolingue |
| Wikipedia lingala (ln.wikipedia.org) | CC-BY-SA 4.0 + GFDL | ✅ | ~4 900 articles, dump ~3,5 Mo compressé | monolingue |
| Lingala TTS (Mozilla Data Collective) | **NOODL-1.0** | ❌ interdiction GenAI explicite | 8 572 clips / ~4h26 | audio + texte |
| Congolese Speech (Lacuna Fund / Mendeley, `doi:10.17632/28x8tc9n9k.1`) | CC-BY-4.0 | ✅ | LRSC 4,3 h labellisé + CSRC 741 h non labellisé | audio (orienté RDC) |
| Bible lingala (jw.org, bible.com) | Copyright + clause anti-TDM | ❌ bloqué | Bible complète | parallèle |

**Absents confirmés** : OSCAR, mC4, AfriBERTa (11 langues, lingala non
inclus), MasakhaNER, MAFAND/LAFAND-MT, MasakhaPOS, AfriSenti, Common Voice.

**Verdict** : **très pauvre.** Les seuls gisements de volume réel sont bloqués
juridiquement (MasakhaNEWS NC, Bible copyright+anti-TDM, TTS NOODL). Le texte
ouvert commercialement propre tient dans quelques Mo (Wikipedia + CC-100 +
SIB-200/FLORES) — **suffisant pour de l'évaluation et un amorçage de style,
pas pour une vraie compétence générative**. La seule ressource dense et propre
(Lacuna Fund, CC-BY-4.0, 741 h) est de l'**audio**, pas du texte.

### 3.3 Kituba / Munukutuba (`mkw` Congo-Brazzaville / `ktu` RDC)

> **Point de vocabulaire décisif** : le kituba/munukutuba est une langue
> **distincte du kikongo** (`kon`/`kg`). Presque toutes les ressources
> « proches » trouvées sur le web couvrent le kikongo, **pas** le kituba
> véhiculaire du sud du Congo qui est la cible réelle de ZolaOS. Ne pas
> confondre les deux dans une future collecte ou négociation.

| Source | Statut vérifié |
|---|---|
| Masakhane (toute tâche) | **absent** |
| FLORES-200 / SIB-200 | **absent** (aucun code `mkw`/`ktu` ; le `kon_Latn`/`kwy` présent = kikongo, pas kituba) |
| OSCAR / mC4 / CC-100 | **absent** |
| Wikipedia / Wiktionary / Incubator | **aucune édition** (`kg.wikipedia.org` = kikongo, ~1 940 articles, 1,3 Mo — et ce n'est **pas** le kituba) |
| AfriBERTa / AfroXLMR | **absent** |
| Kituba TTS (Mozilla Data Collective) | existe (8 302 clips / ~5h50) mais **NOODL-1.0 → interdiction GenAI, bloqué** |
| Bible kituba (bible.com/languages/ktu) | *Nouveau Testament en Kikwango 1950* seulement (pas la Bible complète), copyright société biblique → bloqué |
| Bloom Library | livres en kikongo (`kwy`) confirmés ; **kituba non confirmé** (page dynamique non inspectable en l'état — à vérifier livre par livre) |

**Verdict** : **désert quasi total.** Aucun corpus texte ouvert commercialement
exploitable n'existe. La seule donnée texte substantielle est religieuse (NT
Kikwango, copyright) et le seul audio transcrit (Kituba-TTS) est sous licence
anti-GenAI. **C'est la langue prioritaire pour une collecte primaire** — rien
d'autre à faire ici tant qu'un partenariat local n'est pas noué (§6).

### 3.4 Swahili (`swh`/`sw`)

| Source | Licence | Verdict | Volume | Type |
|---|---|---|---|---|
| mC4 (`swa`) | ODC-BY | ✅ | 823,5 Mo / 4,22 M phrases | monolingue — **meilleure source confirmée** |
| CC-100 (sw) | ambigu | 🟡 | 332 Mo | monolingue |
| OSCAR-2301 (sw) | ambigu | 🟡 | 1 664 documents / ~1 Mo (décevant, à ne pas utiliser comme source principale) | monolingue |
| Wikipedia swahili (sw.wikipedia.org) | CC-BY-SA 4.0 + GFDL | ✅ | ~107 700 articles — **plus grande Wikipédia en langue Niger-Congo** | monolingue |
| AfriSenti | CC-BY-4.0 | ✅ | 3 014 tweets | sentiment |
| AfriBERTa corpus | Apache-2.0 | ✅ | part du corpus combiné 0,91 Go (11 langues) | monolingue |
| Common Voice | CC0 | ✅ | ~700+ h (chiffre 2026 exact à revérifier) | parole |
| ALFFA | MIT | ✅ | volume en heures à vérifier sur le repo | parole (ASR) |
| Zindi/Zenodo Swahili News | CC-BY-4.0 | ✅ | ~31 000+ articles de presse TZ/KE | monolingue presse |
| Aya Dataset / Aya-101 | Apache-2.0 | ✅ | part swahili non isolée dans les 204k exemples/65-101 langues | instruction |
| MasakhaNER/MasakhaNEWS/MAFAND-MT | CC-BY-NC-4.0 | ❌ NON commercial | — | annoté/parallèle |
| JW300, Tanzil (traduction swahili) | copyright / statut douteux | ❌ à écarter | — | parallèle |
| SwahBERT (corpus propre) | non confirmée publiquement | 🟡 à vérifier | ~105 Mo / 16M mots | monolingue (référence méthode seulement) |

**Verdict** : **la langue africaine la mieux dotée de la liste après le
français**, avec un socle commercial solide et vérifié (mC4 + Wikipedia +
CC-100 + AfriSenti + Common Voice). Écarter/isoler les corpus Masakhane NC et
JW300/Tanzil du périmètre commercial.

### 3.5 Wolof (`wol`/`wo`)

| Source | Licence | Verdict | Volume | Type |
|---|---|---|---|---|
| Kallaama (Zenodo/OpenSLR) | CC-BY-4.0 | ✅ | 55 h parole + 1,14 M mots texte | parole + texte |
| SENCORPUS fr-wol | CC-BY-4.0 (papier ; disponibilité effective à vérifier) | 🟡 | ~70 000 phrases parallèles | parallèle |
| FLORES-200 (`wol_Latn`) | CC-BY-SA 4.0 | ✅ | ~2 000 phrases (éval) | parallèle (éval) |
| Wikipedia wolof (wo.wikipedia.org) | CC-BY-SA 4.0 | ✅ | 1 742 articles / 656k mots | monolingue |
| CC-100 (wo) | ambigu | 🟡 | **~3,6 Mo** (anecdotique) | monolingue |
| ALFFA Wolof | à vérifier | 🟡 | ~18-21 h parole | parole (ASR) |
| galsenai/wolof_corpus (HF) | non affichée (README vide) | 🟡 à vérifier | 52 706 lignes / 4,79 Mo | monolingue |
| dVoice / wolof_tts (Baamtu/AI4D) | à vérifier par jeu | 🟡 | ~41 h | TTS/ASR |
| MasakhaNER/MAFAND-MT | CC-BY-NC-4.0 | ❌ NON commercial | ~6 500 phrases annotées | annoté/parallèle |
| Aya Dataset | Apache-2.0 | 🟡 | présent via GALSENAI mais **volume jugé insuffisant, exclu de l'entraînement final** par les auteurs eux-mêmes | instruction |
| JW300 | copyright + anti-TDM | ❌ bloqué | ~601k phrases parallèles | parallèle |
| OSCAR / mC4 / xP3 / Common Voice / AfriSenti | — | — | **wolof absent** de ces 5 corpus (confirmé) | — |

**Verdict** : **pauvre.** Absent des grands corpus web filtrés (OSCAR, mC4) et
des benchmarks d'instruction (xP3). Le seul socle propre et commercial est
petit (Kallaama, SENCORPUS à confirmer). Nécessite un partenariat sénégalais
(GALSENAI, Baamtu Datamation) pour du volume au-delà de l'anecdotique.

### 3.6 Haoussa (`hau`/`ha`)

| Source | Licence | Verdict | Volume | Type |
|---|---|---|---|---|
| mC4 (hau) | ODC-BY | ✅ | 1,16 Go / 252 M tokens | monolingue |
| CC-100 (ha) | ambigu | 🟡 | ~61 M mots | monolingue |
| AfriBERTa corpus | Apache-2.0 | ✅ | part du corpus combiné | monolingue |
| Aya Dataset | Apache-2.0 | ✅ | inclus (part non isolée) | instruction |
| FLEURS (Google) | CC-BY | ✅ | ~12 h | parole |
| BibleTTS Hausa (`vpetukhov/bible_tts_hausa`) | CC-BY-SA | ✅ | 86,6 h / 40 603 versets | parole (TTS/ASR) |
| Wikipedia haoussa (ha.wikipedia.org) | CC-BY-SA 4.0 | ✅ | ~92 000 articles (à revérifier précisément) | monolingue |
| FLORES-200 (`hau_Latn`) | CC-BY-SA 4.0 | ✅ | ~2 000 phrases (éval) | parallèle (éval) |
| AfriSenti | CC-BY-4.0 | ✅ | 22 155 tweets | sentiment |
| MasakhaNER/MasakhaNEWS/MAFAND-MT | CC-BY-NC-4.0 (MasakhaNEWS taguée AFL-3.0 sur une page — incohérence, traiter en NC par prudence) | ❌ NON commercial | — | annoté/parallèle |
| TWB Voice 1.0 Hausa | CC-BY-NC-4.0 | ❌ NON commercial | 58,11 h / 36 665 enregistrements | parole |
| BBC/VOA/DW/Leadership Hausa (presse) | pas de dataset packagé, cité dans une survey (arXiv:2605.22828) | 🟡 à vérifier | ordre de 150-350k mots par média | presse (non packagé) |
| OSCAR / xP3 | — | — | **haoussa absent** (confirmé) | — |

**Verdict** : **correct.** Socle commercial solide (mC4, CC-100, AfriBERTa,
Aya, FLEURS, BibleTTS, FLORES). Le matériel annoté le plus qualitatif
(MasakhaNER, MasakhaNEWS, MAFAND, TWB Voice) reste en CC-BY-NC — négociation à
prévoir si ce volet est jugé nécessaire.

### 3.7 Amharique (`amh`/`am`, écriture Ge'ez/Éthiopique)

| Source | Licence | Verdict | Volume | Type |
|---|---|---|---|---|
| OSCAR-2301 (am) | ambigu | 🟡 | 119 434 docs / 40,26 M mots / 512,9 Mo | monolingue |
| CC-100 (am) | licence "unknown" | 🟡 | ~133 Mo / 68 M tokens | monolingue |
| mC4 (am) | ODC-BY | ✅ | taille exacte non isolée | monolingue |
| Wikipedia amharique (am.wikipedia.org, vérifié en direct) | CC-BY-SA 4.0 + GFDL | ✅ | 15 704 articles | monolingue |
| AfriBERTa corpus | Apache-2.0/MIT | ✅ | ~0,213 Go (BBC Amharic + Common Crawl) | monolingue |
| MasakhaNEWS | **AFL-3.0** (constatée, distincte des autres tâches Masakhane) | ✅ compatible | articles BBC Amharic | classification |
| AfriSenti | CC-BY-4.0 | ✅ | 9 483 tweets | sentiment |
| Amharic News Text Classification (`IsraelAbebe`) | MIT | ✅ | >50 000 articles, 6 classes | classification |
| FLORES-200 (`amh_Ethi`) | CC-BY-SA 4.0 | ✅ | ~2 000 phrases (éval) | parallèle (éval) |
| Aya Dataset | Apache-2.0 | ✅ | volume amharique exact non isolé | instruction |
| MasakhaNER, MAFAND-MT | CC-BY-NC-4.0 | ❌ NON commercial | faible (2 500 phrases / val-test seulement) | annoté/parallèle |
| Common Voice | à vérifier (page non chargée en fetch) | 🟡 | ~1,9 h validées, 49 locuteurs — **très faible** | parole |
| OPUS (Tatoeba, GlobalVoices, bible-uedin, JW300) | variable, JW300 exclu (§1) | 🟡/❌ | quelques centaines de phrases | parallèle |
| Walta Information Center corpus | disponibilité/licence à vérifier | 🟡 | 8 715 articles / 210k tokens | presse |

**Verdict** : **correct en volume et diversité** (langue officielle, presse
d'État, OSCAR 513 Mo, AfriBERTa Apache-2.0, MasakhaNEWS AFL-3.0), mais avec un
**risque de faisabilité technique distinct des 6 autres langues** : l'écriture
Ge'ez/Éthiopique (abugida non latine) est quasi absente du tokenizer BPE de
Llama-3 — voir §4.3, extension/ré-entraînement de tokenizer probablement
nécessaire avant tout fine-tuning sérieux, indépendamment du volume de
données disponible.

### 3.8 Autres langues à fort corpus (hors périmètre immédiat, à noter pour une extension future)

La recherche a confirmé, sans les creuser en détail (hors du périmètre
demandé), que **zoulou, xhosa, yoruba, igbo et shona** disposent de corpus
Masakhane/AfriBERTa/mC4 comparables ou supérieurs à ceux du haoussa et de
l'amharique — candidats naturels pour une phase L2.1-bis si ZolaOS s'étend
au-delà de l'Afrique centrale/CEMAC. Le **wolof reste, dans cet ensemble, l'une
des langues les plus pauvres malgré son statut de langue nationale
sénégalaise** — pas une exception isolée du dossier.

---

## 4. Design du pipeline de données d'entraînement (distinct du pipeline RAG)

Le pipeline RAG (`scripts/ingest_from_manifest.py`, `docs/RAG_INGESTION.md`)
charge du texte à **citer** au moment de la réponse. Le pipeline
d'entraînement charge du texte à **absorber dans les poids** du modèle — deux
finalités, deux manifestes (§5.2), deux jeux de garanties (le RAG exige une
citabilité vérifiable ; l'entraînement exige une hygiène de corpus : dédup,
qualité, langue, PII).

### 4.1 Étapes

1. **Collecte** — téléchargement brut par source (HF `datasets`, dump
   Wikipedia, scraping GitHub Masakhane, export Common Voice), horodaté,
   jamais modifié en place (fichier source conservé tel quel + log de
   provenance).
2. **Normalisation** — encodage UTF-8, normalisation Unicode (NFC), suppression
   du HTML/markdown résiduel, segmentation en documents/phrases selon le type
   (`monolingual` vs `parallel`).
3. **Déduplication near-duplicate** — MinHash/LSH (`text-dedup`,
   Apache-2.0, github.com/ChenghaoMou/text-dedup) ou le patron FineWeb
   (5-grammes, ~112 fonctions de hash, seuil Jaccard 0,85,
   dédup **par lot/snapshot plutôt que globale** — une dédup trop agressive a
   dégradé la qualité du corpus retenu dans FineWeb, retenir cette leçon).
   Agnostique à la langue (opère sur des n-grammes), donc utilisable tel quel
   sur lingala/kituba, mais sans garantie que les seuils par défaut (calibrés
   sur corpus anglophone) soient optimaux pour une morphologie bantoue — à
   valider empiriquement une fois un volume suffisant réuni.
4. **Filtrage qualité/langue (langid)** — **ne pas utiliser `fastText
   lid.176`** : il couvre le swahili mais **pas** le lingala ni le
   kituba/kikongo (absents de ses 176 langues). Utiliser à la place :
   - **GlotLID** (Kargaran et al., EMNLP Findings 2023, arXiv:2310.16248,
     github.com/cisnlp/GlotLID, CC-BY-4.0) — couvre >1 665 langues,
     `lin_Latn` (lingala) confirmé avec F1 0,9965, `swa_Latn` F1 0,998 ;
     couverture kituba/`ktu` **non confirmée dans l'extrait consulté — à
     vérifier avant de trancher**, le kituba étant parfois fusionné avec le
     kikongo générique selon les taxonomies.
   - **AfroLID** (UBC-NLP, EMNLP 2022, arXiv:2210.11744,
     github.com/ubc-nlp/afrolid, Apache-2.0) — 517 langues/variétés
     africaines, macro-F1 ~97,4 %, **cite explicitement le kituba** parmi les
     créoles couverts (9 créoles inclus à l'entraînement) — à tester en
     complément de GlotLID, potentiellement le signal le plus fiable
     spécifiquement pour le kituba.
5. **Filtrage PII/toxicité** — **lacune réelle à documenter, pas à
   masquer** : Microsoft Presidio (github.com/microsoft/presidio) ne fournit
   aucun modèle NER officiel pour les langues bantoues peu dotées (son moteur
   NLP pluggable — spaCy/Stanza — n'a pas de modèle lingala/kituba/swahili
   packagé) ; les heuristiques BigScience/ROOTS (BLOOM) reposent surtout sur
   des règles regex language-agnostic (emails, téléphones, URLs) plutôt que
   sur un NER contextuel. **Pour lingala/kituba, ce maillon devra être
   construit sur mesure** (règles regex + éventuellement un petit modèle NER
   fine-tuné), pas espéré d'un outil existant.
6. **Formatage** — deux formats de sortie distincts selon la finalité :
   - **Continued-pretraining (CPT) monolingue** : texte brut concaténé par
     document, pas de structure question/réponse — réservé aux corpus
     volumineux (français, swahili, dans une moindre mesure haoussa/amharique).
   - **Paires instruction (SFT/LoRA)** : format `{"instruction", "input",
     "output"}` ou conversationnel (`messages: [...]`), à partir des corpus
     d'instruction existants (Aya Dataset/Collection) ou de traductions
     d'instructions existantes vers les langues cibles — c'est la voie
     **réaliste immédiate** pour lingala/kituba/wolof (§4.4), où le volume
     monolingue est trop faible pour justifier un CPT.

### 4.2 Manifeste d'entraînement proposé (`training_manifest.yml`, distinct de `ingest_manifest.yml`)

```yaml
# Manifeste d'entraînement — ZolaOS (couche 2, adaptation Llama-3)
# =====================================================================
# Distinct de ingest_manifest.yml (RAG) : ce manifeste liste des corpus
# destinés à entraîner les POIDS du modèle (CPT/SFT/LoRA), pas à être
# cités au moment de la réponse. Aucune exécution existante à ce jour —
# structure proposée par le sourcing L2.1, à câbler par un futur
# scripts/prepare_training_corpus.py.
#
# Champs :
#   id             identifiant stable du corpus
#   lang           code langue (ISO/glottocode — mkw=kituba CG, ktu=kituba RDC)
#   source         hébergeur (huggingface | github | wikimedia | mendeley | ...)
#   url            URL vérifiée
#   license        licence constatée
#   license_class  open_commercial | ambiguous_pending_legal | non_commercial | blocked
#   type           monolingual | parallel | instruction | speech
#   volume         estimation (phrases/mots/Mo/heures) — "a_verifier" si non confirmé
#   status         ready | pending | blocked
#   note           contexte, réserve, ou raison du blocage
# =====================================================================

defaults:
  pii_policy: to_build  # aucun outil PII mainstream ne couvre les langues bantoues, cf. §4.1.5

corpora:
  - id: wikipedia_fr
    lang: fr
    source: wikimedia
    url: https://dumps.wikimedia.org/frwiki/
    license: CC-BY-SA-4.0
    license_class: open_commercial
    type: monolingual
    volume: "~2,6M articles"
    status: ready

  - id: mc4_swahili
    lang: sw
    source: huggingface
    url: https://huggingface.co/datasets/allenai/c4
    license: ODC-BY
    license_class: open_commercial
    type: monolingual
    volume: "823,5 Mo / 4,22M phrases"
    status: ready

  - id: wikipedia_lingala
    lang: ln
    source: wikimedia
    url: https://dumps.wikimedia.org/lnwiki/latest/
    license: CC-BY-SA-4.0
    license_class: open_commercial
    type: monolingual
    volume: "~4 900 articles / dump ~3,5 Mo compressé"
    status: ready
    note: >-
      Volume anecdotique — insuffisant seul pour une compétence générative,
      cf. docs/sourcing/african_languages.md §3.2.

  - id: kituba_texte_ouvert
    lang: mkw
    source: n/a
    url: n/a
    license: n/a
    license_class: blocked
    type: monolingual
    volume: "0 (aucun corpus ouvert confirmé)"
    status: pending
    note: >-
      Aucune source ouverte trouvée — collecte primaire / partenariat requis,
      cf. §6. Ne pas confondre avec le kikongo (kon/kg), langue distincte.

  - id: masakhanews_lingala
    lang: ln
    source: huggingface
    url: https://huggingface.co/datasets/masakhane/masakhanews
    license: CC-BY-NC-4.0
    license_class: non_commercial
    type: monolingual
    volume: "870 phrases"
    status: blocked
    note: "Licence NC — jamais routé vers l'entraînement d'un modèle vendu sans négociation Masakhane."
```

### 4.3 Piège tokenizer — Llama-3 fragmente mal les langues bantoues (renvoi L2.2)

Le tokenizer de Llama-3 (BPE type tiktoken, ~128k tokens, entraîné très
majoritairement sur de l'anglais/langues à fort volume web) **sur-segmente**
les langues bantoues peu dotées : chaque mot est éclaté en davantage de
sous-tokens que pour l'anglais, ce qui (a) augmente le coût d'inférence à
contenu équivalent et (b) dégrade la qualité, le modèle voyant des unités qui
ne correspondent à aucune morphologie utile.

**Références réelles trouvées** :

- **« The African Language Tax »** (arXiv:2606.24460) — mesure la fertilité de
  tokenizer sur 20 langues africaines × 11 tokenizers : pénalité médiane
  ×1,88 tokens vs anglais, jusqu'à ×8,92 pour les scripts les plus
  défavorisés (dont l'éthiopique) — conséquence directe sur coût, latence, et
  fenêtre de contexte effective réduite à ~11 % de celle de l'anglais dans les
  pires cas.
- **« The Token Tax: Systematic Bias in Multilingual Tokenization »**
  (arXiv:2509.05486, AfricanNLP 2026) — teste explicitement **Llama 3.1 405B**
  sur AfriMMLU (16 langues africaines) : chaque token supplémentaire par mot
  réduit l'exactitude de 8 à 18 points, quel que soit le modèle. Les langues
  bantoues à morphologie agglutinante se regroupent systématiquement dans la
  tranche défavorable (2-3 tokens/mot).
- **Lugha-Llama** (arXiv:2504.06536) — adaptation directe de Llama-3.1-8B pour
  les langues africaines (dont le swahili) : garde le tokenizer Llama
  d'origine et compense par le volume de corpus (+10 % sur AfriQA) — preuve que
  le problème est traitable sans toucher au tokenizer, mais le coût
  d'inférence (fertilité) n'est pas résolu par cette approche seule.

**Solution documentée par analogie** — patron **Chinese-LLaMA-Alpaca**
(arXiv:2304.08177, github.com/ymcui/Chinese-LLaMA-Alpaca) : entraîner un
tokenizer SentencePiece dédié sur corpus local (20k tokens), puis **fusionner
par union** avec le vocabulaire Llama d'origine (32k → 49 953 tokens
dédupliqués), puis ré-entraîner les embeddings des tokens ajoutés. C'est le
patron transposable à lingala/kituba — **mais réservé au lot L2.2**
(`docs/CHAMPION_ROADMAP.md`), pas à ce lot de sourcing.

**Point ouvert** : aucune étude publiée mesurant spécifiquement la fertilité
du tokenizer Llama-3 sur le **lingala** ou le **kituba** isolément n'a été
trouvée (contrairement au swahili/zoulou/xhosa, bien couverts). À traiter par
analogie (bantoue, faible volume web) en attendant une mesure directe une fois
un premier corpus réuni.

### 4.4 Stratégie réaliste — SFT/LoRA d'abord, CPT monolingue quand le volume le justifie

Conforme à `docs/CHAMPION_ROADMAP.md` L2.3 (« démarrer LoRA/QLoRA ») : pour
lingala, kituba et wolof, le volume monolingue ouvert est trop faible pour un
continued-pretraining utile (quelques Mo). La voie réaliste immédiate est
l'**instruction-tuning (SFT/LoRA)** sur les données d'instruction disponibles
ou traduisibles (Aya Dataset/Collection couvrent déjà le français et le
swahili ; pour lingala/kituba, traduire un petit set d'instructions de
référence via un modèle pivot est plus rapide que d'attendre un corpus
monolingue massif). Le **continued-pretraining monolingue** ne devient
pertinent que pour le français et le swahili, où le volume (mC4/CC-100/
Wikipedia, centaines de Mo à dizaines de Go) le justifie déjà.

---

## 5. Ce qui ne sera jamais ingéré en l'état (rappel)

- **JW300 / Bible NWT (jw.org)** — copyright + clause anti-text-and-data-mining
  explicite. Masakhane a essuyé un refus formel et a retiré JW300 d'OPUS. À
  proscrire même si c'est souvent le seul corpus parallèle dense disponible
  pour une langue peu dotée (lingala, kituba, amharique).
- **NOODL-1.0** (TTS lingala/kituba, TWB Voice haoussa) — interdit
  explicitement l'usage « Generative AI » sans permission écrite du
  détenteur.
- **Corpus Masakhane sous CC-BY-NC-4.0** (MasakhaNER, MAFAND-MT, MasakhaPOS, et
  MasakhaNEWS selon la langue) — jamais routés vers l'entraînement du modèle
  vendu sans négociation directe et écrite avec Masakhane.

---

## 6. Où l'ouvert est insuffisant → partenariats nécessaires

| Langue | Priorité partenariat | Piste identifiée |
|---|---|---|
| **Kituba/munukutuba** | **Impérative** — désert quasi total | CERELLO / Université Marien Ngouabi (Brazzaville, lancé 21/07/2026, aucun corpus publié à ce jour) ; médias/radios locales ; sociétés bibliques (autorisation écrite explicite, pas de scraping) |
| **Lingala** | Forte — volume trop faible pour une vraie compétence | Idem CERELLO ; presse/radio congolaise (VOA/RFI lingala) ; Lacuna Fund pour étendre le volet audio déjà CC-BY-4.0 |
| **Wolof** | Modérée — socle petit mais pas nul | GALSENAI, Baamtu Datamation (dVoice) — clarifier la licence de `galsenai/wolof_corpus` |
| **Français (variété Congo)** | Faible-modérée | CERELLO ; presse/administration CG |
| **Amharique** | Faible (volume) / technique (tokenizer) | Presse d'État éthiopienne (ENA, Walta) pour du volume propre ; expertise linguistique pour l'adaptation tokenizer au script Ge'ez (lot L2.2) |
| **Swahili, Haoussa** | Faible | Socle ouvert déjà suffisant pour démarrer ; négociation Masakhane seulement si le volet annoté NC est jugé nécessaire |

**Rappel souveraineté** : ces données servent à entraîner un modèle **servi
localement** (poids ouverts, pas d'API cloud) — tout partenariat de collecte
doit préciser explicitement ce cadre d'usage (fine-tuning d'un modèle
autohébergé) dans toute négociation de licence, pour éviter l'écueil constaté
avec jw.org (refus faute de cadre d'usage suffisamment explicité).

---

## Méthode de vérification (rappel)

Chaque source a été recherchée puis, quand possible, sa page réelle
(HuggingFace, GitHub, Wikimedia, Zenodo/Mendeley, arXiv) a été récupérée pour
confirmer licence et volume affichés — pas seulement un résultat de moteur de
recherche. Les chiffres non confirmés directement sont marqués **à vérifier**
dans les tableaux ci-dessus ; aucune URL ni aucun dataset n'a été inventé.
Cette première passe reste une **recherche de sourcing**, pas un audit
juridique définitif — les cases `ambiguous_pending_legal` (OSCAR, CC-100)
demandent un avis juridique explicite avant tout usage en production
commerciale, à la manière de l'alerte ANSSI dans
`docs/sourcing/cyber_2026.md` §5.
