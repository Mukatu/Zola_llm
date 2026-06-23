# ZolaOS — SIRH (Système d'Information RH) : plan d'action

**Date** : 2026-06-23
**Statut** : sous-plan **faisant autorité** du module RH (rattaché à `docs/PERSISTENCE_ROADMAP.md` §4-6).
**Cadre** : couche IA souveraine + persistance légère ; **on aide au pilotage**, on ne devient pas une suite RH transactionnelle (le lourd → interop).

> Objectif : un **SIRH de pilotage** couvrant les **3 piliers** (Recrutement · Administration du Personnel · Développement du Capital Humain), capable de **générer à la demande** les livrables RH (fiches de poste, contrats, grilles, plans…) tout en tenant des **registres vivants** et un **tableau de bord** d'indicateurs exacts.

---

## 1. Doctrine — comment chaque besoin RH se mappe sur notre modèle
| Type de besoin | Traitement ZolaOS | Exemple |
|---|---|---|
| **Registre** | Persistance légère (`store_*`) | employés, candidats, postes, formations, compétences |
| **Indicateur** | **Déterministe** (calcul en code) | turnover, absentéisme, time-to-hire, écart GPEC |
| **Artefact / document** | **Génération LLM** (agent RH) → `store_documents`, **brouillon à valider** | fiche de poste, CDI/CDD, grille d'entretien, plan de formation |
| **Échéance / alerte** | **Déterministe** (calcul de dates) | fin période d'essai, fin CDD, visite médicale, planning évals |
| **Workflow** | **Léger** (champ `statut`), pas de moteur BPM | candidature : reçue→entretien→offre→embauché |
| **Hors périmètre** | **Interop / futur** | LMS e-learning, job boards, pointage biométrique, paie (module séparé) |

**Garde-fou génération** : tout document généré est un **brouillon** soumis à validation humaine (comme « à faire valider par un juriste » en Droit). La **génération en masse** (CDI/CDD) = gabarit + **fusion déterministe** des données employé + finition LLM ; chaque sortie reste relisible/éditable.

---

## 2. Pilier 1 — Recrutement (Talent Acquisition)

**Registres** : `store_job_positions` (référentiel de postes) · `store_vacancies` (vacance/réquisition : poste, motif, statut, urgence) · `store_candidates` (vivier) · `store_applications` (candidature = candidat × vacance, **étape pipeline**) · `store_interviews` (entretien planifié + grille remplie + score).

**Indicateurs déterministes** : entonnoir de recrutement (candidats par étape, **taux de conversion**), **time-to-hire** (délai), coût par recrutement, taux d'acceptation d'offre, sources de candidats.

**Génération à la demande (agent RH → documents)** :
- **Fiche de poste** (depuis le référentiel + besoin) · **annonce de vacance de poste** · **formulaire de demande de recrutement** (réquisition) · **grille d'entretien** (structurée par compétences du poste) · **plan de recrutement** (planning + canaux) · **contrats CDI/CDD** (unitaire **et en masse** depuis les candidats retenus).

**Échéancier/alertes** : entretiens planifiés, relances candidats, vacances ouvertes depuis trop longtemps.

**Écran** : **pipeline de recrutement** (kanban candidats par étape, façon CRM) + panneau « générer » (les artefacts ci-dessus).

**Hors périmètre / interop** : publication auto sur job boards (LinkedIn/Indeed) → connecteur ; parsing CV avancé → LLM léger optionnel ; tests psychotechniques → externe.

## 3. Pilier 2 — Administration du Personnel (Core HR & Pilotage)

