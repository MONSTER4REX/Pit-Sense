from fastapi import FastAPI, HTTPException, WebSocket, WebSocketDisconnect
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
		raise HTTPException(status_code=422, detail="end_lap must be after start_lap")
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
async def inject_shock(event_type: ShockEventType, lap_number: int = Field(ge=1)):
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
		async for tick in replay_ticks(lap_times, speed=speed):
			await websocket.send_json({"type": "tick", **tick.__dict__})
		await websocket.send_json({"type": "complete"})
	except WebSocketDisconnect:
		return
	except Exception as exc:
		await websocket.send_json({"type": "error", "message": str(exc)})
		await websocket.close(code=1011)
