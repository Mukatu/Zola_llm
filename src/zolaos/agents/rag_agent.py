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

from collections.abc import AsyncIterator
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
from zolaos.rag.sectors import detect_sector

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


@dataclass(frozen=True)
class RAGPrepared:
    """Contexte prêt à générer : retrieve effectué, garde-fous déjà franchis.

    Sépare le « quoi répondre » (retrieve + citations, connu d'avance) du « comment
    le dire » (génération). C'est ce qui permet de streamer : on peut envoyer les
    citations à l'écran avant le premier token du modèle.
    """

    matches: list[Match]
    citations: list[Citation]
    messages: list[Message]
    options: GenerationOptions


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
    # True = la question peut nommer un secteur d'activité doté d'une convention
    # collective dédiée (droit du travail) → retrieve boosté par secteur pour
    # ancrer sur la bonne convention plutôt qu'un mélange. Cf. `_primary_retrieve`.
    sector_aware: ClassVar[bool] = False
    top_k: ClassVar[int] = 5
    max_tokens: ClassVar[int] = 800
    temperature: ClassVar[float] = 0.2

    def __init__(
        self,
        client: LLMClient,
        settings: Settings,
        *,
        mission_client: MissionClient | None = None,
        tenant_id: str | None = None,
    ) -> None:
        """`mission_client` (optionnel) : si fourni, le retrieve RAG passe par
        la Zolabox distante via JWT mission (Polaris-13). Sinon, retrieve local.
        Réservé au profil cortex.

        `tenant_id` (optionnel) : si fourni, le retrieve **local** fusionne le
        corpus de référence (droit public) avec les documents téléversés par le
        client (schéma ``rag_tenant``, filtrés ``tenant:<id>``) → réponse ancrée
        sur « la loi + VOS règles ».
        """
        if not self.name or not self.rag_schema or not self.prompt_file:
            raise ValueError(f"{type(self).__name__} doit définir name, rag_schema et prompt_file.")
        self._client = client
        self._settings = settings
        self._mission_client = mission_client
        self._tenant_id = tenant_id

    @cached_property
    def _system_prompt(self) -> str:
        # `prompt_file` peut être un chemin avec sous-dossiers ("health/pharmacology.md").
        parts = self.prompt_file.split("/")
        return load_prompt(*parts)

    async def prepare(
        self,
        query: str,
        *,
        extra_tags: list[str] | None = None,
        k: int | None = None,
    ) -> RAGPrepared:
        """Étapes 1-2 : retrieve + garde-fous + construction du contexte.

        Lève `InsufficientContextError` si le garde-fou est actif et le corpus
        n'a pas de quoi répondre — **avant** toute génération, donc sans qu'un
        seul token inventé n'ait pu être produit.
        """
        tags = list(self.default_tags) + (extra_tags or [])
        kk = k or self.top_k

        # --- 1. Retrieve : local (DB directe) OU remote (via MissionClient) ---
        matches = await self._do_retrieve(query=query, tags=tags, k=kk)
        return self.assemble(query, matches)

    def assemble(self, query: str, matches: list[Match]) -> RAGPrepared:
        """Applique garde-fous + contexte à des matches DÉJÀ récupérés.

        Séparé de `prepare()` pour que le filet de rattrapage de l'orchestrateur
        puisse réutiliser des matches obtenus par un balayage multi-schéma, sans
        re-chercher. Les garde-fous (`requires_citation`, `min_confidence`) de
        l'agent restent appliqués — un match trop faible lève quand même.
        """
        if self.requires_citation and not matches:
            raise InsufficientContextError(
                f"[{self.name}] aucun match RAG pour la requête (schema={self.rag_schema})"
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
            "Réponds en t'appuyant **strictement** sur les textes ci-dessus. "
            "Cite tes sources avec leur numéro entre crochets, ex: [1], [2]. "
            "Si l'information n'y figure pas, dis-le explicitement. "
            "N'évoque aucun mécanisme interne (ne dis pas « RAG » ni « extraits »)."
        )
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
        return RAGPrepared(
            matches=matches,
            citations=citations,
            messages=[
                Message(role="system", content=self._system_prompt),
                Message(role="user", content=user_msg),
            ],
            options=opts,
        )

    async def answer(
        self,
        query: str,
        *,
        extra_tags: list[str] | None = None,
        k: int | None = None,
    ) -> RAGAgentResponse:
        """Question/réponse RAG. Lève `InsufficientContextError` si garde-fou actif et pas assez de contexte."""
        import time

        prepared = await self.prepare(query, extra_tags=extra_tags, k=k)
        return await self.answer_prepared(prepared)

    async def answer_prepared(self, prepared: RAGPrepared) -> RAGAgentResponse:
        """Étape 3-4 : génère à partir d'un contexte déjà préparé (retrieve fait).

        Permet à l'orchestrateur de générer depuis des matches obtenus autrement
        (filet de rattrapage multi-schéma) sans re-chercher.
        """
        import time

        start = time.perf_counter()
        outcome = "error"
        try:
            result = await self._client.generate(
                prepared.messages,
                model=self._settings.LLM_MODEL_BRIGADE,
                options=prepared.options,
            )
            outcome = "ok"
            duration = time.perf_counter() - start
            _log.info(
                "rag_agent.answer",
                agent=self.name,
                matches=len(prepared.matches),
                top_similarity=(
                    prepared.matches[0].similarity if prepared.matches else None
                ),
                duration_seconds=duration,
            )
            return RAGAgentResponse(
                agent=self.name,
                content=result.content,
                citations=prepared.citations,
                matches=prepared.matches,
                duration_seconds=duration,
            )
        finally:
            AGENT_INVOCATIONS_TOTAL.labels(agent=self.name, outcome=outcome).inc()

    async def stream_prepared(self, prepared: RAGPrepared) -> AsyncIterator[str]:
        """Étape 3, en streaming : yield les fragments de texte au fil de l'eau.

        Prend un `RAGPrepared` (donc garde-fous déjà franchis) pour que l'appelant
        puisse afficher les citations avant le premier token.
        """
        outcome = "error"
        try:
            async for chunk in self._client.stream(
                prepared.messages,
                model=self._settings.LLM_MODEL_BRIGADE,
                options=prepared.options,
            ):
                yield chunk
            outcome = "ok"
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
        matches = await self._primary_retrieve(query=query, tags=tags, k=k)
        # Union avec : le communs partagé (savoir promu, niveau 3) + le corpus du
        # client (documents téléversés, si tenant connu). Chaque source dégrade
        # proprement si indisponible.
        sources: list[tuple[str, list[str]]] = [("rag_commons", ["country:cg"])]
        if self._tenant_id:
            sources.append(("rag_tenant", ["country:cg", f"tenant:{self._tenant_id}"]))
        for schema, req in sources:
            try:
                extra = await retrieve(query=query, schema=schema, required_tags=req, k=k)
            except Exception as exc:  # source indispo → on garde ce qu'on a
                _log.warning("rag_agent.union_retrieve_failed", agent=self.name, schema=schema, error=str(exc))
                extra = []
            if extra:
                merged = [*matches, *extra]
                merged.sort(key=lambda m: m.score)  # score = distance cosine (plus petit = mieux)
                matches = merged[:k]
        return matches

    async def _primary_retrieve(self, *, query: str, tags: list[str], k: int) -> list[Match]:
        """Retrieve dans le schéma de l'agent, avec **boost secteur** si applicable.

        Sans secteur (ou agent non `sector_aware`) : retrieve normal.

        Avec un secteur détecté (ex. « secteur bancaire ») : double détente pour
        ancrer sur la BONNE convention plutôt qu'un mélange de toutes —
          1. un retrieve scopé `secteur:<x>` garantit la présence de la convention
             du secteur, même si elle n'aurait pas atteint le top-k globalement ;
          2. un retrieve général fournit le droit commun (Code du travail, non
             tagué secteur), duquel on **écarte les conventions d'AUTRES secteurs**
             (le bruit : une convention minière n'a rien à faire dans une réponse
             sur les banques).
        On réserve la moitié de `k` au secteur, l'autre au droit commun.
        """
        sector = detect_sector(query) if self.sector_aware else None
        if sector is None:
            return await retrieve(
                query=query, schema=self.rag_schema, required_tags=tags, k=k
            )

        sector_tag = f"secteur:{sector}"
        specific = await retrieve(
            query=query, schema=self.rag_schema, required_tags=[*tags, sector_tag], k=k
        )
        general = await retrieve(
            query=query, schema=self.rag_schema, required_tags=tags, k=k
        )

        def _other_sector(m: Match) -> bool:
            return any(t.startswith("secteur:") and t != sector_tag for t in m.tags)

        n_sector = max(1, k // 2)
        chosen = list(specific[:n_sector])
        seen = {(m.source_uri, m.chunk_index) for m in chosen}
        for m in general:
            if len(chosen) >= k:
                break
            key = (m.source_uri, m.chunk_index)
            if key in seen or _other_sector(m):
                continue
            chosen.append(m)
            seen.add(key)
        chosen.sort(key=lambda m: m.score)  # meilleur (distance min) d'abord
        _log.info(
            "rag_agent.sector_boost",
            agent=self.name,
            sector=sector,
            n_sector=sum(1 for m in chosen if sector_tag in m.tags),
            n_total=len(chosen),
        )
        return chosen

    @staticmethod
    def _format_context(matches: list[Match]) -> str:
        """Sérialise les chunks RAG en bloc numéroté pour le prompt LLM."""
        if not matches:
            return "--- Textes de référence ---\n(aucun extrait disponible)"
        lines = ["--- Textes de référence ---"]
        for i, m in enumerate(matches, start=1):
            src = m.source_id or m.source_uri.rsplit("/", 1)[-1]
            lines.append(
                f"\n[{i}] source={src} chunk={m.chunk_index} similarité={m.similarity:.2f}"
            )
            lines.append(m.content.strip())
        return "\n".join(lines)
