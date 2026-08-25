"""Verify cosine similarity makes the interest term magnitude-invariant.

A flat/generalist user (all six RIASEC dimensions equal) should see the exact
same similarity scores regardless of their overall rating magnitude.  This
catches the old Euclidean-distance bug where a user who rates everything ~70
would get different rankings than one who rates everything ~30.

Note: a flat user vector will NOT have identical similarity to every role,
because the role vectors point in genuinely different directions.  That
directional difference is correct — the invariance guarantee is that the
scores don't change when the user's *magnitude* changes but the *direction*
stays flat.
"""

import pytest

from app.catalog.assessment_loader import get_assessment_catalog
from app.matching.models import MatchProfile, WorkStyleResponses
from app.matching.service import match_profile


def _flat_profile(magnitude: int) -> MatchProfile:
    """Build a profile where every interest question gets the same score."""
    assessment = get_assessment_catalog()
    return MatchProfile(
        interest_responses={q.id: magnitude for q in assessment.interest_questions},
        skill_confidence={},
        work_style_responses=WorkStyleResponses(
            analytical=3, creative=3, collaborative=3, structured=3, systems_oriented=3,
        ),
    )


@pytest.mark.parametrize("magnitude", [2, 3, 4, 5])
def test_flat_profile_interest_scores_are_magnitude_invariant(magnitude: int) -> None:
    """Scores at any non-degenerate magnitude must equal the baseline (magnitude 2)."""
    baseline = match_profile(_flat_profile(2))
    result = match_profile(_flat_profile(magnitude))

    baseline_scores = [r.score_breakdown.interest_alignment for r in baseline.recommendations]
    result_scores = [r.score_breakdown.interest_alignment for r in result.recommendations]

    assert baseline_scores == result_scores, (
        f"Interest scores should be identical at magnitude {magnitude} and magnitude 2, "
        f"but got {result_scores} vs {baseline_scores}"
    )


def test_flat_profiles_at_different_magnitudes_produce_the_same_ranking() -> None:
    """Magnitudes 2, 3, and 5 should all produce exactly the same role ranking."""
    rankings = []
    for magnitude in (2, 3, 5):
        result = match_profile(_flat_profile(magnitude))
        rankings.append([r.role_id for r in result.recommendations])

    assert rankings[0] == rankings[1] == rankings[2], (
        f"Ranking should be magnitude-invariant but got:\n"
        f"  mag 2: {rankings[0]}\n  mag 3: {rankings[1]}\n  mag 5: {rankings[2]}"
    )


def test_flat_profile_interest_scores_are_close_across_roles() -> None:
    """At each magnitude, the spread across all roles should be small (< 5 points).

    A perfectly flat user vector has a slightly different angle to each
    non-flat role vector, so the scores are not identical — but they should
    be close, confirming no single role dominates by construction.
    """
    for magnitude in (2, 3, 5):
        result = match_profile(_flat_profile(magnitude))
        scores = [r.score_breakdown.interest_alignment for r in result.recommendations]
        spread = max(scores) - min(scores)
        assert spread < 5.0, (
            f"At magnitude {magnitude} the interest-score spread was {spread:.2f} "
            f"(scores: {scores}), expected < 5.0"
        )


def test_degenerate_flat_profile_at_magnitude_one_returns_zero() -> None:
    """Magnitude 1 maps to a zero vector after normalization; similarity should be 0."""
    result = match_profile(_flat_profile(1))
    interest_scores = [r.score_breakdown.interest_alignment for r in result.recommendations]
    assert all(score == 0.0 for score in interest_scores), (
        f"Zero-vector user should get 0.0 interest similarity for all roles, got {interest_scores}"
    )
