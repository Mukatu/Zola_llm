"""Registre des entités importables/exportables + classeurs par pôle (IMP-2)."""

from __future__ import annotations

from zolaos.db.store_models import (
    AbsenceRecord,
    ContractRecord,
    EmployeeRecord,
    EmployeeSkillRecord,
    EvaluationRecord,
    InvoiceRecord,
    JobRoleRecord,
    RoleSkillRecord,
    SkillRecord,
    TrainingRecord,
    VacancyRecord,
)
from zolaos.imports.framework import Column, EntitySpec, PoleSpec

_EMPLOYEES = EntitySpec(
    entity="employees",
    label="Employés",
    model=EmployeeRecord,
    natural_key=("matricule",),
    columns=(
        Column(
            "matricule",
            "str",
            required=True,
            help="Identifiant unique de l'employé",
            aliases=("id employe", "n matricule", "numero matricule", "id rh", "code agent"),
        ),
        Column(
            "nom_complet",
            "str",
            required=True,
            aliases=("nom prenom", "nom et prenom", "nom complet employe", "identite"),
        ),
        Column("genre", "str", enum=("H", "F", "NC"), aliases=("sexe", "civilite")),
        Column(
            "date_naissance",
            "date",
            help="AAAA-MM-JJ",
            aliases=("naissance", "ddn", "date de naissance"),
        ),
        Column(
            "date_embauche",
            "date",
            required=True,
            help="AAAA-MM-JJ",
            aliases=("embauche", "date entree", "date d entree", "anciennete"),
        ),
        Column("poste", "str", aliases=("fonction", "intitule poste", "titre")),
        Column("departement", "str", aliases=("service", "direction", "unite")),
        Column("manager_matricule", "str", aliases=("manager", "responsable", "n 1", "superieur")),
        Column("categorie", "str", aliases=("statut categoriel", "classification")),
        Column(
            "code_emploi",
            "str",
            help="Code de l'emploi-repère (RME)",
            aliases=("emploi repere", "code rme"),
        ),
        Column(
            "salaire_base_xaf",
            "decimal",
            aliases=("salaire", "salaire base", "remuneration", "salaire brut"),
        ),
        Column(
            "quotite",
            "decimal",
            help="Temps de travail (1 = plein temps)",
            aliases=("temps de travail", "etp"),
        ),
        Column("statut", "str", enum=("actif", "sorti"), aliases=("etat", "situation")),
    ),
)

_CONTRACTS = EntitySpec(
    entity="contracts",
    label="Contrats",
    model=ContractRecord,
    columns=(
        Column("employee_matricule", "str", required=True),
        Column("type", "str", enum=("CDI", "CDD", "stage", "prestation")),
        Column("date_debut", "date", required=True, help="AAAA-MM-JJ"),
        Column("date_fin", "date"),
        Column("fin_periode_essai", "date"),
        Column("statut", "str"),
    ),
)

_ABSENCES = EntitySpec(
    entity="absences",
    label="Absences",
    model=AbsenceRecord,
    columns=(
        Column("employee_matricule", "str", required=True),
        Column("type", "str", help="conge_paye, maladie, maternite, sans_solde"),
        Column("date_debut", "date", required=True),
        Column("date_fin", "date", required=True),
        Column("jours", "decimal"),
        Column("statut", "str"),
    ),
)

_JOB_ROLES = EntitySpec(
    entity="job_roles",
    label="Emplois (RME)",
    model=JobRoleRecord,
    natural_key=("code_emploi",),
    columns=(
        Column("code_emploi", "str", required=True),
        Column("famille_professionnelle", "str"),
        Column("intitule", "str", required=True),
        Column("mission_principale", "str"),
        Column("activites", "list", help="Activités clés, séparées par ;"),
        Column("kpis", "list", help="Indicateurs, séparés par ;"),
    ),
)

_SKILLS = EntitySpec(
    entity="skills",
    label="Compétences (RMC)",
    model=SkillRecord,
    natural_key=("code_competence",),
    columns=(
        Column("code_competence", "str", required=True),
        Column("domaine", "str", enum=("technique", "transversal", "soft")),
        Column("intitule", "str", required=True),
        Column("niveau_1", "str"),
        Column("niveau_2", "str"),
        Column("niveau_3", "str"),
        Column("niveau_4", "str"),
    ),
)

_ROLE_SKILLS = EntitySpec(
    entity="role_skills",
    label="Profil requis",
    model=RoleSkillRecord,
    natural_key=("code_emploi", "code_competence"),
    columns=(
        Column("code_emploi", "str", required=True),
        Column("code_competence", "str", required=True),
        Column("niveau_requis", "int", help="0 à 4"),
    ),
)

