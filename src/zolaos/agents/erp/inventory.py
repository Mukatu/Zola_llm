"""Inventaire — valorisation des mouvements de stock (PMP / coût moyen pondéré).

**Aucun LLM** : la valorisation est déterministe (norme SYSCOHADA classe 3).
La validation d'un mouvement met à jour la quantité et le PMP de l'article :
- **entrée** : moyenne pondérée du coût (PMP) ;
- **sortie** : valorisée au PMP courant (PMP inchangé) ;
- **ajustement** : delta signé valorisé au PMP ;
- **transfert** : neutre sur la quantité totale et le PMP.
"""

from __future__ import annotations

from dataclasses import dataclass
from decimal import ROUND_HALF_UP, Decimal

_ZERO = Decimal("0")
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
