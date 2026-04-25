"""Offline tests for ranker pure functions."""
from __future__ import annotations

import pytest
from app.schemas.judge import JudgeResult
from app.services.ranker import composite_final_score
from pydantic import ValidationError


class TestComposite:
    def test_default_weights_balanced_scores(self) -> None:
        assert composite_final_score(80, 70, 0.6, 0.4) == round(80 * 0.6 + 70 * 0.4, 2)

    def test_match_only_no_interest(self) -> None:
        # No interest -> falls back to raw match
        assert composite_final_score(75, None, 0.6, 0.4) == 75.0

    def test_interest_only_no_match(self) -> None:
        assert composite_final_score(None, 60, 0.6, 0.4) == 60.0

    def test_both_none_returns_none(self) -> None:
        assert composite_final_score(None, None, 0.6, 0.4) is None

    def test_weight_swap_changes_order(self) -> None:
        a_match, a_interest = 90, 30
        b_match, b_interest = 50, 90
        # match-heavy weights: a wins
        a_w = composite_final_score(a_match, a_interest, 0.8, 0.2)
        b_w = composite_final_score(b_match, b_interest, 0.8, 0.2)
        assert a_w > b_w
        # interest-heavy weights: b wins
        a_w2 = composite_final_score(a_match, a_interest, 0.2, 0.8)
        b_w2 = composite_final_score(b_match, b_interest, 0.2, 0.8)
        assert b_w2 > a_w2


class TestJudgeSchema:
    def test_minimal_valid(self) -> None:
        r = JudgeResult.model_validate({"interest_score": 75})
        assert r.interest_score == 75
        assert r.signals == []

    def test_full_payload(self) -> None:
        r = JudgeResult.model_validate({
            "interest_score": 82,
            "signals": ["asked about team size", "available next week"],
            "concerns": ["wants remote only"],
            "reasoning": "Engaged early; soft commit on availability.",
        })
        assert r.interest_score == 82
        assert "asked about team size" in r.signals

    def test_rejects_score_above_100(self) -> None:
        with pytest.raises(ValidationError):
            JudgeResult.model_validate({"interest_score": 150})

    def test_rejects_negative(self) -> None:
        with pytest.raises(ValidationError):
            JudgeResult.model_validate({"interest_score": -10})
