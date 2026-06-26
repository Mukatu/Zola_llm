"""Inventaire — valorisation des mouvements de stock (PMP / coût moyen pondéré).

**Aucun LLM** : la valorisation est déterministe (norme SYSCOHADA classe 3).
La validation d'un mouvement met à jour la quantité et le PMP de l'article :
- **entrée** : moyenne pondérée du coût (PMP) ;
- **sortie** : valorisée au PMP courant (PMP inchangé) ;
- **ajustement** : delta signé valorisé au PMP ;
- **transfert** : neutre sur la quantité totale et le PMP.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from decimal import ROUND_HALF_UP, Decimal

from pydantic import BaseModel

_ZERO = Decimal("0")
_JOURS_AN = Decimal("365")
TYPES_MOUVEMENT = ("entree", "sortie", "ajustement", "transfert")

# Au-delà de ce montant, un mouvement requiert une double validation (N1 puis N2).
SEUIL_VALIDATION_DEFAUT_XAF = Decimal("1000000")

_Q_QTE = Decimal("0.001")
_Q_XAF = Decimal("0.01")


class StockInsuffisant(ValueError):
    """Sortie/ajustement amenant le stock sous zéro sans autorisation explicite."""


@dataclass(frozen=True)
class ResultatMouvement:
    nouvelle_quantite: Decimal
    nouveau_pmp_xaf: Decimal
    valeur_mouvement_xaf: Decimal


def _qte(v: Decimal) -> Decimal:
    return v.quantize(_Q_QTE, rounding=ROUND_HALF_UP)


def _xaf(v: Decimal) -> Decimal:
    return v.quantize(_Q_XAF, rounding=ROUND_HALF_UP)


def appliquer_mouvement(
    *,
    type: str,
    quantite: Decimal,
    quantite_actuelle: Decimal,
    pmp_actuel: Decimal,
    cout_unitaire: Decimal | None = None,
    autoriser_negatif: bool = False,
) -> ResultatMouvement:
    """Calcule l'état de l'article après validation d'un mouvement (déterministe)."""
    if type == "entree":
        cu = cout_unitaire if cout_unitaire is not None else pmp_actuel
        nouvelle_qte = quantite_actuelle + quantite
        nouveau_pmp = (
            (quantite_actuelle * pmp_actuel + quantite * cu) / nouvelle_qte
            if nouvelle_qte > 0
            else cu
        )
        return ResultatMouvement(_qte(nouvelle_qte), _xaf(nouveau_pmp), _xaf(quantite * cu))

    if type == "sortie":
        if quantite > quantite_actuelle and not autoriser_negatif:
            raise StockInsuffisant(f"Sortie {quantite} > stock disponible {quantite_actuelle}.")
        return ResultatMouvement(
            _qte(quantite_actuelle - quantite), _xaf(pmp_actuel), _xaf(quantite * pmp_actuel)
        )

    if type == "ajustement":
        nouvelle_qte = quantite_actuelle + quantite  # quantite signée (+/-)
        if nouvelle_qte < 0 and not autoriser_negatif:
            raise StockInsuffisant(f"Ajustement {quantite} amène le stock à {nouvelle_qte}.")
        return ResultatMouvement(
            _qte(nouvelle_qte), _xaf(pmp_actuel), _xaf(abs(quantite) * pmp_actuel)
        )

    if type == "transfert":
        # Déplacement d'emplacement : neutre sur la quantité totale et le PMP.
        return ResultatMouvement(_qte(quantite_actuelle), _xaf(pmp_actuel), _ZERO)

    raise ValueError(f"Type de mouvement inconnu : {type!r}")


def estimer_valeur_mouvement(
    *, type: str, quantite: Decimal, pmp_actuel: Decimal, cout_unitaire: Decimal | None = None
) -> Decimal:
    """Valeur estimée d'un mouvement **avant** application (pour le seuil de validation)."""
    if type == "entree":
        cu = cout_unitaire if cout_unitaire is not None else pmp_actuel
        return _xaf(quantite * cu)
    if type in ("sortie", "ajustement"):
        return _xaf(abs(quantite) * pmp_actuel)
    return _ZERO


def requiert_double_validation(valeur_estimee: Decimal, seuil_xaf: Decimal) -> bool:
    """Vrai si le mouvement dépasse le seuil → validation N1 puis N2."""
    return valeur_estimee > seuil_xaf


# ----------------------------------------------------------------- pilotage stock (STOCK-4)


class ArticleStock(BaseModel):
    model_config = {"extra": "forbid"}

    sku: str
    libelle: str = ""
    quantite_actuelle: Decimal = _ZERO
    conso_moyenne_jour: Decimal = _ZERO
    stock_securite: Decimal = _ZERO
    pmp_xaf: Decimal = _ZERO


@dataclass(frozen=True)
class ArticleLigne:
    sku: str
    libelle: str
    quantite: Decimal
    valeur_stock_xaf: Decimal
    valeur_conso_annuelle_xaf: Decimal
    couverture_jours: Decimal | None
    rotation_annuelle: Decimal | None
    classe_abc: str  # A | B | C


