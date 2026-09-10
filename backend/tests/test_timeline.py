from app.timeline.logger import TimelineLogger


def test_timeline_persists_strategy_events(tmp_path) -> None:
    logger = TimelineLogger(tmp_path / "timeline.sqlite3")
    logger.record("pit_call", 18, "Pit Now")
    logger.record("shock_event", 19, "vsc")

    events = logger.list_events()
    assert [event.event_type for event in events] == ["pit_call", "shock_event"]
    assert events[1].lap_number == 19