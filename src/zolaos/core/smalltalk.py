"""Détection de salutations / bavardage (small talk).

Sans ce garde-fou, un simple « bonjour » — préfixé par le contexte du dock
(« En droit des affaires OHADA : bonjour ») — déclenche un retrieval, trouve des
articles au hasard et produit une réponse juridique **sans rapport avec la saisie**.
On court-circuite ces cas par une réponse conversationnelle.

Volontairement STRICT : correspondance **exacte** sur un petit ensemble normalisé.
Un faux négatif (salutation traitée comme une question) est bénin ; un faux positif
(vraie question court-circuitée) ne l'est pas. D'où l'absence de correspondance par
sous-chaîne — « merci de préciser le délai » n'est PAS « merci ».
"""

from __future__ import annotations

import unicodedata


def _normalize(text: str) -> str:
    """Minuscule, sans accents, sans ponctuation de bord, espaces compactés."""
    decomposed = unicodedata.normalize("NFKD", text.lower())
    stripped = "".join(c for c in decomposed if not unicodedata.combining(c))
    stripped = stripped.strip().strip("!?.,;:«»\"'()… ").strip()
    return " ".join(stripped.split())


def _payload(query: str) -> str:
    """Isole la charge utile : le dock préfixe « <contexte> : <question> ».

    On prend le dernier segment après « : » (le vrai texte de l'utilisateur).
    """
    parts = query.split(" : ")
    return parts[-1] if len(parts) > 1 else query


_GREETINGS = {
    "bonjour",
    "bonsoir",
    "bonne journee",
    "bonne soiree",
    "salut",
    "coucou",
    "cc",
    "hello",
    "hi",
    "hey",
    "yo",
    "allo",
    "hola",
    "re",
    "rebonjour",
    "ca va",
    "comment ca va",
    "comment vas tu",
    "comment allez vous",
    "tu vas bien",
}
_THANKS = {"merci", "merci beaucoup", "merci bien", "thanks", "thank you"}
_BYE = {"au revoir", "aurevoir", "a bientot", "bonne continuation", "bye", "bonne fin de journee"}

_GREETING_REPLY = (
    "Bonjour. Je suis l'assistant ZolaOS. Posez-moi une question précise "
    "(droit, fiscalité, procédures, RH…) et j'y répondrai en m'appuyant sur les "
    "textes du corpus, sources à l'appui."
)
_THANKS_REPLY = "Je vous en prie. N'hésitez pas si vous avez une autre question."
_BYE_REPLY = "Au revoir, et à bientôt sur ZolaOS."


def smalltalk_reply(query: str) -> str | None:
    """Réponse conversationnelle si la requête est une pure salutation / remerciement
    / au revoir ; sinon ``None`` (la requête suit le pipeline normal)."""
    payload = _normalize(_payload(query))
    if not payload:
        return None
    if payload in _GREETINGS:
        return _GREETING_REPLY
    if payload in _THANKS:
        return _THANKS_REPLY
    if payload in _BYE:
        return _BYE_REPLY
    return None
