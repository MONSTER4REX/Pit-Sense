from app.ingestion.fastf1_client import SUPPORTED_RACES, list_race_availability


def test_race_availability_returns_two_tier_flags(monkeypatch) -> None:
	"""PRD 5.C / FR-21: the two tiers are separate flags, not one list."""

	def fake_geometry(
		year: int, event_name: str, session_name: str = "R", cache_dir=None
	) -> tuple[bool, str]:
		if event_name == "Canadian Grand Prix":
			return True, "Racing line and pit lane both traced from this session's telemetry."
		return False, "No usable in-lap and out-lap telemetry was found for this session."

	monkeypatch.setattr("app.ingestion.fastf1_client.has_verified_geometry", fake_geometry)
	entries = list_race_availability()

	assert len(entries) == len(SUPPORTED_RACES)
	for entry in entries:
		# Every race stays available for Race Analysis regardless of geometry.
		assert entry["race_analysis_available"] is True
		assert isinstance(entry["simulation_geometry_available"], bool)
		# A race is never left unexplained: the reason travels with the flag.
		assert entry["geometry_note"]

	verified = [entry for entry in entries if entry["simulation_geometry_available"]]
	unverified = [entry for entry in entries if not entry["simulation_geometry_available"]]
	assert [entry["event"] for entry in verified] == ["Canadian Grand Prix"]
	assert unverified, "The fixture must exercise the geometry-unavailable tier"
	assert "no usable" in unverified[0]["geometry_note"].lower()
