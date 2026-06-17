"""Garde-fou anti-fallback API externe.

Tant que `ENABLE_EXTERNAL_FALLBACK=false`, **aucun** appel sortant LLM ne doit
être effectué. Ce garde-fou est testé en CI et instrumenté via Prometheus.
"""

from __future__ import annotations

from zolaos.core.metrics import EXTERNAL_FALLBACK_BLOCKED_TOTAL
from zolaos.core.settings import Settings


class ExternalFallbackDisabledError(RuntimeError):
    """Levée quand un appel externe est tenté alors que le flag est OFF."""


def ensure_external_fallback_allowed(settings: Settings, *, caller: str) -> None:
    """Vérifie que le flag autorise un appel externe. Sinon, lève et incrémente la métrique.

    À appeler **avant** toute initialisation de client externe ou tout `await
    client.messages.create(...)`. Le garde-fou est volontairement placé en amont
    pour qu'aucune requête réseau ne parte si le flag est OFF.
    """
    if not settings.ENABLE_EXTERNAL_FALLBACK:
        EXTERNAL_FALLBACK_BLOCKED_TOTAL.labels(reason="flag_disabled").inc()
        raise ExternalFallbackDisabledError(
            f"Appel externe bloqué (ENABLE_EXTERNAL_FALLBACK=false). Caller={caller}. "
            "Activation manuelle uniquement après rapport de plafonnement local documenté."
        )

    if not settings.ANTHROPIC_API_KEY.get_secret_value():
        EXTERNAL_FALLBACK_BLOCKED_TOTAL.labels(reason="no_api_key").inc()
        raise ExternalFallbackDisabledError(
            f"Appel externe bloqué : ANTHROPIC_API_KEY vide. Caller={caller}."
        )

    if settings.EXTERNAL_FALLBACK_BUDGET_MONTHLY_USD <= 0:
        EXTERNAL_FALLBACK_BLOCKED_TOTAL.labels(reason="no_budget").inc()
        raise ExternalFallbackDisabledError(
            f"Appel externe bloqué : plafond budgétaire à 0. Caller={caller}."
        )
