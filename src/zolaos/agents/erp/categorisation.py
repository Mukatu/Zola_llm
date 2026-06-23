"""Auto-catégorisation assistée — libellé → compte SYSCOHADA.

Doctrine : **déterministe d'abord**. Un moteur de règles (mots-clés → compte)
**propose** un compte, filtré contre le plan de comptes réel (on ne suggère
jamais un compte inexistant). Le `JournalValidator` **valide** ; l'humain
**confirme**. Le LLM n'est pas requis (suggestion explicable, hors-ligne) ; il
pourra enrichir les cas ambigus plus tard.
"""

from __future__ import annotations

import unicodedata
from dataclasses import dataclass

from zolaos.agents.erp.compta import ChartOfAccounts

# (mots-clés, compte SYSCOHADA, raison). Le compte n'est proposé que s'il
# existe dans le plan chargé (résolu via ChartOfAccounts).
_RULES: tuple[tuple[tuple[str, ...], str, str], ...] = (
    (("vente de marchandise", "vente marchandise", "vente"), "701", "Vente de marchandises"),
    (("prestation", "service vendu", "honoraires", "service"), "706", "Services vendus"),
    (("client", "facture client", "creance"), "411", "Créance client"),
    (("fournisseur", "facture fournisseur"), "401", "Dette fournisseur"),
    (("achat de marchandise", "achat marchandise", "marchandise"), "601", "Achats de marchandises"),
    (("fourniture", "eau", "electricite", "carburant", "autre achat"), "605", "Autres achats"),
    (("loyer", "location", "bail"), "622", "Locations et charges locatives"),
    (("salaire", "paie", "remuneration", "personnel paye"), "661", "Rémunérations du personnel"),
    (("charge sociale", "cotisation patronale", "cotisations sociales"), "664", "Charges sociales"),
    (("cnss", "securite sociale", "dette sociale"), "431", "Sécurité sociale (CNSS)"),
    (("tva collectee", "tva facturee", "tva sur vente"), "4431", "TVA collectée"),
    (("tva deductible", "tva recuperable", "tva sur achat"), "4452", "TVA déductible"),
    (("banque", "virement", "cheque"), "521", "Banque"),
    (("cheque postal", "ccp"), "531", "Chèques postaux"),
    (("caisse", "espece", "especes", "cash"), "571", "Caisse"),
    (("impot", "taxe"), "641", "Impôts et taxes"),
    (("interet", "revenu financier", "produit financier"), "771", "Revenus financiers"),
    (("terrain",), "211", "Terrains"),
    (("construction", "batiment", "immeuble"), "213", "Constructions"),
    (("materiel", "outillage", "machine"), "215", "Matériel et outillage"),
    (("vehicule", "voiture", "camion", "transport"), "218", "Matériel de transport"),
    (("amortissement", "dotation"), "681", "Dotations aux amortissements"),
    (("capital",), "101", "Capital social"),
    (("emprunt", "pret bancaire", "credit bancaire"), "161", "Emprunts"),
)


@dataclass(frozen=True)
class AccountSuggestion:
    compte: str
    libelle_compte: str
    score: float
    raison: str


def _norm(s: str) -> str:
    """Minuscule sans accents (comparaison robuste)."""
    nfkd = unicodedata.normalize("NFKD", s.lower())
    return "".join(c for c in nfkd if not unicodedata.combining(c))


def suggest_accounts(
    libelle: str,
    *,
    chart: ChartOfAccounts,
    sens: str | None = None,
    top_k: int = 3,
) -> list[AccountSuggestion]:
    """Propose les comptes SYSCOHADA les plus probables pour un libellé.

    Déterministe : score = longueur du mot-clé le plus spécifique trouvé,
    bonifié si le sens normal du compte correspond au sens de la ligne.
    """
    text = _norm(libelle)
    best: dict[str, tuple[float, str, str]] = {}  # compte -> (score, raison, libelle_compte)
    for keywords, compte, raison in _RULES:
        account = chart.resolve(compte)
        if account is None:
            continue
        matched = [k for k in keywords if _norm(k) in text]
        if not matched:
            continue
        score = float(max(len(k) for k in matched))
        if sens is not None and account.sens_normal in (sens, "mixte"):
            score += 0.5
        current = best.get(compte)
        if current is None or score > current[0]:
            best[compte] = (score, raison, account.libelle)

    ranked = sorted(best.items(), key=lambda kv: kv[1][0], reverse=True)[:top_k]
    if not ranked:
        return []
    top = ranked[0][1][0]
    return [
        AccountSuggestion(
            compte=compte,
            libelle_compte=meta[2],
            score=round(meta[0] / top, 2),
            raison=meta[1],
        )
        for compte, meta in ranked
    ]
