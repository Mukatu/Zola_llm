"""Connecteur d'entrée par webhook (V2.2 §2.4 — livré en standard).

Réception d'événements poussés par un système tiers (au lieu d'aller les
chercher). Sécurité d'entrée : IP allowlist optionnelle + vérification de
signature HMAC-SHA256 optionnelle. Normalisation via mapping déclaratif.

Contrairement aux autres connecteurs (sortants), celui-ci est **entrant** : il
n'expose pas `list_*` mais `ingest()`. Il s'intègre derrière une route FastAPI.

Config attendue :
    {
      "secret": SecretStr("..."),         # clé HMAC partagée (optionnel)
      "signature_header": "X-Signature",  # en-tête portant la signature hex
      "allowlist": ["10.0.0.0/8"],        # IP/plages autorisées (optionnel)
      "entity": "invoice"                  # entité canonique cible
    }
"""

from __future__ import annotations

import hashlib
import hmac
import json
from typing import Any

from pydantic import SecretStr

from zolaos.connectors.auth import IPAllowlist
from zolaos.connectors.base import BaseConnector, ConnectorAuthError, ConnectorConfigError
from zolaos.connectors.models import BankTransaction, Employee, Invoice
from zolaos.core.logging import get_logger

_log = get_logger("zolaos.connectors.webhook")

_ENTITY_MODELS = {
    "employee": Employee,
    "invoice": Invoice,
    "bank_transaction": BankTransaction,
}


class WebhookConnector(BaseConnector):
    """Connecteur entrant : valide + normalise un événement webhook."""

    name = "webhook"

    def __init__(self, **kwargs: Any) -> None:
        super().__init__(**kwargs)
        allow = self.config.get("allowlist")
        self._allowlist = IPAllowlist(allow) if allow else None

    # -- sécurité d'entrée ----------------------------------------------------

    def check_ip(self, ip: str | None) -> None:
        if self._allowlist is None:
            return
        if ip is None or not self._allowlist.is_allowed(ip):
            raise ConnectorAuthError(f"IP non autorisée: {ip!r}")

    def verify_signature(self, body: bytes, signature: str | None) -> None:
        secret = self.config.get("secret")
        if secret is None:
            return  # pas de vérification configurée
        raw = secret.get_secret_value() if isinstance(secret, SecretStr) else str(secret)
        expected = hmac.new(raw.encode(), body, hashlib.sha256).hexdigest()
        if signature is None or not hmac.compare_digest(expected, signature.strip().lower()):
            raise ConnectorAuthError("Signature webhook invalide.")

    # -- ingestion ------------------------------------------------------------

    def ingest(
        self,
        *,
        body: bytes,
        signature: str | None = None,
        ip: str | None = None,
    ):  # type: ignore[no-untyped-def]
        """Valide (IP + signature), parse, normalise → modèle canonique."""
        self.check_ip(ip)
        self.verify_signature(body, signature)
        try:
            payload = json.loads(body.decode("utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError) as exc:
            raise ConnectorConfigError(f"Payload webhook non-JSON: {exc}") from exc

        entity = self.config.get("entity")
        if entity not in _ENTITY_MODELS:
            raise ConnectorConfigError(
                f"config['entity'] invalide ({entity!r}); attendu: {sorted(_ENTITY_MODELS)}"
            )
        canonical = self.mapping.apply(payload) if self.mapping is not None else payload
        model = _ENTITY_MODELS[entity](**canonical)
        _log.info("connector.webhook.ingested", connector=self.name, entity=entity)
        return model
