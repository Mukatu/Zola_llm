"""Packs juridiction (L1.4) — « ajouter un pays = ajouter un pack, pas du code ».

Un **pack** déclare, pour un pays, le label affichable, les tags de corpus RAG
qui le concernent (`corpus_country_tags`, ex. `country:cg` + `country:cemac`
pour la République du Congo — CEMAC/OHADA couvrent plusieurs pays) et les
pôles activés pour ce pays (`enabled_poles`). Le registre est déclaratif
(YAML package-relatif `src/zolaos/core/jurisdictions.yaml`, surchargeable par
`ZOLAOS_JURISDICTIONS_PATH`) : ajouter un pays ne touche PAS ce module ni
l'orchestrateur, seulement le fichier.

Sélection **hybride (décision produit actée)** : surcharge de requête (header
`X-Country` ou `?country=`) > pays du principal authentifié (tenant) >
`Settings.DEFAULT_COUNTRY`. La surcharge de requête est un choix EXPLICITE de
l'appelant : un pays inconnu y échoue immédiatement (400), sans repli
silencieux — c'est le seul endroit où un typo utilisateur doit être signalé.
Le pays du principal, lui, dérive du système (tenant enregistré) : s'il ne
correspond à aucun pack connu (pack pas encore déclaré pour ce pays), on
dégrade gracieusement vers le défaut plutôt que de faire échouer la requête
d'un tenant existant.

**Portée de ce lot (L1.4)** : l'abstraction pack + la sélection hybride.
**SUIVI (L1.4b), non inclus ici** : l'injection effective de
`corpus_country_tags` dans le retrieval (rendre les agents/le RAG conscients
du pack résolu, pour filtrer/prioriser le corpus par pays). Ce module reste
donc non-invasif : il ne modifie aucun comportement existant tant que rien
n'appelle `current_jurisdiction()`.
"""

from __future__ import annotations

import os
from functools import lru_cache
from pathlib import Path

import yaml
from fastapi import Depends, Header, HTTPException, Query, status
from pydantic import BaseModel, Field

from zolaos.api.auth import Principal, authenticate
from zolaos.core.logging import get_logger
from zolaos.core.settings import Settings, get_settings

_log = get_logger("zolaos.core.jurisdictions")

_ENV_VAR = "ZOLAOS_JURISDICTIONS_PATH"


class JurisdictionError(ValueError):
    """Erreur de configuration ou de résolution de juridiction."""


class UnknownJurisdictionError(JurisdictionError):
    """Le pays demandé/résolu ne correspond à aucun pack déclaré."""


class JurisdictionPack(BaseModel):
    """Pack pays : corpus + pôles activés pour une juridiction donnée."""

    country: str = Field(pattern=r"^[a-z]{2}$")
    label: str
    corpus_country_tags: list[str] = Field(default_factory=list)
    enabled_poles: list[str] = Field(default_factory=list)


def _default_path() -> Path:
    """Résout le chemin du registre : env var, sinon le YAML **package-relatif**
    (livré avec le code, toujours monté/embarqué — comme `zolaos.agents._prompts`).

    NB : le fichier vit à côté de ce module (`src/zolaos/core/jurisdictions.yaml`)
    et NON à la racine du repo, pour rester disponible en conteneur (montage
    sélectif de `src/`) et dans le wheel."""
    if env := os.environ.get(_ENV_VAR):
        return Path(env)
    return Path(__file__).resolve().parent / "jurisdictions.yaml"


def _parse_packs(raw: dict) -> dict[str, JurisdictionPack]:
    entries = raw.get("packs") if isinstance(raw, dict) else None
    if not isinstance(entries, dict) or not entries:
        raise JurisdictionError(
            "Registre de juridictions invalide : clé racine 'packs' (mapping non vide) attendue."
        )
    packs: dict[str, JurisdictionPack] = {}
    for key, spec in entries.items():
        if not isinstance(spec, dict):
            raise JurisdictionError(f"Pack {key!r} : spec invalide ({type(spec)!r}).")
        pack = JurisdictionPack.model_validate(spec)
        packs[pack.country] = pack
    return packs


