"""Routeur ZolaOS — classifie une requête utilisateur dans un pôle métier.

Llama-3-8B local, JSON strict, garde-fou de validation côté Python.
"""

from __future__ import annotations

from enum import Enum
from typing import Literal

import orjson
from pydantic import BaseModel, Field, ValidationError, field_validator

from zolaos.agents._prompts import load_prompt
from zolaos.core.logging import get_logger
from zolaos.core.metrics import AGENT_INVOCATIONS_TOTAL
from zolaos.core.settings import Settings
from zolaos.llm.base import GenerationOptions, LLMClient, Message

_log = get_logger("zolaos.agents.router")


class Pole(str, Enum):
    HEALTH = "health"
    LEGAL = "legal"
    ERP = "erp"
    GRC = "grc"
    FINTECH = "fintech"
    CYBER = "cyber"
    ENGINEERING = "engineering"
    GENERAL = "general"


# Modules connus par pôle (extensible — la liste sert au prompt + à la validation
# lâche côté Python : un module inconnu est accepté mais loggué pour pouvoir
# enrichir cette liste sans casser le routage).
KNOWN_MODULES: dict[Pole, tuple[str, ...]] = {
    Pole.HEALTH: ("pharmacology", "diagnosis", "case"),
    Pole.LEGAL: (
        "ohada",
        "travail_cg",
        "fiscal_cg",
        "social_cg",
        "civil_cg",
        "penal_cg",
        "ip_oapi",
        "data_protection_cg",
        "admin_cg",
    ),
    Pole.ERP: ("compta_syscohada", "finance", "tresorerie", "rh", "projets_ong"),
    Pole.GRC: (
        "conformite",
        "audit_institutionnel",
        "reporting_bailleurs",
        "compliance_data",
        "audit_sante",
    ),
    Pole.FINTECH: ("scoring", "kyc"),
    Pole.CYBER: ("defense",),
    Pole.ENGINEERING: ("code",),
    Pole.GENERAL: (),
}


class RouteDecision(BaseModel):
    """Sortie validée du routeur."""

    pole: Pole
    # Champ OBLIGATOIRE pour forcer la grammar GBNF llama.cpp à le générer.
    # Valeur `null` autorisée pour requêtes génériques (pole=general typiquement).
    # `Field(...)` sans default = champ requis dans le JSON schema.
    module: str | None = Field(..., max_length=64, description="Module métier précis (ex: ohada, travail_cg, pharmacology) ou null si générique")
    confidence: float = Field(ge=0.0, le=1.0)
    language: Literal["fr", "ln", "kg", "other"] = "fr"
    country_hint: str = Field(default="cg", pattern=r"^[a-z]{2}$")
    complexity: Literal["simple", "moderate", "complex"] = "moderate"
    warning: str | None = None

    @field_validator("warning")
    @classmethod
    def empty_warning_is_none(cls, v: str | None) -> str | None:
        if v is None or v == "" or v.lower() == "null":
            return None
        return v

    @field_validator("module")
    @classmethod
    def normalize_module(cls, v: str | None) -> str | None:
        if v is None or not v.strip() or v.strip().lower() in {"null", "none", "n/a"}:
            return None
        return v.strip().lower()


_SYSTEM_PROMPT_CACHE: str | None = None


def _system_prompt() -> str:
    global _SYSTEM_PROMPT_CACHE  # noqa: PLW0603
    if _SYSTEM_PROMPT_CACHE is None:
        _SYSTEM_PROMPT_CACHE = load_prompt("router.md")
    return _SYSTEM_PROMPT_CACHE


class Router:
    """Routeur principal de ZolaOS."""

    def __init__(self, client: LLMClient, settings: Settings) -> None:
        self._client = client
        self._settings = settings

    async def classify(self, user_query: str) -> RouteDecision:
        """Classifie la requête. Lève `RouterError` si la sortie ne parse pas."""
        messages = [
            Message(role="system", content=_system_prompt()),
            Message(role="user", content=user_query),
        ]
        options = GenerationOptions(
            temperature=0.0,
            max_tokens=200,
            json_mode=True,
            json_schema=RouteDecision.model_json_schema(),
        )

        outcome = "error"
        try:
            result = await self._client.generate(
                messages,
                model=self._settings.LLM_MODEL_ROUTER,
                options=options,
            )
            decision = self._parse(result.content)
            outcome = "ok"
            # On signale un module inconnu sans rejeter : le routage reste valide
            # au niveau du pôle, c'est juste de la traçabilité pour enrichir
            # KNOWN_MODULES plus tard.
            known = KNOWN_MODULES.get(decision.pole, ())
            module_known = decision.module is None or decision.module in known
            _log.info(
                "router.classify",
                pole=decision.pole,
                module=decision.module,
                module_known=module_known,
                confidence=decision.confidence,
                language=decision.language,
                country_hint=decision.country_hint,
                duration_seconds=result.duration_seconds,
            )
            return decision
        finally:
            AGENT_INVOCATIONS_TOTAL.labels(agent="router", outcome=outcome).inc()

    @staticmethod
    def _parse(raw: str) -> RouteDecision:
        """Parse + valide la sortie JSON du LLM. Tolérant aux préfixes parasites."""
        text = raw.strip()
        # Le LLM peut parfois inclure ```json … ``` ; on tente d'extraire.
        if "```" in text:
            first = text.find("{")
            last = text.rfind("}")
            if first >= 0 and last > first:
                text = text[first : last + 1]

        try:
            data = orjson.loads(text)
        except orjson.JSONDecodeError as exc:
            raise RouterError(f"Sortie LLM non-JSON : {raw[:200]!r}") from exc

        try:
            return RouteDecision.model_validate(data)
        except ValidationError as exc:
            raise RouterError(f"Sortie LLM invalide : {exc}") from exc


class RouterError(RuntimeError):
    """Sortie du routeur non parseable ou invalide."""
