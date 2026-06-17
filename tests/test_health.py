"""Tests de l'endpoint /health et /metrics."""

from __future__ import annotations

from fastapi.testclient import TestClient


def test_health_returns_ok(client: TestClient) -> None:
    response = client.get("/health")
    assert response.status_code == 200
    payload = response.json()
    assert payload["status"] == "ok"
    assert payload["country"] == "cg"
    assert payload["external_fallback_enabled"] is False


def test_metrics_endpoint_exposes_prometheus_format(client: TestClient) -> None:
    response = client.get("/metrics")
    assert response.status_code == 200
    assert "text/plain" in response.headers["content-type"]
    # Au moins une métrique zolaos_ doit être présente après une requête.
    client.get("/health")
    response = client.get("/metrics")
    body = response.text
    assert "zolaos_http_requests_total" in body
    assert "zolaos_external_fallback_enabled" in body
