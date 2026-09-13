/*
 * Race Analysis state. This provider belongs to Race Analysis alone (PRD 2.1) -
 * the Simulation Lab has its own, and neither can reach into the other.
 *
 * There is no shock injection, no fork, and no projected state here, because
 * this product never shows any (PRD 8.4). Everything on screen is real
 * historical data plus the engine's recommendation for the lap being viewed.
 */
import { createContext, useCallback, useContext, useEffect, useMemo, useRef, useState } from "react";

import {
	fetchAvailableRaces,
	fetchRecommendation,
	fetchTimeline,
	fetchTyreModelStatus,
	loadRaceSession,
} from "../api";

const RaceAnalysisContext = createContext(null);

/* The lap the dashboard opens on. Not a hardcoded race lap: it is the first lap
 * of whichever race is loaded, and the user moves from there (PRD 8.3). */
const FIRST_LAP = 1;

export function RaceAnalysisProvider({ children }) {
	const [races, setRaces] = useState([]);
	const [selectedRace, setSelectedRace] = useState(null);
	const [session, setSession] = useState(null);
	const [currentLap, setCurrentLap] = useState(FIRST_LAP);
	const [recommendation, setRecommendation] = useState(null);
	const [recommendationPending, setRecommendationPending] = useState(false);
	const [timelineEvents, setTimelineEvents] = useState([]);
	const [tyreModel, setTyreModel] = useState(null);
	const [status, setStatus] = useState("loading");
	const [error, setError] = useState(null);

	// Guards against an older in-flight recommendation overwriting a newer one
	// when the user scrubs quickly.
	const requestRef = useRef(0);

	const totalLaps = session?.total_laps ?? 0;

	const selectRace = useCallback((race) => {
		setSelectedRace(race);
		setSession(null);
		setRecommendation(null);
		setCurrentLap(FIRST_LAP);
		setStatus("loading");
		setError(null);
	}, []);

	/* Load the race list once, then open on the first available race. */
	useEffect(() => {
		const controller = new AbortController();
		/*
		 * Keep the first API requests sequential. Both responses can establish
		 * the visitor cookie; racing them lets the later response replace the
		 * cookie after the race-load request has already started, leaving the
		 * comparison endpoint with an empty visitor slot.
		 */
		fetchTyreModelStatus(controller.signal)
			.then(setTyreModel, () => setTyreModel(null))
			.then(() => fetchAvailableRaces(controller.signal))
			.then((available) => {
				setRaces(available);
				if (available.length) selectRace(available[0]);
			})
			.catch((cause) => {
				if (cause.name !== "AbortError") setError(cause.message);
			});
		return () => controller.abort();
	}, [selectRace]);

	/* Selecting a race reloads every dependent panel, not just a header label
	 * (PRD 8.3): session, recommendation, and timeline all refetch below. */
	useEffect(() => {
		if (!selectedRace) return undefined;
		const controller = new AbortController();
		loadRaceSession(selectedRace.year, selectedRace.event, controller.signal)
			.then((loaded) => {
				setSession(loaded);
				setStatus("synced");
			})
			.catch((cause) => {
				if (cause.name !== "AbortError") {
					setError(cause.message);
					setStatus("error");
				}
			});
		return () => controller.abort();
	}, [selectedRace]);

	/* One recommendation per viewed lap, always recomputed by the backend for
	 * that lap's own state (PRD 5.A) - never frozen from initial load. */
	useEffect(() => {
		if (!session || !totalLaps) return undefined;
		const controller = new AbortController();
		const requestId = ++requestRef.current;
		setRecommendationPending(true);

		fetchRecommendation(Math.min(currentLap, totalLaps), controller.signal)
			.then((fresh) => {
				if (requestId !== requestRef.current) return;
				setRecommendation(fresh);
				setRecommendationPending(false);
				setStatus("synced");
			})
			.catch((cause) => {
				if (cause.name === "AbortError" || requestId !== requestRef.current) return;
				setError(cause.message);
				setRecommendationPending(false);
				setStatus("error");
			});
		return () => controller.abort();
	}, [session, currentLap, totalLaps]);

	useEffect(() => {
		if (!session) return undefined;
		const controller = new AbortController();
		fetchTimeline(controller.signal)
			.then((data) => setTimelineEvents(data.events ?? []))
			.catch(() => setTimelineEvents([]));
		return () => controller.abort();
	}, [session]);

	const lapState = useMemo(
		() => session?.p2_lap_states?.find((lap) => lap.lap_number === currentLap) ?? null,
		[session, currentLap],
	);

	const value = useMemo(
		() => ({
			races,
			selectedRace,
			selectRace,
			session,
			lapState,
			currentLap,
			setCurrentLap,
			totalLaps,
			recommendation,
			recommendationPending,
			timelineEvents,
			tyreModel,
			status,
			error,
		}),
		[
			races,
			selectedRace,
			selectRace,
			session,
			lapState,
			currentLap,
			totalLaps,
			recommendation,
			recommendationPending,
			timelineEvents,
			tyreModel,
			status,
			error,
		],
	);

	return <RaceAnalysisContext.Provider value={value}>{children}</RaceAnalysisContext.Provider>;
}

export function useRaceAnalysis() {
	const context = useContext(RaceAnalysisContext);
	if (!context) throw new Error("useRaceAnalysis must be used inside RaceAnalysisProvider");
	return context;
}
