from app.timeline.logger import TimelineLogger


def test_timeline_persists_strategy_events(tmp_path) -> None:
	logger = TimelineLogger(tmp_path / "timeline.sqlite3")
	logger.record("visitor-a", "pit_call", 18, "Pit Now")
	logger.record("visitor-a", "shock_event", 19, "vsc")

	events = logger.list_events("visitor-a")
	assert [event.event_type for event in events] == ["pit_call", "shock_event"]
	assert events[1].lap_number == 19


def test_timelines_are_scoped_to_the_visitor_who_caused_them(tmp_path) -> None:
	"""Two people using a deployed instance must not read each other's events."""
	logger = TimelineLogger(tmp_path / "timeline.sqlite3")
	logger.record("visitor-a", "shock_event", 12, "safety_car")
	logger.record("visitor-b", "shock_event", 40, "rain")

	assert [event.lap_number for event in logger.list_events("visitor-a")] == [12]
	assert [event.lap_number for event in logger.list_events("visitor-b")] == [40]
	assert logger.list_events("visitor-c") == []


def test_clearing_one_visitor_leaves_the_others_intact(tmp_path) -> None:
	logger = TimelineLogger(tmp_path / "timeline.sqlite3")
	logger.record("visitor-a", "pit_call", 5, "Pit Now")
	logger.record("visitor-b", "pit_call", 6, "Stay Out")

	logger.clear("visitor-a")

	assert logger.list_events("visitor-a") == []
	assert [event.lap_number for event in logger.list_events("visitor-b")] == [6]
