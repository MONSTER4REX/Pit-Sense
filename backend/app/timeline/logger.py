from __future__ import annotations

import os
import sqlite3
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path


@dataclass(frozen=True)
class TimelineEvent:
	"""One logged event. ``session_id`` scopes it to the visitor who caused it, so
	two people using a deployed instance do not read each other's timeline."""

	event_type: str
	lap_number: int
	detail: str
	timestamp: str


class TimelineLogger:
	def __init__(self, database_path: str | Path | None = None) -> None:
		# A deployed container's working directory is not necessarily writable, so
		# the path is overridable without touching code.
		database_path = database_path or os.environ.get("PITSENSE_DB_PATH", "pitsense.sqlite3")
		self.database_path = str(database_path)
		with sqlite3.connect(self.database_path) as connection:
			connection.execute(
				"CREATE TABLE IF NOT EXISTS timeline_events ("
				"id INTEGER PRIMARY KEY, session_id TEXT NOT NULL DEFAULT '', "
				"event_type TEXT NOT NULL, lap_number INTEGER NOT NULL, "
				"detail TEXT NOT NULL, timestamp TEXT NOT NULL)"
			)
			# A database written before events were scoped needs the column adding.
			columns = {row[1] for row in connection.execute("PRAGMA table_info(timeline_events)")}
			if "session_id" not in columns:
				connection.execute(
					"ALTER TABLE timeline_events ADD COLUMN session_id TEXT NOT NULL DEFAULT ''"
				)

	def record(
		self, session_id: str, event_type: str, lap_number: int, detail: str
	) -> TimelineEvent:
		timestamp = datetime.now(timezone.utc).isoformat()
		event = TimelineEvent(event_type, lap_number, detail, timestamp)
		with sqlite3.connect(self.database_path) as connection:
			connection.execute(
				"INSERT INTO timeline_events (session_id, event_type, lap_number, detail, timestamp) "
				"VALUES (?, ?, ?, ?, ?)",
				(session_id, event.event_type, event.lap_number, event.detail, event.timestamp),
			)
		return event

	def list_events(self, session_id: str) -> list[TimelineEvent]:
		with sqlite3.connect(self.database_path) as connection:
			rows = connection.execute(
				"SELECT event_type, lap_number, detail, timestamp FROM timeline_events "
				"WHERE session_id = ? ORDER BY id",
				(session_id,),
			).fetchall()
		return [TimelineEvent(*row) for row in rows]

	def clear(self, session_id: str) -> None:
		with sqlite3.connect(self.database_path) as connection:
			connection.execute("DELETE FROM timeline_events WHERE session_id = ?", (session_id,))
