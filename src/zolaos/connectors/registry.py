"""Registre + fabrique de connecteurs (V2.2 §2.4).

Instanciation **déclarative** d'un connecteur depuis une configuration (YAML/JSON
ou dict) : type, config, auth, mapping. Les connecteurs intégrés sont enregistrés
en import paresseux (on n'importe httpx/sqlalchemy que si le connecteur est utilisé).

Exemple de spec :
    {
      "type": "generic_rest",
      "config": {"base_url": "https://erp.client.cg/api", "endpoints": {...}},
      "auth": {"type": "api_key", "key": "secret", "header_name": "X-API-Key"},
      "mapping": "src/zolaos/connectors/mappings/example_employee.yaml"
    }

    conn = create_connector(spec)
    async with conn:
        employes = await conn.list_employees()

Un connecteur maison (SDK custom) s'enregistre via `register_connector("mon_erp",
MonErpConnector)` puis devient instanciable par `type: "mon_erp"`.
"""

from __future__ import annotations

import importlib
from typing import Any

from pydantic import SecretStr

from zolaos.connectors.auth import (
    ApiKeyAuth,
    AuthStrategy,
    BasicAuth,
    CertificateAuth,
    NoAuth,
    OAuth2Auth,
)
from zolaos.connectors.base import BaseConnector, ConnectorConfigError
from zolaos.connectors.mapping import FieldMapping
from zolaos.core.logging import get_logger

_log = get_logger("zolaos.connectors.registry")

# Connecteurs intégrés (import paresseux "module:Classe").
_BUILTIN: dict[str, str] = {
    "csv_excel": "zolaos.connectors.csv_excel:CsvExcelConnector",
    "generic_rest": "zolaos.connectors.generic_rest:GenericRestConnector",
    "generic_sql": "zolaos.connectors.generic_sql:GenericSqlConnector",
    "generic_soap": "zolaos.connectors.generic_soap:GenericSoapConnector",
    "webhook": "zolaos.connectors.webhook:WebhookConnector",
    "odoo": "zolaos.connectors.odoo:OdooConnector",
    "erpnext": "zolaos.connectors.erpnext:ErpNextConnector",
    "sage": "zolaos.connectors.sage:SageConnector",
}


class ConnectorRegistry:
    """Registre de types de connecteurs + fabrique déclarative."""

    def __init__(self) -> None:
        self._lazy: dict[str, str] = dict(_BUILTIN)
        self._classes: dict[str, type[BaseConnector]] = {}

    # -- enregistrement -------------------------------------------------------

    def register(self, name: str, cls: type[BaseConnector]) -> None:
        if not issubclass(cls, BaseConnector):
            raise ConnectorConfigError(f"{cls!r} n'est pas un BaseConnector.")
        self._classes[name] = cls
        _log.info("connectors.registry.registered", type=name, cls=cls.__name__)

    def available(self) -> list[str]:
        return sorted(set(self._lazy) | set(self._classes))

    def resolve(self, name: str) -> type[BaseConnector]:
        if name in self._classes:
            return self._classes[name]
        if name in self._lazy:
            module_path, _, cls_name = self._lazy[name].partition(":")
            cls = getattr(importlib.import_module(module_path), cls_name)
            self._classes[name] = cls
            return cls
        raise ConnectorConfigError(
            f"Type de connecteur inconnu: {name!r}. Disponibles: {self.available()}"
        )

    # -- fabriques auth / mapping --------------------------------------------

    @staticmethod
    def build_auth(spec: dict[str, Any] | None) -> AuthStrategy:
        if not spec:
            return NoAuth()
        kind = spec.get("type", "none")
        if kind == "none":
            return NoAuth()
        if kind == "api_key":
            return ApiKeyAuth(
                SecretStr(spec["key"]), header_name=spec.get("header_name", "X-API-Key")
            )
        if kind == "basic":
            return BasicAuth(spec["username"], SecretStr(spec["password"]))
        if kind == "oauth2":
            return OAuth2Auth(
                token_url=spec["token_url"],
                client_id=spec["client_id"],
                client_secret=SecretStr(spec["client_secret"]),
                scope=spec.get("scope"),
            )
        if kind == "certificate":
            return CertificateAuth(spec["cert_path"], spec.get("key_path"))
        raise ConnectorConfigError(f"Type d'auth inconnu: {kind!r}")

    @staticmethod
    def build_mapping(spec: str | dict[str, Any] | None) -> FieldMapping | None:
        if spec is None:
            return None
        if isinstance(spec, str):
            return FieldMapping.from_yaml(spec)
        if isinstance(spec, dict):
            return FieldMapping.from_dict(spec)
        raise ConnectorConfigError(f"Spec de mapping invalide: {type(spec)!r}")

    # -- fabrique connecteur --------------------------------------------------

    def create(self, spec: dict[str, Any]) -> BaseConnector:
        if "type" not in spec:
            raise ConnectorConfigError("Spec connecteur invalide : clé 'type' obligatoire.")
        cls = self.resolve(spec["type"])
        config = dict(spec.get("config", {}))
        # Injecte le timeout par défaut global si la config ne le précise pas.
        if "timeout_seconds" not in config:
            try:
                from zolaos.core.settings import get_settings

                config["timeout_seconds"] = get_settings().CONNECTOR_DEFAULT_TIMEOUT_SECONDS
            except Exception:  # noqa: S110 — réglage best-effort, fallback silencieux acceptable
                pass
        return cls(
            config=config,
            auth=self.build_auth(spec.get("auth")),
            mapping=self.build_mapping(spec.get("mapping")),
        )


# Instance globale + helpers de commodité.
_REGISTRY = ConnectorRegistry()


def register_connector(name: str, cls: type[BaseConnector]) -> None:
    _REGISTRY.register(name, cls)


def create_connector(spec: dict[str, Any]) -> BaseConnector:
    return _REGISTRY.create(spec)


def available_connectors() -> list[str]:
    return _REGISTRY.available()


def get_registry() -> ConnectorRegistry:
    return _REGISTRY
