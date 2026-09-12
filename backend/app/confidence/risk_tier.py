from __future__ import annotations

from typing import Literal

from app.schemas.recommendation import ConfidenceBand

UndercutRiskTier = Literal["safe", "marginal", "optimal", "critical"]

_UNCERTAINTY_PENALTY = {"low": 0.0, "medium": 0.15, "high": 0.3}


def score_undercut_risk_tier(
    *,
    rival_cover_stop_probability: float,
    confidence: ConfidenceBand,
) -> UndercutRiskTier:
    """Combine rival cover-stop probability with confidence uncertainty into a discrete tier.

    Tier order (ascending severity) mirrors the PRD's Safe/Marginal/Optimal/Critical labels.
    """
    risk_score = rival_cover_stop_probability + _UNCERTAINTY_PENALTY[confidence.uncertainty]
    if risk_score < 0.25:
        return "safe"
    if risk_score < 0.5:
        return "marginal"
    if risk_score < 0.75:
        return "optimal"
    return "critical"
