"""Test endpoint Marketing déterministe (/v1/mkt/audience) via TestClient."""

from __future__ import annotations


def test_mkt_audience_consent(client) -> None:  # type: ignore[no-untyped-def]
    payload = {
        "finalite": "promotions",
        "contacts": [
            {
                "id_externe": "C1",
                "nom": "Awa",
                "consentement_marketing": True,
                "finalites": ["promotions"],
            },
            {"id_externe": "C2", "nom": "Paul", "consentement_marketing": False, "finalites": []},
            {
                "id_externe": "C3",
                "nom": "Sylvie",
                "consentement_marketing": True,
                "finalites": ["newsletter"],
            },
        ],
    }
    r = client.post("/v1/mkt/audience", json=payload)
    assert r.status_code == 200
    body = r.json()
    assert body["consent"]["eligibles"] == 1  # seul C1 consent à 'promotions'
    assert body["consent"]["exclus"] == 2
    assert "segments" in body
