"""Anonymisation d'un candidat de contribution — **avant** franchissement (I2).

Réutilise la rédaction PII générique (e-mails, téléphones, IBAN, cartes, montants,
noms). C'est le point unique où l'on garantit que rien d'identifiant ne sort.
"""

from __future__ import annotations

import hashlib
import json
from typing import Any

from zolaos.security.pii import PIIRedactionPolicy, redact_text


def anonymize(text: str) -> str:
    """Anonymise un texte (identifiants + montants + noms) via la rédaction générique."""
    if not text or not text.strip():
        return ""
    redige, _ = redact_text(text, PIIRedactionPolicy.GENERIC)
    return redige.strip()


def content_hash(payload: dict[str, Any]) -> str:
    """Empreinte stable du contenu assaini (déduplication + compteur k-anonymat, I3)."""
    blob = json.dumps(payload, sort_keys=True, ensure_ascii=False)
    return hashlib.sha256(blob.encode("utf-8")).hexdigest()
