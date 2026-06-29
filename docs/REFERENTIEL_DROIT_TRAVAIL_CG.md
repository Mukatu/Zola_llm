# Référentiel — Droit du travail & paie · République du Congo (Brazzaville)

> Note de cadrage pour le module RH/Paie. **Sources secondaires fiables, non
> confirmées sur texte primaire** pour certaines valeurs — voir niveaux de
> confiance et incertitudes. Code pays **CG** (Congo-Brazzaville, **pas la RDC**).
> Établie le 2026-06-29 (sourcing PAIE-4). À faire valider par un expert paie/fiscal CG.

## Cadre légal de référence

- **Loi n° 45-75 du 15 mars 1975** — Code du travail (texte fondateur)
- **Loi n° 88-22 du 17 sept. 1988**, **Loi n° 96-06 du 6 mars 1996** (CDD, travail temporaire)
- **Décret n° 78-360 du 12 mai 1978** — heures supplémentaires
- **Décret n° 2024-2762 du 20 nov. 2024** — SMIG 2025
- **Loi de finances 2026 (loi n° 42-2025)** — ITS, quotient familial
- Conventions collectives sectorielles (commerce, pétrole, BTP, industrie, hôtellerie, transport)
- Textes officiels : [sgg.cg](https://www.sgg.cg) · ILO NATLEX

---

## 1. Paramètres LÉGAUX NATIONAUX (à encoder en dur)

| Règle | Valeur | Base / confiance |
|---|---|---|
| SMIG | **70 400 XAF/mois** (depuis 01/01/2025) | Décret 2024-2762 — élevée |
| Durée légale | **40 h/semaine** | Code du travail — élevée |
| HS 41ᵉ–48ᵉ h | **+10 %** | Décret 78-360 — élevée |
| HS au-delà 48ᵉ h | **+25 %** | Décret 78-360 — élevée |
| HS nuit | **+50 %** | Décret 78-360 — moyenne |
| HS dimanche/férié | **+100 %** | Décret 78-360 — élevée |
| Plafond HS annuel | **240 h/an** | Code du travail — moyenne |
| Congés payés | **26 jours ouvrables/an** | Code du travail — élevée |
| CDD durée max | **24 mois** (initial 12 + 1 renouvellement) | Loi 96-06 — élevée |
| Essai ouvrier | **1 mois** (renouvelable 1× → 2 mois max) | Code du travail — moyenne |
| Essai cadre | **3 mois** (renouvelable 1× → 6 mois max) | Code du travail — moyenne |
| Préavis cat. 1-4 | **1 mois** | Code du travail — moyenne |
| Préavis cat. 5-7 | **2 mois** | Code du travail — moyenne |
| Préavis cat. 8+ | **3 mois** | Code du travail — moyenne |

### Cotisations & impôts (cohérent avec `ref/payroll_cg.json`)

| Prélèvement | Salarié | Employeur | Assiette/plafond |
|---|---|---|---|
| CNSS retraite (PVID) | 4 % | 8 % | plafond 1 200 000/mois |
| CNSS allocations familiales | — | 10,03 % | plafond 600 000/mois |
| CNSS accidents du travail | — | 2,25 % | plafond 600 000/mois |
| CAMU | 2,27 % (plafond 600 000) | 4,55 % | — |
| TUS (taxe unique sur salaires) | — | 7,5 % | brut total, sans plafond |
| IRPP (≤2025) / ITS (≥2026) | progressif | — | base = 80 % du brut net de retraite, ÷ parts |
| Abattement frais pro | 20 % | | avant impôt |
| Quotient familial | plafond **6,5 parts** | | LF 2026 |

> Cohérence : la CAMU salarié (2,27 %) et le TUS (7,5 %) sont **confirmés par cette
> seconde source**, mais restent `autres_charges_a_confirmer` dans le barème (risque
> de double comptage avec les branches CNSS via la ventilation du TUS) → non
> appliqués tant que non tranchés.

### Obligations déclaratives (documents à générer)

| Déclaration | Échéance | Destinataire |
|---|---|---|
| Bordereau cotisations CNSS | avant le 15 du mois M+1 | CNSS |
| Déclaration ITS | avant le 15 du mois M+1 | DGI |
| Déclaration TUS | avant le 15 du mois M+1 | DGI / CNSS |
| **DAS — Déclaration Annuelle des Salaires** | **avant le 31 mars** | CNSS |
| Déclaration d'embauche | J+8 | Inspection du travail |
| Déclaration accident du travail | H+48 | Inspection + CNSS |
| Bulletins de paie | mensuel | salarié |
| Requalification CDD→CDI | alerte automatique à 24 mois | employeur |

### Registres obligatoires

Registre unique du personnel · registre des contrats · registre des heures
supplémentaires · registre des accidents du travail. Présentables sur réquisition
de l'Inspection du travail.

---

## 2. Paramètres CONVENTIONNELS (paramétrables par tenant)

Varient par convention collective sectorielle (UNICONGO + fédérations) :

- **Classifications** de postes (catégories 1–10+ selon secteur)
- **Grilles salariales** minimales par catégorie (au-dessus du SMIG)
- **Prime d'ancienneté** (taux, paliers)
- **Bonifications de congés** par ancienneté (renvoyées aux CC — pas de barème légal national unifié)
- **Primes** : panier, transport, risque, éloignement, outillage
- Période d'essai par sous-catégorie, préavis si CC plus favorable

Conventions recensées : Commerce (grille révisée oct. 2024 : +5 à +12 % selon
catégorie), Services pétroliers, Recherche & Production hydrocarbures (grille fév.
2023), Industrie & Métallurgie, Hôtellerie, Transport aérien, BTP.

---

## 3. Incertitudes / à confirmer sur source primaire

1. **Indemnité de licenciement** : barème légal contradictoire selon sources
   (de « pas d'indemnité légale » à « ½ mois/an puis 1 mois/an »). Lire l'art. 38
   de la Loi 96-06 + doc OARH « Droit du licenciement au Congo » (2024) avant encodage.
2. **Bonification congés/ancienneté** : déléguée aux conventions collectives.
3. **Taux AT/MP CNSS (2,25 %)** : possible modulation selon code risque de l'activité.
4. **CAMU salarié** : 2,27 % (CLEISS) vs 0,5 % >500k (sources 2026) — divergence non tranchée.
5. **Préavis** : règle catégorielle retenue ; une source isolée propose une autre formule.

---

## 4. Implications pour le moteur (état & reste à faire)

- **Déjà en place** : CNSS multi-branches plafonnées, IRPP/ITS par exercice, abattement
  20 %, quotient familial (6,5 parts), SMIG 70 400, DAS 1 + état annuel, verrou de
  validation du barème (PAIE-5).
- **Pistes** : durée légale & heures supplémentaires (majorations), congés payés (26 j +
  bonifications conventionnelles), alerte requalification CDD→CDI à 24 mois, génération
  des déclarations périodiques (CNSS/ITS/TUS) et des registres légaux, paramétrage des
  conventions collectives (grilles, primes) par tenant.

---

## Sources principales

- [Décret SMIG 2024-2762 (PDF)](https://www.oarh.cg/wp-content/uploads/2025/01/Decret-n%C2%B02024-2762-du-20-novembre-2024-fixant-le-montant-du-salaire-minimum-interprofessionnel-garanti-SMIG.pdf) · [Agence Ecofin](https://www.agenceecofin.com/actualites/1411-123408-congo-hausse-de-40-du-smig-a-partir-du-1er-janvier-2025)
- [Code du travail 1975 (sgg.cg)](https://www.sgg.cg/codes/congo-code-1975-travail.pdf) · [Loi 96-06 (sgg.cg)](https://www.sgg.cg/textes-officiels/lois/1996/congo-loi-1996-06.pdf) · [ILO NATLEX — Loi 45-75](https://natlex.ilo.org/dyn/natlex2/r/natlex/fe/details?p3_isn=14546)
- [WageIndicator CG — droit du travail](https://wageindicator.org/fr-cg/travail-au-congo-brazzaville/droit-du-travail/)
- [AfricaPaieRH — durée du travail](https://africapaierh.com/juridique/duree-du-travail-en-republique-du-congo/) · [congés payés](https://africapaierh.com/juridique/les-conges-payes-en-republique-du-congo/)
- [CNSS.cg — taux](https://www.cnss.cg/taux-de-cotisation/) · [CLEISS — régime Congo](https://www.cleiss.fr/docs/regimes/regime_congo.html)
- [CongoPaye — CNSS/CAMU](https://congopaie.com/blog/declaration-cnss-camu-congo) · [TUS](https://congopaie.com/blog/tus-taxe-unique-salaires-congo) · [ITS DGI](https://congopaie.com/blog/declaration-its-mensuelle-dgi-congo)
- [UNICONGO — conventions collectives](https://www.unicongo.cg/les-conventions-collectives/) · [OARH.cg — conventions](https://www.oarh.cg/convention-collective/) · [OARH — droit du licenciement (2024)](https://www.oarh.cg/wp-content/uploads/2024/06/LE-DROIT-DU-LICENCIEMENT-AU-CONGO.pdf)
- [Min. Fonction Publique — obligations sociales des entreprises (PDF)](https://fonction-publique.gouv.cg/sites/default/files/2021-07/Les_obligations_sociales_des_entreprises.pdf)
