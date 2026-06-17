"""Métriques d'évaluation pour les sous-agents RAG.

Métriques calculées par cas :
  - `case_passed`           : bool global (toutes les assertions OK)
  - `expected_kw_hit_rate`  : fraction de keywords attendus présents dans la réponse
  - `forbidden_kw_hit`      : un mot interdit est apparu (= échec critique)
  - `citation_precision`    : fraction des citations attendues effectivement présentes
  - `citation_recall`       : fraction des citations attendues couvertes
  - `refusal_correct`       : si must_refuse=true, vérifie qu'il y a bien refus
  - `latency_seconds`       : temps de l'appel agent
  - `failure_reasons`       : liste textuelle des assertions échouées

Métriques agrégées sur un dataset (cf. CaseReport.aggregate) :
  - taux de réussite global, taux par sévérité
  - hallucination_rate (% de cas avec citations attendues non couvertes)
  - p50/p95 de latence
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field

from zolaos.agents.rag_agent import RAGAgentResponse
from zolaos.eval.dataset import EvalCase

# Phrases qui signalent un refus de l'agent (pour valider `must_refuse=true`).
_REFUSAL_MARKERS = [
    r"je ne sais pas",
    r"je ne peux pas répondre",
    r"information.{0,30}n'est pas",
    r"sources.{0,40}ne couvrent pas",
    r"consulter un expert",
    r"hors\s+(?:de\s+)?(?:mon|notre)\s+périmètre",
    r"insufficientcontexterror",
]
_REFUSAL_RE = re.compile("|".join(_REFUSAL_MARKERS), re.IGNORECASE)


@dataclass
class CaseReport:
    """Résultat d'évaluation d'un cas."""

    case_id: str
    severity: str
    passed: bool
    latency_seconds: float
    expected_kw_hit_rate: float = 0.0
    forbidden_kw_hit: bool = False
    citation_precision: float = 0.0
    citation_recall: float = 0.0
    refusal_correct: bool = True
    failure_reasons: list[str] = field(default_factory=list)
    raw_response_preview: str = ""

    @property
    def summary(self) -> str:
        status = "✓" if self.passed else "✗"
        return (
            f"[{status}] {self.case_id} ({self.severity}) "
            f"kw={self.expected_kw_hit_rate:.0%} "
            f"cit.precision={self.citation_precision:.0%} "
            f"cit.recall={self.citation_recall:.0%} "
            f"latency={self.latency_seconds:.2f}s"
        )


def _has_refusal_pattern(text: str) -> bool:
    return bool(_REFUSAL_RE.search(text or ""))


def _keyword_hits(text: str, keywords: list[str]) -> tuple[int, int]:
    """(hits, total) — insensible à la casse, match littéral simple."""
    if not keywords:
        return 0, 0
    lower = text.lower()
    hits = sum(1 for kw in keywords if kw.lower() in lower)
    return hits, len(keywords)


def _citation_match(case_citations: list, response: RAGAgentResponse) -> tuple[int, int]:
    """(matched, expected) — citation attendue OK si :
    - source_id ou source_uri correspond à un match du retrieve, OU
    - article apparaît textuellement dans la réponse générée (insensible à la casse).
    """
    if not case_citations:
        return 0, 0
    response_text_lower = (response.content or "").lower()
    response_sources = {(m.source_id, m.source_uri) for m in response.matches}
    matched = 0
    for cit in case_citations:
        # match par source_id ou source_uri
        if (cit.source_id and any(cit.source_id == sid for sid, _ in response_sources)) or (
            cit.source_uri and any(cit.source_uri == suri for _, suri in response_sources)
        ):
            matched += 1
            continue
        # ou bien : article cité textuellement
        if cit.article and cit.article.lower() in response_text_lower:
            matched += 1
    return matched, len(case_citations)


def evaluate_case(
    case: EvalCase,
    response: RAGAgentResponse | None,
    *,
    refused: bool = False,
    latency_seconds: float = 0.0,
) -> CaseReport:
    """Compare un cas attendu à la réponse réelle d'un agent. Si l'agent a
    levé InsufficientContextError, passer `refused=True` et `response=None`."""
    report = CaseReport(
        case_id=case.id,
        severity=case.severity,
        passed=True,
        latency_seconds=latency_seconds,
    )

    # Cas où on s'attend à un refus
    if case.must_refuse:
        ok = refused or (response is not None and _has_refusal_pattern(response.content))
        report.refusal_correct = ok
        if not ok:
            report.passed = False
            report.failure_reasons.append(
                "must_refuse=true mais l'agent a répondu sans refuser"
            )
        # On ne calcule pas le reste (mots-clés / citations) si on attendait un refus
        if response is not None:
            report.raw_response_preview = (response.content or "")[:200]
        return report

    # Cas normal : on attend une réponse exploitable
    if response is None or refused:
        report.passed = False
        report.failure_reasons.append(
            "must_refuse=false mais l'agent a refusé (InsufficientContextError)"
        )
        return report

    text = response.content or ""
    report.raw_response_preview = text[:200]

    # Keywords attendus
    if case.expected_keywords:
        hits, total = _keyword_hits(text, case.expected_keywords)
        report.expected_kw_hit_rate = hits / total
        if hits < total:
            missing = [kw for kw in case.expected_keywords if kw.lower() not in text.lower()]
            report.failure_reasons.append(f"keywords attendus manquants: {missing}")
            report.passed = False

    # Keywords interdits
    if case.forbidden_keywords:
        forbidden_hit = any(kw.lower() in text.lower() for kw in case.forbidden_keywords)
        report.forbidden_kw_hit = forbidden_hit
        if forbidden_hit:
            present = [kw for kw in case.forbidden_keywords if kw.lower() in text.lower()]
            report.failure_reasons.append(f"keywords interdits présents: {present}")
            report.passed = False

    # Citations
    if case.expected_citations:
        matched, expected = _citation_match(case.expected_citations, response)
        report.citation_recall = matched / expected if expected else 1.0
        # precision approximative : matched / nb citations dans la réponse (ici len(response.citations))
        n_resp_citations = len(response.citations)
        report.citation_precision = (matched / n_resp_citations) if n_resp_citations else 0.0
        if matched < expected:
            report.failure_reasons.append(
                f"citations attendues manquantes ({matched}/{expected})"
            )
            report.passed = False

    return report


@dataclass
class DatasetReport:
    """Agrégation des résultats sur un dataset complet."""

    dataset_name: str
    cases: list[CaseReport]

    @property
    def passed(self) -> int:
        return sum(1 for c in self.cases if c.passed)

    @property
    def total(self) -> int:
        return len(self.cases)

    @property
    def pass_rate(self) -> float:
        return self.passed / self.total if self.total else 0.0

    @property
    def latency_p50(self) -> float:
        vals = sorted(c.latency_seconds for c in self.cases)
        return vals[len(vals) // 2] if vals else 0.0

    @property
    def latency_p95(self) -> float:
        vals = sorted(c.latency_seconds for c in self.cases)
        if not vals:
            return 0.0
        idx = max(0, int(len(vals) * 0.95) - 1)
        return vals[idx]

    @property
    def hallucination_rate(self) -> float:
        """Cas où l'agent a répondu mais sans couvrir les citations attendues."""
        critical = [c for c in self.cases if c.citation_recall < 1.0 and not c.forbidden_kw_hit]
        return len(critical) / self.total if self.total else 0.0

    def by_severity(self) -> dict[str, tuple[int, int]]:
        out: dict[str, tuple[int, int]] = {}
        for sev in ("critical", "high", "medium", "low"):
            subset = [c for c in self.cases if c.severity == sev]
            if subset:
                out[sev] = (sum(1 for c in subset if c.passed), len(subset))
        return out

    def render(self) -> str:
        lines = [f"=== Dataset: {self.dataset_name} ===", ""]
        for c in self.cases:
            lines.append(c.summary)
            for fr in c.failure_reasons:
                lines.append(f"     · {fr}")
        lines.append("")
        lines.append(
            f"Pass rate     : {self.passed}/{self.total} ({self.pass_rate:.0%})"
        )
        lines.append(f"Latency p50/p95: {self.latency_p50:.2f}s / {self.latency_p95:.2f}s")
        lines.append(f"Hallucination : {self.hallucination_rate:.0%}")
        for sev, (ok, tot) in self.by_severity().items():
            lines.append(f"  · {sev:<8}: {ok}/{tot}")
        return "\n".join(lines)
