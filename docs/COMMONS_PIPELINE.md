# Commons de connaissance — pipeline de contribution (niveau 3)

> **Statut : cadrage (design). Aucun code de promotion n'existe encore.**
> Ce document définit *comment* l'usage chez les clients peut rendre le moteur
> ZolaOS partagé « perpétuellement plus expert », **sans jamais** faire remonter
> de donnée privée. Il précède l'implémentation.

## 1. Le problème

Le niveau 1 (enrichissement **local** par le retrieval-union) est acquis : les
documents d'un client rendent **son** assistant plus pertinent, chez lui.

La question du niveau 3 : comment le **moteur central partagé** (celui que tous
les déploiements reçoivent) profite-t-il de l'usage réel — sans violer :

- la **souveraineté** (argument de vente n°1 : les données restent chez le client) ;
- le **secret professionnel** (côté cabinet : jamais mélanger client A et client B) ;
- la **Loi 29-2019** sur la protection des données personnelles (Congo).

Réponse de cadrage : **seul un savoir dérivé, dé-identifié, généralisé et validé
franchit la frontière du locataire — jamais la donnée source.**

## 2. Les 6 invariants (non négociables)

- **I1 — Rien de brut ne sort.** Aucun document, montant, nom, ni `source_uri`
  privé ne quitte le locataire. Seuls des **candidats dérivés** circulent.
- **I2 — Dé-identification avant la frontière.** L'anonymisation (réutilise
  `security/pii.PIIRedactionPolicy`) s'exécute **côté locataire**, avant tout
  transfert. Un candidat non anonymisé ne peut pas être émis.
- **I3 — k-anonymat.** Un motif n'est éligible à la promotion que s'il est
  **corroboré** (vu ≥ *k* fois, idéalement sur ≥ *k* locataires indépendants).
  Empêche de ré-identifier un client unique par un motif singulier. Défaut *k=3*.
- **I4 — Opt-in explicite, par locataire, révocable.** Contribution **désactivée
  par défaut**. Le client active par périmètre (ex. « comptabilité oui, RH non »).
  La révocation stoppe les contributions futures ; le savoir déjà promu est, par
  construction, non ré-attachable.
- **I5 — Validation humaine.** Rien n'entre dans le moteur sans revue d'un
  **curateur** (rôle gouvernance). Même patron que le barème de paie :
  `validated:false → true`.
- **I6 — Traçabilité anonyme.** Chaque candidat porte une empreinte de provenance
  **anonyme** (hash), jamais l'identité. Journal d'audit complet des promotions.

## 3. Ce qui peut / ne peut pas être contribué

| Contribuable (dérivé, généralisable) | Jamais contribué (brut, privé) |
|---|---|
| Motif de catégorisation : *libellé type → compte SYSCOHADA* | Le libellé réel d'une écriture, son montant |
| Terminologie / synonyme local inconnu du moteur | Le document où il apparaît |
| Correction de citation : *« pour X, citer l'art. Z »* | La question exacte du client |
| Paire Q/R validée, **expurgée** de tout spécifique | Toute donnée personnelle (Loi 29-2019) |

Règle mentale : on contribue une **règle**, pas un **dossier**.

## 4. Le pipeline — entonnoir de promotion à barrières

```
[1] CAPTURE (local, par locataire) — déjà en place
    store_agent_feedback : verdict ✓/✗ + correction experte
        │  (rien ne sort)
        ▼
[2] OPT-IN (local) — le client active « Contribuer au moteur commun » (par périmètre)
        │
        ▼
[3] EXTRACTION DE CANDIDAT (local)
    dérive un motif généralisable typé : categorisation | terminologie | qa | citation
        │
        ▼
[4] DÉ-IDENTIFICATION (local, obligatoire — I2)
    PII redaction + suppression montants / noms / source_uri / identité locataire
    → « candidat assaini » sans lien retour
        │  ← SEUL point de franchissement de la frontière
        ▼
[5] QUARANTAINE (schéma partagé de staging — PAS encore le moteur)
    contrib_staging.candidates ; compteur d'occurrences ; garde k-anonymat (I3)
        │
        ▼
[6] VALIDATION HUMAINE (gouvernance — I5)
    curateur : correct ? généralisable ? sûr ?  validated:false → true
        │
        ▼
[7] PROMOTION
    fusion dans un corpus dédié rag_commons (tag source:contribution), ou table de
    « règles apprises » que les agents consultent
        │
        ▼
[8] DISTRIBUTION + AUDIT (I6)
    livré à tous les déploiements à la mise à jour ; journal : quoi, origine anonyme, validateur
```

