"""Schémas Pydantic exposés par l'API publique."""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field

from zolaos.agents.router import Pole


class QueryRequest(BaseModel):
    query: str = Field(min_length=1, max_length=8000)
    country_hint: str | None = Field(default=None, pattern=r"^[a-z]{2}$")
    tenant_id: str | None = Field(default=None, max_length=64)


class RoutingInfo(BaseModel):
    pole: Pole
    confidence: float
    language: Literal["fr", "ln", "kg", "other"]
    country_hint: str
    complexity: Literal["simple", "moderate", "complex"]
    warning: str | None = None


class PlanStepOut(BaseModel):
    id: int
    description: str
    agent: Pole
    depends_on: list[int]
    expected_output: str


class PlanOut(BaseModel):
    needs_planning: bool
    rationale: str
    steps: list[PlanStepOut]


class AgentResponseOut(BaseModel):
    pole: Pole
    content: str
    model: str
    duration_seconds: float


class QueryResponse(BaseModel):
    request_id: uuid.UUID
    decision: RoutingInfo
    plan: PlanOut | None
    responses: list[AgentResponseOut]
    duration_seconds: float


class AgentInfo(BaseModel):
    pole: Pole
    label: str
    enabled: bool
    phase: int


class AgentsListResponse(BaseModel):
    agents: list[AgentInfo]
    server_time: datetime
