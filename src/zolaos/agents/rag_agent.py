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
from zolaos.rag.formes import detect_forme_juridique
from zolaos.rag.retrieval import Match, rerank_or_trim, retrieve
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
    # Texte VERBATIM du chunk cité. Surfacé tel quel à l'écran sous la réponse :
    # la complétude et la fidélité viennent de l'affichage du texte réel, pas de
    # ce que le modèle (8B, sujet à la sous-lecture) en restitue. Le raisonnement
    # du modèle s'adosse à ce texte au lieu d'en être la seule source.
    content: str = ""


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
    # True = la question peut nommer une forme de société (SARL, SA, coopérative…)
    # → retrieve boosté par forme pour ancrer sur les articles OHADA de la bonne
    # forme plutôt qu'un mélange (SARL vs coopératives). Cf. `_primary_retrieve`.
    forme_aware: ClassVar[bool] = False
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
        evidence: str | None = None,
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
        return self.assemble(query, matches, evidence=evidence)

    def assemble(
        self, query: str, matches: list[Match], *, evidence: str | None = None
    ) -> RAGPrepared:
        """Applique garde-fous + contexte à des matches DÉJÀ récupérés.

        Séparé de `prepare()` pour que le filet de rattrapage de l'orchestrateur
        puisse réutiliser des matches obtenus par un balayage multi-schéma, sans
        re-chercher. Les garde-fous (`requires_citation`, `min_confidence`) de
        l'agent restent appliqués — un match trop faible lève quand même.

        `evidence` (optionnel) : faits **déjà calculés par un moteur déterministe**
        (ex. audit de durcissement, détection d'anomalies) à restituer tels quels.
        Le LLM les narre/priorise sans les recalculer ni en inventer — doctrine
        « le moteur calcule, le LLM narre ».
        """
        if self.requires_citation and not matches:
            raise InsufficientContextError(
                f"[{self.name}] aucun match RAG pour la requête (schema={self.rag_schema})"
            )
        # Garde-fou de confiance : abstention s'il n'existe AUCUN chunk assez
        # similaire. On raisonne sur le MAX de similarité, pas sur matches[0] :
        # depuis le re-ranking hybride, matches[0] est le meilleur au score
        # hybride (lexical + dense), pas forcément le plus proche sémantiquement.
        # Vérifier matches[0].similarity ferait abandonner à tort un bon match
        # lexical (ex. l'article qui contient littéralement « préavis ») dont la
        # similarité brute est moyenne, et renverrait au filet de rattrapage.
        if self.min_confidence is not None and matches:
            best_sim = max(m.similarity for m in matches)
            if best_sim < self.min_confidence:
                raise InsufficientContextError(
                    f"[{self.name}] meilleure similarité ({best_sim:.2f}) "
                    f"< seuil {self.min_confidence:.2f}"
                )

        # --- 2. Build context ---
        context = self._format_context(matches)
        evidence_block = ""
        if evidence:
            evidence_block = (
                "--- Résultats de l'audit déterministe (établis par le moteur ; "
                "à restituer et prioriser, NE PAS recalculer ni compléter) ---\n"
                f"{evidence}\n\n"
            )
        user_msg = (
            f"{context}\n\n"
            f"{evidence_block}"
            f"--- Question utilisateur ---\n{query}\n\n"
            "Réponds en t'appuyant **strictement** sur les textes ci-dessus. "
            "Cite tes sources avec leur numéro entre crochets, ex: [1], [2]. "
            "Si l'information n'y figure pas, dis-le explicitement. "
            "N'évoque aucun mécanisme interne (ne dis pas « RAG » ni « extraits »)."
        )
        if any(self._is_tenant_match(m) for m in matches):
            user_msg += (
                "\n\nCertains extraits ci-dessus sont marqués « RÈGLE INTERNE DE "
                "L'ENTREPRISE ». Ce sont des documents internes du client (règlement "
                "intérieur, notes internes…), PAS des textes légaux : ils COMPLÈTENT "
                "la loi et la convention collective, ne les REMPLACENT jamais, et ne "
                "priment pas sur elles en cas de contradiction. Ne les cite JAMAIS "
                "comme fondement légal — précise explicitement quand une affirmation "
                "provient d'une règle interne plutôt que de la loi."
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
                content=m.content,
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
        evidence: str | None = None,
    ) -> RAGAgentResponse:
        """Question/réponse RAG. Lève `InsufficientContextError` si garde-fou actif et pas assez de contexte."""

        prepared = await self.prepare(query, extra_tags=extra_tags, k=k, evidence=evidence)
        return await self.answer_prepared(prepared)

    async def answer_prepared(
        self,
        prepared: RAGPrepared,
        *,
        client: LLMClient | None = None,
        model: str | None = None,
    ) -> RAGAgentResponse:
        """Étape 3-4 : génère à partir d'un contexte déjà préparé (retrieve fait).

        Permet à l'orchestrateur de générer depuis des matches obtenus autrement
        (filet de rattrapage multi-schéma) sans re-chercher.

        `client`/`model` (optionnels) surchargent le LLM de génération : c'est le
        levier du 70B sélectif — l'orchestrateur y pointe le `core_client` +
        `LLM_MODEL_CORE` pour les cas complexes, tout en gardant le retrieve et le
        routage sur le 8B. Par défaut : le client de l'agent + le modèle brigade (8B).
        """
        import time

        gen_client = client or self._client
        gen_model = model or self._settings.LLM_MODEL_BRIGADE
        start = time.perf_counter()
        outcome = "error"
        try:
            result = await gen_client.generate(
                prepared.messages,
                model=gen_model,
                options=prepared.options,
            )
            outcome = "ok"
            duration = time.perf_counter() - start
            _log.info(
                "rag_agent.answer",
                agent=self.name,
                model=gen_model,
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

    async def stream_prepared(
        self,
        prepared: RAGPrepared,
        *,
        client: LLMClient | None = None,
        model: str | None = None,
    ) -> AsyncIterator[str]:
        """Étape 3, en streaming : yield les fragments de texte au fil de l'eau.

        Prend un `RAGPrepared` (donc garde-fous déjà franchis) pour que l'appelant
        puisse afficher les citations avant le premier token. `client`/`model`
        surchargent le LLM de génération (70B sélectif — cf. `answer_prepared`).
        """
        gen_client = client or self._client
        gen_model = model or self._settings.LLM_MODEL_BRIGADE
        outcome = "error"
        try:
            async for chunk in gen_client.stream(
                prepared.messages,
                model=gen_model,
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
                # Union re-classée par score hybride (dense + lexical) : le chunk
                # qui régit réellement la question l'emporte, quelle que soit sa
                # source (schéma de l'agent, communs, tenant). Dégrade en tri par
                # distance cosine si le re-ranking est désactivé.
                matches = rerank_or_trim(query, [*matches, *extra], k, self._settings)
        return matches

    def _detect_facet(self, query: str) -> tuple[str, str] | None:
        """Facette (préfixe de tag, valeur) à booster pour cette requête, ou None.

        Une facette regroupe des sous-corpus concurrents et sémantiquement
        proches, qu'il faut départager par un signal explicite de la question :
          - `secteur:<x>` (conventions collectives par secteur — droit du travail) ;
          - `forme:<x>` (articles OHADA par forme de société — SARL vs coopérative).
        Un agent n'active qu'une facette (`sector_aware` OU `forme_aware`).
        """
        if self.sector_aware:
            sector = detect_sector(query)
            if sector is not None:
                return "secteur", sector
        if self.forme_aware:
            forme = detect_forme_juridique(query)
            if forme is not None:
                return "forme", forme
        return None

    async def _primary_retrieve(self, *, query: str, tags: list[str], k: int) -> list[Match]:
        """Retrieve dans le schéma de l'agent, avec **boost de facette** si applicable.

        Sans facette détectée (ou agent non concerné) : retrieve normal.

        Avec une facette (ex. « secteur bancaire », ou « statuts d'une SARL ») :
        double détente pour ancrer sur le BON sous-corpus plutôt qu'un mélange —
          1. un retrieve scopé `<facette>:<valeur>` garantit la présence des
             chunks de la bonne facette, même s'ils n'auraient pas atteint le
             top-k globalement ;
          2. un retrieve général fournit le droit commun (non tagué de cette
             facette), duquel on **écarte les chunks d'une AUTRE valeur de la même
             facette** (le bruit : une convention minière dans une réponse sur les
             banques ; un article coopératives dans une réponse sur les SARL).
        On réserve la moitié de `k` à la facette, l'autre au droit commun.
        """
        facet = self._detect_facet(query)
        if facet is None:
            return await retrieve(
                query=query, schema=self.rag_schema, required_tags=tags, k=k
            )

        prefix, value = facet
        facet_tag = f"{prefix}:{value}"
        specific = await retrieve(
            query=query, schema=self.rag_schema, required_tags=[*tags, facet_tag], k=k
        )
        general = await retrieve(
            query=query, schema=self.rag_schema, required_tags=tags, k=k
        )

        prefix_ = f"{prefix}:"

        def _other_value(m: Match) -> bool:
            return any(t.startswith(prefix_) and t != facet_tag for t in m.tags)

        n_facet = max(1, k // 2)
        chosen = list(specific[:n_facet])
        seen = {(m.source_uri, m.chunk_index) for m in chosen}
        for m in general:
            if len(chosen) >= k:
                break
            key = (m.source_uri, m.chunk_index)
            if key in seen or _other_value(m):
                continue
            chosen.append(m)
            seen.add(key)
        # Classement final du mélange facette/droit-commun par score hybride :
        # les termes décisifs de la question priment (dégrade en tri distance).
        chosen = rerank_or_trim(query, chosen, k, self._settings)
        _log.info(
            "rag_agent.facet_boost",
            agent=self.name,
            facet=facet_tag,
            n_facet=sum(1 for m in chosen if facet_tag in m.tags),
            n_total=len(chosen),
        )
        return chosen

    #: Préfixe apposé devant tout extrait issu du corpus TENANT (documents
    #: téléversés par le client : règlement intérieur, notes internes…) pour
    #: qu'il ne soit jamais confondu avec le droit applicable (loi, convention
    #: collective). Volontairement explicite et redondant : lu par le modèle
    #: ET par l'humain qui consulte les citations affichées à l'écran.
    _TENANT_LABEL = "[RÈGLE INTERNE DE L'ENTREPRISE — non légale, à ne pas confondre avec la loi]"

    @staticmethod
    def _is_tenant_match(m: Match) -> bool:
        """Un extrait est « tenant » s'il porte un tag `tenant:<id>` et/ou si
        son `source_uri` commence par `tenant://` (upload client, cf.
        `api/v1/kb.py` et `api/v1/legal.py`). Les deux signaux sont vérifiés
        car selon le chemin de retrieve (local direct vs. MissionClient), l'un
        ou l'autre peut être la seule information disponible.
        """
        if any(t == "tenant" or t.startswith("tenant:") for t in m.tags):
            return True
        return m.source_uri.startswith("tenant://")

    @classmethod
    def _format_context(cls, matches: list[Match]) -> str:
        """Sérialise les chunks RAG en bloc numéroté pour le prompt LLM.

        La numérotation [1], [2]… reste continue et inchangée quelle que soit
        l'origine du chunk : seule la PRÉSENTATION distingue un extrait TENANT
        (documents internes du client, non légaux) d'un extrait du corpus de
        référence (loi, convention collective, communs). Aucune repondération
        ni exclusion — le retrieval en amont n'est pas touché.
        """
        if not matches:
            return "--- Textes de référence ---\n(aucun extrait disponible)"
        lines = ["--- Textes de référence ---"]
        for i, m in enumerate(matches, start=1):
            src = m.source_id or m.source_uri.rsplit("/", 1)[-1]
            header = f"\n[{i}] source={src} chunk={m.chunk_index} similarité={m.similarity:.2f}"
            if cls._is_tenant_match(m):
                header += f"\n{cls._TENANT_LABEL}"
            lines.append(header)
            lines.append(m.content.strip())
        return "\n".join(lines)
