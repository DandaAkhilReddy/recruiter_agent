"""Unit tests for pure helpers in scripts/seed_candidates.py.

Live AOAI calls and the DB insert are not exercised here — those are validated
by running the script against a local Postgres + AOAI deployment.
"""
from __future__ import annotations

from collections import Counter

from scripts.seed_candidates import (
    INTEREST_BUCKETS,
    _archetype_for_index,
    _scale_archetype_counts,
    _twist_motivations,
)


def test_scale_archetype_counts_sums_to_total() -> None:
    for total in [50, 100, 250, 500, 1000]:
        scaled = _scale_archetype_counts(total)
        assert sum(c for _, _, c in scaled) == total


def test_archetype_distribution_matches_buckets_within_5pct() -> None:
    total = 1000
    counts = Counter(_archetype_for_index(i, total) for i in range(total))
    for arch, expected_frac in INTEREST_BUCKETS.items():
        actual = counts[arch] / total
        assert abs(actual - expected_frac) < 0.05, f"{arch}: {actual} vs {expected_frac}"


def test_twist_motivations_appends_archetype_flavor() -> None:
    base = "I want to grow my system design skills"
    for arch in ("strong", "medium", "weak", "wildcard"):
        out = _twist_motivations(base, arch)
        assert out.startswith(base)
        assert len(out) > len(base) + 5
