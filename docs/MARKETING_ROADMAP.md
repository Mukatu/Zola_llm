# Feuille de route — Marketing

**Date** : 2026-06-21
**Référence** : `ZOLAOS_MASTER_PLAN_ADDENDUM_BI_COMMERCIAL_MARKETING.md` §3.3. Dernière extension de l'addendum. S'appuie sur les données CRM (contacts).
**Engagement** : ordre MKT-1 → MKT-3, chaque jalon tracé + tests verts.

---

## Principe directeur
**Déterministe d'abord** : segmentation et **conformité Loi 29-2019** (consentement + finalité) calculées **en code**. Le **LLM génère le contenu** (offres, emailing, posts). **Privacy by design** : pas de ciblage sans consentement vérifié.

---

## Jalon MKT-1 — Modèles + segmentation + consentement — **premier**
- `src/zolaos/agents/mkt/models.py` : `MarketingContact` (avec `consentement_marketing`, `finalites`), `Campaign`.
- `src/zolaos/agents/mkt/segmentation.py` (pur) : segmentation déterministe (type × récence, secteur), buckets RFM-like.
- `src/zolaos/agents/mkt/consent.py` (pur, **Loi 29-2019**) : filtrage par consentement + finalité, `ensure_consent`, `ConsentError`.
- Tests exacts.

## Jalon MKT-2 — Agent Marketing (génération de contenu)
- `src/zolaos/agents/mkt/agent.py` : `MarketingAgent` :
  - délègue segmentation + audience éligible (consentement) ;
  - **génératif** : contenu de campagne (offre, email, post) selon canal + finalité + brief ;
  - **garde consentement** : refuse de produire une campagne ciblée sans audience consentante.
- `agents/prompts/mkt/marketing.md` versionné (incl. conformité données perso). Tests.

## Jalon MKT-3 — Overlay Polaris + clôture
- Overlay Polaris **Audit marketing / conformité** (dépôt privé, profil cortex).
- Doc + maj statut addendum (**3/3 extensions livrées**) + tests d'ensemble sans régression.

---

## Critères de sortie
- Segmentation + consentement (Loi 29-2019) **en code**, testés.
- `MarketingAgent` : génération de contenu avec **garde consentement** (privacy by design).
- Overlay Polaris présent. Aucune régression.

## Hors périmètre (clarté)
- **Envoi réel** (ESP email / passerelle SMS) → intégration via connecteurs ultérieure.
- **Tracking/analytics de campagne** → relève de la BI.
- A/B testing, scoring prédictif d'audience → briques ultérieures.

---

## Statut

| Jalon | État |
|-------|------|
| MKT-1 modèles + segmentation + consentement | ✅ livré |
| MKT-2 agent Marketing (contenu) | ✅ livré (génération + garde consentement) |
| MKT-3 overlay + clôture | ✅ overlay privé `ZolaCortex-Audit-Marketing` + 183 tests verts |

> **Marketing bouclé (2026-06-21). Addendum BI/Commercial/Marketing complet — 3/3 extensions livrées.**

*Feuille de route établie et exécutée le 2026-06-21.*
