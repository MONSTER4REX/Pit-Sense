"""Confidence banding (PRD FR-19 / FR-20).

Every recommendation carries a band, and the band widens as real uncertainty
rises. Two things widen it:

	- Race conditions: a safety car, VSC, or rain makes the next laps less
	  predictable, which is the explicit FR-20 requirement.
	- Missing measurements: a recommendation resting on a factor that could not
	  be measured is genuinely less certain, and says so.

The band is reported with the reasons that set it, so a wide band is never just
an unexplained number on screen.
"""
from __future__ import annotations

from typing import Iterable, Mapping

from app.schemas.recommendation import ConfidenceBand

# Band width with everything measured and the race running green.
BASE_WIDTH = 0.08
# Added width per active shock condition (FR-20).
WIDTH_PER_SHOCK = 0.12
# Added width per factor the engine could not measure from session data.
WIDTH_PER_UNMEASURED_FACTOR = 0.10
# Centre of the band under green-flag, fully-measured conditions.
BASE_MIDPOINT = 0.86

SHOCK_EVENTS = {"safety_car", "vsc", "rain"}
# Band-width boundaries between the reported uncertainty levels.
LOW_UNCERTAINTY_MAX_WIDTH = 0.10
MEDIUM_UNCERTAINTY_MAX_WIDTH = 0.22


def score_confidence(
	*,
	uncertainty_events: Iterable[str] = (),
	measured_factors: Mapping[str, bool] | None = None,
) -> ConfidenceBand:
	events = {event.lower() for event in uncertainty_events}
	active_shocks = sorted(events.intersection(SHOCK_EVENTS))
	unmeasured = sorted(name for name, measured in (measured_factors or {}).items() if not measured)

	width = (
		BASE_WIDTH
		+ WIDTH_PER_SHOCK * len(active_shocks)
		+ WIDTH_PER_UNMEASURED_FACTOR * len(unmeasured)
	)
	width = min(width, 1.0)

	# A wider band is also a lower band: more uncertainty means less confidence,
	# so the midpoint falls as the band opens.
	midpoint = max(width / 2, min(1.0 - width / 2, BASE_MIDPOINT - width / 2))
	lower = max(0.0, midpoint - width / 2)
	upper = min(1.0, midpoint + width / 2)

	if width <= LOW_UNCERTAINTY_MAX_WIDTH:
		level = "low"
	elif width <= MEDIUM_UNCERTAINTY_MAX_WIDTH:
		level = "medium"
	else:
		level = "high"

	drivers = [f"{event.replace('_', ' ')} active" for event in active_shocks]
	drivers += [f"{name.replace('_', ' ')} not measurable from session data" for name in unmeasured]

	return ConfidenceBand(lower=lower, upper=upper, uncertainty=level, drivers=drivers)
