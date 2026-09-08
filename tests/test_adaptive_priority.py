"""Boundary and weighting tests for the Module 13.2 priority calculator."""

from __future__ import annotations

import math

import pytest

from app.services.adaptive_priority import calculate_priority


def test_all_zero_inputs_return_zero() -> None:
    assert calculate_priority(0, 0, 0, 0) == 0


def test_all_maximum_inputs_return_hundred() -> None:
    assert calculate_priority(100, 100, 100, 100) == 100


def test_calculates_configured_weighted_score() -> None:
    assert calculate_priority(100, 0, 0, 0) == 25
    assert calculate_priority(0, 100, 0, 0) == 35
    assert calculate_priority(0, 0, 100, 0) == 25
    assert calculate_priority(0, 0, 0, 100) == 15


@pytest.mark.parametrize("invalid_score", [-1, 101])
def test_rejects_scores_outside_normalized_range(invalid_score: int) -> None:
    with pytest.raises(ValueError):
        calculate_priority(invalid_score, 0, 0, 0)


@pytest.mark.parametrize("invalid_score", [True, "50", math.nan, math.inf])
def test_rejects_non_numeric_or_non_finite_scores(invalid_score: object) -> None:
    with pytest.raises(ValueError):
        calculate_priority(invalid_score, 0, 0, 0)


def test_accepts_fractional_component_scores() -> None:
    assert calculate_priority(12.5, 25.0, 37.5, 50.0) == pytest.approx(28.75)
