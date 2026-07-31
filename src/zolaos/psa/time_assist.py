"""Saisie de temps assistée — récit libre → propositions de feuilles de temps.

Le consultant décrit sa semaine en langage naturel ; l'IA (modèle léger local)
en **extrait** des lignes de temps structurées (date, durée, activité, mission).
C'est une **PROPOSITION** : rien n'est créé — le consultant relit, corrige et
valide chaque ligne (doctrine « je propose, l'humain valide »). Les taux et
montants restent **déterministes** (figés à la création réelle selon le grade) :
l'IA ne touche jamais à l'économie, seulement à la mise en forme du récit.

Hors-RAG : pas de corpus, extraction pure du texte du consultant. Servi
localement (souveraineté). Ne lève jamais : `unavailable` si le LLM échoue ou
si sa sortie est illisible.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from datetime import date
from typing import Any

from zolaos.core.logging import get_logger
from zolaos.llm.base import GenerationOptions, Message
from zolaos.llm.factory import make_router_client

_log = get_logger("zolaos.psa.time_assist")

_MAX_SUGGESTIONS = 30
_MAX_MINUTES = 24 * 60

_SYSTEM_PROMPT = (
    "Tu assistes la saisie de temps d'un consultant de cabinet. À partir de son "
    "récit libre, EXTRAIS les lignes de temps. Réponds UNIQUEMENT par un objet JSON "
    '{"entries": [...]}. Chaque entrée : {"date": "YYYY-MM-DD" ou null, '
    '"hours": nombre > 0, "activity": "description courte", '
    '"mission_id": "<un id de la liste>" ou null, "billable": true/false}. '
    "Règles impératives : n'invente AUCUNE durée ni activité absente du récit ; si une "
    "information manque, mets null (date/mission) — ne devine pas. Choisis mission_id "
    "STRICTEMENT parmi les id fournis (jamais un id inventé). billable=true par défaut. "
    "Utilise le lundi de référence pour convertir « lundi/mardi/… » en dates ISO."
)


@dataclass
class TimeSuggestion:
    """Une ligne de temps proposée (à valider par le consultant, rien n'est créé)."""

    entry_date: str | None  # ISO YYYY-MM-DD, ou None si le récit ne le précise pas
    minutes: int
    activity: str
    billable: bool
    mission_id: str | None
    mission_label: str | None


@dataclass
class AssistOutcome:
    """Résultat d'une saisie assistée."""

    status: str  # suggested | unavailable
    suggestions: list[TimeSuggestion] = field(default_factory=list)


def _missions_block(missions: list[dict[str, str]]) -> str:
    if not missions:
        return "Aucune mission connue pour ce consultant (mission_id = null)."
    lines = "\n".join(f'- id={m["id"]} : {m["label"]}' for m in missions)
    return "Missions du consultant (choisis mission_id STRICTEMENT parmi ces id) :\n" + lines


def build_prompt(
    narrative: str, week_start: date | None, missions: list[dict[str, str]]
) -> str:
    """Assemble le message utilisateur (référence de semaine + missions + récit)."""
    wk = (
        f"Lundi de référence : {week_start.isoformat()}."
        if week_start is not None
        else "Semaine non précisée (mets date=null si le jour est ambigu)."
    )
    return (
        f"{wk}\n{_missions_block(missions)}\n\n"
        f"Récit du consultant :\n{(narrative or '').strip()}\n\n"
        "Extrais les lignes de temps au format JSON demandé."
    )


def _parse_entries(
    raw: str, valid_ids: set[str], labels: dict[str, str]
) -> list[TimeSuggestion]:
    """Parse la sortie JSON du LLM en suggestions validées (robuste, jamais confiant).

    Chaque champ est borné/validé : durée > 0 et ≤ 24 h, date ISO sinon None,
    mission_id retenu seulement s'il figure dans la liste fournie (anti-hallucination)."""
    data: Any = json.loads(raw)
    entries = data.get("entries") if isinstance(data, dict) else data
    if not isinstance(entries, list):
        return []
    out: list[TimeSuggestion] = []
    for item in entries:
        if not isinstance(item, dict):
            continue
        try:
            minutes = round(float(item.get("hours")) * 60)
        except (TypeError, ValueError):
            continue
        if minutes <= 0:
            continue
        minutes = min(minutes, _MAX_MINUTES)

        entry_date: str | None = None
        d = item.get("date")
        if isinstance(d, str) and d.strip():
            try:
                entry_date = date.fromisoformat(d.strip()[:10]).isoformat()
            except ValueError:
                entry_date = None

        activity = str(item.get("activity") or "").strip()[:1000]

        mid = item.get("mission_id")
        mid = str(mid) if (mid is not None and str(mid) in valid_ids) else None

        billable_raw = item.get("billable")
        billable = True if billable_raw is None else bool(billable_raw)

        out.append(
            TimeSuggestion(
                entry_date=entry_date,
                minutes=minutes,
                activity=activity,
                billable=billable,
                mission_id=mid,
                mission_label=labels.get(mid) if mid else None,
            )
        )
        if len(out) >= _MAX_SUGGESTIONS:
            break
    return out


async def suggest_time_entries(
    settings: Any,
    *,
    narrative: str,
    week_start: date | None = None,
    missions: list[dict[str, str]] | None = None,
) -> AssistOutcome:
    """Extrait des propositions de lignes de temps du récit (LLM local, hors-RAG).

    Ne lève jamais : `unavailable` si le LLM est indisponible ou sa sortie illisible ;
    `suggested` sinon (la liste peut être vide si rien n'a pu être extrait). Ne crée
    RIEN : c'est au consultant de valider chaque ligne."""
    missions = missions or []
    valid_ids = {str(m["id"]) for m in missions}
    labels = {str(m["id"]): m["label"] for m in missions}
    client = make_router_client(settings)
    prompt = build_prompt(narrative, week_start, missions)
    try:
        result = await client.generate(
            [
                Message(role="system", content=_SYSTEM_PROMPT),
                Message(role="user", content=prompt),
            ],
            model=settings.LLM_MODEL_BRIGADE,
            options=GenerationOptions(temperature=0.1, max_tokens=900, json_mode=True),
        )
    except Exception as exc:  # LLM local indisponible
        _log.warning("time_assist.llm_unavailable", error=str(exc))
        return AssistOutcome("unavailable")
    try:
        suggestions = _parse_entries(result.content, valid_ids, labels)
    except Exception as exc:  # sortie non-JSON / inattendue
        _log.warning("time_assist.parse_failed", error=str(exc))
        return AssistOutcome("unavailable")
    return AssistOutcome("suggested", suggestions=suggestions)
