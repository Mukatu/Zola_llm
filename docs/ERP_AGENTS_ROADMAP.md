# Feuille de route — Sous-agents ERP (Phase 4, pilier critique)

**Date** : 2026-06-20
**Référence** : `ZOLAOS_MASTER_PLAN_V2.md` §4 (Pôle ERP). S'appuie sur
[`DATA_KNOWLEDGE_ROADMAP.md`](./DATA_KNOWLEDGE_ROADMAP.md) (couches de données),
[`LEGAL_TASK_MODES.md`](./LEGAL_TASK_MODES.md) (rédaction vs contentieux),
[`CONNECTOR_FRAMEWORK_ROADMAP.md`](./CONNECTOR_FRAMEWORK_ROADMAP.md) (livré).
**Engagement** : suivie dans l'ordre RH → Finance → Compta, chaque jalon tracé (TaskList) + tests verts.

---

## Principe transverse : déterministe d'abord, RAG pour l'interprétation
Pour tout l'ERP : les **chiffres et règles exactes** (barèmes, plan de comptes, calculs) sont **déterministes** (tables `ref` + code), **jamais** confiés au RAG probabiliste. Le RAG/LLM sert à **interpréter, expliquer, rédiger, justifier** — toujours avec citation. Validation humaine sur fiscal/RH avant production (directive §5.7).

---

## Jalon RH (§4.1) — **en cours, premier**

### RH-1 — Agent RH génératif (cœur §4.1)
- `src/zolaos/agents/erp/rh.py` : `RhAgent(RAGAgent)`, ancré sur le corpus `travail_cg` (réutilisé), **mode rédaction** (génératif + citations).
- Capacités : fiches de poste, lettres d'embauche, **contrats CDI/CDD**, notifications disciplinaires, **contrôle de conformité** d'un contrat existant.
- Garde-fous : `requires_citation=True`, refus si base insuffisante, jurisprudence en garde-fou de sécurisation, **assistance non substitution**.
- `agents/prompts/erp/rh.md` versionné. Tests `tests/test_erp_rh.py`.
- Overlay Polaris : `Conformité-RH` **déjà livré** (`ConformiteRhOverlay`).

### RH-2 — Moteur de paie déterministe (différé données)
- Schéma `ref` + tables structurées : **SMIG/SMAG**, grilles conventionnelles, **CNSS + CIPRES**, **IRPP/retenues** (CGI).
- Calcul **déterministe** d'un bulletin (brut → cotisations → net → retenues) + justification RAG (base légale citée).
- ⏳ Dépend des **barèmes** (sourcing 🔴, cf. data roadmap). Codé quand les données arrivent ; structure prête.

## Jalon Finance (§4.2)
- `src/zolaos/agents/erp/finance.py` : branché sur le **Connector Framework** (`list_bank_transactions` : banque/MoMo/Airtel).
- **Détection d'anomalies déterministe** (doublons, dépassements, échéances) + **synthèse générative** (rapport mensuel/trimestriel format DGID-compatible).
- Overlay `Trésorerie` déjà amorcé (`TresorerieOverlay`).

## Jalon Compta & Fiscalité (§4.3) — moteur hybride
- **Schéma `ref` + table plan de comptes SYSCOHADA** (source de vérité ; cf. data roadmap §3bis.1).
- **Moteur de validation déterministe** : équilibre (Σdébit=Σcrédit), cohérence classe/sens, comptes autorisés, pré-saisie d'écritures.
- `src/zolaos/agents/erp/compta.py` : RAG **AUDCIF + CGI** **uniquement** pour l'interprétation/conformité fiscale (TVA/IS/IRPP) + citations.
- Données : corpus OHADA HF (AUDCIF, CC-BY-4.0) + plan de comptes structuré.

## Jalon clôture ERP
- Overlay Polaris par nouvel agent (mémoire : overlay dans la foulée).
- Tests d'ensemble, aucune régression, doc + maj `PHASE_4_REPORT`.

---

## Critères de sortie
- 3 sous-agents ERP (RH/Finance/Compta) instanciables et testés (mode dégradé corpus différé accepté).
- Séparation déterministe vs RAG respectée (plan de comptes/barèmes = `ref`, jamais RAG).
- Connecteurs branchés sur Finance (≥ `list_bank_transactions`).
- Overlays Polaris présents pour chaque agent. Aucune régression sur la suite existante.

## Hors périmètre (pour ne pas confondre avec un oubli)
- Sourcing réel des barèmes/corpus (côté utilisateur).
- Connecteurs Mobile Money (Phase 6 Fintech).
- Consultation documentaire `/v1/kb/*` (chantier dédié, après ERP).
- 5 modules juridiques différés (chantier Droit séparé).

---

## Statut

| Jalon | État |
|-------|------|
| RH-1 agent génératif | 🔄 en cours |
| RH-2 moteur paie déterministe | ⏳ différé (barèmes) |
| Finance | ⏳ à venir |
| Compta & Fiscalité | ⏳ à venir |
| Clôture ERP | ⏳ à venir |

*Feuille de route établie le 2026-06-20, ordre RH → Finance → Compta.*
