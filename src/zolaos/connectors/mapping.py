"""Mapping déclaratif YAML pour le Connector Framework (V2.2 §2.4).

Principe imposé : `employee.full_name → person.nom_complet` **sans code**. Un
fichier YAML décrit, pour une entité, comment chaque champ canonique ZolaOS est
alimenté depuis un champ source (chemin pointé) + transformation optionnelle.

Exemple :

    entity: employee
    country_default: cg
    fields:
      nom_complet:     { from: full_name }
      poste:           { from: job.title }
      email:           { from: contact.email }
      salaire_base_xaf: { from: salary, transform: to_decimal }
      id_externe:      { from: id }

Application : `FieldMapping.apply(record)` produit un dict canonique prêt à
instancier le modèle correspondant (`Employee(**mapping.apply(row))`).
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from datetime import date
from decimal import Decimal, InvalidOperation
from pathlib import Path
from typing import Any

import yaml

from zolaos.core.logging import get_logger

_log = get_logger("zolaos.connectors.mapping")


class MappingError(ValueError):
    """Configuration de mapping invalide ou transformation impossible."""


def _to_decimal(v: Any) -> Decimal | None:
    if v is None or v == "":
        return None
    try:
        return Decimal(str(v).replace(" ", "").replace(",", "."))
    except (InvalidOperation, ValueError) as exc:
        raise MappingError(f"to_decimal: valeur non numérique {v!r}") from exc


def _to_int(v: Any) -> int | None:
    if v is None or v == "":
        return None
    try:
        return int(str(v).strip())
    except ValueError as exc:
        raise MappingError(f"to_int: valeur non entière {v!r}") from exc


def _to_date(v: Any) -> date | None:
    if v is None or v == "":
        return None
    if isinstance(v, date):
        return v
    try:
        return date.fromisoformat(str(v).strip()[:10])
    except ValueError as exc:
        raise MappingError(f"to_date: format ISO attendu, reçu {v!r}") from exc


def _to_bool(v: Any) -> bool | None:
    if v is None or v == "":
        return None
    if isinstance(v, bool):
        return v
    return str(v).strip().lower() in {"1", "true", "vrai", "oui", "yes", "y", "x"}


# Registre de transformations autorisées (allowlist — pas d'eval de code).
_TRANSFORMS: dict[str, Callable[[Any], Any]] = {
    "strip": lambda v: v.strip() if isinstance(v, str) else v,
    "upper": lambda v: v.upper() if isinstance(v, str) else v,
    "lower": lambda v: v.lower() if isinstance(v, str) else v,
    "to_decimal": _to_decimal,
    "to_int": _to_int,
    "to_date": _to_date,
    "to_bool": _to_bool,
}


@dataclass(frozen=True)
class FieldRule:
    """Règle d'alimentation d'un champ canonique."""

    source: str  # chemin pointé dans l'enregistrement source
    transform: str | None = None
    default: Any = None


class FieldMapping:
    """Mapping déclaratif source → canonique pour une entité."""

    def __init__(
        self,
        *,
        entity: str,
        fields: dict[str, FieldRule],
        country_default: str = "cg",
    ) -> None:
        self.entity = entity
        self.fields = fields
        self.country_default = country_default
        for name, rule in fields.items():
            if rule.transform is not None and rule.transform not in _TRANSFORMS:
                raise MappingError(
                    f"Transformation inconnue {rule.transform!r} pour le champ {name!r}. "
                    f"Autorisées : {sorted(_TRANSFORMS)}"
                )

    # -- chargement -----------------------------------------------------------

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> FieldMapping:
        if "entity" not in data or "fields" not in data:
            raise MappingError("Mapping invalide : clés 'entity' et 'fields' obligatoires.")
        fields: dict[str, FieldRule] = {}
        for name, spec in data["fields"].items():
            if isinstance(spec, str):
                fields[name] = FieldRule(source=spec)
            elif isinstance(spec, dict):
                if "from" not in spec:
                    raise MappingError(f"Champ {name!r} : clé 'from' obligatoire.")
                fields[name] = FieldRule(
                    source=spec["from"],
                    transform=spec.get("transform"),
                    default=spec.get("default"),
                )
            else:
                raise MappingError(f"Champ {name!r} : spec invalide ({type(spec)!r}).")
        return cls(
            entity=data["entity"],
            fields=fields,
            country_default=data.get("country_default", "cg"),
        )

    @classmethod
    def from_yaml(cls, path: str | Path) -> FieldMapping:
        p = Path(path)
        if not p.is_file():
            raise MappingError(f"Fichier de mapping introuvable : {p}")
        data = yaml.safe_load(p.read_text(encoding="utf-8"))
        return cls.from_dict(data)

    # -- application ----------------------------------------------------------

    @staticmethod
    def _dotted_get(record: dict[str, Any], path: str) -> Any:
        cur: Any = record
        for part in path.split("."):
            if isinstance(cur, dict) and part in cur:
                cur = cur[part]
            else:
                return None
        return cur

    def apply(self, record: dict[str, Any]) -> dict[str, Any]:
        """Traduit un enregistrement source en dict canonique."""
        out: dict[str, Any] = {}
        for name, rule in self.fields.items():
            value = self._dotted_get(record, rule.source)
            if value is None:
                value = rule.default
            if value is not None and rule.transform is not None:
                value = _TRANSFORMS[rule.transform](value)
            if value is not None:
                out[name] = value
        out.setdefault("country", self.country_default)
        return out
