"""Tests de l'endpoint /v1/config (GET/PUT personnalisation) via TestClient."""

from __future__ import annotations


def test_get_default_config(client) -> None:  # type: ignore[no-untyped-def]
    r = client.get("/v1/config")
    assert r.status_code == 200
    assert r.json()["profil"] == "box"


def test_put_then_get_persists(client) -> None:  # type: ignore[no-untyped-def]
    upd = {
        "tenant_id": "t-test",
        "modules_actifs": ["sante.pharmacology", "erp.compta"],
        "branding": {"nom_affichage": "Clinique X", "couleur_primaire": "#00AA55"},
        "locale": "fr",
    }
    r = client.put("/v1/config", json=upd)
    assert r.status_code == 200
    body = r.json()
    assert body["branding"]["nom_affichage"] == "Clinique X"
    assert set(body["modules_actifs"]) == {"sante.pharmacology", "erp.compta"}
    # Persisté : un GET avec le même tenant retourne les overrides
    r2 = client.get("/v1/config", params={"tenant_id": "t-test"})
    assert r2.json()["branding"]["couleur_primaire"] == "#00AA55"


def test_put_unknown_module_rejected(client) -> None:  # type: ignore[no-untyped-def]
    r = client.put("/v1/config", json={"tenant_id": "t2", "modules_actifs": ["pole.inexistant"]})
    assert r.status_code == 422
