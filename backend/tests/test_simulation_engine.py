from app.ingestion.normalizer import normalize_race
from app.replay.shock_events import ShockEventType
from app.simulation.engine import SCHEDULED_REVIEW_INTERVAL_LAPS, SimulationEngine


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
	# The engine keeps giving its own independent recommendation; the user's
	# committed action is what drives the projection (PRD 9.7 separates the two).
	assert [record.action for record in engine.decision_history] == ["PIT"]
	assert next(car for car in projected.cars if car.car == "P2").pit_status == "PIT_IN"
	assert summary.historical_vs_projected == "COUNTERFACTUAL_PROJECTION"
	assert summary.session_id == engine.session_id
	assert summary.assumptions


def test_counterfactual_reoptimizes_at_next_review_lap() -> None:
	engine = SimulationEngine(_race("P1DRV", 1, 0.0), _race("P2DRV", 2, 4.0))
	engine.inject_shock(2, ShockEventType.SAFETY_CAR)
	first = engine.accept_decision(2, "STAY_OUT")
	review = engine.tick(4)
	second = engine.accept_decision(4, "PIT")

	# Clamped to the end of this short fixture race.
	assert first.next_review_lap == min(engine.end_lap, 2 + SCHEDULED_REVIEW_INTERVAL_LAPS)
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
	# The committed stop is taken on the fork lap, so lap 2 shows the entry and
	# lap 3 the rejoin - no teleporting between them.
	assert engine.tick(2).cars[1].pit_status == "PIT_IN"
	assert engine.tick(3).cars[1].pit_status == "PIT_OUT"


def test_reoptimization_triggers_and_log_records() -> None:
	p1_data = normalize_race(
		year=2024,
		event_name="Test Grand Prix",
		session_name="R",
		driver="P1DRV",
		total_laps=10,
		lap_rows=[
			{"LapNumber": 1, "LapTime": 90.0, "Compound": "MEDIUM", "TyreLife": 1, "Position": 1, "GapToLeader": 0.0},
			{"LapNumber": 2, "LapTime": 90.0, "Compound": "MEDIUM", "TyreLife": 2, "Position": 1, "GapToLeader": 0.0},
			{"LapNumber": 3, "LapTime": 90.0, "Compound": "HARD", "TyreLife": 1, "Position": 2, "GapToLeader": 0.0},  # TYRE_STATE_CHANGE & TRAFFIC_CHANGE
			{"LapNumber": 4, "LapTime": 90.0, "Compound": "HARD", "TyreLife": 2, "Position": 2, "GapToLeader": 3.0},  # GAP_CHANGE
			{"LapNumber": 5, "LapTime": 90.0, "Compound": "HARD", "TyreLife": 3, "Position": 2, "GapToLeader": 3.0},
			{"LapNumber": 6, "LapTime": 90.0, "Compound": "HARD", "TyreLife": 4, "Position": 2, "GapToLeader": 3.0},
			{"LapNumber": 7, "LapTime": 90.0, "Compound": "HARD", "TyreLife": 5, "Position": 2, "GapToLeader": 3.0},
			{"LapNumber": 8, "LapTime": 90.0, "Compound": "HARD", "TyreLife": 6, "Position": 2, "GapToLeader": 3.0},
			{"LapNumber": 9, "LapTime": 90.0, "Compound": "HARD", "TyreLife": 7, "Position": 2, "GapToLeader": 3.0},
			{"LapNumber": 10, "LapTime": 90.0, "Compound": "HARD", "TyreLife": 8, "Position": 2, "GapToLeader": 3.0},
		],
		pit_rows=[{"Lap": 3, "PitDuration": 20.0}],
	)

	p2_data = normalize_race(
		year=2024,
		event_name="Test Grand Prix",
		session_name="R",
		driver="P2DRV",
		total_laps=10,
		lap_rows=[
			{"LapNumber": 1, "LapTime": 91.0, "Compound": "MEDIUM", "TyreLife": 1, "Position": 2, "GapToLeader": 1.0},
			{"LapNumber": 2, "LapTime": 91.0, "Compound": "MEDIUM", "TyreLife": 2, "Position": 2, "GapToLeader": 1.0},
			{"LapNumber": 3, "LapTime": 91.0, "Compound": "MEDIUM", "TyreLife": 3, "Position": 1, "GapToLeader": 1.0},
			{"LapNumber": 4, "LapTime": 91.0, "Compound": "HARD", "TyreLife": 1, "Position": 1, "GapToLeader": 0.0},
			{"LapNumber": 5, "LapTime": 91.0, "Compound": "HARD", "TyreLife": 2, "Position": 1, "GapToLeader": 0.0},
			{"LapNumber": 6, "LapTime": 91.0, "Compound": "HARD", "TyreLife": 3, "Position": 1, "GapToLeader": 0.0},
			{"LapNumber": 7, "LapTime": 91.0, "Compound": "HARD", "TyreLife": 4, "Position": 1, "GapToLeader": 0.0},
			{"LapNumber": 8, "LapTime": 91.0, "Compound": "HARD", "TyreLife": 5, "Position": 1, "GapToLeader": 0.0},
			{"LapNumber": 9, "LapTime": 91.0, "Compound": "HARD", "TyreLife": 6, "Position": 1, "GapToLeader": 0.0},
			{"LapNumber": 10, "LapTime": 91.0, "Compound": "HARD", "TyreLife": 7, "Position": 1, "GapToLeader": 0.0},
		],
		pit_rows=[{"Lap": 4, "PitDuration": 20.0}],
	)

	engine = SimulationEngine(p1_data, p2_data)

	# Lap 1: initial tick sets baseline snapshot
	engine.tick(1)

	# Lap 2: inject SHOCK_EVENT
	shock_tick = engine.inject_shock(2, ShockEventType.SAFETY_CAR)
	assert "SHOCK_EVENT" in shock_tick.triggers

	# Lap 3: P1 pits -> P1_PIT, TYRE_STATE_CHANGE, TRAFFIC_CHANGE detected
	p1_pit_tick = engine.tick(3)
	assert "P1_PIT" in p1_pit_tick.triggers
	assert "TYRE_STATE_CHANGE" in p1_pit_tick.triggers
	assert "TRAFFIC_CHANGE" in p1_pit_tick.triggers

	# Lap 4: P2 pits -> P2_PIT & GAP_CHANGE detected
	p2_pit_tick = engine.tick(4)
	assert "P2_PIT" in p2_pit_tick.triggers
	assert "GAP_CHANGE" in p2_pit_tick.triggers

	# USER_DECISION
	user_tick = engine.accept_decision(4, "STAY_OUT")
	assert "USER_DECISION" in user_tick.triggers
	review_lap = 4 + SCHEDULED_REVIEW_INTERVAL_LAPS
	assert user_tick.next_review_lap == review_lap

	# TARGET_LAP_REACHED when the scheduled review comes due
	target_tick = engine.tick(review_lap)
	assert "TARGET_LAP_REACHED" in target_tick.triggers

	# OTHER_MATERIAL_EVENT via flag_material_event
	other_tick = engine.flag_material_event(review_lap + 1)
	assert "OTHER_MATERIAL_EVENT" in other_tick.triggers

	# Verify every record in engine.reoptimization_log contains required fields
	assert len(engine.reoptimization_log) > 0
	for rec in engine.reoptimization_log:
		assert rec.lap >= 1
		assert len(rec.triggers) > 0
		assert rec.p1_decision is not None
		assert rec.p2_decision is not None
		assert "p1_position" in rec.state_summary
		assert "p2_position" in rec.state_summary
