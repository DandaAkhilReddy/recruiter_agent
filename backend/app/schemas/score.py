from __future__ import annotations

from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

DimKey = Literal["skill", "experience", "domain", "location"]


class PerDimScore(BaseModel):
    """LLM-emitted per-candidate score in a rerank batch."""

    model_config = ConfigDict(strict=True, extra="ignore")

    candidate_id: UUID
    skill: int = Field(ge=0, le=100)
    experience: int = Field(ge=0, le=100)
    domain: int = Field(ge=0, le=100)
    location: int = Field(ge=0, le=100)
    justifications: dict[DimKey, str]


class RerankBatchResult(BaseModel):
    model_config = ConfigDict(strict=True, extra="ignore")

    scores: list[PerDimScore] = Field(default_factory=list)


class CandidateBrief(BaseModel):
    """Summary of a candidate as it appears in match output."""

    model_config = ConfigDict(extra="forbid")

    id: UUID
    name: str
    title: str
    yoe: int
    seniority: str
    skills: list[str]
    location: str | None
    remote_ok: bool


class ScoreOut(BaseModel):
    """Match-only score for a single candidate (returned by POST /jobs/{id}/match)."""

    model_config = ConfigDict(extra="forbid")

    rank: int
    candidate: CandidateBrief
    match_score: float
    breakdown: dict[DimKey, float]
    justifications: dict[DimKey, str]


class MatchOut(BaseModel):
    model_config = ConfigDict(extra="forbid")

    job_id: UUID
    matched_count: int
    rerank_count: int
    top: list[ScoreOut]
