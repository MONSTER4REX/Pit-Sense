"""PitSense HTTP and WebSocket API.

The backend is authoritative for all race state (PRD 5). Every endpoint that
returns a recommendation derives the lap's compound, tyre age, gaps, rival state,
and stint history from the loaded session itself. The frontend supplies a lap
number and renders what comes back; it never assembles engine inputs of its own,
so it cannot compute an authoritative lap, tyre, gap, position, or outcome.
"""
from __future__ import annotations

import asyncio
from time import perf_counter

from pathlib import Path

from fastapi import FastAPI, HTTPException, Query, Request, WebSocket, WebSocketDisconnect
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

from app.engine.reoptimizer import optimize_strategy
from app.ingestion.fastf1_client import (
	list_race_availability,
	load_circuit_data,
	load_historical_session,
)
from app.replay.session_context import SessionReplayContext, lap_context
from app.replay.shock_events import ShockEventType
from app.replay.tick_stream import replay_session_ticks, replay_ticks
from app.simulation.engine import SimulationEngine
from app.timeline.logger import TimelineLogger
from app.tyre_model.active import active_model_selection
from app.tyre_model.comparison import load_comparison_report
from app.ingestion import bundle
from app.session_store import COOKIE_NAME, VisitorState, new_session_id, store
from app.whatif.simulator import compare_branches

app = FastAPI(title="PitSense Historical Strategy Console", version="2.0.0")

timeline = TimelineLogger()
SESSION_HEADER = "X-PitSense-Session"


@app.middleware("http")
async def attach_session_cookie(request: Request, call_next):
	"""Give every visitor their own slot, so two people on one URL do not share
	a loaded race (see app.session_store)."""
	session_id = request.headers.get(SESSION_HEADER) or request.cookies.get(COOKIE_NAME) or new_session_id()
	request.state.session_id = session_id
	response = await call_next(request)
	response.headers[SESSION_HEADER] = session_id
	response.set_cookie(
		COOKIE_NAME,
		session_id,
		max_age=60 * 60 * 8,
		httponly=True,
		samesite="lax",
	)
	return response


def session_id(request: Request) -> str:
	return getattr(request.state, "session_id", "anonymous")


def visitor(request: Request) -> VisitorState:
	return store.get(session_id(request))


class ShockRequest(BaseModel):
	lap: int = Field(ge=1)
	event_type: ShockEventType


class DecisionRequest(BaseModel):
	lap: int = Field(ge=1)
	action: str


def _require_simulation(state: VisitorState) -> SimulationEngine:
	if state.simulation is None:
		raise HTTPException(status_code=409, detail="Load a historical race session first")
	return state.simulation


def _require_context(state: VisitorState) -> SessionReplayContext:
	if state.context is None:
		raise HTTPException(status_code=409, detail="Load a historical race session first")
	return state.context


def _engine_inputs(ctx: SessionReplayContext, lap: int) -> dict:
	"""Everything the engine needs for one lap, read from the loaded session."""
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
		"field_baseline": context["field_baseline"],
	}


@app.get("/health")
async def health() -> dict[str, str]:
	return {"status": "ok", "mode": "historical replay"}


@app.get("/api/model/tyre")
async def tyre_model_status() -> dict[str, object]:
	"""Which degradation model is live, and the recorded comparison behind it."""
	selection = active_model_selection()
	return {
		"active_model": selection.model_name,
		"selection_source": selection.source,
		"note": selection.note,
		"comparison": load_comparison_report(),
	}


@app.get("/api/races/available")
def available_races() -> list[dict[str, object]]:
	# The bundle already carries verified geometry flags, so a deployed instance
	# answers this instantly instead of loading telemetry for five races.
	return bundle.availability() if bundle.is_available() else list_race_availability()


@app.get("/api/race/{year}/{event_name}/session")
def race_session(year: int, event_name: str, request: Request) -> dict[str, object]:
	state = visitor(request)
	session = bundle.load_session(year, event_name)
	if session is None:
		try:
			session = load_historical_session(year, event_name)
		except (RuntimeError, ValueError) as exc:
			raise HTTPException(status_code=503, detail=str(exc)) from exc

	timeline.clear(getattr(request.state, "session_id", "anonymous"))
	state.simulation = SimulationEngine(
		session.p1, session.p2, field_median_lap_times=session.field_median_lap_times
	)
	state.historical_events = session.historical_events
	state.context = SessionReplayContext(
		p1=session.p1,
		p2=session.p2,
		end_lap=state.simulation.end_lap,
		field_median_lap_times=session.field_median_lap_times,
	)

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
		"total_laps": state.simulation.end_lap,
		"p1_laps": len(session.p1.laps),
		"p2_laps": len(session.p2.laps),
		"p1_lap_states": [lap.model_dump(mode="json") for lap in session.p1.laps],
		"p2_lap_states": [lap.model_dump(mode="json") for lap in session.p2.laps],
		"p1_pit_stops": [stop.model_dump(mode="json") for stop in session.p1.pit_stops],
		"p2_pit_stops": [stop.model_dump(mode="json") for stop in session.p2.pit_stops],
		"p1_data_gaps": [gap.model_dump(mode="json") for gap in session.p1.data_gaps],
		"p2_data_gaps": [gap.model_dump(mode="json") for gap in session.p2.data_gaps],
		"historical_events": state.historical_events,
	}


