"""Conformité consentement — Loi 29-2019 (addendum §3.3, MKT-1).

Garde **déterministe** : on ne cible un contact que s'il a **consenti** ET que
la **finalité** de la campagne est couverte par son consentement. Privacy by
design : le code refuse, pas le LLM.
"""

from __future__ import annotations

from dataclasses import dataclass

from zolaos.agents.mkt.models import MarketingContact


class ConsentError(RuntimeError):
    """Tentative de ciblage marketing sans consentement valide (Loi 29-2019)."""


def is_eligible(contact: MarketingContact, finalite: str) -> bool:
    """Éligible si consentement marketing donné ET finalité couverte."""
    return contact.consentement_marketing and finalite in contact.finalites


def filter_consented(contacts: list[MarketingContact], finalite: str) -> list[MarketingContact]:
    """Ne garde que les contacts éligibles pour la finalité."""
    return [c for c in contacts if is_eligible(c, finalite)]


def ensure_consent(contact: MarketingContact, finalite: str) -> None:
    """Lève `ConsentError` si le contact n'est pas éligible."""
    if not is_eligible(contact, finalite):
        raise ConsentError(
            f"Contact {contact.id_externe!r} non éligible pour la finalité {finalite!r} "
            "(consentement manquant — Loi 29-2019)."
        )


@dataclass(frozen=True)
class ConsentSummary:
    finalite: str
    eligibles: int
    exclus: int
    total: int


def consent_summary(contacts: list[MarketingContact], finalite: str) -> ConsentSummary:
    eligibles = len(filter_consented(contacts, finalite))
    total = len(contacts)
    return ConsentSummary(finalite=finalite, eligibles=eligibles, exclus=total - eligibles, total=total)
