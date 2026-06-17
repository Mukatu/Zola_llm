"""Sous-agent Code (Pôle Engineering) — V2.2 Phase 3 #25, Engineering-1.

Premier vrai sous-agent du Pôle Engineering. **MVP Phase 3** : génération,
refactor, debug, explication de code. Pas d'exécution de code (à venir Phase 3.2
avec sandbox éphémère Docker). Pas de RAG (le code est généré par le LLM, pas
récupéré d'un corpus indexé).

Pattern différent des sous-agents RAG : pas de `requires_citation`, pas de
`rag_schema`. Sortie structurée optionnelle (`CodeArtifact`) pour qu'un appelant
puisse extraire `language`, `code`, `tests_suggested`…

Pour persister le code généré : utiliser `SafeWriteTool` séparément (allowlist
de workspaces obligatoire). Le Code Agent en lui-même n'écrit jamais sur disque.

Disponible dans les deux profils (`box` ET `cortex`) : un développeur d'une
entreprise cliente peut tout autant l'utiliser qu'un consultant Polaris dans
une mission d'audit technique.
"""

from __future__ import annotations

import time
from dataclasses import dataclass, field
from typing import Literal

from pydantic import BaseModel, Field

from zolaos.agents._prompts import load_prompt
from zolaos.core.logging import get_logger
from zolaos.core.metrics import AGENT_INVOCATIONS_TOTAL
from zolaos.core.settings import Settings
from zolaos.llm.base import GenerationOptions, LLMClient, Message

_log = get_logger("zolaos.agents.engineering.code")


# =============================================================================
# Schémas
# =============================================================================

CodeIntent = Literal["generate", "refactor", "debug", "explain", "review", "test"]


class CodeArtifact(BaseModel):
    """OUTPUT_FORMAT structuré optionnel.

    Quand `structured_output=True`, le LLM doit renvoyer ce schéma. Sinon, la
    réponse libre est conservée dans `CodeAgentResponse.content`.
    """

    language: str = Field(..., max_length=32, description="python, typescript, sql, bash, ...")
    code: str = Field(..., max_length=20_000)
    explanation: str = Field(..., max_length=2_000)
    suggested_tests: list[str] = Field(default_factory=list, max_length=20)
    warnings: list[str] = Field(default_factory=list, max_length=20)


@dataclass(frozen=True)
class CodeAgentResponse:
    agent: str
    intent: CodeIntent
    content: str                              # JSON si structured_output, sinon texte libre
    artifact: CodeArtifact | None = None      # parsé si structured_output=True et JSON valide
    duration_seconds: float = 0.0
    metadata: dict[str, str] = field(default_factory=dict)


# =============================================================================
# Agent
# =============================================================================

class CodeAgent:
    """Sous-agent Code — génération, refactor, debug, explication, review, tests."""

    name = "engineering.code"
    prompt_file = "engineering/code.md"

    # Le Code Agent utilise potentiellement le modèle CORE (Llama-3-70B) pour
    # les gros projets, mais en MVP on reste sur BRIGADE (8B) pour la latence.
    # L'appelant peut surcharger via `force_model` à l'invocation.
    default_model_attr = "LLM_MODEL_BRIGADE"

    def __init__(self, client: LLMClient, settings: Settings) -> None:
        self._client = client
        self._settings = settings

    @property
    def _system_prompt(self) -> str:
        return load_prompt("engineering", "code.md")

    async def answer(
        self,
        query: str,
        *,
        intent: CodeIntent = "generate",
        language_hint: str | None = None,
        structured_output: bool = False,
        force_model: str | None = None,
        temperature: float = 0.2,
        max_tokens: int = 2000,
    ) -> CodeAgentResponse:
        """Génère/refactore/debug/explique/review du code via LLM.

        Args:
            intent: nature de la demande (oriente le prompt).
            language_hint: langage cible (ex: "python", "typescript"). Si None,
                le LLM infère depuis la requête.
            structured_output: si True, le LLM doit renvoyer un `CodeArtifact`
                JSON. Sinon, réponse libre (markdown + blocs code typiques).
        """
        start = time.perf_counter()
        outcome = "error"

        user_msg_parts = [f"[Intent] {intent}"]
        if language_hint:
            user_msg_parts.append(f"[Language] {language_hint}")
        user_msg_parts.append(f"\n[Demande]\n{query}")
        if structured_output:
            user_msg_parts.append(
                "\n[Format de sortie] OBLIGATOIRE — JSON conforme au schéma "
                "`CodeArtifact` (language, code, explanation, suggested_tests, warnings)."
            )
        user_msg = "\n".join(user_msg_parts)

        opts = GenerationOptions(
            temperature=temperature,
            max_tokens=max_tokens,
            json_mode=structured_output,
            json_schema=CodeArtifact.model_json_schema() if structured_output else None,
        )

        try:
            result = await self._client.generate(
                [
                    Message(role="system", content=self._system_prompt),
                    Message(role="user", content=user_msg),
                ],
                model=force_model or getattr(self._settings, self.default_model_attr),
                options=opts,
            )

            artifact: CodeArtifact | None = None
            if structured_output and result.content:
                try:
                    artifact = CodeArtifact.model_validate_json(result.content)
                except Exception as exc:  # noqa: BLE001
                    # On laisse `artifact=None` ; le contenu brut reste dans `content`.
                    _log.warning(
                        "code_agent.parse_artifact_failed",
                        error=str(exc),
                        content_preview=result.content[:200],
                    )

            outcome = "ok"
            duration = time.perf_counter() - start
            _log.info(
                "code_agent.answer",
                intent=intent,
                language_hint=language_hint,
                structured=structured_output,
                duration_seconds=duration,
                artifact_parsed=artifact is not None,
            )
            return CodeAgentResponse(
                agent=self.name,
                intent=intent,
                content=result.content,
                artifact=artifact,
                duration_seconds=duration,
                metadata={"model": result.model, "provider": result.provider},
            )
        finally:
            AGENT_INVOCATIONS_TOTAL.labels(agent=self.name, outcome=outcome).inc()
