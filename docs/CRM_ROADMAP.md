# Feuille de route — Commercial / CRM & Ventes

**Date** : 2026-06-21
**Référence** : `ZOLAOS_MASTER_PLAN_ADDENDUM_BI_COMMERCIAL_MARKETING.md` §3.2. S'appuie sur le Connector Framework + la Compta (devis→factures) + la BI (pipeline).
**Engagement** : ordre CRM-1 → CRM-3, chaque jalon tracé + tests verts.

---

## Principe directeur
**Déterministe d'abord** : pipeline, scoring de leads, détection des relances et conversion devis→facture sont calculés **en code**. Le **LLM rédige** (relances, propositions) et **interprète** (synthèse pipeline) — il ne calcule pas les montants ni les scores.

---

## Jalon CRM-1 — Modèles + moteur déterministe — **premier**
- `src/zolaos/agents/crm/models.py` : `Customer` (client/prospect), `Opportunity` (pipeline), `Quote` (devis).
- `src/zolaos/agents/crm/engine.py` (pur) :
  - **Pipeline** : valeur totale ouverte, valeur pondérée (montant × probabilité), répartition par étape, taux de conversion (win rate).
  - **Scoring de leads** déterministe paramétré (étape, récence, montant, source).
  - **Relances** : devis expirés/sans réponse, opportunités sans contact depuis N jours.
  - **Devis → facture** : conversion vers `Invoice` canonique (branche la Compta).
- Tests exacts.

## Jalon CRM-2 — Agent CRM (couche IA)
- `src/zolaos/agents/crm/agent.py` : `CrmAgent` :
  - délègue le déterministe (pipeline, scoring, relances) ;
  - **génératif** : rédaction de **relances** (emails) et de **propositions commerciales** ;
  - **narration** du pipeline + **priorisation** des leads (explique le score déterministe).
- `agents/prompts/crm/commercial.md` versionné. Tests.

## Jalon CRM-3 — Overlay Polaris + clôture
- Overlay Polaris **Audit commercial / performance** (dépôt privé, profil cortex).
- Doc d'usage + maj statut + tests d'ensemble sans régression.

---

## Critères de sortie
- Pipeline, scoring, relances, devis→facture **en code**, testés exacts.
- `CrmAgent` : relances/propositions génératives + narration pipeline (le LLM ne calcule pas).
- Overlay Polaris présent. Aucune régression.

## Hors périmètre (clarté)
- **Forecasting des ventes** (séries temporelles) → brique dédiée ultérieure.
- Connecteurs CRM externes spécifiques (au-delà du `generic_rest` existant).
- **Marketing** → chantier suivant de l'addendum.

---

## Statut

| Jalon | État |
|-------|------|
| CRM-1 modèles + moteur déterministe | 🔄 en cours |
| CRM-2 agent CRM (IA) | ⏳ |
| CRM-3 overlay + clôture | ⏳ |

*Feuille de route établie le 2026-06-21.*
