from app.ingestion.normalizer import normalize_race
from app.replay.shock_events import ShockEventType
from app.simulation.engine import SimulationEngine


def _race(driver: str, position: int, gap: float):
	return normalize_race(
		year=2024,
		event_name="Test Grand Prix",
		session_name="R",
		driver=driver,
		total_laps=6,
		lap_rows=[
			{
				"LapNumber": lap,
				"LapTime": 90.0 + lap / 10,
				"Compound": "MEDIUM",
				"TyreLife": lap,
				"Position": position,
				"GapToLeader": gap,
			}
			for lap in range(1, 7)
		],
	)


def test_shock_recomputes_both_policies_without_leaving_historical_mode() -> None:
	engine = SimulationEngine(_race("P1DRV", 1, 0.0), _race("P2DRV", 2, 4.0))

	before = engine.tick(3)
	shock = engine.inject_shock(3, ShockEventType.SAFETY_CAR)

	assert before.mode == "HISTORICAL"
	assert before.session_id == shock.session_id
	assert all(car.mode == "HISTORICAL" for car in shock.cars)
	assert {decision.model_type for decision in shock.decisions} == {"PITSENSE", "BASELINE"}
	assert all(decision.lap == 3 for decision in shock.decisions)


def test_accepting_action_creates_projected_fork_and_summary() -> None:
	engine = SimulationEngine(_race("P1DRV", 1, 0.0), _race("P2DRV", 2, 4.0))
	engine.inject_shock(3, ShockEventType.RAIN)

	projected = engine.accept_decision(3, "PIT")
	summary = engine.summary()

	assert projected.mode == "PROJECTED"
	assert all(car.mode == "PROJECTED" for car in projected.cars)
	assert next(decision for decision in projected.decisions if decision.car == "P2").action == "PIT"
	assert summary.historical_vs_projected == "COUNTERFACTUAL_PROJECTION"
	assert summary.session_id == engine.session_id
	assert summary.assumptions


def test_counterfactual_reoptimizes_at_next_review_lap() -> None:
	engine = SimulationEngine(_race("P1DRV", 1, 0.0), _race("P2DRV", 2, 4.0))
	engine.inject_shock(2, ShockEventType.SAFETY_CAR)
	first = engine.accept_decision(2, "STAY_OUT")
	review = engine.tick(4)
	second = engine.accept_decision(4, "PIT")

	assert first.next_review_lap == 4
	assert review.mode == "PROJECTED"
	assert review.next_review_lap is not None
	assert [record.lap for record in engine.decision_history] == [2, 4]
	assert second.decision_lap == 4


def test_pit_status_uses_historical_and_projected_lap_phases() -> None:
	historical = normalize_race(
		year=2024,
		event_name="Test Grand Prix",
		session_name="R",
		driver="P1DRV",
		total_laps=6,
		lap_rows=[{"LapNumber": lap, "LapTime": 90.0, "Compound": "MEDIUM", "Position": 1} for lap in range(1, 7)],
		pit_rows=[{"Lap": 3, "PitDuration": 22.0}],
	)
	other = _race("P2DRV", 2, 4.0)
	engine = SimulationEngine(historical, other)

	assert engine.tick(3).cars[0].pit_status == "PIT_IN"
	assert engine.tick(4).cars[0].pit_status == "PIT_OUT"
	engine.inject_shock(2, ShockEventType.SAFETY_CAR)
	engine.accept_decision(2, "PIT")
	assert engine.tick(4).cars[1].pit_status == "PIT_IN"