## 5. Modèle de données (esquisse)

- **`store_contribution_optin`** (local, par locataire) : `tenant_id`, `enabled`,
  `scopes[]` (poles/modules autorisés), `updated_at`, `updated_by`. Le consentement.
- **`contrib_staging.candidates`** (nouveau schéma **partagé** de staging,
  propriété `migrator`, à l'image des `rag_*`) :
  `id`, `type`, `payload` (JSON assaini), `occurrences`, `first_seen`,
  `status` (pending/validated/rejected), `validated_by`, `validated_at`,
  `provenance_hash` (anonyme). **Ni `tenant_id`, ni lien source.**
- **Cible de promotion** : `rag_commons` (schéma de référence dédié, tag
  `source:contribution`, réversible) **ou** une table `learned_rules` lue par les
  agents. Un schéma dédié garde la provenance nette et la **révocabilité** (on peut
  retirer une contribution promue sans toucher aux corpus sourcés).

Cloisonnement DB : `contrib_staging` et `rag_commons` suivent le même zero-trust
que les `rag_*` (app en lecture seule sur `rag_commons` ; écriture par un rôle
d'administration/curation).

## 6. Ancrages légaux & éthiques (Congo)

- **Loi 29-2019** (données personnelles) : base = **consentement** (I4) +
  **anonymisation** (I2) + **minimisation** (on ne dérive que le motif utile).
- **Secret professionnel** (cabinet) : le k-anonymat (I3) + l'absence de lien
  locataire (I1/I6) rendent tout croisement client A ↔ client B impossible.
- **Réversibilité** : un contributeur peut se retirer ; un corpus `rag_commons`
  séparé permet de dé-promouvoir une contribution.

## 7. Plan par phases (implémentation ultérieure)

- **Phase A — Socle & consentement.** `store_contribution_optin` + UI de
  consentement par périmètre (désactivé par défaut) + extraction de candidats
  depuis `store_agent_feedback` + dé-identification (réutilise PII). Les candidats
  atterrissent en **quarantaine**. **Aucune promotion.** *Livrable sûr et isolé.*
- **Phase B — Gouvernance.** Écran curateur (revue/validation/rejet) + garde
  k-anonymat + `validated` flag. *Rien n'entre dans le moteur sans humain.*
- **Phase C — Promotion & distribution.** Fusion des candidats validés dans
  `rag_commons` (consulté par les agents) + journal d'audit + livraison à la mise
  à jour.

Chaque phase est autonome et sûre : même en s'arrêtant après A, aucune donnée
privée n'a franchi la frontière (les candidats restent en quarantaine, non promus).

## 8. Décisions (tranchées le 2026-07-07)

1. **k = 3** — un motif doit être corroboré ≥ 3 fois avant d'être éligible.
2. **Curation mixte (auto + humain)** — pré-filtrage automatique (k-anonymat,
   doublons) puis validation humaine sur les seuls candidats qui passent.
3. **Cible de promotion : les deux** — `rag_commons` (sémantique, cité) pour Q/R
   & terminologie ; `learned_rules` (déterministe) pour les mappings compta.
4. **Incitation** : à décider plus tard (piste : accès prioritaire aux améliorations
   du commun pour les contributeurs).

### Séquencement de stockage (précision d'implémentation)

- **Phase A** : la quarantaine est une **table `core`** `store_contrib_candidates`
  **sans `tenant_id` ni lien source** (anonymat *logique*). Simple, sûr, isolé —
  aucune promotion. Les 6 invariants sont respectés (l'anonymisation a lieu avant
  l'écriture ; rien de brut n'est stocké).
- **Phase C** : introduction des **schémas physiques dédiés** `contrib_staging`
  (quarantaine) et `rag_commons` (savoir promu, app en lecture seule) avec grants
  zero-trust — la séparation physique compte au moment où le savoir entre
  réellement dans le moteur.

---

*Référence : boucle de feedback (`store_agent_feedback`), isolation par locataire
(retrieval-union + Bibliothèque cloisonnée), gouvernance `validated` (barème de
paie), `security/pii.PIIRedactionPolicy`. Cf. `docs/ARCHITECTURE_TOPOLOGIE.md`.*
