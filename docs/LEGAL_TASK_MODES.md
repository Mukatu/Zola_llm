# Modes de tâche des agents juridiques — rédaction vs contentieux

**Date** : 2026-06-20
**Objet** : figer comment les agents Droit/ERP combinent les couches de corpus
(texte normatif vs jurisprudence) selon la tâche. Complète
[`DATA_KNOWLEDGE_ROADMAP.md`](./DATA_KNOWLEDGE_ROADMAP.md) (couches) et
[`PHASE_4_REPORT.md`](./PHASE_4_REPORT.md).

---

## Mode 1 — Rédaction (génératif, ancré sur le normatif)

- **Entrée** : besoin contractuel (type, parties, paramètres).
- **Couches** : **texte normatif** (Actes Uniformes, Code du travail, conventions) + **templates** (CDI/CDD, SARL-OHADA, bail, cession de parts, NDA) ; **jurisprudence en garde-fou** (éviter les clauses invalidées).
- **Processus** : retrieve articles + clauses-types → génération **clause par clause** → **citation de l'article** par clause → retrieve jurisprudence à risque → **avertissements de sécurisation** → refus si base insuffisante.
- **Sortie** : document généré + citations + warnings de risque (mode génératif libre, `response_schema=None`).
- **Pattern de référence** : overlay `Conformité-RH` (`clause → risque_prudhommal → reference_legale → note_securisation`).

## Mode 2 — Contentieux / résolution (analytique, loi + jurisprudence)

- **Entrée** : situation litigieuse / faits.
- **Couches** : **loi d'abord** (la règle) + **jurisprudence** (`type:jurisprudence`, application réelle, issue probable) + doctrine.
- **Processus** : qualification juridique des faits → règle applicable (article) → **confrontation à la jurisprudence** (précédents, sens des arrêts, revirements) → évaluation **risque/chances** → argumentaire (moyens) → références (articles **+ arrêts datés**).
- **Sortie structurée** (OUTPUT_FORMAT) : situation → qualification → base légale → jurisprudence applicable (réf.+date) → analyse de risque → recommandation. Probabiliste (« tendance jurisprudentielle », jamais « verdict »).
- **Pattern de référence** : overlay `Audit-Juridique-OHADA`.

---

## Règles transverses (non négociables)

1. **Primauté de la loi** : en cas de conflit texte ↔ arrêt, le texte l'emporte ; signaler le point.
2. **Jurisprudence = interprète/prédit**, ne crée pas la règle ; gérer les **revirements** (un précédent peut être périmé) → privilégier récent/confirmé.
3. **Citation obligatoire** (article + arrêt réf./date) ; refus si base insuffisante (`requires_citation`, `min_confidence`).
4. **Assistance, pas substitution** : l'app produit un **projet** (contrat) ou une **analyse de risque** ; un **juriste valide** avant usage réel (responsabilité, déontologie — directive §5.7). Audit systématique.
5. **Tagging** : `type:texte_legal` vs `type:jurisprudence` / `type:doctrine` ; `juridiction`, `date`, `reference`.

## Mapping composants

| Tâche | Composant | Couches |
|------|-----------|---------|
| Rédaction | sous-agents génératifs Droit (`OhadaAgent`, `TravailCgAgent`, `RhAgent` ERP) | `texte_legal` + templates (+ jurisprudence garde-fou) |
| Contentieux | overlay/sous-agent analytique (`Audit-Juridique-OHADA`) | loi + `type:jurisprudence` + doctrine |
