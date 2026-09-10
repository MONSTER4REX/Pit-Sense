from __future__ import annotations

from statistics import fmean


def cover_stop_probability(
	*,
	rival_tyre_age: int,
	observed_response_laps: list[int],
	pit_window_lap: int,
) -> float:
	"""Estimate response likelihood from observed rival response timing, not random noise."""
	if rival_tyre_age < 0 or pit_window_lap < 1:
		raise ValueError("Tyre age and pit-window lap must be valid")
	if not observed_response_laps:
		return min(1.0, rival_tyre_age / 30.0)
	typical_response = fmean(observed_response_laps)
	age_pressure = min(1.0, rival_tyre_age / max(1.0, typical_response))
	timing_pressure = 1.0 if pit_window_lap <= typical_response else max(0.0, typical_response / pit_window_lap)
	return round(min(1.0, 0.5 * age_pressure + 0.5 * timing_pressure), 4)
