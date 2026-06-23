"""Chargement et validation des datasets vérité-terrain.

Format YAML attendu (cf. tests/eval/datasets/) :

```yaml
dataset:
  agent: legal.ohada           # nom du sous-agent ciblé
  module: ohada
  version: 1.0
  language: fr
  reviewer: jean-juriste       # qui a validé
  reviewed_at: 2026-05-17
cases:
  - id: ohada_001
    question: "Capital social minimum SARL OHADA ?"
    expected_pole: legal       # facultatif (utile pour test routeur)
    expected_module: ohada     # idem
    expected_citations:        # facultatif : sources qu'on s'attend à voir citées
      - source_id: AUSCGIE
        article: "Art. 311"
    expected_keywords: ["1 000 000", "capital"]  # mots qui DOIVENT apparaître
    forbidden_keywords: ["€"]                    # mots qui NE doivent PAS apparaître
    must_refuse: false                           # true = on attend un refus (sujet hors RAG)
    severity: high                               # critical | high | medium | low
```

Le dataset est validé via Pydantic à l'ouverture — un format incorrect lève
une `ValidationError` claire avant tout test.
"""

from __future__ import annotations

from datetime import date, datetime
from pathlib import Path
from typing import Literal

import yaml
from pydantic import BaseModel, Field, field_validator

from zolaos.core.logging import get_logger

_log = get_logger("zolaos.eval.dataset")


class ExpectedCitation(BaseModel):
    """Citation attendue dans la réponse de l'agent."""

    source_id: str | None = None
    source_uri: str | None = None
    article: str | None = None  # ex: "Art. 311" — match approximatif dans le contenu


class EvalCase(BaseModel):
    """Un cas vérité-terrain pour évaluer un agent."""

    id: str
    question: str
    expected_pole: str | None = None
    expected_module: str | None = None
    expected_citations: list[ExpectedCitation] = Field(default_factory=list)
    expected_keywords: list[str] = Field(default_factory=list)
    forbidden_keywords: list[str] = Field(default_factory=list)
    must_refuse: bool = False
    severity: Literal["critical", "high", "medium", "low"] = "medium"
    extra_tags: list[str] = Field(default_factory=list)  # tags additionnels pour le retrieve RAG
    notes: str | None = None


class DatasetHeader(BaseModel):
    agent: str
    module: str | None = None
    version: str = "1.0"
    language: str = "fr"
    reviewer: str | None = None
    reviewed_at: str | None = None
    notes: str | None = None

    @field_validator("reviewed_at", "version", mode="before")
    @classmethod
    def coerce_to_str(cls, v: object) -> str | None:
        # PyYAML parse `2026-05-17` en datetime.date et `1.0` en float ;
        # on accepte les deux et on stringifie pour éviter ValidationError.
        if v is None:
            return None
        if isinstance(v, date | datetime):
            return v.isoformat()
        return str(v)


class EvalDataset(BaseModel):
    """Un jeu de données vérité-terrain pour un agent."""

    dataset: DatasetHeader
    cases: list[EvalCase] = Field(min_length=1)

    @classmethod
    def from_yaml(cls, path: str | Path) -> EvalDataset:
        p = Path(path)
        if not p.exists():
            raise FileNotFoundError(p)
        raw = yaml.safe_load(p.read_text(encoding="utf-8"))
        ds = cls.model_validate(raw)
        _log.info(
            "eval.dataset.loaded",
            path=str(p),
            agent=ds.dataset.agent,
            cases=len(ds.cases),
            version=ds.dataset.version,
        )
        return ds