**Registres** : `store_employees` (riche) · `store_contracts` · `store_absences` · `store_hr_movements` (embauche/départ/mutation/promotion) · `store_org_units` (mailles d'organigramme).

**Indicateurs déterministes** : effectif + **ETP**, répartitions (département/contrat/genre), **masse salariale** (totale, moyenne/médiane), **turnover**, **absentéisme**, **ancienneté** + pyramide, **pyramide des âges**, **index égalité H/F**, ratio d'encadrement.

**Génération à la demande** : **CDI/CDD/avenants**, **attestations** (travail, salaire), **registre unique du personnel** (export légal OHADA/CG), **organigramme** (généré depuis `manager_id`), courriers (fin de période d'essai, fin de CDD).

**Échéancier/alertes (déterministe)** : **expiration** période d'essai, fin de CDD, visite médicale, anniversaires d'ancienneté, congés à solder, échéances sociales **CNSS**.

**Écran** : Registre · **Tableau de bord** (KPIs + mini-graphes) · Échéancier · **Organigramme**.

**Conformité** : registre unique du personnel ; cohérence avec le **Droit du travail CG** (synergie agent Droit) et la CNSS.

## 3bis. Socle Référentiels (RME · RMC · Matrice) — **fondation partagée** ⭐ ✅ livré

Construit **au début de SIRH-2** car il alimente **recrutement** (fiches de poste, grilles) **et** **GPEC/formation** (SIRH-3). **Livré** (`ea01ef9` back · `6ebf40d` écran) : RME, RMC, profil requis, matrice (tableau croisé éditable), analyse d'écart GPEC + compétences critiques ; capacité `erp.referentiels`. *Reste : génération (fiche de poste/grille depuis RME), 9-box.*

- **RME — Référentiel des Emplois** (`store_job_roles`) : `code_emploi`, `famille_professionnelle`, `intitule` (emploi-repère), `mission_principale`, `activites` (clés, JSON), `kpis` (JSON).
- **RMC — Cartographie des Compétences** (`store_skills`) : `code_competence`, `domaine` (technique/transversal/soft), `intitule`, `niveau_1` (notions) → `niveau_4` (expert).
- **Profil requis par emploi** (`store_role_skills`) : `code_emploi` × `code_competence` → `niveau_requis` (0-4). *(le chaînon qui rend la matrice exploitable)*
- **Matrice opérationnelle** (`store_employee_skills`) : `matricule` × `code_competence` → **note 0-4**. Rendu = **tableau croisé** (lignes : matricule/nom/code_emploi ; colonnes : codes compétences ; intersection : note).

**Indicateurs déterministes débloqués** : **analyse d'écart GPEC** (requis − détenu par employé/compétence), **taux de couverture** des compétences, **nombre d'experts** par compétence (= **risque de perte de compétence clé** si trop peu), compétences critiques en déficit.

**Génération (LLM, validée)** : depuis le RME → **fiche de poste**, annonce de vacance, **grille d'entretien** (sur compétences requises) ; depuis les écarts → **plan de formation**, **plan GPEC**.

**Écran Référentiels** (3 onglets) : **RME** · **RMC** · **Matrice** (tableau croisé éditable) + vue **GPEC/écarts**.

## 4. Pilier 3 — Développement du Capital Humain (Talent Management & GPEC)

**Registres** : `store_skills` (référentiel compétences) · `store_employee_skills` (détenues + niveau) · `store_position_skills` (requises par poste) · `store_trainings` (catalogue) · `store_training_sessions` (planning) · `store_training_enrollments` · `store_evaluations` (performance + à chaud / à froid).

**Indicateurs déterministes** : **analyse d'écart GPEC** (compétences requises par poste vs détenues → **écarts** par employé/équipe), taux de réalisation du plan de formation, coût de formation, **matrice 9-box** (performance × potentiel), taux de complétion des évaluations.

**Génération à la demande** : **plan de formation**, **formulaires d'évaluation à chaud / à froid**, **planning des évaluations de formation**, **plan GPEC** (depuis les écarts), **matrice des risques et opportunités RH** (depuis écarts + pyramide des âges + turnover : risques de départ/perte de compétence clés, opportunités de mobilité), supports d'**entretien annuel/professionnel**.

**Échéancier/alertes** : planning des évaluations à chaud/à froid, échéances du plan GPEC, sessions de formation à venir.

**Écran** : **GPEC** (matrice compétences + écarts) · **Formation** (plan + planning + évaluations) · **Revue de talents** (9-box).

**Hors périmètre / interop** : LMS (contenu e-learning, SCORM) → interop ; gestion fine de la performance par objectifs (OKR workflow) → léger seulement.

---

## 5. Capacités « à la demande » — récapitulatif (ce que le système/agent RH génère)
| Livrable demandé | Source (registre) | Producteur | Sortie |
|---|---|---|---|
| Vacance de poste / réquisition | postes | LLM + gabarit | document + entrée `store_vacancies` |
| Formulaire de demande de recrutement | poste/besoin | LLM | document |
| Fiche de poste | référentiel poste + compétences | LLM | document (réutilisable) |
| Grille d'entretien | compétences du poste | LLM (structuré) | document |
| Plan de recrutement | vacances + canaux | LLM | document |
| **CDI / CDD (en masse)** | candidats/employés retenus | **fusion déterministe + LLM** | N contrats relisibles |
| Alerte d'expiration (essai/CDD/visite) | contrats/absences | **déterministe** | notification + échéancier |
| Plan de formation | écarts GPEC + budget | LLM | document |
| Formulaire d'évaluation à chaud / à froid | session de formation | LLM | document |
| Planning des évaluations | sessions/échéances | **déterministe** | calendrier |
| Matrice risques & opportunités RH | écarts + pyramide + turnover | **déterministe** + narration LLM | matrice + synthèse |
| Organigramme | `manager_id` | **déterministe** (graphe) | visuel + export |
| Plan GPEC | écarts de compétences | **déterministe** (écarts) + LLM (plan) | document |

## 6. Phasage SIRH (selon le patron 7-livrables de PERSISTENCE_ROADMAP §2)
- **SIRH-1 — Core HR & Pilotage** (= bloc RH de P2c) : employés, contrats, absences, mouvements, organigramme ; tableau de bord ; échéancier ; registre légal ; génération contrats/attestations.
- **SIRH-2 — Recrutement** : postes, vacances, candidats, candidatures (pipeline), entretiens ; indicateurs entonnoir/time-to-hire ; génération (fiche de poste, vacance, grille, plan, **contrats en masse**).
- **SIRH-3 — Développement / GPEC & Formation** : compétences (référentiel + détenues + requises), formations/sessions/inscriptions, évaluations ; analyse d'écart GPEC, 9-box ; génération (plan de formation, évals chaud/froid, planning, plan GPEC, matrice risques/opportunités).

Dépendances : SIRH-2 et SIRH-3 s'appuient sur SIRH-1 (employés/postes). Paie historisée (PERSISTENCE_ROADMAP §4-7) dépend de SIRH-1.

## 7. Limites tenues (promesse)
- **Pas de** : LMS e-learning, posting job boards, pointage biométrique, BPM d'approbation multi-niveaux, exécution de paie (module séparé).
- **Oui à** : registres + indicateurs déterministes + **génération assistée** (brouillons validés) + échéanciers + workflows **légers** (statuts).
- Tout reste **souverain, local-first, déterministe d'abord** ; le LLM rédige, l'humain valide.

## 8. Suivi
| Sous-phase | Périmètre | DoD | Commit |
|---|---|---|---|
| SIRH-1 | Core HR & Pilotage (registres employés/contrats/absences + tableau de bord + échéancier + registre légal) | ✅ | `e13a97f` (back) · `22ca9ea` (écran) |
| Socle Référentiels | RME + RMC + matrice + écarts GPEC | ✅ | `ea01ef9` · `6ebf40d` |
| SIRH-2 | Recrutement (pipeline + génération) | ☐ | — |
| SIRH-3 | Développement (GPEC/Formation) | ☐ | — |

> SIRH-1 livré : moteur déterministe (effectif/ETP, masse salariale, turnover, absentéisme, ancienneté, pyramide des âges, égalité H/F, ratio d'encadrement), échéancier (essai/CDD/anniversaires), registre unique du personnel ; écran RH 3 onglets. Restant SIRH-1 : organigramme visuel, mouvements RH dédiés, génération de contrats/attestations (rattachée à `store_documents`, P2f).

---

*Sous-plan SIRH établi le 2026-06-23. Améliore et structure le besoin en 3 piliers, mappé sur la doctrine ZolaOS (registres + indicateurs déterministes + génération LLM validée + interop pour le lourd). Rattaché à `docs/PERSISTENCE_ROADMAP.md` §4-6.*