_EMPLOYEE_SKILLS = EntitySpec(
    entity="employee_skills",
    label="Matrice compétences",
    model=EmployeeSkillRecord,
    natural_key=("employee_matricule", "code_competence"),
    columns=(
        Column("employee_matricule", "str", required=True),
        Column("code_competence", "str", required=True),
        Column("note", "int", help="0 (aucune) à 4 (expert)"),
    ),
)

_VACANCIES = EntitySpec(
    entity="vacancies",
    label="Vacances",
    model=VacancyRecord,
    natural_key=("code_vacance",),
    columns=(
        Column("code_vacance", "str", required=True),
        Column("code_emploi", "str"),
        Column("intitule", "str", required=True),
        Column("type_contrat_cible", "str", enum=("CDI", "CDD", "stage", "prestation")),
        Column("nb_postes", "int"),
        Column("departement", "str"),
        Column("lieu", "str"),
        Column("statut", "str"),
        Column("date_ouverture", "date", required=True),
        Column("date_cible", "date"),
    ),
)

_TRAININGS = EntitySpec(
    entity="trainings",
    label="Formations",
    model=TrainingRecord,
    natural_key=("code",),
    columns=(
        Column("code", "str", required=True),
        Column("intitule", "str", required=True),
        Column("competences_visees", "list", help="Codes compétences, séparés par ;"),
        Column("modalite", "str"),
        Column("duree_heures", "decimal"),
        Column("cout_xaf", "decimal"),
    ),
)

_EVALUATIONS = EntitySpec(
    entity="evaluations",
    label="Évaluations",
    model=EvaluationRecord,
    natural_key=("employee_matricule", "periode"),
    columns=(
        Column("employee_matricule", "str", required=True),
        Column("periode", "str", required=True),
        Column("performance", "int", help="1 à 5"),
        Column("potentiel", "int", help="1 à 5"),
        Column("objectifs", "str"),
        Column("commentaire", "str"),
        Column("statut", "str"),
    ),
)

_INVOICES = EntitySpec(
    entity="invoices",
    label="Factures",
    model=InvoiceRecord,
    natural_key=("numero",),
    columns=(
        Column(
            "numero",
            "str",
            required=True,
            help="Numéro unique de facture",
            aliases=("n facture", "numero facture", "ref facture", "reference"),
        ),
        Column("sens", "str", enum=("vente", "achat"), aliases=("type", "nature", "sens facture")),
        Column(
            "tiers",
            "str",
            required=True,
            help="Client ou fournisseur",
            aliases=("client", "fournisseur", "partenaire", "raison sociale"),
        ),
        Column(
            "date_emission",
            "date",
            required=True,
            help="AAAA-MM-JJ",
            aliases=("date facture", "emission", "date emission facture"),
        ),
        Column("date_echeance", "date", aliases=("echeance", "date limite", "date reglement")),
        Column("montant_ht_xaf", "decimal", aliases=("ht", "montant ht", "total ht")),
        Column(
            "montant_ttc_xaf", "decimal", aliases=("ttc", "montant ttc", "total ttc", "montant")
        ),
        Column("devise", "str", aliases=("monnaie", "currency")),
        Column(
            "payee", "bool", help="oui/non", aliases=("reglee", "soldee", "paye", "statut paiement")
        ),
    ),
)

# Toutes les entités (endpoints par entité).
REGISTRY: dict[str, EntitySpec] = {
    s.entity: s
    for s in (
        _EMPLOYEES,
        _CONTRACTS,
        _ABSENCES,
        _JOB_ROLES,
        _SKILLS,
        _ROLE_SKILLS,
        _EMPLOYEE_SKILLS,
        _VACANCIES,
        _TRAININGS,
        _EVALUATIONS,
        _INVOICES,
    )
}

# Classeurs par pôle (multi-feuilles).
POLES: dict[str, PoleSpec] = {
    "rh": PoleSpec(
        pole="rh",
        label="Ressources Humaines",
        entities=(
            _EMPLOYEES,
            _CONTRACTS,
            _ABSENCES,
            _JOB_ROLES,
            _SKILLS,
            _ROLE_SKILLS,
            _EMPLOYEE_SKILLS,
            _VACANCIES,
            _TRAININGS,
            _EVALUATIONS,
        ),
    ),
    "compta": PoleSpec(pole="compta", label="Comptabilité", entities=(_INVOICES,)),
}
