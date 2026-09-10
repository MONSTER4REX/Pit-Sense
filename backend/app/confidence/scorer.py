from __future__ import annotations

from typing import Iterable

from app.schemas.recommendation import ConfidenceBand


def score_confidence(*, uncertainty_events: Iterable[str] = ()) -> ConfidenceBand:
    events = {event.lower() for event in uncertainty_events}
    width = 0.08 + 0.12 * len(events.intersection({"safety_car", "vsc", "rain"}))
    midpoint = max(0.0, min(1.0, 0.86 - width / 2))
    lower = max(0.0, midpoint - width / 2)
    upper = min(1.0, midpoint + width / 2)
    level = "high" if width <= 0.08 else "medium" if width <= 0.16 else "high"
    if width > 0.16:
        level = "high"
    return ConfidenceBand(lower=lower, upper=upper, uncertainty=level)