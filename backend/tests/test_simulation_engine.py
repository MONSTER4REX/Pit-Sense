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
	assert summary.assumptions