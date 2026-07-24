"""Extraction de candidats de contribution depuis le feedback (local, gaté opt-in).

On dérive une **règle généralisable** (une paire Q/R validée, ou une correction),
jamais un dossier. La sortie est déjà anonymisée. Le périmètre de l'agent doit
être explicitement consenti (I4).
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from zolaos.commons.anonymize import anonymize, content_hash

MAX_LEN = 1200  # on contribue un motif, pas un dossier → on tronque les textes longs


@dataclass(frozen=True)
class Candidate:
    type: str  # qa | correction
    domaine: str  # agent/pôle (catégorie, non privé)
    payload: dict[str, Any]  # assaini, sans lien source ni tenant
    content_hash: str


def scope_allowed(enabled: bool, scopes: list[str], agent: str) -> bool:
    """Le périmètre de l'agent est-il autorisé par le consentement du locataire ?

    Accepte **tout segment** du nom : ``erp.rh`` matche ``erp`` ou ``rh`` ;
    ``legal.ohada`` matche ``legal`` ou ``ohada``. Ainsi les périmètres proposés
    (legal, erp, achats, rh, sante) restent intuitifs malgré le nommage interne.
    """
    if not enabled:
        return False
    segments = agent.split(".") if agent else []
    return agent in scopes or any(seg in scopes for seg in segments)


def feedback_to_candidate(
    fb: dict[str, Any], *, enabled: bool, scopes: list[str]
) -> Candidate | None:
    """Dérive un candidat anonymisé d'un retour, si le périmètre est consenti.

    - correction présente → candidat ``correction`` (règle experte à retenir) ;
    - sinon verdict ``up`` → candidat ``qa`` (paire Q/R validée) ;
    - ``down`` sans correction → aucun savoir contribuable → ``None``.
    """
    agent = str(fb.get("agent") or "")
    if not scope_allowed(enabled, scopes, agent):
        return None

    question = anonymize(str(fb.get("query") or ""))[:MAX_LEN]
    if not question:
        return None

    correction = str(fb.get("correction") or "").strip()
    if correction:
        reponse = anonymize(correction)[:MAX_LEN]
        ctype = "correction"
    elif fb.get("verdict") == "up":
        reponse = anonymize(str(fb.get("response") or ""))[:MAX_LEN]
        ctype = "qa"
    else:
        return None

    if not reponse:
        return None

    payload = {"domaine": agent, "question": question, "reponse": reponse}
    return Candidate(type=ctype, domaine=agent, payload=payload, content_hash=content_hash(payload))