@lru_cache(maxsize=8)
def _load_packs_cached(path_str: str) -> dict[str, JurisdictionPack]:
    p = Path(path_str)
    if not p.is_file():
        raise JurisdictionError(f"Registre de juridictions introuvable : {p}")
    raw = yaml.safe_load(p.read_text(encoding="utf-8"))
    packs = _parse_packs(raw)
    _log.info("jurisdictions.loaded", path=str(p), countries=sorted(packs))
    return packs


def load_packs(path: str | Path | None = None) -> dict[str, JurisdictionPack]:
    """Charge (et cache) le registre de packs, indexé par code pays.

    `path=None` résout le chemin par défaut (env `ZOLAOS_JURISDICTIONS_PATH`
    sinon `config/jurisdictions.yaml`). Le cache est indexé par chemin
    résolu — appeler avec un chemin explicite (tests) contourne le cache du
    chemin par défaut sans le polluer.
    """
    resolved = Path(path) if path is not None else _default_path()
    return _load_packs_cached(str(resolved))


def resolve_jurisdiction(
    *,
    requested: str | None,
    principal_country: str | None,
    default: str,
    packs: dict[str, JurisdictionPack] | None = None,
) -> JurisdictionPack:
    """Résout le pack applicable — sélection hybride (c), PURE (sans FastAPI).

    Précédence :
    1. ``requested`` (surcharge explicite de l'appelant) : si fourni, DOIT être
       un pack connu — sinon `UnknownJurisdictionError` immédiate (pas de
       repli silencieux sur un choix explicite, potentiellement un typo).
    2. ``principal_country`` (dérivé du tenant authentifié) : utilisé s'il
       correspond à un pack connu ; sinon dégradation gracieuse vers l'étape
       suivante (un pays de principal pas encore packagé ne doit pas casser
       la requête d'un tenant existant).
    3. ``default`` (`Settings.DEFAULT_COUNTRY`) : doit correspondre à un pack
       connu, sinon `UnknownJurisdictionError` (erreur de configuration).
    """
    registry = packs if packs is not None else load_packs()

    if requested:
        key = requested.strip().lower()
        if key not in registry:
            raise UnknownJurisdictionError(
                f"pays demandé inconnu : {requested!r}. Packs disponibles : {sorted(registry)}."
            )
        return registry[key]

    if principal_country:
        key = principal_country.strip().lower()
        if key in registry:
            return registry[key]

    key = default.strip().lower()
    if key not in registry:
        raise UnknownJurisdictionError(
            f"aucun pack pour le pays par défaut {default!r}. "
            f"Packs disponibles : {sorted(registry)}."
        )
    return registry[key]


async def current_jurisdiction(
    x_country: str | None = Header(default=None, alias="X-Country"),
    country: str | None = Query(
        default=None, description="Surcharge du pack pays (X-Country prime)"
    ),
    principal: Principal = Depends(authenticate),
    settings: Settings = Depends(get_settings),
) -> JurisdictionPack:
    """Dépendance FastAPI : pack résolu pour l'appelant courant.

    Lit la surcharge de requête (header `X-Country` prioritaire sur `?country=`),
    le pays du principal authentifié (`DEFAULT_COUNTRY` en repli si le
    principal n'en porte pas), et applique `resolve_jurisdiction`. Une
    surcharge inconnue lève 400 (validation explicite, cf. docstring module).
    """
    requested = x_country or country
    principal_country = getattr(principal, "country", None) or settings.DEFAULT_COUNTRY
    try:
        return resolve_jurisdiction(
            requested=requested,
            principal_country=principal_country,
            default=settings.DEFAULT_COUNTRY,
        )
    except UnknownJurisdictionError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
