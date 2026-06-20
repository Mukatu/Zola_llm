"""Métriques Prometheus exposées par l'application.

Toutes les métriques sont préfixées `zolaos_*`.
"""

from __future__ import annotations

from prometheus_client import Counter, Gauge, Histogram

# ===== HTTP =====
HTTP_REQUESTS_TOTAL = Counter(
    "zolaos_http_requests_total",
    "Nombre total de requêtes HTTP.",
    labelnames=("method", "path", "status"),
)

HTTP_REQUEST_DURATION_SECONDS = Histogram(
    "zolaos_http_request_duration_seconds",
    "Latence des requêtes HTTP (secondes).",
    labelnames=("method", "path"),
    buckets=(0.005, 0.01, 0.025, 0.05, 0.1, 0.25, 0.5, 1.0, 2.5, 5.0, 10.0),
)

# ===== LLM =====
LLM_CALLS_TOTAL = Counter(
    "zolaos_llm_calls_total",
    "Nombre total d'appels LLM.",
    labelnames=("provider", "model", "outcome"),  # provider=ollama|external
)

LLM_CALL_DURATION_SECONDS = Histogram(
    "zolaos_llm_call_duration_seconds",
    "Latence des appels LLM (secondes).",
    labelnames=("provider", "model"),
    buckets=(0.1, 0.25, 0.5, 1.0, 2.5, 5.0, 10.0, 30.0, 60.0, 120.0),
)

# ===== Garde-fou anti-fallback =====
EXTERNAL_FALLBACK_BLOCKED_TOTAL = Counter(
    "zolaos_external_fallback_blocked_total",
    "Nombre de tentatives d'appel externe bloquées par le garde-fou.",
    labelnames=("reason",),
)

EXTERNAL_FALLBACK_ENABLED = Gauge(
    "zolaos_external_fallback_enabled",
    "Indique si le fallback API externe est activé (1) ou désactivé (0).",
)

# ===== Agents =====
AGENT_INVOCATIONS_TOTAL = Counter(
    "zolaos_agent_invocations_total",
    "Nombre d'invocations de sous-agents.",
    labelnames=("agent", "outcome"),
)

# ===== RAG =====
RAG_QUERIES_TOTAL = Counter(
    "zolaos_rag_queries_total",
    "Nombre de recherches vectorielles.",
    labelnames=("schema", "country"),
)

# ===== Connector Framework =====
CONNECTOR_CALLS_TOTAL = Counter(
    "zolaos_connector_calls_total",
    "Nombre d'opérations de connecteurs externes.",
    labelnames=("connector", "operation", "outcome"),
)

CONNECTOR_CALL_DURATION_SECONDS = Histogram(
    "zolaos_connector_call_duration_seconds",
    "Latence des opérations de connecteurs (secondes).",
    labelnames=("connector", "operation"),
    buckets=(0.01, 0.05, 0.1, 0.25, 0.5, 1.0, 2.5, 5.0, 10.0, 30.0),
)
