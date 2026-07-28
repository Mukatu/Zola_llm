"""Sous-agent Code (Pôle Engineering) — assistant code SOUVERAIN (produit client).

Assistant de codage destiné aux **clients tech**, exécuté **sur la box du client**
sur un modèle dédié code servi localement (Qwen2.5-Coder-32B, cf. `LLM_MODEL_CODE`) :
le code du client **ne quitte jamais ses murs**. C'est la proposition de valeur —
là où l'entreprise ne peut/veut pas envoyer son code propriétaire à une API externe.

**RAG ancré sur le dépôt DU CLIENT** : avant de générer, l'agent récupère les
extraits pertinents du code indexé (`rag_code`, **cloisonné par tenant** comme
`rag_tenant`) et les injecte en contexte → il connaît *ce* dépôt, pas du code
générique. Si rien n'est indexé, il retombe en génération pure (dégradation douce).
Le corpus est peuplé par `scripts/index_codebase.py`.

Intents : génération, refactor, debug, explication, review, tests. Sortie
structurée optionnelle (`CodeArtifact`). Pas d'exécution de code (Phase 3.2 :
sandbox éphémère Docker). L'agent n'écrit jamais sur disque (persistance via
`SafeWriteTool` séparé, allowlist obligatoire).
"""

from __future__ import annotations

import time
from dataclasses import dataclass, field
from typing import Literal

from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from zolaos.agents._prompts import load_prompt
from zolaos.core.logging import get_logger
from zolaos.core.metrics import AGENT_INVOCATIONS_TOTAL
from zolaos.core.settings import Settings
from zolaos.llm.base import GenerationOptions, LLMClient, Message
from zolaos.rag.retrieval import retrieve

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
    content: str  # JSON si structured_output, sinon texte libre
    artifact: CodeArtifact | None = None  # parsé si structured_output=True et JSON valide
    duration_seconds: float = 0.0
    metadata: dict[str, str] = field(default_factory=dict)


# =============================================================================
# Agent
# =============================================================================


class CodeAgent:
    """Sous-agent Code — génération, refactor, debug, explication, review, tests."""

    name = "engineering.code"
    prompt_file = "engineering/code.md"

    # Assistant code SOUVERAIN : tourne sur le modèle dédié code servi localement
    # sur la box du client (Qwen2.5-Coder-32B, cf. LLM_MODEL_CODE) — le code ne
    # quitte jamais ses murs. L'appelant peut surcharger via `force_model`.
    default_model_attr = "LLM_MODEL_CODE"

    #: Nb d'extraits du dépôt indexé injectés en contexte (retrieval rag_code).
    top_k = 6

    def __init__(self, client: LLMClient, settings: Settings, *, tenant_id: str = "local") -> None:
        self._client = client
        self._settings = settings
        # Clé d'isolation : le retrieval du code est borné à CE tenant (rag_code
        # cloisonné, comme rag_tenant). Un tenant ne voit jamais le code d'un autre.
        self._tenant_id = tenant_id

    async def _retrieve_context(self, query: str, *, session: AsyncSession | None) -> str:
        """Récupère les extraits pertinents du dépôt du client (rag_code),
        **cloisonnés au tenant courant**. Chaîne vide si rien n'est indexé (pas
        d'échec : l'agent répond alors sans contexte de dépôt)."""
        try:
            matches = await retrieve(
                query=query,
                schema="rag_code",
                required_tags=[f"tenant:{self._tenant_id}"],
                k=self.top_k,
                session=session,
            )
        except Exception as exc:  # index absent, DB indisponible… → dégradation douce
            _log.warning("code_agent.retrieve_failed", error=str(exc))
            return ""
        if not matches:
            return ""
        return "\n\n".join(
            f"--- {m.source_uri} (sim {m.similarity:.2f}) ---\n{m.content}" for m in matches
        )

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
        session: AsyncSession | None = None,
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

        # Ancrage sur le dépôt du client (rag_code, cloisonné tenant). Vide si
        # rien n'est indexé → l'assistant répond alors en génération pure.
        contexte = await self._retrieve_context(query, session=session)

        user_msg_parts = [f"[Intent] {intent}"]
        if language_hint:
            user_msg_parts.append(f"[Language] {language_hint}")
        if contexte:
            user_msg_parts.append(
                "\n[Contexte du dépôt indexé — extraits pertinents du code du client. "
                "Utilise ces éléments en PRIORITÉ ; n'invente pas d'API/signature absente "
                "du dépôt ; cite les chemins de fichiers concernés]\n" + contexte
            )
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
                except Exception as exc:
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
                metadata={
                    "model": result.model,
                    "provider": result.provider,
                    "repo_context": "yes" if contexte else "no",
                },
            )
        finally:
            AGENT_INVOCATIONS_TOTAL.labels(agent=self.name, outcome=outcome).inc()
