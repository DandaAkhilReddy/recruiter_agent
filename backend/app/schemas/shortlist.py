from __future__ import annotations

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

from app.schemas.score import CandidateBrief, DimKey


class ShortlistItem(BaseModel):
    model_config = ConfigDict(extra="forbid")

    rank: int
    candidate: CandidateBrief
    match_score: float | None
    interest_score: float | None
    final_score: float | None
    breakdown: dict[DimKey, float] | None
    match_justifications: dict[str, str] | None
    interest_signals: list[str] | None
    interest_concerns: list[str] | None
    interest_reasoning: str | None


class ShortlistOut(BaseModel):
    model_config = ConfigDict(extra="forbid")

    job_id: UUID
    match_weight: float
    interest_weight: float
    total: int
    items: list[ShortlistItem]


class TranscriptMessage(BaseModel):
    model_config = ConfigDict(extra="forbid")

    role: str
    content: str
    turn_index: int
    created_at: datetime


class ConversationDetailOut(BaseModel):
    model_config = ConfigDict(extra="forbid")

    job_id: UUID
    candidate: CandidateBrief
    status: str
    started_at: datetime
    completed_at: datetime | None
    interest_score: float | None
    interest_signals: list[str] | None
    interest_concerns: list[str] | None
    interest_reasoning: str | None
    messages: list[TranscriptMessage] = Field(default_factory=list)
