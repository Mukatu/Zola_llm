"""Garde-fou anti-fallback : critique pour la souveraineté.

Vérifie qu'aucun appel externe ne peut être effectué tant que
ENABLE_EXTERNAL_FALLBACK=false. Ce test est marqué `security` et doit
**toujours** passer en CI — c'est la garantie qu'aucun changement futur
ne réintroduit silencieusement un appel sortant.
"""

from __future__ import annotations

import pytest

from zolaos.core.settings import Settings
from zolaos.llm.guard import (
    ExternalFallbackDisabledError,
    ensure_external_fallback_allowed,
)


@pytest.mark.security
def test_fallback_blocked_when_flag_off() -> None:
    settings = Settings(
        ENABLE_EXTERNAL_FALLBACK=False,
        ANTHROPIC_API_KEY="dummy-but-irrelevant",
        EXTERNAL_FALLBACK_BUDGET_MONTHLY_USD=100.0,
    )
    with pytest.raises(ExternalFallbackDisabledError, match="ENABLE_EXTERNAL_FALLBACK=false"):
        ensure_external_fallback_allowed(settings, caller="test")


@pytest.mark.security
def test_fallback_blocked_when_no_api_key() -> None:
    settings = Settings(
        ENABLE_EXTERNAL_FALLBACK=True,
        ANTHROPIC_API_KEY="",
        EXTERNAL_FALLBACK_BUDGET_MONTHLY_USD=100.0,
    )
    with pytest.raises(ExternalFallbackDisabledError, match="ANTHROPIC_API_KEY vide"):
        ensure_external_fallback_allowed(settings, caller="test")


@pytest.mark.security
def test_fallback_blocked_when_no_budget() -> None:
    settings = Settings(
        ENABLE_EXTERNAL_FALLBACK=True,
        ANTHROPIC_API_KEY="dummy",
        EXTERNAL_FALLBACK_BUDGET_MONTHLY_USD=0.0,
    )
    with pytest.raises(ExternalFallbackDisabledError, match="plafond budgétaire"):
        ensure_external_fallback_allowed(settings, caller="test")


@pytest.mark.security
def test_fallback_allowed_when_all_conditions_met() -> None:
    """Le garde-fou laisse passer uniquement si toutes les conditions sont réunies."""
    settings = Settings(
        ENABLE_EXTERNAL_FALLBACK=True,
        ANTHROPIC_API_KEY="dummy",
        EXTERNAL_FALLBACK_BUDGET_MONTHLY_USD=100.0,
    )
    # Ne doit PAS lever.
    ensure_external_fallback_allowed(settings, caller="test")
