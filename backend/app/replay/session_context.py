"""Per-lap view of a loaded historical session.

Everything the engine needs at a given lap is read out of the two loaded
RaceStates. Nothing is defaulted to a stand-in value: where the session has no
data for a field, the context reports the absence and the engine treats that
factor as unmeasured.
"""
from __future__ import annotations

from dataclasses import dataclass, field

from app.schemas.race_state import LapState, RaceState


def _lap_row(laps: list[LapState], lap_number: int) -> LapState | None:
	return next((item for item in laps if item.lap_number == lap_number), None)


def _compound_at(laps: list[LapState], lap_number: int) -> str | None:
	row = _lap_row(laps, lap_number)
	if row and row.compound:
		return row.compound
	previous = [item for item in laps if item.lap_number <= lap_number and item.compound]
	return previous[-1].compound if previous else None


def _tyre_age_at(laps: list[LapState], lap_number: int) -> int | None:
	row = _lap_row(laps, lap_number)
	if row and row.tyre_life is not None:
		return row.tyre_life
	return None


@dataclass(frozen=True)
class SessionReplayContext:
	p1: RaceState
	p2: RaceState
	end_lap: int
	uncertainty_events: tuple[str, ...] = ()
	# Field median lap time per lap number, from the same session. See
	# app.tyre_model.field_pace for why this is what makes wear measurable.
	field_median_lap_times: dict[int, float] = field(default_factory=dict)


def lap_context(ctx: SessionReplayContext, lap_number: int) -> dict[str, object]:
	"""Assemble the real state of our car (P2) and the rival (P1) at one lap."""
	p2_row = _lap_row(ctx.p2.laps, lap_number)
	p1_row = _lap_row(ctx.p1.laps, lap_number)

	compound = _compound_at(ctx.p2.laps, lap_number)
	tyre_age = _tyre_age_at(ctx.p2.laps, lap_number)
	rival_tyre_age = _tyre_age_at(ctx.p1.laps, lap_number)

	# Gap to the car ahead, only where both cars have a recorded gap to the
	# leader on this lap and the rival is genuinely ahead.
	gaps_to_ahead: list[float] = []
	if (
		p2_row
		and p1_row
		and p2_row.position is not None
		and p1_row.position is not None
		and p2_row.position > p1_row.position
		and p2_row.gap_to_leader_seconds is not None
		and p1_row.gap_to_leader_seconds is not None
	):
		gap = p2_row.gap_to_leader_seconds - p1_row.gap_to_leader_seconds
		if gap > 0:
			gaps_to_ahead = [gap]

	# The rival's cover-stop behaviour is read from the stops it has actually
	# made by this lap, so the probability moves with the race rather than being
	# fixed by a preset list of response laps.
	rival_pit_laps = tuple(
		stop.lap_number for stop in ctx.p1.pit_stops if stop.lap_number <= lap_number
	)

	# Our car's history up to this lap, for the tyre model to fit the live stint.
	history = [row for row in ctx.p2.laps if row.lap_number <= lap_number]

	return {
		"compound": compound or "UNKNOWN",
		"tyre_age": tyre_age if tyre_age is not None else 0,
		"lap_time": p2_row.lap_time_seconds if p2_row else None,
		"position": p2_row.position if p2_row else None,
		"gap_to_leader": p2_row.gap_to_leader_seconds if p2_row else None,
		"rival_tyre_age": rival_tyre_age if rival_tyre_age is not None else 0,
		"gaps_to_ahead": gaps_to_ahead,
		"distance_to_driver_ahead": gaps_to_ahead[0] if gaps_to_ahead else 0.0,
		"rival_pit_laps": rival_pit_laps,
		"lap_times": [row.lap_time_seconds for row in ctx.p2.laps if row.lap_time_seconds is not None],
		"stint_lap_numbers": tuple(row.lap_number for row in history),
		"stint_compounds": tuple(row.compound for row in history),
		"stint_tyre_ages": tuple(row.tyre_life for row in history),
		"stint_lap_times": tuple(row.lap_time_seconds for row in history),
		"field_baseline": ctx.field_median_lap_times,
	}
