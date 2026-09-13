"""Per-visitor simulation state.

The API used to hold one loaded race in module-level globals. That is fine for a
single operator on a laptop and wrong the moment the app is deployed: two people
on the same URL share one ``active_simulation``, so one loading Baku silently
replaces the race the other is part-way through analysing.

Each visitor therefore gets their own slot, keyed by a cookie the server sets on
first contact. Slots are held in memory - this is a replay console, not a system
of record, and a visitor who returns after a restart simply loads their race
again. The number of slots is capped so an unattended public URL cannot grow
memory without bound; the least recently used slot is dropped first.

This also means the app must run as a single worker. Nothing here is shared
between processes, so a second worker would serve a visitor an empty slot half
the time.
"""
from __future__ import annotations

from collections import OrderedDict
from dataclasses import dataclass, field
from threading import Lock
from uuid import uuid4

from app.replay.session_context import SessionReplayContext
from app.simulation.engine import SimulationEngine

COOKIE_NAME = "pitsense_session"
# Concurrent visitors kept in memory at once. Each slot holds one loaded race,
# which is a few hundred kilobytes of lap states plus its projection cache.
MAX_SESSIONS = 64


# Computed answers held per visitor. A recommendation is a pure function of the
# loaded race, the lap, and the active shock, so re-deriving it every time the
# user scrubs back over a lap they have already seen is wasted work - and on a
# small instance that wasted CPU is what starves the health check.
MAX_CACHED_LAPS = 128


@dataclass
class VisitorState:
	"""One visitor's loaded race and everything derived from it."""

	simulation: SimulationEngine | None = None
	context: SessionReplayContext | None = None
	historical_events: list[dict[str, str]] = field(default_factory=list)
	circuit_cache: dict[str, dict[str, object]] = field(default_factory=dict)
	_answers: OrderedDict[tuple, dict] = field(default_factory=OrderedDict)

	def cached(self, key: tuple) -> dict | None:
		answer = self._answers.get(key)
		if answer is not None:
			self._answers.move_to_end(key)
		return answer

	def remember(self, key: tuple, answer: dict) -> dict:
		self._answers[key] = answer
		while len(self._answers) > MAX_CACHED_LAPS:
			self._answers.popitem(last=False)
		return answer

	def forget_answers(self) -> None:
		"""Drop cached answers after anything that changes what they would be."""
		self._answers.clear()


class SessionStore:
	def __init__(self, max_sessions: int = MAX_SESSIONS) -> None:
		self._sessions: OrderedDict[str, VisitorState] = OrderedDict()
		self._max = max_sessions
		# Endpoints run in FastAPI's threadpool, so the store is touched from
		# several threads at once.
		self._lock = Lock()

	def get(self, session_id: str) -> VisitorState:
		with self._lock:
			state = self._sessions.get(session_id)
			if state is None:
				state = VisitorState()
				self._sessions[session_id] = state
				while len(self._sessions) > self._max:
					self._sessions.popitem(last=False)
			else:
				self._sessions.move_to_end(session_id)
			return state

	def reset(self, session_id: str) -> VisitorState:
		with self._lock:
			state = VisitorState()
			self._sessions[session_id] = state
			self._sessions.move_to_end(session_id)
			return state

	@property
	def active_sessions(self) -> int:
		with self._lock:
			return len(self._sessions)


def new_session_id() -> str:
	return uuid4().hex


store = SessionStore()
