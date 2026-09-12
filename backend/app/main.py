import asyncio

from fastapi import FastAPI, HTTPException, Query, WebSocket, WebSocketDisconnect
from pydantic import BaseModel, Field

from app.engine.reoptimizer import optimize_strategy
from app.ingestion.fastf1_client import load_historical_session
from app.replay.tick_stream import replay_ticks
from app.replay.shock_events import ShockEventType
from app.simulation.engine import SimulationEngine
from app.timeline.logger import TimelineLogger
from app.whatif.simulator import compare_branches

app = FastAPI(title="PitSense Historical Strategy Console", version="0.1.0")
timeline = TimelineLogger()
active_simulation: SimulationEngine | None = None
active_historical_events: list[dict[str, str]] = []


SUPPORTED_RACES = [
	{"year": 2024, "event": "Canadian Grand Prix"},
	{"year": 2023, "event": "Dutch Grand Prix"},
	{"year": 2024, "event": "Australian Grand Prix"},
	{"year": 2024, "event": "British Grand Prix"},
	{"year": 2024, "event": "Azerbaijan Grand Prix"},
]


class OptimizeRequest(BaseModel):
	start_lap: int = Field(ge=1)
	end_lap: int = Field(ge=2)
	current_compound: str = Field(min_length=1)
	current_tyre_age: int = Field(ge=0)
	lap_time_seconds: list[float] = Field(min_length=1)
	uncertainty_events: tuple[str, ...] = ()
	rival_cover_stop_probability: float = Field(default=0.0, ge=0, le=1)


class ShockRequest(BaseModel):
	lap: int = Field(ge=1)
	event_type: ShockEventType


class DecisionRequest(BaseModel):
	lap: int = Field(ge=1)
	action: str


@app.get("/health")
async def health() -> dict[str, str]:
	return {"status": "ok", "mode": "historical replay"}


@app.get("/api/races/available")
async def available_races() -> list[dict[str, object]]:
	return SUPPORTED_RACES


@app.get("/api/race/{year}/{event_name}/session")
async def race_session(year: int, event_name: str) -> dict[str, object]:
	global active_historical_events, active_simulation
	try:
		session = load_historical_session(year, event_name)
		active_simulation = SimulationEngine(session.p1, session.p2)
		active_historical_events = session.historical_events
	except (RuntimeError, ValueError) as exc:
		raise HTTPException(status_code=503, detail=str(exc)) from exc
	return {
		"year": year,
		"event": event_name,
		"session": "R",
		"mode": "HISTORICAL",
		"p1": session.p1.driver,
		"p2": session.p2.driver,
		"p1_driver": session.p1_name,
		"p1_team": session.p1_team,
		"p2_driver": session.p2_name,
		"p2_team": session.p2_team,
		"total_laps": active_simulation.end_lap,
		"p1_laps": len(session.p1.laps),
		"p2_laps": len(session.p2.laps),
		"historical_events": active_historical_events,
	}


def _require_simulation() -> SimulationEngine:
	if active_simulation is None:
		raise HTTPException(status_code=409, detail="Load a historical race session first")
	return active_simulation


@app.post("/api/simulation/shock")
async def simulation_shock(request: ShockRequest) -> dict[str, object]:
	try:
		engine = _require_simulation()
		result = engine.inject_shock(request.lap, request.event_type)
	except ValueError as exc:
		raise HTTPException(status_code=422, detail=str(exc)) from exc
	return {"accepted": True, "fork_updated": False, "tick": result.model_dump(mode="json")}


@app.post("/api/simulation/decision")
async def simulation_decision(request: DecisionRequest) -> dict[str, object]:
	try:
		engine = _require_simulation()
		result = engine.accept_decision(request.lap, request.action)
	except ValueError as exc:
		raise HTTPException(status_code=422, detail=str(exc)) from exc
	return {"accepted": True, "fork_updated": True, "tick": result.model_dump(mode="json")}


@app.get("/api/simulation/counterfactual")
async def counterfactual_summary() -> dict[str, object]:
	return _require_simulation().summary().model_dump(mode="json")


@app.post("/api/strategy/recommendation")
async def recommendation(request: OptimizeRequest):
	if request.end_lap <= request.start_lap:
		return {
			"action": "stay_out",
			"pit_lap": request.start_lap,
			"projected_total_time_seconds": 0.0,
			"undercut_risk_tier": "safe",
			"explainability": {
				"tyre_delta_risk": 0.0,
				"traffic_rejoin_risk": 0.0,
				"rival_cover_stop_probability": request.rival_cover_stop_probability,
				"pit_lane_time_loss": 0.0,
			},
			"confidence": {"lower": 1.0, "upper": 1.0, "uncertainty": "low"}
		}
	return optimize_strategy(**request.model_dump())


@app.post("/api/strategy/what-if")
async def what_if(request: OptimizeRequest):
	return compare_branches(
		current_lap=request.start_lap,
		end_lap=request.end_lap,
		current_compound=request.current_compound,
		current_tyre_age=request.current_tyre_age,
		lap_time_seconds=request.lap_time_seconds,
		uncertainty_events=request.uncertainty_events,
		rival_cover_stop_probability=request.rival_cover_stop_probability,
	)


@app.post("/api/timeline/shock")
async def inject_shock(event_type: ShockEventType, lap_number: int = Query(ge=1)):
	event = timeline.record("shock_event", lap_number, event_type.value)
	result = None
	if active_simulation is not None:
		try:
			result = active_simulation.inject_shock(lap_number, event_type).model_dump(mode="json")
		except ValueError as exc:
			raise HTTPException(status_code=422, detail=str(exc)) from exc
	return {"event": event, "status": "queued_for_reoptimization", "tick": result}


@app.get("/api/timeline")
async def get_timeline():
	return {"events": timeline.list_events()}


@app.websocket("/ws/replay")
async def replay_socket(websocket: WebSocket):
	await websocket.accept()
	try:
		request = await websocket.receive_json()
		speed = float(request.get("speed", 1.0))
		if active_simulation is not None and request.get("simulation", False):
			start_lap = max(1, int(request.get("start_lap", 1)))
			for lap in range(start_lap, active_simulation.end_lap + 1):
				tick = active_simulation.tick(lap)
				await websocket.send_json({"type": "tick", **tick.model_dump(mode="json")})
				await asyncio.sleep(min(0.01, 0.1 / speed))
			await websocket.send_json({"type": "complete", "scenario_id": active_simulation.scenario_id})
			return
		lap_times = request.get("lap_times", [])
		start_lap = int(request.get("start_lap", 1))
		start_tyre_age = int(request.get("start_tyre_age", 12))
		async for tick in replay_ticks(lap_times, speed=speed, start_lap=start_lap, start_tyre_age=start_tyre_age):
			payload = {"type": "tick", **tick.__dict__}
			print(f"[WebSocket] Sending tick payload: {payload}")
			await websocket.send_json(payload)
		await websocket.send_json({"type": "complete"})
	except WebSocketDisconnect:
		return
	except Exception as exc:
		await websocket.send_json({"type": "error", "message": str(exc)})
		await websocket.close(code=1011)
