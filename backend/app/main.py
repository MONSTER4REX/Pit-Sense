from fastapi import FastAPI, HTTPException, Query, WebSocket, WebSocketDisconnect
from pydantic import BaseModel, Field

from app.engine.reoptimizer import optimize_strategy
from app.replay.tick_stream import replay_ticks
from app.replay.shock_events import ShockEventType
from app.timeline.logger import TimelineLogger
from app.whatif.simulator import compare_branches

app = FastAPI(title="PitSense Historical Strategy Console", version="0.1.0")
timeline = TimelineLogger()


class OptimizeRequest(BaseModel):
	start_lap: int = Field(ge=1)
	end_lap: int = Field(ge=2)
	current_compound: str = Field(min_length=1)
	current_tyre_age: int = Field(ge=0)
	lap_time_seconds: list[float] = Field(min_length=1)
	uncertainty_events: tuple[str, ...] = ()
	rival_cover_stop_probability: float = Field(default=0.0, ge=0, le=1)


@app.get("/health")
async def health() -> dict[str, str]:
	return {"status": "ok", "mode": "historical replay"}


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
	return {"event": event, "status": "queued_for_reoptimization"}


@app.get("/api/timeline")
async def get_timeline():
	return {"events": timeline.list_events()}


@app.websocket("/ws/replay")
async def replay_socket(websocket: WebSocket):
	await websocket.accept()
	try:
		request = await websocket.receive_json()
		speed = float(request.get("speed", 1.0))
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
