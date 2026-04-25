from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field


class JudgeResult(BaseModel):
    """Strict shape returned by the Judge LLM."""

    model_config = ConfigDict(strict=True, extra="ignore")

    interest_score: int = Field(ge=0, le=100)
    signals: list[str] = Field(default_factory=list, max_length=10)
    concerns: list[str] = Field(default_factory=list, max_length=10)
    reasoning: str = Field(default="", max_length=1000)