@app.get("/api/circuit/{year}/{event_name}")
def circuit_data(year: int, event_name: str) -> dict[str, object]:
	bundled = bundle.load_circuit(year, event_name)
	if bundled is not None:
		return bundled.model_dump(mode="json")
	try:
		data = load_circuit_data(year, event_name)
	except (RuntimeError, ValueError) as exc:
		raise HTTPException(status_code=503, detail=str(exc)) from exc
	return data.model_dump(mode="json")


@app.get("/api/strategy/recommendation")
def recommendation(request: Request, lap: int = Query(ge=1)) -> dict[str, object]:
	"""The engine's call for one lap of the loaded race, computed server-side."""
	ctx = _require_context(visitor(request))
	if lap > ctx.end_lap:
		raise HTTPException(status_code=422, detail=f"Lap {lap} is beyond this race's {ctx.end_lap} laps")

	started = perf_counter()
	result = optimize_strategy(
		start_lap=lap,
		end_lap=max(lap + 1, ctx.end_lap),
		uncertainty_events=ctx.uncertainty_events,
		**_engine_inputs(ctx, lap),
	)
	payload = result.model_dump(mode="json")
	payload["computed_in_seconds"] = round(perf_counter() - started, 5)
	payload["lap"] = lap
	return payload


@app.get("/api/strategy/what-if")
def what_if(request: Request, lap: int = Query(ge=1)) -> dict[str, object]:
	"""Pit / stay out / extend, each a real optimisation from this lap's state."""
	ctx = _require_context(visitor(request))
	if lap > ctx.end_lap:
		raise HTTPException(status_code=422, detail=f"Lap {lap} is beyond this race's {ctx.end_lap} laps")

	branches = compare_branches(
		current_lap=lap,
		end_lap=max(lap + 1, ctx.end_lap),
		uncertainty_events=ctx.uncertainty_events,
		**_engine_inputs(ctx, lap),
	)
	return {
		"lap": lap,
		"branches": {name: branch.model_dump(mode="json") for name, branch in branches.items()},
	}


@app.post("/api/simulation/shock")
def simulation_shock(shock: ShockRequest, request: Request) -> dict[str, object]:
	"""Inject a shock and re-optimise, reporting the real latency (PRD FR-7)."""
	state = visitor(request)
	engine = _require_simulation(state)
	started = perf_counter()
	try:
		result = engine.inject_shock(shock.lap, shock.event_type)
	except ValueError as exc:
		raise HTTPException(status_code=422, detail=str(exc)) from exc
	elapsed = perf_counter() - started

	if state.context is not None:
		state.context = SessionReplayContext(
			p1=state.context.p1,
			p2=state.context.p2,
			end_lap=state.context.end_lap,
			uncertainty_events=(shock.event_type.value,),
			field_median_lap_times=state.context.field_median_lap_times,
		)
	timeline.record(session_id(request), "shock_event", shock.lap, shock.event_type.value)

	return {
		"accepted": True,
		"fork_updated": False,
		"reoptimization_seconds": round(elapsed, 5),
		# Surfaced so the UI can show a stale state rather than silently
		# presenting a late recomputation as fresh (PRD 14).
		"within_budget": elapsed <= 1.0,
		"tick": result.model_dump(mode="json"),
	}


@app.post("/api/simulation/decision")
def simulation_decision(decision: DecisionRequest, request: Request) -> dict[str, object]:
	engine = _require_simulation(visitor(request))
	try:
		result = engine.accept_decision(decision.lap, decision.action)
	except ValueError as exc:
		raise HTTPException(status_code=422, detail=str(exc)) from exc
	timeline.record(session_id(request), "user_decision", decision.lap, decision.action)
	return {"accepted": True, "fork_updated": True, "tick": result.model_dump(mode="json")}


