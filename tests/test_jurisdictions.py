"""Tests — packs juridiction (L1.4) : résolution hybride + registre + endpoint.

Pas de DB/Redis : le router est monté sur une `FastAPI()` minimale et
`authenticate` est overridé directement (comme documenté dans
`current_jurisdiction`, qui ne dépend que du principal + des settings).
"""

from __future__ import annotations

import uuid
from collections.abc import Iterator

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from zolaos.api.auth import Principal, authenticate
from zolaos.api.v1.jurisdictions import router as jurisdictions_router
from zolaos.core.jurisdictions import (
    JurisdictionError,
    JurisdictionPack,
    UnknownJurisdictionError,
    load_packs,
    resolve_jurisdiction,
)
from zolaos.core.settings import Settings, get_settings

_PACKS = {
    "cg": JurisdictionPack(
        country="cg",
        label="République du Congo",
        corpus_country_tags=["country:cg", "country:cemac"],
        enabled_poles=["legal", "erp", "general"],
    ),
    "cd": JurisdictionPack(
        country="cd",
        label="RDC (pack minimal)",
        corpus_country_tags=[],
        enabled_poles=[],
    ),
}


# --- resolve_jurisdiction : précédence hybride ------------------------------


def test_resolve_prefers_requested_when_known() -> None:
    pack = resolve_jurisdiction(requested="cd", principal_country="cg", default="cg", packs=_PACKS)
    assert pack.country == "cd"


def test_resolve_falls_back_to_principal_when_no_request() -> None:
    pack = resolve_jurisdiction(requested=None, principal_country="cd", default="cg", packs=_PACKS)
    assert pack.country == "cd"


def test_resolve_falls_back_to_default_when_neither_request_nor_principal() -> None:
    pack = resolve_jurisdiction(requested=None, principal_country=None, default="cg", packs=_PACKS)
    assert pack.country == "cg"


def test_resolve_degrades_gracefully_when_principal_country_unknown() -> None:
    """Un pays de principal pas encore packagé ne casse pas la requête : repli défaut."""
    pack = resolve_jurisdiction(requested=None, principal_country="zz", default="cg", packs=_PACKS)
    assert pack.country == "cg"


def test_resolve_requested_unknown_raises_clear_error_no_silent_fallback() -> None:
    """Une surcharge explicite inconnue échoue — pas de repli silencieux sur principal/défaut."""
    with pytest.raises(UnknownJurisdictionError, match="zz"):
        resolve_jurisdiction(requested="zz", principal_country="cg", default="cg", packs=_PACKS)


def test_resolve_is_case_insensitive() -> None:
    pack = resolve_jurisdiction(requested="CG", principal_country=None, default="cg", packs=_PACKS)
    assert pack.country == "cg"


def test_resolve_unknown_default_raises() -> None:
    with pytest.raises(UnknownJurisdictionError):
        resolve_jurisdiction(requested=None, principal_country=None, default="zz", packs=_PACKS)


# --- registre YAML -----------------------------------------------------------


def test_load_packs_reads_repo_registry() -> None:
    """Le registre `config/jurisdictions.yaml` du repo charge bien le pack cg."""
    packs = load_packs()
    assert "cg" in packs
    cg = packs["cg"]
    assert cg.label == "République du Congo"
    assert "country:cg" in cg.corpus_country_tags
    assert "country:cemac" in cg.corpus_country_tags
    assert "legal" in cg.enabled_poles


def test_load_packs_second_pack_is_extensible_but_no_corpus_claimed() -> None:
    """Le 2e pack (cd) prouve l'extensibilité sans prétendre à un corpus existant."""
    packs = load_packs()
    assert "cd" in packs
    assert packs["cd"].corpus_country_tags == []


def test_load_packs_missing_file_raises(tmp_path) -> None:  # type: ignore[no-untyped-def]
    with pytest.raises(JurisdictionError):
        load_packs(tmp_path / "does_not_exist.yaml")


def test_load_packs_invalid_registry_raises(tmp_path) -> None:  # type: ignore[no-untyped-def]
    bad = tmp_path / "bad.yaml"
    bad.write_text("not_packs_key: {}", encoding="utf-8")
    with pytest.raises(JurisdictionError):
        load_packs(bad)


# --- endpoint /v1/jurisdictions (montage minimal, sans DB/Redis) ------------

_TEST_PRINCIPAL_CG = Principal(
    user_id=uuid.UUID(int=1),
    email="test@zolaos.test",
    tenant_id="local",
    country="cg",
    auth_method="jwt",
)


@pytest.fixture
def minimal_app() -> FastAPI:
    app = FastAPI()
    app.include_router(jurisdictions_router)
    app.dependency_overrides[authenticate] = lambda: _TEST_PRINCIPAL_CG
    app.dependency_overrides[get_settings] = lambda: Settings(
        POSTGRES_PASSWORD_APP="x",
        POSTGRES_PASSWORD_MIGRATIONS="x",
        JWT_SECRET="x" * 32,
    )
    return app


@pytest.fixture
def minimal_client(minimal_app: FastAPI) -> Iterator[TestClient]:
    with TestClient(minimal_app) as c:
        yield c


def test_list_endpoint_returns_catalog(minimal_client: TestClient) -> None:
    resp = minimal_client.get("/v1/jurisdictions")
    assert resp.status_code == 200
    countries = {p["country"] for p in resp.json()["packs"]}
    assert "cg" in countries


def test_current_endpoint_defaults_to_principal_country(minimal_client: TestClient) -> None:
    resp = minimal_client.get("/v1/jurisdictions/current")
    assert resp.status_code == 200
    assert resp.json()["country"] == "cg"


def test_current_endpoint_query_override_unknown_country_is_400(
    minimal_client: TestClient,
) -> None:
    resp = minimal_client.get("/v1/jurisdictions/current", params={"country": "zz"})
    assert resp.status_code == 400


def test_current_endpoint_header_override_prevails(minimal_client: TestClient) -> None:
    """Le header X-Country prime sur ?country= (cf. docstring `current_jurisdiction`)."""
    resp = minimal_client.get(
        "/v1/jurisdictions/current",
        params={"country": "cg"},
        headers={"X-Country": "cd"},
    )
    assert resp.status_code == 200
    assert resp.json()["country"] == "cd"
