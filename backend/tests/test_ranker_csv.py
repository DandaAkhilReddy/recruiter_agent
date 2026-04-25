"""Offline tests for ranker.shortlist_to_csv — well-formed CSV output."""
from __future__ import annotations

import csv
import io
from uuid import uuid4

import pytest
from app.schemas.score import CandidateBrief
from app.schemas.shortlist import ShortlistItem
from app.services.ranker import shortlist_to_csv


def _make_item(rank: int, *, match: float | None = 80.0, interest: float | None = 70.0) -> ShortlistItem:
    return ShortlistItem(
        rank=rank,
        candidate=CandidateBrief(
            id=uuid4(),
            name=f"Candidate {rank}",
            title="Senior Backend Engineer",
            yoe=7,
            seniority="senior",
            skills=["python", "fastapi"],
            location="Remote (US)",
            remote_ok=True,
        ),
        match_score=match,
        interest_score=interest,
        final_score=(match * 0.6 + interest * 0.4) if (match is not None and interest is not None) else match,
        breakdown={"skill": 85.0, "experience": 80.0, "domain": 70.0, "location": 90.0},
        match_justifications={
            "skill": "Strong overlap",
            "experience": "Hits target",
            "domain": "Adjacent",
            "location": "Remote ok",
        },
        interest_signals=["asked about team size"],
        interest_concerns=["wants higher comp"],
        interest_reasoning="Engaged but cautious.",
    )


async def _collect_csv(items: list[ShortlistItem]) -> str:
    chunks: list[bytes] = []
    async for chunk in shortlist_to_csv(items):
        chunks.append(chunk)
    return b"".join(chunks).decode("utf-8")


@pytest.mark.asyncio
async def test_csv_header_and_rows_are_well_formed() -> None:
    items = [_make_item(i + 1) for i in range(3)]
    text = await _collect_csv(items)
    reader = csv.reader(io.StringIO(text))
    rows = list(reader)
    assert len(rows) == 4  # 1 header + 3 data
    header = rows[0]
    # Spot-check the columns we promise downstream
    for required in ("rank", "name", "match_score", "interest_score", "final_score", "skill", "interest_signals"):
        assert required in header
    # Each data row has the same column count as the header
    for r in rows[1:]:
        assert len(r) == len(header)


@pytest.mark.asyncio
async def test_csv_handles_partial_data_row() -> None:
    """Missing interest_score must yield empty cell, not 'None'."""
    item = _make_item(1, match=82.5, interest=None)
    text = await _collect_csv([item])
    reader = csv.DictReader(io.StringIO(text))
    row = next(reader)
    assert row["match_score"] == "82.5"
    assert row["interest_score"] == ""
    assert row["final_score"] == "82.5"  # falls back to raw match


@pytest.mark.asyncio
async def test_csv_signals_concerns_join_with_semicolon() -> None:
    item = _make_item(1)
    text = await _collect_csv([item])
    reader = csv.DictReader(io.StringIO(text))
    row = next(reader)
    assert row["interest_signals"] == "asked about team size"
    assert row["interest_concerns"] == "wants higher comp"