@app.get("/api/simulation/tick")
def simulation_tick(request: Request, lap: int = Query(ge=1)) -> dict[str, object]:
	"""The simulation's state at one lap.

	Before the fork this is the recorded race; after it, the projected branch.
	The frontend asks for a lap and renders what comes back, so scrubbing and
	playback follow the projection rather than showing the fork's state forever.
	"""
	engine = _require_simulation(visitor(request))
	if lap > engine.end_lap:
		raise HTTPException(status_code=422, detail=f"Lap {lap} is beyond this race's {engine.end_lap} laps")
	tick = engine.tick(lap)
	payload = tick.model_dump(mode="json")
	payload["fork_lap"] = engine.fork_lap
	payload["is_review_lap"] = engine.fork_lap is not None and engine.is_review_lap(lap)
	if engine.fork_lap is not None and lap >= engine.fork_lap:
		# Branches computed from the projected state, so the numbers on screen
		# belong to the lap the heading names.
		payload["what_if"] = {
			name: branch.model_dump(mode="json")
			for name, branch in engine.projected_what_if(lap).items()
		}
	return payload


@app.get("/api/simulation/counterfactual")
def counterfactual_summary(request: Request) -> dict[str, object]:
	engine = _require_simulation(visitor(request))
	try:
		summary = engine.summary().model_dump(mode="json")
	except ValueError as exc:
		raise HTTPException(status_code=409, detail=str(exc)) from exc
	summary["reoptimization_log"] = [
		record.model_dump(mode="json") for record in engine.reoptimization_log
	]
	return summary


@app.get("/api/simulation/reoptimizations")
def reoptimization_log(request: Request) -> dict[str, object]:
	engine = _require_simulation(visitor(request))
	return {
		"session_id": engine.session_id,
		"records": [record.model_dump(mode="json") for record in engine.reoptimization_log],
	}


@app.get("/api/simulation/assumptions")
def simulation_assumptions(request: Request) -> dict[str, object]:
	"""The stated assumptions behind every projected value (PRD FR-25)."""
	engine = _require_simulation(visitor(request))
	return {"assumptions": engine.model_assumptions(), "fork_lap": engine.fork_lap}


@app.get("/api/timeline")
def get_timeline(request: Request) -> dict[str, object]:
	return {"events": timeline.list_events(getattr(request.state, "session_id", "anonymous"))}


@app.websocket("/ws/replay")
async def replay_socket(websocket: WebSocket) -> None:
	await websocket.accept()
	try:
		state = store.get(websocket.cookies.get(COOKIE_NAME) or "anonymous")
		request = await websocket.receive_json()
		speed = float(request.get("speed", 1.0))
		start_lap = max(1, int(request.get("start_lap", 1)))

		if state.simulation is not None and request.get("simulation", False):
			for lap in range(start_lap, state.simulation.end_lap + 1):
				tick = state.simulation.tick(lap)
				await websocket.send_json({"type": "tick", **tick.model_dump(mode="json")})
				await asyncio.sleep(min(0.01, 0.1 / speed))
			await websocket.send_json(
				{"type": "complete", "scenario_id": state.simulation.scenario_id}
			)
			return

		if state.context is not None:
			async for tick in replay_session_ticks(
				state.context, speed=speed, start_lap=start_lap
			):
				await websocket.send_json({"type": "tick", **tick.__dict__})
			await websocket.send_json({"type": "complete"})
			return

		lap_times = request.get("lap_times", [])
		async for tick in replay_ticks(
			lap_times,
			speed=speed,
			start_lap=start_lap,
			start_tyre_age=int(request.get("start_tyre_age", 1)),
		):
			await websocket.send_json({"type": "tick", **tick.__dict__})
		await websocket.send_json({"type": "complete"})

	except WebSocketDisconnect:
		return
	except Exception as exc:  # noqa: BLE001 - the client is told, not left hanging
		await websocket.send_json({"type": "error", "message": str(exc)})
		await websocket.close(code=1011)


# ---------------------------------------------------------------- static site
#
# In a deployment the built frontend is served by this same process, so the whole
# app is one container on one port with no CORS and no second service to keep
# alive. In development Vite serves the frontend itself and this directory simply
# does not exist, so the mount is skipped.
_FRONTEND_DIST = Path(__file__).resolve().parents[1] / "static"

if _FRONTEND_DIST.is_dir():

	@app.get("/", include_in_schema=False)
	def index() -> FileResponse:
		return FileResponse(_FRONTEND_DIST / "index.html")

	app.mount("/", StaticFiles(directory=_FRONTEND_DIST, html=True), name="static")
