from __future__ import annotations

import sqlite3
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path


@dataclass(frozen=True)
class TimelineEvent:
	event_type: str
	lap_number: int
	detail: str
	timestamp: str


class TimelineLogger:
	def __init__(self, database_path: str | Path = "pitsense.sqlite3") -> None:
		self.database_path = str(database_path)
		with sqlite3.connect(self.database_path) as connection:
			connection.execute(
				"CREATE TABLE IF NOT EXISTS timeline_events ("
				"id INTEGER PRIMARY KEY, event_type TEXT NOT NULL, lap_number INTEGER NOT NULL, "
				"detail TEXT NOT NULL, timestamp TEXT NOT NULL)"
			)

	def record(self, event_type: str, lap_number: int, detail: str) -> TimelineEvent:
		timestamp = datetime.now(timezone.utc).isoformat()
		event = TimelineEvent(event_type, lap_number, detail, timestamp)
		with sqlite3.connect(self.database_path) as connection:
			connection.execute(
				"INSERT INTO timeline_events (event_type, lap_number, detail, timestamp) VALUES (?, ?, ?, ?)",
				(event.event_type, event.lap_number, event.detail, event.timestamp),
			)
		return event

	def list_events(self) -> list[TimelineEvent]:
		with sqlite3.connect(self.database_path) as connection:
			rows = connection.execute(
				"SELECT event_type, lap_number, detail, timestamp FROM timeline_events ORDER BY id"
			).fetchall()
		return [TimelineEvent(*row) for row in rows]
