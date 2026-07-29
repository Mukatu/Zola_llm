"""Tests de l'endpoint /v1/config (GET/PUT personnalisation) via TestClient."""

from __future__ import annotations


def test_get_default_config(client) -> None:  # type: ignore[no-untyped-def]
    r = client.get("/v1/config")
    assert r.status_code == 200
    assert r.json()["profil"] == "box"


def test_put_persists_personalization_not_modules(client) -> None:  # type: ignore[no-untyped-def]
    # Le client personnalise branding/langue…
    upd = {
        "tenant_id": "t-test",
        "modules_actifs": ["sante.pharmacology", "erp.compta"],  # tentative d'auto-octroi
        "branding": {"nom_affichage": "Clinique X", "couleur_primaire": "#00AA55"},
        "locale": "fr",
    }
    r = client.put("/v1/config", json=upd)
    assert r.status_code == 200
    body = r.json()
    assert body["branding"]["nom_affichage"] == "Clinique X"
    # …mais NE PEUT PAS s'octroyer de modules : `modules_actifs` envoyé est IGNORÉ
    # (champ retiré de ConfigUpdate — la distribution est un entitlement Polaris).
    assert set(body["modules_actifs"]) != {"sante.pharmacology", "erp.compta"}
    # Persisté : un GET avec le même tenant retourne les overrides de personnalisation.
    r2 = client.get("/v1/config", params={"tenant_id": "t-test"})
    assert r2.json()["branding"]["couleur_primaire"] == "#00AA55"


def test_client_cannot_grant_modules_via_config(client) -> None:  # type: ignore[no-untyped-def]
    # L'ancien trou (« lamentable ») : le client réglait ses propres modules.
    # Désormais impossible — le champ n'existe plus, la valeur est sans effet.
    before = set(client.get("/v1/config", params={"tenant_id": "t3"}).json()["modules_actifs"])
    r = client.put("/v1/config", json={"tenant_id": "t3", "modules_actifs": ["cyber.defense"]})
    assert r.status_code == 200
    after = set(r.json()["modules_actifs"])
    assert "cyber.defense" not in after  # le client ne s'est rien octroyé
    assert after == before  # inchangé
