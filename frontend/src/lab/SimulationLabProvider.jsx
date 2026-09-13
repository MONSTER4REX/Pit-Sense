/*
 * Simulation Lab state - entirely separate from Race Analysis (PRD 2.1).
 *
 * This provider owns the things Race Analysis has none of: circuit geometry, an
 * injected shock, the fork from historical into projected, the projected tick
 * stream, the decision history, and the final counterfactual result.
 *
 * The one rule that runs through all of it: a value is either HISTORICAL or
 * PROJECTED, and the two are never mixed or relabelled.
 */
import { createContext, useCallback, useContext, useEffect, useMemo, useRef, useState } from "react";

import {
	acceptSimulationDecision,
	fetchAvailableRaces,
	fetchCircuitData,
	fetchCounterfactualSummary,
	fetchRecommendation,
	fetchSimulationAssumptions,
	fetchSimulationTick,
	fetchTimeline,
	fetchWhatIf,
	injectSimulationShock,
	loadRaceSession,
} from "../api";

const SimulationLabContext = createContext(null);

export const PHASES = { HISTORICAL: "HISTORICAL", PROJECTED: "PROJECTED" };
/* PRD FR-7: a re-optimisation slower than this is shown as stale, not as fresh. */
export const REOPTIMIZATION_BUDGET_SECONDS = 1.0;

