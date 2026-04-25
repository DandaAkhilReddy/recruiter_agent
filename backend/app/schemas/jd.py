from __future__ import annotations

from datetime import datetime
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

Seniority = Literal["junior", "mid", "senior", "staff", "principal"]


class JobIn(BaseModel):
    """Request body for POST /jobs."""

    model_config = ConfigDict(strict=True, extra="forbid")

    raw_text: str = Field(min_length=20, max_length=20_000)


class ParsedJD(BaseModel):
    """Strict structured representation of a job description.

    Returned by the JD parser LLM (gpt-4o, JSON mode). Used for matching.
    """

    model_config = ConfigDict(strict=True, extra="ignore")

    title: str = Field(min_length=1, max_length=200)
    seniority: Seniority
    min_yoe: int = Field(ge=0, le=40)
    must_have_skills: list[str] = Field(default_factory=list, max_length=30)
    nice_to_have: list[str] = Field(default_factory=list, max_length=30)
    domain: str | None = Field(default=None, max_length=200)
    location_pref: str | None = Field(default=None, max_length=200)
    remote_ok: bool = True


class JobOut(BaseModel):
    """Response body for POST /jobs and GET /jobs/{id}."""

    model_config = ConfigDict(extra="forbid")

    id: UUID
    title: str | None
    seniority: str | None
    min_yoe: int | None
    must_have_skills: list[str]
    nice_to_have: list[str]
    domain: str | None
    location_pref: str | None
    remote_ok: bool
    status: str
    created_at: datetime
