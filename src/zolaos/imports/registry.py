"""Registre des entités importables/exportables (pilotes IMP-1)."""

from __future__ import annotations

from zolaos.db.store_models import EmployeeRecord, InvoiceRecord
from zolaos.imports.framework import Column, EntitySpec

REGISTRY: dict[str, EntitySpec] = {
    "employees": EntitySpec(
        entity="employees",
        label="Employés",
        model=EmployeeRecord,
        natural_key=("matricule",),
        columns=(
            Column("matricule", "str", required=True, help="Identifiant unique de l'employé"),
            Column("nom_complet", "str", required=True),
            Column("genre", "str", enum=("H", "F", "NC"), help="H, F ou NC"),
            Column("date_naissance", "date", help="AAAA-MM-JJ"),
            Column("date_embauche", "date", required=True, help="AAAA-MM-JJ"),
            Column("poste", "str"),
            Column("departement", "str"),
            Column("manager_matricule", "str"),
            Column("categorie", "str"),
            Column("code_emploi", "str", help="Code de l'emploi-repère (RME)"),
            Column("salaire_base_xaf", "decimal"),
            Column("quotite", "decimal", help="Temps de travail (1 = plein temps)"),
            Column("statut", "str", enum=("actif", "sorti")),
        ),
    ),
    "invoices": EntitySpec(
        entity="invoices",
        label="Factures",
        model=InvoiceRecord,
        natural_key=("numero",),
        columns=(
            Column("numero", "str", required=True, help="Numéro unique de facture"),
            Column("sens", "str", enum=("vente", "achat")),
            Column("tiers", "str", required=True, help="Client ou fournisseur"),
            Column("date_emission", "date", required=True, help="AAAA-MM-JJ"),
            Column("date_echeance", "date"),
            Column("montant_ht_xaf", "decimal"),
            Column("montant_ttc_xaf", "decimal"),
            Column("devise", "str"),
            Column("payee", "bool", help="oui/non"),
        ),
    ),
}