export function SimulationLabProvider({ children }) {
	const [races, setRaces] = useState([]);
	const [selectedRace, setSelectedRace] = useState(null);
	const [session, setSession] = useState(null);
	const [circuit, setCircuit] = useState(null);
	const [circuitLoading, setCircuitLoading] = useState(false);

	const [currentLap, setCurrentLap] = useState(1);
	const [phase, setPhase] = useState(PHASES.HISTORICAL);
	const [forkLap, setForkLap] = useState(null);
	const [committedAction, setCommittedAction] = useState(null);

	const [shock, setShock] = useState(null);
	const [reoptimizationStatus, setReoptimizationStatus] = useState(null);

	const [recommendation, setRecommendation] = useState(null);
	const [whatIf, setWhatIf] = useState(null);
	const [projectedTicks, setProjectedTicks] = useState([]);
	const [summary, setSummary] = useState(null);
	const [assumptions, setAssumptions] = useState([]);
	const [timelineEvents, setTimelineEvents] = useState([]);

	const [busy, setBusy] = useState(false);
	const [error, setError] = useState(null);
	// True when a scheduled strategy review falls due on the lap being viewed, so
	// the decision panel can offer the strategist a fresh call (PRD 5.H / 9.1).
	const [isReviewLap, setReviewLap] = useState(false);

	const requestRef = useRef(0);
	const totalLaps = session?.total_laps ?? 0;
	const geometryVerified = selectedRace?.simulation_geometry_available === true;

	const resetRun = useCallback(() => {
		setPhase(PHASES.HISTORICAL);
		setForkLap(null);
		setCommittedAction(null);
		setShock(null);
		setReoptimizationStatus(null);
		setProjectedTicks([]);
		setSummary(null);
		setAssumptions([]);
		setCurrentLap(1);
		setReviewLap(false);
		setError(null);
	}, []);

	/* Selecting a race never silently switches to a different one. A race without
	 * verified geometry stays selected and shows the honest empty state, because
	 * hiding it or substituting another race would misrepresent what is available
	 * (PRD 9.4, 9.6). */
	const selectRace = useCallback(
		(race) => {
			setSelectedRace(race);
			setSession(null);
			setCircuit(null);
			setRecommendation(null);
			setWhatIf(null);
			resetRun();
		},
		[resetRun],
	);

	useEffect(() => {
		const controller = new AbortController();
		fetchAvailableRaces(controller.signal)
			.then((available) => {
				setRaces(available);
				// Open on a geometry-verified race when one exists, so the lab starts
				// in its full form; the others stay selectable with their real state.
				const preferred = available.find((race) => race.simulation_geometry_available);
				if (preferred ?? available[0]) selectRace(preferred ?? available[0]);
			})
			.catch((cause) => {
				if (cause.name !== "AbortError") setError(cause.message);
			});
		return () => controller.abort();
	}, [selectRace]);

	useEffect(() => {
		if (!selectedRace) return undefined;
		const controller = new AbortController();
		loadRaceSession(selectedRace.year, selectedRace.event, controller.signal)
			.then(setSession)
			.catch((cause) => {
				if (cause.name !== "AbortError") setError(cause.message);
			});
		return () => controller.abort();
	}, [selectedRace]);

	/* Circuit geometry is only fetched for a race the backend verified. An
	 * unverified race is never probed for a track to draw anyway. */
	useEffect(() => {
		if (!selectedRace || !geometryVerified) {
			setCircuit(null);
			return undefined;
		}
		const controller = new AbortController();
		setCircuitLoading(true);
		fetchCircuitData(selectedRace.year, selectedRace.event, controller.signal)
			.then((data) => {
				setCircuit(data);
				setCircuitLoading(false);
			})
			.catch((cause) => {
				if (cause.name === "AbortError") return;
				setCircuit(null);
				setCircuitLoading(false);
			});
		return () => controller.abort();
	}, [selectedRace, geometryVerified]);

	/* After the fork, follow the projected branch: every lap has its own state,
	 * its own re-optimisation and its own pit phases. Without this the whole
	 * projected phase rendered the fork lap's tick forever, so the run looked
	 * like nothing happened - no stops, no re-optimisations, nothing moving. */
	useEffect(() => {
		if (!session || !totalLaps || phase !== PHASES.PROJECTED) return undefined;
		const controller = new AbortController();
		const requestId = ++requestRef.current;

		fetchSimulationTick(Math.min(currentLap, totalLaps), controller.signal)
			.then((tick) => {
				if (requestId !== requestRef.current) return;
				recordProjectedTick(tick);
				setReviewLap(Boolean(tick.is_review_lap));
				// Branches computed from the projected state for this same lap, so
				// the panel's heading and its numbers always refer to one lap.
				if (tick.what_if) setWhatIf(tick.what_if);
			})
			.catch((cause) => {
				if (cause.name !== "AbortError") setError(cause.message);
			});
		return () => controller.abort();
	}, [session, currentLap, totalLaps, phase]);

	/* Historical phase only: the engine's live call for the lap being viewed.
	 * After the fork the projected ticks carry their own recommendation, and a
	 * historical-phase value must never be shown against projected state. */
	useEffect(() => {
		if (!session || !totalLaps || phase !== PHASES.HISTORICAL) return undefined;
		const controller = new AbortController();
		const requestId = ++requestRef.current;
		const lap = Math.min(currentLap, totalLaps);

		Promise.all([
			fetchRecommendation(lap, controller.signal),
			fetchWhatIf(lap, controller.signal),
		])
			.then(([fresh, branches]) => {
				if (requestId !== requestRef.current) return;
				setRecommendation(fresh);
				setWhatIf(branches.branches);
			})
			.catch((cause) => {
				if (cause.name !== "AbortError") setError(cause.message);
			});
		return () => controller.abort();
	}, [session, currentLap, totalLaps, phase]);

	const refreshTimeline = useCallback(() => {
		fetchTimeline()
			.then((data) => setTimelineEvents(data.events ?? []))
			.catch(() => setTimelineEvents([]));
	}, []);

	useEffect(() => {
		if (session) refreshTimeline();
	}, [session, refreshTimeline]);

	const injectShock = useCallback(
		async (eventType) => {
			setBusy(true);
			setError(null);
			try {
				const response = await injectSimulationShock(eventType, currentLap);
				setShock({ eventType, lap: currentLap, tick: response.tick });
				setReoptimizationStatus({
					seconds: response.reoptimization_seconds,
					withinBudget: response.within_budget,
				});
				// The engine re-optimises under the shock, so the standing call and
				// the what-if both have to be replaced rather than reused (PRD 9.9).
				const [fresh, branches] = await Promise.all([
					fetchRecommendation(currentLap),
					fetchWhatIf(currentLap),
				]);
				setRecommendation(fresh);
				setWhatIf(branches.branches);
				refreshTimeline();
			} catch (cause) {
				setError(`Shock injection failed: ${cause.message}`);
			} finally {
				setBusy(false);
			}
		},
		[currentLap, refreshTimeline],
	);

	const commitDecision = useCallback(
		async (action) => {
			setBusy(true);
			setError(null);
			try {
				const response = await acceptSimulationDecision(action, currentLap);
				if (!response.tick) throw new Error("The backend returned no projected tick");

				// The first decision is the fork. Later ones change the plan inside
				// the branch that already exists, so the fork lap stays where it was.
				setForkLap((existing) => existing ?? currentLap);
				setCommittedAction(action);
				setPhase(PHASES.PROJECTED);
				// Everything after this lap was projected under the old plan and is
				// now wrong, so it is dropped rather than left on screen.
				setProjectedTicks((current) => [
					...current.filter((tick) => tick.lap < currentLap),
					response.tick,
				]);

				const [finalSummary, stated] = await Promise.all([
					fetchCounterfactualSummary(),
					fetchSimulationAssumptions(),
				]);
				setSummary(finalSummary);
				setAssumptions(stated.assumptions ?? []);
				refreshTimeline();
			} catch (cause) {
				setError(`Counterfactual fork failed: ${cause.message}`);
			} finally {
				setBusy(false);
			}
		},
		[currentLap, refreshTimeline],
	);

	const recordProjectedTick = useCallback((tick) => {
		setProjectedTicks((current) => {
			const others = current.filter((item) => item.lap !== tick.lap);
			return [...others, tick].sort((left, right) => left.lap - right.lap);
		});
	}, []);

	const projectedTick = useMemo(
		() => projectedTicks.find((tick) => tick.lap === currentLap) ?? projectedTicks.at(-1) ?? null,
		[projectedTicks, currentLap],
	);

	/* After the fork the recommendation on screen is the one carried by the
	 * projected tick for the lap being viewed - never the historical-phase value. */
	const activeRecommendation = useMemo(() => {
		if (phase !== PHASES.PROJECTED) return recommendation;
		return projectedTick?.decisions?.find((decision) => decision.car === "P2")?.recommendation ?? null;
	}, [phase, recommendation, projectedTick]);

	const value = useMemo(
		() => ({
			races,
			selectedRace,
			selectRace,
			session,
			circuit,
			circuitLoading,
			geometryVerified,
			currentLap,
			setCurrentLap,
			totalLaps,
			phase,
			forkLap,
			committedAction,
			shock,
			reoptimizationStatus,
			isReviewLap,
			recommendation: activeRecommendation,
			whatIf,
			projectedTicks,
			projectedTick,
			recordProjectedTick,
			summary,
			assumptions,
			timelineEvents,
			busy,
			error,
			injectShock,
			commitDecision,
			resetRun,
		}),
		[
			races,
			selectedRace,
			selectRace,
			session,
			circuit,
			circuitLoading,
			geometryVerified,
			currentLap,
			totalLaps,
			phase,
			forkLap,
			committedAction,
			shock,
			reoptimizationStatus,
			isReviewLap,
			activeRecommendation,
			whatIf,
			projectedTicks,
			projectedTick,
			recordProjectedTick,
			summary,
			assumptions,
			timelineEvents,
			busy,
			error,
			injectShock,
			commitDecision,
			resetRun,
		],
	);

	return <SimulationLabContext.Provider value={value}>{children}</SimulationLabContext.Provider>;
}

export function useSimulationLab() {
	const context = useContext(SimulationLabContext);
	if (!context) throw new Error("useSimulationLab must be used inside SimulationLabProvider");
	return context;
}
