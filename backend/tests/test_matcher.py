"""Offline tests for matcher pure helpers + composite formula."""
from __future__ import annotations

from uuid import uuid4

import pytest
from pydantic import ValidationError

from app.schemas.score import PerDimScore, RerankBatchResult
from app.services.matcher import WEIGHTS, composite_match_score


def test_weights_sum_to_one() -> None:
    assert sum(WEIGHTS.values()) == pytest.approx(1.0)


def test_composite_perfect_score() -> None:
    assert composite_match_score(100, 100, 100, 100) == 100.0


def test_composite_zero_score() -> None:
    assert composite_match_score(0, 0, 0, 0) == 0.0


def test_composite_skill_dominant() -> None:
    # 100 skill, 0 elsewhere → 40.0 (skill weight)
    assert composite_match_score(100, 0, 0, 0) == 40.0


def test_composite_mixed() -> None:
    # 80*0.40 + 70*0.25 + 60*0.20 + 90*0.15
    expected = round(80 * 0.40 + 70 * 0.25 + 60 * 0.20 + 90 * 0.15, 2)
    assert composite_match_score(80, 70, 60, 90) == expected


def test_per_dim_score_validation_clamps_to_0_100() -> None:
    with pytest.raises(ValidationError):
        PerDimScore.model_validate({
            "candidate_id": str(uuid4()),
            "skill": 150, "experience": 50, "domain": 50, "location": 50,
            "justifications": {"skill": "x", "experience": "x", "domain": "x", "location": "x"},
        })


def test_per_dim_score_rejects_negative() -> None:
    with pytest.raises(ValidationError):
        PerDimScore.model_validate({
            "candidate_id": str(uuid4()),
            "skill": -1, "experience": 50, "domain": 50, "location": 50,
            "justifications": {"skill": "x", "experience": "x", "domain": "x", "location": "x"},
        })


def test_per_dim_score_requires_justifications() -> None:
    with pytest.raises(ValidationError):
        PerDimScore.model_validate({
            "candidate_id": str(uuid4()),
            "skill": 80, "experience": 70, "domain": 60, "location": 90,
        })


def test_rerank_batch_result_empty_list_ok() -> None:
    r = RerankBatchResult.model_validate({"scores": []})
    assert r.scores == []


def test_rerank_batch_result_parses_full_payload() -> None:
    cid = str(uuid4())
    r = RerankBatchResult.model_validate({
        "scores": [
            {
                "candidate_id": cid,
                "skill": 85, "experience": 70, "domain": 60, "location": 90,
                "justifications": {
                    "skill": "Has python+postgres+aws but missing kafka",
                    "experience": "8 yoe vs 6 required",
                    "domain": "Adjacent fintech",
                    "location": "Remote ok",
                },
            }
        ]
    })
    assert len(r.scores) == 1
    assert r.scores[0].skill == 85
