"""Classe de base pour tous les sous-agents RAG (santé, droit, ERP…).

Pattern d'implémentation commun :
  1. Retrieve  : top-k pgvector cosine + filtre tags RBAC
  2. Build     : assemble le contexte (chunks numérotés [1], [2], …)
  3. Generate  : LLM (réponse libre OU JSON structuré selon `response_schema`)
  4. Return    : RAGAgentResponse (content + citations + matches bruts)

Les sous-agents concrets se contentent de fixer 4 attributs de classe :
  - `name`           : identifiant logique (utilisé pour métriques + logs)
  - `rag_schema`     : "rag_health" | "rag_legal"
  - `prompt_file`    : chemin relatif depuis agents/prompts/ (ex: "health/pharmacology.md")
  - `default_tags`   : tags RBAC obligatoires (ex: ["country:cg", "module:pharmacology"])

Optionnels :
  - `response_schema`: BaseModel pour OUTPUT_FORMAT structuré (overlays Polaris)
  - `min_confidence` : seuil de refus si la similarité du meilleur chunk est trop faible
  - `requires_citation`: si True, refuse si aucun match RAG (anti-hallucination strict)

Garde-fou anti-hallucination :
  - Si `requires_citation=True` et `retrieve()` retourne 0 match → on lève
    `InsufficientContextError` au lieu d'inventer une réponse.
  - Si `min_confidence` set et que `matches[0].similarity < min_confidence`
    → on lève aussi.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from functools import cached_property
from typing import TYPE_CHECKING, ClassVar

from pydantic import BaseModel

from zolaos.agents._prompts import load_prompt
from zolaos.core.logging import get_logger
from zolaos.core.metrics import AGENT_INVOCATIONS_TOTAL
from zolaos.core.settings import Settings
from zolaos.llm.base import GenerationOptions, LLMClient, Message
from zolaos.rag.retrieval import Match, retrieve

if TYPE_CHECKING:
    from zolaos.missions.client import MissionClient

_log = get_logger("zolaos.agents.rag_agent")


@dataclass(frozen=True)
class Citation:
    """Citation d'un chunk RAG dans la réponse de l'agent."""

    index: int  # numéro [1], [2]… dans la réponse
    source_uri: str
    source_id: str | None
    chunk_index: int
    similarity: float


@dataclass(frozen=True)
class RAGAgentResponse:
    """Résultat d'un appel à un sous-agent RAG."""

    agent: str
    content: str  # réponse libre OU JSON sérialisé selon response_schema
    citations: list[Citation]
    matches: list[Match] = field(default_factory=list)  # chunks bruts pour audit
    duration_seconds: float = 0.0


class InsufficientContextError(RuntimeError):
    """Pas assez de matches RAG pour répondre sans halluciner."""


