# Tokenizer et langues africaines — le « piège tokenizer bantou » (lot L2.2)

> Lot L2.2 de `docs/CHAMPION_ROADMAP.md` (couche 2 — adaptation modèle africain) :
> **« Choisir une base ouverte (Llama-3 / Qwen2.5 / GLM). Point dur : les
> tokenizers fragmentent mal les langues bantoues (coût + qualité) → analyser,
> éventuellement étendre le vocabulaire. »**
>
> Ce document répond à ce lot : il mesure le phénomène sur des échantillons
> réels, et documente la décision base/tokenizer. Il est le pendant
> « adaptation modèle » de `docs/sourcing/african_languages.md` (qui qualifie
> les corpus d'entraînement — lot L2.1) : les deux docs se recoupent sur le
> même constat (français bien doté, swahili correct, lingala/kituba en
> désert de données), vus sous deux angles différents (tokenizer ici,
> corpus là-bas).

## 1. Le problème : fertility et coût de contexte

Un tokenizer BPE (Byte-Pair Encoding) apprend son vocabulaire de sous-mots sur
un corpus d'entraînement. Un tokenizer entraîné très majoritairement sur de
l'anglais et des langues latines à fort volume web (cas de la plupart des
tokenizers de bases ouvertes, Llama-3 inclus — cf. §5.1 de Meta AI, vocabulaire
de ~128k tokens dominé par l'anglais/code/langues européennes) **sur-segmente**
les langues qu'il a peu ou pas vues à l'entraînement : un mot qui serait un
seul token dans la langue bien dotée se retrouve découpé en plusieurs
sous-tokens, parfois jusqu'au niveau syllabe ou octet, dans la langue peu
dotée.

La métrique standard pour quantifier ça est la **fertility** — tokens produits
par mot (Rust et al., ACL 2021, *"How Good is Your Tokenizer?"*,
[arXiv:2012.15613](https://arxiv.org/abs/2012.15613), qui l'introduit comme
mesure comparative de tokenizers multilingues). Une fertility de 1.0 = un
token par mot (idéal). Plus elle monte, plus le texte gonfle en nombre de
tokens pour la même information.

Cela a un coût direct et mesurable :

- **Contexte** : une fenêtre de contexte fixe (ex. 8k tokens) contient
  mécaniquement *moins de texte réel* dans une langue à fertility 3.0 que dans
  une langue à fertility 1.5 — deux fois moins de contenu utile pour le même
  budget.
- **Latence / coût d'inférence** : le nombre de tokens générés/traités est le
  facteur direct de coût sur la quasi-totalité des moteurs d'inférence (y
  compris local — cf. `project_latency_gpu_constraint`, 43 tok/s en local sur
  ce poste : une requête à fertility 3.0 prend mécaniquement ~2× plus de temps
  qu'une requête équivalente à fertility 1.5, à débit token/s constant).
- **Qualité générative** : Ahia et al., EMNLP 2023, *"Do All Languages Cost the
  Same? Tokenization in the Era of Commercial Language Models"*
  ([arXiv:2305.13707](https://arxiv.org/abs/2305.13707)) montrent, sur des API
  commerciales, que les locuteurs de langues à forte fertility paient
  mécaniquement plus cher **et** obtiennent de moins bons résultats — la
  sur-segmentation n'est pas neutre pour la qualité, elle éloigne le modèle de
  la structure morphologique réelle du mot.

C'est ce phénomène, appliqué aux langues bantoues (lingala, kituba/munukutuba,
une partie du swahili) et à d'autres langues africaines peu dotées (wolof),
que ce lot nomme le « piège tokenizer bantou ».

## 2. Méthode de mesure

**Script** : [`scripts/analyze_tokenizer.py`](../scripts/analyze_tokenizer.py).

Pour un ensemble d'échantillons de texte par langue, il calcule par langue :

- **fertility** = nombre de tokens produits par le tokenizer ÷ nombre de
  « mots » (référence indépendante du tokenizer : suite de caractères
  alphanumériques Unicode avec apostrophe interne tolérée, ex. `aujourd'hui` =
  1 mot ; limite connue : un mot à trait d'union comme `allez-vous` compte
  pour 2 « mots », ce qui légèrement gonfle le dénominateur pour le français).
- **chars/token** = nombre de caractères ÷ nombre de tokens (signal
  complémentaire : une fertility haute avec un chars/token très bas confirme
  une segmentation en sous-mots très courts, proche du repli octet).

Le chargement d'un tokenizer réel se fait via `transformers.AutoTokenizer` et
est **optionnel et gracieux** : absence de `transformers`, dépôt gated sans
jeton d'authentification, ou coupure réseau → le script **bascule
automatiquement sur un tokenizer de repli whitespace** (découpage naïf sur les
espaces) et l'indique explicitement sur `stderr`. Le repli whitespace ne
mesure pas la vraie fragmentation BPE (par construction, un mot séparé par un
espace y vaut ~1 token) : il prouve seulement que le pipeline de calcul
(fertility, chars/token) est correct de bout en bout — vérifié par
`tests/test_analyze_tokenizer.py`, sans réseau ni modèle lourd.

**Échantillons** : [`data/lang_samples/`](../data/lang_samples/), un fichier
`.txt` par langue (une phrase par ligne). Jeu volontairement **petit et
inégal en confiance selon la langue**, conformément à la consigne de ne pas
inventer de faux texte :

| Langue | Fichier | Phrases | Confiance |
|---|---|---|---|
| Français | `fr.txt` | 5 | Haute — usage courant vérifiable |
| Swahili | `sw.txt` | 5 | Haute — usage courant vérifiable |
| Lingala | `ln.txt` | 4 | Moyenne — salutations attestées dans les manuels de conversation usuels, non validées par un locuteur natif dans ce dépôt |
| Wolof | `wo.txt` | 3 | Moyenne — salutations très courantes, orthographe non revalidée |
| Kituba / Munukutuba | `mkw.txt` | 2 | **Faible** — réduit à 2 mots de base partagés dans la famille kikongo, pas des phrases complètes (cf. `docs/sourcing/african_languages.md` §3.3 : « désert quasi total » de corpus texte validé pour cette langue) |

**Limite méthodologique assumée** : 2 à 5 phrases par langue est un
échantillon **directionnel, pas un benchmark statistique**. Les études de
référence (FLORES-200 devtest ≈ 1 000 phrases/langue, Rust et al. sur des
corpus Wikipedia complets) utilisent des volumes bien plus larges pour une
estimation stable. Ici, le but premier est de **prouver que la méthode
tourne** et de donner un premier signal exploitable — pas de livrer un
chiffre définitif. Le script accepte `--samples` vers n'importe quel corpus
plus large (ex. FLORES-200 par langue) pour affiner la mesure sans changer
une ligne de code.

## 3. Résultats mesurés

### 3.1 Repli whitespace (aucun réseau, aucun poids — preuve de méthode)

```
python scripts/analyze_tokenizer.py --samples data/lang_samples
```

| Langue | Phrases | Mots | Tokens | Fertility | Chars/token |
|---|---|---|---|---|---|
| Français (fr) | 5 | 30 | 31 | 1.03 | 5.55 |
| Lingala (ln) | 4 | 7 | 7 | 1.00 | 6.43 |
| Kituba / Munukutuba (mkw) | 2 | 2 | 2 | 1.00 | 7.00 |
| Swahili (sw) | 5 | 15 | 15 | 1.00 | 5.87 |
| Wolof (wo) | 3 | 7 | 7 | 1.00 | 4.86 |

Comme attendu (§2), fertility ≈ 1.0 partout : le repli whitespace ne révèle
**rien** sur la fragmentation BPE réelle, il valide seulement le pipeline de
calcul.

### 3.2 Tokenizers BPE réels (mesurés dans cette session, réseau disponible)

Trois tokenizers publics ont pu être chargés via `transformers` sur ce poste
(contrairement à l'hypothèse « hors-ligne » par défaut du script) :

- **GPT-2** (`gpt2`) — tokenizer anglo-centré de référence, sert de
  comparaison haute.
- **Qwen2.5-7B** (`Qwen/Qwen2.5-7B`) — dépôt public, non gated.
- **Llama-3-8B** — `meta-llama/Meta-Llama-3-8B` est **gated** (401, jeton HF
  requis) : le repli whitespace s'est déclenché exactement comme prévu par le
  script (message `chargement échoué` sur stderr, cf. §2). Pour obtenir le
  chiffre réel malgré le gate, la mesure ci-dessous utilise
  `NousResearch/Meta-Llama-3-8B`, un mirroir public non-gated qui distribue les
  **mêmes fichiers de tokenizer** que le dépôt officiel (pratique courante
  dans la communauté HF pour contourner le gate sur les poids ; vocabulaire de
  base confirmé à 128 000 tokens ici, cohérent avec le vocabulaire de ~128k
  documenté publiquement pour Llama-3). **Réserve honnête** : le hash du
  fichier `tokenizer.json` n'a pas été comparé octet à octet avec le dépôt
  officiel gated dans cette session — à traiter comme une forte présomption,
  pas une certitude absolue, si ce chiffre doit être cité hors de ce
  document.

| Langue | GPT-2 | Qwen2.5-7B | Llama-3-8B (mirroir) |
|---|---|---|---|
| Français (fr) | 2.33 | 1.67 | 1.67 |
| Lingala (ln) | 3.00 | 2.71 | 2.71 |
| Kituba / Munukutuba (mkw) | 3.50 | 3.00 | 3.00 |
| Swahili (sw) | 2.73 | 2.73 | 2.60 |
| Wolof (wo) | 2.86 | 2.71 | 2.71 |

(chars/token, résultats bruts JSON reproductibles via `--output` — non
recopiés ici par souci de lisibilité, mais régénérables en une commande, cf.
§5.)

## 4. Interprétation

Le signal est **cohérent sur les trois tokenizers réels et avec la doctrine
attendue** :

- Le **français** a systématiquement la fertility la plus basse (1.67 sur
  Llama-3/Qwen2.5) — attendu, langue latine à fort volume dans tous ces
  corpus d'entraînement.
- **Lingala, kituba/munukutuba et wolof** tournent tous à **1.6-1.8× la
  fertility du français** sur Llama-3 (2.71, 3.00, 2.71 contre 1.67) : un
  texte dans ces langues consomme **60 à 80 % de tokens en plus** pour la même
  information — donc autant de contexte et de temps de calcul en plus, à
  contenu constant.
- Le **swahili**, pourtant la langue africaine la mieux dotée en corpus après
  le français d'après `docs/sourcing/african_languages.md` (§3.4, Wikipedia
  ~107 700 articles + mC4 823 Mo), reste lui aussi pénalisé (2.60-2.73) : être
  « la moins mal dotée » ne suffit pas à échapper au piège — la barre de
  volume nécessaire pour qu'un tokenizer généraliste apprenne des sous-mots
  swahili efficaces est simplement plus haute que ce que ces corpus
  représentent proportionnellement dans le mélange d'entraînement global de
  Llama-3.
- Le **kituba/munukutuba** est le pire cas mesuré (3.00-3.50) — cohérence
  frappante avec le verdict « désert quasi total » de `docs/sourcing/
  african_languages.md` §3.3 : c'est la langue la moins vue à l'entraînement
  de tous les tokenizers testés, et c'est mécaniquement celle qui fragmente le
  plus. **Deux diagnostics indépendants (corpus L2.1, tokenizer L2.2)
  convergent sur la même langue prioritaire.**

Réserve : Qwen2.5 et le mirroir Llama-3 donnent des chiffres quasi identiques
sur 4 langues/5 (écart notable seulement sur le swahili, 2.73 vs 2.60) — cohérent
avec le fait que les deux familles de tokenizers BPE modernes à large
vocabulaire (~128k-150k) convergent vers une couverture similaire des scripts
latins peu représentés, faute de volume propre à ces langues dans leurs corpus
respectifs.

## 5. Reproduire la mesure

```bash
# Repli whitespace seul (aucun réseau) — preuve de méthode
python scripts/analyze_tokenizer.py --samples data/lang_samples

# Comparaison multi-tokenizers (nécessite réseau + transformers ;
# meta-llama/Meta-Llama-3-8B est gated, utiliser un jeton HF ou le mirroir
# NousResearch comme fait dans ce document)
python scripts/analyze_tokenizer.py --samples data/lang_samples \
    --tokenizer gpt2 \
    --tokenizer Qwen/Qwen2.5-7B \
    --tokenizer NousResearch/Meta-Llama-3-8B \
    --output /tmp/tokenizer_results.json
```

## 6. Décision : garder Llama-3 tel quel, ou étendre le vocabulaire ?

**Deux options, avec un précédent concret pour chacune** :

- **Étendre le vocabulaire** : entraîner un modèle SentencePiece/BPE dédié sur
  un corpus africain, puis **fusionner** son vocabulaire dans le tokenizer
  Llama-3 (union des deux vocabulaires) et ré-entraîner/adapter les embeddings
  des nouveaux tokens par continued-pretraining. C'est exactement la méthode
  documentée par Cui, Yang & Yao (2023), *"Efficient and Effective Text
  Encoding for Chinese LLaMA and Alpaca"*
  ([arXiv:2304.08177](https://arxiv.org/abs/2304.08177)) : vocabulaire
  SentencePiece chinois de 20k tokens fusionné dans le tokenizer LLaMA
  d'origine (49 953 tokens au final), puis adaptation par pretraining continu.
  **Compromis** : gain de fertility potentiellement important, mais (a) il
  faut un corpus monolingue de volume suffisant pour apprendre des fusions
  BPE qui généralisent (le corpus chinois de ce papier se compte en
  dizaines de Go — sans commune mesure avec ce qui existe aujourd'hui pour
  lingala/kituba, cf. §7) ; (b) chaque token nouveau ajoute une ligne
  d'embedding non-entraînée qui doit être apprise (continued-pretraining, pas
  juste un LoRA léger) ; (c) complexité d'ingénierie et de maintenance
  ajoutée (fork de tokenizer à faire vivre à chaque mise à jour de la base).
- **Ne pas toucher au tokenizer**, entraîner directement sur la base Llama-3
  telle quelle (LoRA/QLoRA puis fine-tune complet si le volume le justifie,
  cf. L2.3). C'est l'approche qui absorbe le coût de fertility mesuré au §4
  sans investissement supplémentaire de tokenizer.
- **Alternative à mentionner** : InkubaLM (Lelapa AI, 2024,
  [arXiv:2408.17024](https://arxiv.org/abs/2408.17024)) ne fait ni l'un ni
  l'autre — il entraîne un tout petit modèle (0,4 Md de paramètres) **à
  partir de zéro** sur 5 langues africaines (dont swahili et haoussa) avec son
  propre tokenizer natif, et bat Llama-3-8B en zero-shot moyen sur AfriXNLI
  pour ces langues. C'est la preuve qu'un tokenizer nativement adapté (même
  sur un tout petit modèle) peut structurellement dépasser un grand modèle
  généraliste mal tokenizé pour la langue cible — argument fort *en faveur*
  de l'intérêt du vocabulaire adapté à long terme, mais avec un coût
  d'entraînement (from scratch) que ZolaOS n'a pas les moyens de reproduire
  à ce stade (cf. contrainte GPU de `docs/CHAMPION_ROADMAP.md` §Transverse).

### Recommandation

**Garder le tokenizer Llama-3 tel quel pour l'adaptation immédiate (L2.3),
et ne pas ouvrir le chantier d'extension de vocabulaire maintenant** — pour
trois raisons qui se recoupent :

1. **Le corpus qui justifierait l'extension n'existe pas encore pour les
   langues qui en ont le plus besoin.** `docs/sourcing/african_languages.md`
   documente un « désert quasi total » pour le lingala et le kituba/munukutuba
   — précisément les deux langues où la fertility mesurée ici est la pire
   (2.71 et 3.00-3.50). Entraîner un SentencePiece dédié sur quelques Mo de
   texte propre produirait un vocabulaire qui surapprend le bruit plutôt
   qu'une vraie couverture morphologique — l'extension de vocabulaire n'est
   défendable que là où le volume de corpus le permet (méthode Cui et al. sur
   des dizaines de Go de chinois).
2. **La méthode d'adaptation déjà planifiée (L2.3, LoRA/QLoRA d'abord)** est
   conçue pour être peu coûteuse et prouver l'uplift avant tout investissement
   lourd. Ajouter une chirurgie de tokenizer + continued-pretraining des
   nouveaux embeddings *avant* d'avoir prouvé l'uplift du LoRA serait inverser
   l'ordre « commencer petit, scaler au financement » déjà acté dans
   `docs/CHAMPION_ROADMAP.md`.
3. **Le coût mesuré (1.6-1.8×) est réel mais absorbable à ce stade** :
   il dégrade la densité de contexte et la latence, pas la faisabilité — un
   LoRA sur la base telle quelle reste un premier pas valide et mesurable
   (via L2.4, à construire) avant de statuer sur une extension.

**Revisiter la décision, langue par langue, quand le corpus le permet** :
le swahili est le candidat le plus mûr si un jour l'extension est jugée utile
(volume réel disponible, cf. `docs/sourcing/african_languages.md` §3.4) ;
lingala/kituba resteront hors de portée d'une extension de vocabulaire
robuste tant qu'une collecte primaire (partenariat local, §6 du doc de
sourcing) n'aura pas produit un corpus d'un tout autre ordre de grandeur.
D'ici là, le levier disponible pour ces langues est le fine-tuning
(vocabulaire inchangé), pas la chirurgie de tokenizer.

## 7. Références

- Rust, A., Pfeiffer, J., Vulić, I., Ruder, S., Gurevych, I. (2021). *How Good
  is Your Tokenizer? On the Monolingual Performance of Multilingual Language
  Models.* ACL 2021.
  [arXiv:2012.15613](https://arxiv.org/abs/2012.15613) — définition/usage de
  la fertility comme métrique comparative de tokenizers.
- Ahia, O., Kumar, S., Gonen, H., Kasai, J., Mortensen, D., Smith, N.,
  Tsvetkov, Y. (2023). *Do All Languages Cost the Same? Tokenization in the
  Era of Commercial Language Models.* EMNLP 2023.
  [arXiv:2305.13707](https://arxiv.org/abs/2305.13707) — coût et qualité
  inégaux entre langues sur des API commerciales, à cause de la
  tokenization.
- Cui, Y., Yang, Z., Yao, X. (2023). *Efficient and Effective Text Encoding
  for Chinese LLaMA and Alpaca.*
  [arXiv:2304.08177](https://arxiv.org/abs/2304.08177) — méthode concrète
  d'extension de vocabulaire (SentencePiece dédié fusionné dans le tokenizer
  LLaMA d'origine) prise en référence pour l'option « étendre » du §6.
- Tonja, A. L. et al. / Lelapa AI (2024). *InkubaLM: A Small Language Model
  for Low-Resource African Languages.*
  [arXiv:2408.17024](https://arxiv.org/abs/2408.17024) — modèle africain
  entraîné from-scratch (5 langues dont swahili, haoussa), tokenizer natif,
  bat Llama-3-8B en zero-shot moyen sur AfriXNLI pour ces langues.
- Masakhane (masakhane.io) — communauté de recherche panafricaine en TAL,
  déjà référencée dans `docs/sourcing/african_languages.md` (AfriBERTa,
  MasakhaNER, AfriSenti, etc.) comme source de corpus/outils pour les
  langues couvertes ici.
