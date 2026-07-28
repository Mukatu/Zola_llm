"""Test simple de l'endpoint /v1/agents (catalogue déclaratif, pas d'LLM)."""

from __future__ import annotations

from fastapi.testclient import TestClient


def test_agents_catalog_lists_all_pole(client: TestClient) -> None:
    response = client.get("/v1/agents")
    assert response.status_code == 200
    data = response.json()
    poles = {a["pole"] for a in data["agents"]}
    assert poles == {
        "general",
        "health",
        "legal",
        "engineering",
        "erp",
        "grc",
        "fintech",
        "cyber",
    }
    # Activés : "general" (assistance) + "engineering" (assistant code souverain on-box).
    enabled = {a["pole"] for a in data["agents"] if a["enabled"]}
    assert enabled == {"general", "engineering"}