@dataclass(frozen=True)
class PilotageStock:
    nb_articles: int
    valorisation_totale_xaf: Decimal
    nb_rupture: int
    nb_sous_securite: int
    taux_rupture_pct: Decimal
    couverture_moyenne_jours: Decimal | None
    dormant_nb: int
    dormant_valeur_xaf: Decimal
    repartition_abc: dict[str, int]
    par_article: list[ArticleLigne] = field(default_factory=list)


def _pct1(part: int, whole: int) -> Decimal:
    if whole <= 0:
        return _ZERO
    return (Decimal(part) / Decimal(whole) * 100).quantize(Decimal("0.1"), rounding=ROUND_HALF_UP)


@dataclass
class _Mesure:
    a: ArticleStock
    valeur_stock: Decimal
    conso_an_val: Decimal
    couverture: Decimal | None
    rotation: Decimal | None
    classe: str = "C"


def pilotage_stock(articles: list[ArticleStock]) -> PilotageStock:
    """Indicateurs d'inventaire : valorisation, rupture, couverture, dormant, ABC.

    **Déterministe** : rotation/couverture déduites de la consommation moyenne ;
    ABC fondée sur la valeur de consommation annuelle (repli sur la valeur de stock).
    """
    n = len(articles)
    mesures: list[_Mesure] = []
    for a in articles:
        couverture = (
            a.quantite_actuelle / a.conso_moyenne_jour if a.conso_moyenne_jour > 0 else None
        )
        rotation = (
            a.conso_moyenne_jour * _JOURS_AN / a.quantite_actuelle
            if a.quantite_actuelle > 0 and a.conso_moyenne_jour > 0
            else None
        )
        mesures.append(
            _Mesure(
                a=a,
                valeur_stock=a.quantite_actuelle * a.pmp_xaf,
                conso_an_val=a.conso_moyenne_jour * _JOURS_AN * a.pmp_xaf,
                couverture=couverture,
                rotation=rotation,
            )
        )

    valorisation = sum((m.valeur_stock for m in mesures), _ZERO)
    nb_rupture = sum(1 for a in articles if a.quantite_actuelle <= 0)
    nb_sous_securite = sum(1 for a in articles if 0 < a.quantite_actuelle < a.stock_securite)
    dormant = [m for m in mesures if m.a.conso_moyenne_jour <= 0 and m.a.quantite_actuelle > 0]
    dormant_valeur = sum((m.valeur_stock for m in dormant), _ZERO)

    couvertures = [m.couverture for m in mesures if m.couverture is not None]
    couverture_moyenne = (
        (sum(couvertures, _ZERO) / Decimal(len(couvertures))).quantize(
            Decimal("0.1"), rounding=ROUND_HALF_UP
        )
        if couvertures
        else None
    )

    # ABC : tri décroissant sur la valeur de conso annuelle (repli valeur stock).
    use_conso = any(m.conso_an_val > 0 for m in mesures)
    ordonne = sorted(
        mesures, key=lambda m: (m.conso_an_val if use_conso else m.valeur_stock), reverse=True
    )
    total = sum(((m.conso_an_val if use_conso else m.valeur_stock) for m in ordonne), _ZERO)
    cumul = _ZERO
    repartition = {"A": 0, "B": 0, "C": 0}
    for m in ordonne:
        if total > 0:
            # Bande déterminée par le cumul AVANT l'article (celui qui franchit le
            # seuil reste dans sa bande) → le 1er article est toujours « A ».
            prev_pct = cumul / total * 100
            m.classe = "A" if prev_pct < 80 else "B" if prev_pct < 95 else "C"
            cumul += m.conso_an_val if use_conso else m.valeur_stock
        repartition[m.classe] += 1

    par_article = [
        ArticleLigne(
            sku=m.a.sku,
            libelle=m.a.libelle,
            quantite=m.a.quantite_actuelle,
            valeur_stock_xaf=_xaf(m.valeur_stock),
            valeur_conso_annuelle_xaf=_xaf(m.conso_an_val),
            couverture_jours=(
                m.couverture.quantize(Decimal("0.1"), rounding=ROUND_HALF_UP)
                if m.couverture is not None
                else None
            ),
            rotation_annuelle=(
                m.rotation.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
                if m.rotation is not None
                else None
            ),
            classe_abc=m.classe,
        )
        for m in ordonne
    ]

    return PilotageStock(
        nb_articles=n,
        valorisation_totale_xaf=_xaf(valorisation),
        nb_rupture=nb_rupture,
        nb_sous_securite=nb_sous_securite,
        taux_rupture_pct=_pct1(nb_rupture, n),
        couverture_moyenne_jours=couverture_moyenne,
        dormant_nb=len(dormant),
        dormant_valeur_xaf=_xaf(dormant_valeur),
        repartition_abc=repartition,
        par_article=par_article,
    )