class RAGAgent:
    """Squelette commun à tous les sous-agents RAG. À sous-classer.

    Exemple minimal :
        class PharmacologyAgent(RAGAgent):
            name = "health.pharmacology"
            rag_schema = "rag_health"
            prompt_file = "health/pharmacology.md"
            default_tags = ["country:cg", "module:pharmacology"]
    """

    # --- contrat à surcharger par les sous-classes ---
    name: ClassVar[str] = ""
    rag_schema: ClassVar[str] = ""
    prompt_file: ClassVar[str] = ""
    default_tags: ClassVar[tuple[str, ...]] = ()

    # --- contrat optionnel ---
    response_schema: ClassVar[type[BaseModel] | None] = None
    min_confidence: ClassVar[float | None] = None  # ex: 0.55 pour Droit (refus si < seuil)
    requires_citation: ClassVar[bool] = True  # False = autorise réponse hors RAG
    top_k: ClassVar[int] = 5
    max_tokens: ClassVar[int] = 800
    temperature: ClassVar[float] = 0.2

    def __init__(
        self,
        client: LLMClient,
        settings: Settings,
        *,
        mission_client: MissionClient | None = None,
    ) -> None:
        """`mission_client` (optionnel) : si fourni, le retrieve RAG passe par
        la Zolabox distante via JWT mission (Polaris-13). Sinon, retrieve local.
        Réservé au profil cortex.
        """
        if not self.name or not self.rag_schema or not self.prompt_file:
            raise ValueError(f"{type(self).__name__} doit définir name, rag_schema et prompt_file.")
        self._client = client
        self._settings = settings
        self._mission_client = mission_client

    @cached_property
    def _system_prompt(self) -> str:
        # `prompt_file` peut être un chemin avec sous-dossiers ("health/pharmacology.md").
        parts = self.prompt_file.split("/")
        return load_prompt(*parts)

    async def answer(
        self,
        query: str,
        *,
        extra_tags: list[str] | None = None,
        k: int | None = None,
    ) -> RAGAgentResponse:
        """Question/réponse RAG. Lève `InsufficientContextError` si garde-fou actif et pas assez de contexte."""
        import time

        tags = list(self.default_tags) + (extra_tags or [])
        kk = k or self.top_k

        start = time.perf_counter()
        outcome = "error"
        try:
            # --- 1. Retrieve : local (DB directe) OU remote (via MissionClient) ---
            matches = await self._do_retrieve(query=query, tags=tags, k=kk)

            if self.requires_citation and not matches:
                raise InsufficientContextError(
                    f"[{self.name}] aucun match RAG pour la requête "
                    f"(tags={tags}, schema={self.rag_schema})"
                )
            if (
                self.min_confidence is not None
                and matches
                and matches[0].similarity < self.min_confidence
            ):
                raise InsufficientContextError(
                    f"[{self.name}] similarité top-1 ({matches[0].similarity:.2f}) "
                    f"< seuil {self.min_confidence:.2f}"
                )

            # --- 2. Build context ---
            context = self._format_context(matches)
            user_msg = (
                f"{context}\n\n"
                f"--- Question utilisateur ---\n{query}\n\n"
                "Réponds en t'appuyant **strictement** sur les extraits ci-dessus. "
                "Cite tes sources avec leur numéro entre crochets, ex: [1], [2]. "
                "Si l'information n'est pas dans les extraits, dis-le explicitement."
            )

            # --- 3. Generate ---
            opts = GenerationOptions(
                temperature=self.temperature,
                max_tokens=self.max_tokens,
                json_mode=self.response_schema is not None,
                json_schema=(
                    self.response_schema.model_json_schema()
                    if self.response_schema is not None
                    else None
                ),
            )
            result = await self._client.generate(
                [
                    Message(role="system", content=self._system_prompt),
                    Message(role="user", content=user_msg),
                ],
                model=self._settings.LLM_MODEL_BRIGADE,
                options=opts,
            )

            # --- 4. Build response ---
            citations = [
                Citation(
                    index=i + 1,
                    source_uri=m.source_uri,
                    source_id=m.source_id,
                    chunk_index=m.chunk_index,
                    similarity=m.similarity,
                )
                for i, m in enumerate(matches)
            ]
            outcome = "ok"
            duration = time.perf_counter() - start
            _log.info(
                "rag_agent.answer",
                agent=self.name,
                matches=len(matches),
                top_similarity=matches[0].similarity if matches else None,
                duration_seconds=duration,
            )
            return RAGAgentResponse(
                agent=self.name,
                content=result.content,
                citations=citations,
                matches=matches,
                duration_seconds=duration,
            )
        finally:
            AGENT_INVOCATIONS_TOTAL.labels(agent=self.name, outcome=outcome).inc()

    async def _do_retrieve(self, *, query: str, tags: list[str], k: int) -> list[Match]:
        """Délègue le retrieve : MissionClient si présent (Cortex → Box), sinon DB locale."""
        if self._mission_client is not None:
            raw = await self._mission_client.rag_search(
                schema=self.rag_schema,
                query=query,
                required_tags=tags,
                k=k,
            )
            return [
                Match(
                    content=m["content"],
                    score=float(m["score"]),
                    source_uri=m["source_uri"],
                    source_id=m.get("source_id"),
                    chunk_index=int(m["chunk_index"]),
                    tags=list(m.get("tags", [])),
                    extra_metadata=(
                        dict(m.get("extra_metadata", {})) if m.get("extra_metadata") else {}
                    ),
                )
                for m in raw
            ]
        return await retrieve(
            query=query,
            schema=self.rag_schema,
            required_tags=tags,
            k=k,
        )

    @staticmethod
    def _format_context(matches: list[Match]) -> str:
        """Sérialise les chunks RAG en bloc numéroté pour le prompt LLM."""
        if not matches:
            return "--- Contexte RAG ---\n(aucun extrait disponible)"
        lines = ["--- Contexte RAG ---"]
        for i, m in enumerate(matches, start=1):
            src = m.source_id or m.source_uri.rsplit("/", 1)[-1]
            lines.append(
                f"\n[{i}] source={src} chunk={m.chunk_index} similarité={m.similarity:.2f}"
            )
            lines.append(m.content.strip())
        return "\n".join(lines)
