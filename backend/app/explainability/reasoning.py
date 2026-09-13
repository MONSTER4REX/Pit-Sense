"""Plain-language reasoning for a recommendation (PRD FR-8 / FR-10).

The sentence a strategist reads must be generated from the same numbers the
engine actually computed. The frontend must never author its own explanation for
a decision it did not make, so the text is built here, next to the factors.

Unmeasured factors are named as unmeasured. A recommendation that rests on thin
data says so in the same sentence that delivers it.
"""
from __future__ import annotations

from app.schemas.recommendation import ConfidenceBand, ExplainabilityBreakdown

# Cover-stop probability above which the rival is described as likely to respond.
LIKELY_COVER_PROBABILITY = 0.5


def describe_recommendation(
	*,
	action: str,
	pit_lap: int,
	start_lap: int,
	explainability: ExplainabilityBreakdown,
	confidence: ConfidenceBand,
) -> str:
	parts: list[str] = []

	if action == "pit_now":
		lead = (
			f"The shortest projected race-time path stops on lap {pit_lap}"
			if pit_lap != start_lap
			else "The shortest projected race-time path stops now"
		)
		parts.append(
			f"{lead}, paying {explainability.pit_lane_time_loss:.1f}s of pit-lane loss"
			+ (
				f" plus {explainability.traffic_rejoin_risk:.1f}s of projected rejoin traffic"
				if explainability.traffic_rejoin_risk > 0
				else ""
			)
			+ "."
		)
	else:
		parts.append(
			f"The shortest projected race-time path stays out past lap {start_lap}"
			+ (
				f", with {explainability.tyre_delta_risk:.1f}s of accumulated tyre degradation on the path"
				if explainability.tyre_delta_risk > 0
				else ""
			)
			+ "."
		)

	if explainability.measured.get("rival_cover_stop"):
		probability = explainability.rival_cover_stop_probability
		verdict = "likely" if probability >= LIKELY_COVER_PROBABILITY else "unlikely"
		parts.append(
			f"The rival is {verdict} to cover this window ({probability * 100:.0f}% from its recorded stops)."
		)

	unmeasured = [name for name, measured in explainability.measured.items() if not measured]
	if unmeasured:
		readable = ", ".join(name.replace("_", " ") for name in unmeasured)
		parts.append(f"Not measurable from this lap's data: {readable}.")

	parts.append(
		f"Confidence {confidence.lower * 100:.0f}-{confidence.upper * 100:.0f}% "
		f"({confidence.uncertainty} uncertainty)."
	)
	return " ".join(parts)
