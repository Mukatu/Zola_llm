"""Registre des entités importables/exportables + classeurs par pôle (IMP-2)."""

from __future__ import annotations

from zolaos.db.store_models import (
    AbsenceRecord,
    BankAccountRecord,
    CashFlowRecord,
    ContractRecord,
    CustomerRecord,
    EmployeeRecord,
    EmployeeSkillRecord,
    EngagementRecord,
    EvaluationRecord,
    InvoiceRecord,
    JobRoleRecord,
    OpportunityRecord,
    PurchaseBudgetRecord,
    PurchaseOrderRecord,
    QuoteRecord,
    RoleSkillRecord,
    SkillRecord,
    StockItemRecord,
    StockMoveRecord,
    SupplierRecord,
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

# ----------------------------------------------------------------- Commercial / CRM (P2b)

_CUSTOMERS = EntitySpec(
    entity="customers",
    label="Clients",
    model=CustomerRecord,
    natural_key=("id_externe",),
    columns=(
        Column(
            "id_externe",
            "str",
            required=True,
            help="Identifiant unique du client",
            aliases=("id client", "code client", "reference client", "n client"),
        ),
        Column(
            "nom",
            "str",
            required=True,
            aliases=("nom client", "raison sociale", "intitule"),
        ),
        Column("type", "str", enum=("client", "prospect"), aliases=("categorie", "statut client")),
        Column("email", "str", aliases=("courriel", "mail", "adresse email")),
        Column("telephone", "str", aliases=("tel", "tel.", "numero", "contact")),
        Column("secteur", "str", aliases=("activite", "domaine", "branche")),
        Column(
            "source",
            "str",
            enum=("referral", "salon", "web", "appel", "autre"),
            help="Canal d'acquisition",
            aliases=("origine", "provenance", "canal"),
        ),
        Column("date_creation", "date", help="AAAA-MM-JJ", aliases=("date entree", "creation")),
        Column(
            "derniere_interaction",
            "date",
            help="AAAA-MM-JJ",
            aliases=("dernier contact", "derniere relance"),
        ),
    ),
)

_OPPORTUNITIES = EntitySpec(
    entity="opportunities",
    label="Opportunités",
    model=OpportunityRecord,
    natural_key=("id_externe",),
    columns=(
        Column(
            "id_externe",
            "str",
            required=True,
            help="Identifiant unique de l'opportunité",
            aliases=("id opportunite", "code affaire", "reference"),
        ),
        Column("client", "str", required=True, aliases=("nom client", "compte", "tiers")),
        Column("libelle", "str", required=True, aliases=("intitule", "objet", "affaire")),
        Column("montant_xaf", "decimal", aliases=("montant", "valeur", "ca potentiel")),
        Column(
            "etape",
            "str",
            enum=("prospection", "qualification", "proposition", "negociation", "gagnee", "perdue"),
            aliases=("stade", "phase", "statut", "pipeline"),
        ),
        Column("probabilite", "decimal", help="0 à 1 (sinon déduite de l'étape)"),
        Column(
            "date_cloture_prevue",
            "date",
            help="AAAA-MM-JJ",
            aliases=("cloture prevue", "date signature", "echeance"),
        ),
    ),
)

_QUOTES = EntitySpec(
    entity="quotes",
    label="Devis",
    model=QuoteRecord,
    natural_key=("numero",),
    columns=(
        Column("id_externe", "str", required=True, aliases=("id devis", "reference")),
        Column(
            "numero",
            "str",
            required=True,
            help="Numéro unique du devis",
            aliases=("n devis", "numero devis", "ref devis"),
        ),
        Column("client", "str", required=True, aliases=("nom client", "tiers")),
        Column("date_emission", "date", required=True, help="AAAA-MM-JJ", aliases=("date devis",)),
        Column("date_validite", "date", help="AAAA-MM-JJ", aliases=("validite", "echeance")),
        Column(
            "statut",
            "str",
            enum=("brouillon", "envoye", "accepte", "refuse"),
            aliases=("etat", "situation"),
        ),
        Column("montant_ht_xaf", "decimal", aliases=("ht", "montant ht", "total ht")),
        Column(
            "montant_ttc_xaf", "decimal", aliases=("ttc", "montant ttc", "total ttc", "montant")
        ),
    ),
)

# ----------------------------------------------------------------- Achats (P2c)

_SUPPLIERS = EntitySpec(
    entity="suppliers",
    label="Fournisseurs",
    model=SupplierRecord,
    natural_key=("id_externe",),
    columns=(
        Column(
            "id_externe",
            "str",
            required=True,
            help="Identifiant unique du fournisseur",
            aliases=("id fournisseur", "code fournisseur", "n fournisseur"),
        ),
        Column("nom", "str", required=True, aliases=("nom fournisseur", "raison sociale")),
        Column("secteur", "str", aliases=("activite", "domaine")),
        Column("note_qualite", "decimal", help="Historique 0 à 5", aliases=("note", "qualite")),
        Column(
            "delai_moyen_jours",
            "int",
            help="Délai de livraison moyen (jours)",
            aliases=("delai", "delai moyen", "delai livraison"),
        ),
        Column(
            "documents_conformite",
            "list",
            help="Pièces fournies, séparées par ; (rccm, niu, attestation_fiscale)",
            aliases=("conformite", "documents", "pieces"),
        ),
        Column("actif", "bool", help="oui/non", aliases=("statut", "actif?")),
    ),
)

_PURCHASE_ORDERS = EntitySpec(
    entity="purchase_orders",
    label="Bons de commande",
    model=PurchaseOrderRecord,
    natural_key=("numero",),
    columns=(
        Column("id_externe", "str", required=True, aliases=("id bc", "reference")),
        Column(
            "numero",
            "str",
            required=True,
            help="Numéro unique du bon de commande",
            aliases=("n bc", "numero bc", "ref bc", "numero commande"),
        ),
        Column("fournisseur", "str", required=True, aliases=("nom fournisseur", "tiers")),
        Column("objet", "str", aliases=("intitule", "designation")),
        Column("date_emission", "date", required=True, help="AAAA-MM-JJ", aliases=("date bc",)),
        Column(
            "statut",
            "str",
            enum=("brouillon", "envoye", "confirme", "receptionne"),
            aliases=("etat", "situation"),
        ),
        Column("montant_ht_xaf", "decimal", aliases=("ht", "montant ht", "total ht")),
        Column(
            "montant_ttc_xaf", "decimal", aliases=("ttc", "montant ttc", "total ttc", "montant")
        ),
        Column(
            "delai_livraison_jours",
            "int",
            help="Délai de livraison (jours)",
            aliases=("delai", "delai livraison"),
        ),
    ),
)

# ----------------------------------------------------------------- Engagements (Achats v2)

# Colonnes alignées sur l'outil métier réel (feuille « BD ») → import direct.
_ENGAGEMENTS = EntitySpec(
    entity="engagements",
    label="Engagements",
    model=EngagementRecord,
    natural_key=("numero_eb",),
    columns=(
        Column(
            "numero_eb",
            "str",
            required=True,
            help="N° Expression de Besoin",
            aliases=("n eb", "n° eb", "numero eb", "n  eb"),
        ),
        Column(
            "numero_da", "str", help="N° Demande d'Achat", aliases=("n da", "n° da", "numero da")
        ),
        Column(
            "numero_bc", "str", help="N° Bon de Commande", aliases=("n bc", "n° bc", "numero bc")
        ),
        Column("date_eb", "date", help="AAAA-MM-JJ", aliases=("date eb",)),
        Column("date_da", "date", help="AAAA-MM-JJ", aliases=("date da",)),
        Column("date_bc", "date", help="AAAA-MM-JJ", aliases=("date bc",)),
        Column("direction", "str", aliases=("direction", "dir")),
        Column("service", "str", aliases=("service",)),
        Column("demandeur", "str", aliases=("demandeur", "requerant")),
        Column(
            "description_besoin",
            "str",
            aliases=("description du besoin", "description besoin", "besoin"),
        ),
        Column("description_da", "str", aliases=("description da",)),
        Column("acheteur", "str", aliases=("acheteur",)),
        Column("fournisseur", "str", aliases=("fournisseur", "prestataire")),
        Column("description_bc", "str", aliases=("description bc",)),
        Column(
            "estimation_xaf",
            "decimal",
            help="Montant estimé du besoin",
            aliases=("estimation", "estime", "budget"),
        ),
        Column(
            "montant_xaf",
            "decimal",
            help="Montant engagé (BC)",
            aliases=("montant", "montant engage", "engage"),
        ),
        Column("statut_ebda", "str", aliases=("statut eb/da", "statut ebda", "statut eb da")),
        Column("statut_bc", "str", aliases=("statut bc",)),
    ),
)

_PURCHASE_BUDGETS = EntitySpec(
    entity="purchase_budgets",
    label="Budgets achats",
    model=PurchaseBudgetRecord,
    natural_key=("direction", "exercice"),
    columns=(
        Column("direction", "str", required=True, aliases=("direction", "dir", "entite")),
        Column(
            "exercice", "str", required=True, help="Année (ex. 2026)", aliases=("annee", "exercice")
        ),
        Column(
            "budget_xaf",
            "decimal",
            help="Budget alloué pour l'exercice",
            aliases=("budget", "dotation", "enveloppe"),
        ),
    ),
)

# ----------------------------------------------------------------- Supply / Stocks (P2)

_STOCK_ITEMS = EntitySpec(
    entity="stock_items",
    label="Articles de stock",
    model=StockItemRecord,
    natural_key=("sku",),
    columns=(
        Column(
            "sku",
            "str",
            required=True,
            help="Référence article (SKU)",
            aliases=("reference", "ref", "code article", "code"),
        ),
        Column("libelle", "str", required=True, aliases=("designation", "intitule", "produit")),
        Column(
            "quantite_actuelle",
            "decimal",
            aliases=("quantite", "stock", "qte", "stock actuel"),
        ),
        Column("unite", "str", aliases=("unite mesure", "u")),
        Column(
            "conso_moyenne_jour",
            "decimal",
            help="Consommation moyenne par jour",
            aliases=("conso", "conso jour", "consommation"),
        ),
        Column(
            "delai_appro_jours",
            "int",
            help="Délai de réapprovisionnement (jours)",
            aliases=("delai appro", "delai", "lead time"),
        ),
        Column("stock_securite", "decimal", aliases=("securite", "stock min", "seuil")),
    ),
)

_STOCK_MOVES = EntitySpec(
    entity="stock_moves",
    label="Mouvements de stock",
    model=StockMoveRecord,
    natural_key=("reference",),
    columns=(
        Column(
            "reference",
            "str",
            required=True,
            help="Référence unique du mouvement",
            aliases=("ref", "n mouvement", "numero mouvement"),
        ),
        Column(
            "type",
            "str",
            enum=("entree", "sortie", "ajustement", "transfert"),
            aliases=("sens", "nature"),
        ),
        Column(
            "sku", "str", required=True, aliases=("reference article", "code article", "article")
        ),
        Column("quantite", "decimal", aliases=("qte", "quantite mouvement")),
        Column(
            "cout_unitaire_xaf",
            "decimal",
            help="Coût unitaire (entrée)",
            aliases=("cout", "pu", "prix unitaire"),
        ),
        Column("emplacement", "str", aliases=("entrepot", "magasin", "depot")),
        Column("emplacement_dest", "str", aliases=("destination",)),
        Column("lot", "str", aliases=("numero lot", "batch")),
        Column("date_peremption", "date", help="AAAA-MM-JJ", aliases=("peremption", "dlc", "dluo")),
        Column("motif", "str", aliases=("commentaire", "note")),
        Column("date_mouvement", "date", required=True, help="AAAA-MM-JJ", aliases=("date",)),
    ),
)

# ----------------------------------------------------------------- Trésorerie (TRESO-1)

_BANK_ACCOUNTS = EntitySpec(
    entity="bank_accounts",
    label="Comptes de trésorerie",
    model=BankAccountRecord,
    natural_key=("code",),
    columns=(
        Column(
            "code",
            "str",
            required=True,
            help="Code unique du compte",
            aliases=("code compte", "n compte"),
        ),
        Column("libelle", "str", required=True, aliases=("intitule", "nom compte")),
        Column("banque", "str", aliases=("etablissement",)),
        Column("type", "str", enum=("banque", "caisse", "mobile_money"), aliases=("nature",)),
        Column("devise", "str", aliases=("monnaie", "currency")),
        Column("iban", "str", aliases=("rib",)),
        Column(
            "solde_initial_xaf",
            "decimal",
            help="Solde d'ouverture",
            aliases=("solde initial", "solde ouverture", "solde"),
        ),
    ),
)

_CASH_FLOWS = EntitySpec(
    entity="cash_flows",
    label="Flux de trésorerie",
    model=CashFlowRecord,
    natural_key=("reference",),
    columns=(
        Column(
            "reference",
            "str",
            required=True,
            help="Référence unique du flux",
            aliases=("ref", "piece"),
        ),
        Column("compte_code", "str", required=True, aliases=("compte", "code compte")),
        Column("sens", "str", enum=("encaissement", "decaissement"), aliases=("type", "nature")),
        Column("montant_xaf", "decimal", aliases=("montant", "valeur")),
        Column(
            "date_operation",
            "date",
            required=True,
            help="AAAA-MM-JJ",
            aliases=("date", "date operation"),
        ),
        Column(
            "date_prevue", "date", help="AAAA-MM-JJ (si prévu)", aliases=("echeance", "date prevue")
        ),
        Column("statut", "str", enum=("prevu", "realise"), aliases=("etat",)),
        Column("categorie", "str", aliases=("rubrique", "poste")),
        Column("tiers", "str", aliases=("beneficiaire", "client", "fournisseur")),
        Column("libelle", "str", aliases=("intitule", "motif", "objet")),
        Column(
            "mode",
            "str",
            help="virement, cheque, especes, mobile_money",
            aliases=("moyen", "mode reglement"),
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
        _CUSTOMERS,
        _OPPORTUNITIES,
        _QUOTES,
        _SUPPLIERS,
        _PURCHASE_ORDERS,
        _ENGAGEMENTS,
        _PURCHASE_BUDGETS,
        _STOCK_ITEMS,
        _STOCK_MOVES,
        _BANK_ACCOUNTS,
        _CASH_FLOWS,
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
    "commercial": PoleSpec(
        pole="commercial",
        label="Commercial / CRM",
        entities=(_CUSTOMERS, _OPPORTUNITIES, _QUOTES),
    ),
    "achats": PoleSpec(
        pole="achats",
        label="Achats",
        entities=(_SUPPLIERS, _PURCHASE_ORDERS, _ENGAGEMENTS, _PURCHASE_BUDGETS),
    ),
    "supply": PoleSpec(
        pole="supply",
        label="Supply Chain",
        entities=(_STOCK_ITEMS, _STOCK_MOVES),
    ),
    "tresorerie": PoleSpec(
        pole="tresorerie",
        label="Trésorerie",
        entities=(_BANK_ACCOUNTS, _CASH_FLOWS),
    ),
}
