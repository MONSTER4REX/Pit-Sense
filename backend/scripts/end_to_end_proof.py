"""End-to-end proof run against a real FastF1 race (PRD 5.A, 5.D, 5.E, 5.F, 5.H, 5.I).

	python -m scripts.end_to_end_proof "Azerbaijan Grand Prix" 2024

Drives the real API surface the way the UI does and prints what actually comes
back, so each PRD claim can be checked against output rather than taken on faith:

	5.A  recommendation, confidence, and factors differ across laps
	5.D  P1 and P2 are the race's real finishers
	5.E  the same shock at different laps produces different output
	5.F  the opponent's post-fork path is computed, not replayed
	5.H  re-optimisation fires more than once, with stated reasons
	5.I  a final historical-vs-projected comparison with its assumptions
"""
from __future__ import annotations

import sys
from pathlib import Path
from time import perf_counter

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.engine.reoptimizer import optimize_strategy  # noqa: E402
from app.ingestion.fastf1_client import DEFAULT_CACHE_DIR, load_historical_session  # noqa: E402
from app.replay.session_context import SessionReplayContext, lap_context  # noqa: E402
from app.replay.shock_events import ShockEventType  # noqa: E402
from app.simulation.engine import SimulationEngine  # noqa: E402


def _inputs(ctx: SessionReplayContext, lap: int) -> dict:
	context = lap_context(ctx, lap)
	return {
		"current_compound": str(context["compound"]),
		"current_tyre_age": int(context["tyre_age"]),
		"lap_time_seconds": list(context["lap_times"]) or [90.0, 90.0],
		"rival_pit_laps": tuple(context["rival_pit_laps"]),
		"rival_tyre_age": int(context["rival_tyre_age"]),
		"cars_ahead_gaps_seconds": list(context["gaps_to_ahead"]) or None,
		"stint_lap_numbers": tuple(context["stint_lap_numbers"]),
		"stint_compounds": tuple(context["stint_compounds"]),
		"stint_tyre_ages": tuple(context["stint_tyre_ages"]),
		"stint_lap_times": tuple(context["stint_lap_times"]),
	}


def main(event: str, year: int) -> int:
	session = load_historical_session(year, event, cache_dir=str(DEFAULT_CACHE_DIR))
	engine = SimulationEngine(session.p1, session.p2)
	ctx = SessionReplayContext(p1=session.p1, p2=session.p2, end_lap=engine.end_lap)

	print(f"=== {year} {event} ===")
	print("[5.D] Real finishers from FastF1 session results")
	print(f"  P1 (opponent) : {session.p1_name} ({session.p1.driver}), {session.p1_team}")
	print(f"  P2 (our car)  : {session.p2_name} ({session.p2.driver}), {session.p2_team}")
	print(f"  Race distance : {engine.end_lap} laps")

	print("\n[5.A] Recommendation recomputed per lap, from that lap's real state")
	header = f"  {'LAP':>4} {'CMPD':>6} {'AGE':>4} {'ACTION':>10} {'PIT':>5} {'CONF':>12} {'TYRE s':>8} {'TRAFFIC s':>10}"
	print(header)
	for lap in (8, 16, 24, 32, 40):
		if lap > engine.end_lap:
			continue
		inputs = _inputs(ctx, lap)
		result = optimize_strategy(start_lap=lap, end_lap=max(lap + 1, engine.end_lap), **inputs)
		factors = result.explainability
		band = f"{result.confidence.lower * 100:.0f}-{result.confidence.upper * 100:.0f}%"
		print(
			f"  {lap:>4} {inputs['current_compound'][:6]:>6} {inputs['current_tyre_age']:>4} "
			f"{result.action:>10} {result.pit_lap:>5} {band:>12} "
			f"{factors.tyre_delta_risk:>8.2f} {factors.traffic_rejoin_risk:>10.2f}"
		)
	sample = optimize_strategy(start_lap=16, end_lap=engine.end_lap, **_inputs(ctx, 16))
	print(f"  Lap 16 reasoning: {sample.reasoning}")
	print(f"  Degradation model in use: {sample.degradation_model} @ {sample.degradation_rate_seconds_per_lap}s/lap")

	print("\n[5.E] The same shock type at different laps gives different output")
	for shock_lap in (14, 28):
		if shock_lap > engine.end_lap:
			continue
		probe = SimulationEngine(session.p1, session.p2)
		started = perf_counter()
		tick = probe.inject_shock(shock_lap, ShockEventType.SAFETY_CAR)
		elapsed = perf_counter() - started
		ours = next(d for d in tick.decisions if d.car == "P2")
		theirs = next(d for d in tick.decisions if d.car == "P1")
		print(f"  Safety car at lap {shock_lap} (re-optimised in {elapsed:.4f}s, budget 1.000s)")
		print(f"    PitSense : {ours.action} -> lap {ours.target_lap}")
		print(f"    Baseline : {theirs.action} -> lap {theirs.target_lap}")
		print(f"    Why      : {theirs.explanation}")

	print("\n[5.F] Counterfactual fork - the opponent runs its own model")
	fork_lap = min(20, engine.end_lap - 10)
	engine.inject_shock(fork_lap, ShockEventType.SAFETY_CAR)
	engine.accept_decision(fork_lap, "PIT")
	historical_p1_after = [
		stop.lap_number for stop in session.p1.pit_stops if stop.lap_number > fork_lap
	]
	projected_p1_after: list[int] = []
	for lap in range(fork_lap, engine.end_lap + 1):
		tick = engine.projected_tick(lap)
		p1 = next(car for car in tick.cars if car.car == "P1")
		if p1.pit_status == "PIT_IN":
			projected_p1_after.append(lap)
	print(f"  Fork at lap {fork_lap}, our car committed to PIT")
	print(f"  Opponent's REAL stops after the fork      : {historical_p1_after or 'none'}")
	print(f"  Opponent's PROJECTED stops after the fork : {projected_p1_after or 'none'}")
	print(
		"  -> "
		+ (
			"Projected path differs from the historical record, so it is computed, not replayed."
			if projected_p1_after != historical_p1_after
			else "Projected path happens to coincide with history here; it is still produced by the baseline model."
		)
	)

	print("\n[5.H] Rolling re-optimisation fires repeatedly with stated reasons")
	for record in engine.reoptimization_log[-6:]:
		print(f"  lap {record.lap:>3} [{record.computation_id}] {record.reason}")
	ids = {record.computation_id for record in engine.reoptimization_log}
	print(f"  {len(engine.reoptimization_log)} re-optimisations, {len(ids)} distinct computation ids")

	print("\n[5.I] Final counterfactual comparison")
	summary = engine.summary()
	print(f"  Historical finish  : P{summary.historical_finish['P2']} (our car)")
	print(f"  Projected finish   : P{summary.pitsense_projected_finish} (our car, PROJECTED)")
	print(f"  Historical margin  : {summary.historical_finishing_gap_seconds:.2f}s")
	print(f"  Projected margin   : {summary.projected_finishing_gap_seconds:.2f}s")
	print(f"  Projected advantage: {summary.projected_advantage_seconds:+.2f}s")
	print("  Stated assumptions:")
	for line in summary.assumptions:
		print(f"    - {line}")
	return 0


if __name__ == "__main__":
	event_name = sys.argv[1] if len(sys.argv) > 1 else "Azerbaijan Grand Prix"
	season = int(sys.argv[2]) if len(sys.argv) > 2 else 2024
	raise SystemExit(main(event_name, season))
