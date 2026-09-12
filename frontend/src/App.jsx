import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import WhatIfPanel from "./components/WhatIfPanel";
import StrategyTimeline from "./components/StrategyTimeline";
import ReplayControls from "./components/ReplayControls";
import AppHeader from "./components/AppHeader";
import PrimaryDecision from "./components/PrimaryDecision";
import RaceCarPanels from "./components/RaceCarPanels";
import TrackVisualization from "./components/TrackVisualization";
import ShockEventConsole from "./components/ShockEventConsole";
import DecisionComparison from "./components/DecisionComparison";
import CounterfactualSimulation from "./components/CounterfactualSimulation";
import ForkTransition from "./components/ForkTransition";
import DualLayerTimeline from "./components/DualLayerTimeline";
import PostDecisionImpact from "./components/PostDecisionImpact";
import FinalResult from "./components/FinalResult";
import HeadToHead from "./components/HeadToHead";
import TyreDegradationView from "./components/TyreDegradationView";
import { acceptSimulationDecision, fetchAvailableRaces, fetchCounterfactualSummary, fetchRecommendation, fetchTimeline, injectShockEvent, loadRaceSession } from "./api";
import { useSimulation } from "./state/SimulationContext";

const BASE_CONFIG = {
	current_compound: "UNKNOWN",
};

// Cycled through so repeated shock injections exercise different uncertainty
// events against the confidence scorer instead of repeating the same input.
const SHOCK_CYCLE = ["safety_car", "rain", "vsc", "puncture"];

const REOPT_BUDGET_MS = 1000;

export default function App() {
	const {
		selectedRace,
		currentLap,
		totalLaps,
		raceMetadata,
		selectRace,
		setRaceMetadata,
		setCurrentLap,
		resetSimulation,
		replayMode,
		forkLap,
		acceptedAction,
		acceptCounterfactual,
		shockEvent,
		shockLap,
		shockDecisions,
		recordShockEvent,
		recordProjectedTick,
		projectedTicks,
		counterfactualSummary,
		setCounterfactualSummary,
	} = useSimulation();
	const [races, setRaces] = useState([]);
	const [raceLoading, setRaceLoading] = useState(true);
	const [replayInstanceKey, setReplayInstanceKey] = useState(0);
	const [recommendation, setRecommendation] = useState(null);
	const [recommendationPending, setRecommendationPending] = useState(false);
	const [loadError, setLoadError] = useState(null);
	const [reoptStatus, setReoptStatus] = useState("loading"); // loading | synced | recomputing | stale_timeout | error
	const [reoptError, setReoptError] = useState(null);
	const [currentTyreAge, setCurrentTyreAge] = useState(0);
	const [uncertaintyEvents, setUncertaintyEvents] = useState([]);
	const [timelineEvents, setTimelineEvents] = useState([]);
	const [timelineLoading, setTimelineLoading] = useState(true);
	const [timelineError, setTimelineError] = useState(null);
	const [playback, setPlayback] = useState({ isPlaying: false, play: null, pause: null });
	
	const currentLapRef = useRef(1);
	const currentTyreAgeRef = useRef(0);
	const shockIndexRef = useRef(0);
	const tickRequestRef = useRef(0);
	const strategyLapTimes = useMemo(
		() => (raceMetadata?.p2_lap_states ?? [])
			.map((lap) => lap.lap_time_seconds)
			.filter((lapTime) => lapTime != null),
		[raceMetadata],
	);
	const currentLapState = useMemo(
		() => (raceMetadata?.p2_lap_states ?? []).find((lap) => lap.lap_number === currentLap)
			?? (raceMetadata?.p2_lap_states ?? []).filter((lap) => lap.lap_number <= currentLap).at(-1),
		[raceMetadata, currentLap],
	);
	const currentCompound = currentLapState?.compound
		?? (raceMetadata?.p2_lap_states ?? []).find((lap) => lap.compound)?.compound
		?? BASE_CONFIG.current_compound;
	const initialCompound = (raceMetadata?.p2_lap_states ?? []).find((lap) => lap.compound)?.compound
		?? BASE_CONFIG.current_compound;

	const resetRaceData = useCallback(() => {
		setRecommendation(null);
		setRecommendationPending(false);
		setLoadError(null);
		setReoptStatus("loading");
		setReoptError(null);
		setCurrentTyreAge(0);
		setUncertaintyEvents([]);
		setTimelineEvents([]);
		setTimelineLoading(true);
		setTimelineError(null);
		currentLapRef.current = 1;
		currentTyreAgeRef.current = 0;
		shockIndexRef.current = 0;
		setReplayInstanceKey((key) => key + 1);
	}, []);

	const handleRaceChange = useCallback((race) => {
		resetRaceData();
		selectRace(race);
	}, [resetRaceData, selectRace]);

	const handleReset = useCallback(() => {
		resetRaceData();
		resetSimulation();
		setCurrentLap(1);
	}, [resetRaceData, resetSimulation, setCurrentLap]);

	const handlePlaybackStateChange = useCallback((nextPlayback) => {
		setPlayback(nextPlayback);
	}, []);

	const refreshTimeline = async () => {
		try {
			const data = await fetchTimeline();
			setTimelineEvents(data.events);
			setTimelineError(null);
		} catch (err) {
			setTimelineError(err.message);
		} finally {
			setTimelineLoading(false);
		}
	};

	useEffect(() => {
		let cancelled = false;
		fetchAvailableRaces()
			.then((availableRaces) => {
				if (!cancelled) {
					setRaces(availableRaces);
					if (availableRaces[0]) handleRaceChange(availableRaces[0]);
				}
			})
			.catch((err) => {
				if (!cancelled) {
					setLoadError(err.message);
					setRaceLoading(false);
				}
			});
		return () => { cancelled = true; };
	}, [handleRaceChange]);

	useEffect(() => {
		if (!selectedRace) return undefined;
		const controller = new AbortController();
		setRaceLoading(true);
		loadRaceSession(selectedRace.year, selectedRace.event, controller.signal)
			.then((metadata) => {
				setRaceMetadata(metadata);
				const initialTyreAge = metadata.p2_lap_states?.find((lap) => lap.lap_number === 1)?.tyre_life ?? 0;
				currentTyreAgeRef.current = initialTyreAge;
				setCurrentTyreAge(initialTyreAge);
				setRaceLoading(false);
			})
			.catch((err) => {
				if (err.name !== "AbortError") {
					setLoadError(err.message);
					setRaceLoading(false);
				}
			});
		return () => controller.abort();
	}, [selectedRace, setRaceMetadata]);

	useEffect(() => {
		if (!selectedRace || !totalLaps || !strategyLapTimes.length) return undefined;
		const endLap = totalLaps;
		const controller = new AbortController();
		fetchRecommendation({
			...BASE_CONFIG,
			current_compound: initialCompound,
			end_lap: endLap,
			start_lap: 1,
			current_tyre_age: currentTyreAge,
			lap_time_seconds: strategyLapTimes,
			uncertainty_events: [],
			rival_cover_stop_probability: 0.0,
		}, controller.signal)
			.then((data) => {
				if (controller.signal.aborted) return;
				setRecommendation(data);
				setRecommendationPending(false);
				setReoptStatus("synced");
			})
			.catch((err) => {
				if (err.name === "AbortError") return;
				setLoadError(err.message);
				setReoptStatus("error");
			});
		refreshTimeline();
		return () => controller.abort();
	}, [initialCompound, selectedRace, strategyLapTimes, totalLaps]);

	const handleTick = useCallback((tick) => {
		currentLapRef.current = tick.lapNumber;
		setCurrentLap(tick.lapNumber);
		const observedTyreAge = raceMetadata?.p2_lap_states?.find((lap) => lap.lap_number === tick.lapNumber)?.tyre_life;
		const tyreAge = observedTyreAge ?? 0;
		currentTyreAgeRef.current = tyreAge;
		setCurrentTyreAge(tyreAge);
		if (!totalLaps) return;
		const requestId = ++tickRequestRef.current;
		setRecommendationPending(true);
		fetchRecommendation({
			...BASE_CONFIG,
			current_compound: raceMetadata?.p2_lap_states?.find((lap) => lap.lap_number === tick.lapNumber)?.compound ?? currentCompound,
			end_lap: totalLaps,
			start_lap: Math.min(tick.lapNumber, totalLaps - 1),
			current_tyre_age: tyreAge,
			lap_time_seconds: strategyLapTimes,
			uncertainty_events: uncertaintyEvents,
			rival_cover_stop_probability: 0.0,
		})
			.then((fresh) => {
				if (requestId === tickRequestRef.current) {
					setRecommendation(fresh);
					setRecommendationPending(false);
				}
			})
			.catch((err) => {
				if (requestId === tickRequestRef.current) {
					setReoptError(err.message);
					setRecommendationPending(false);
				}
			});
	}, [currentCompound, raceMetadata, setCurrentLap, strategyLapTimes, totalLaps, uncertaintyEvents]);

	const handleDecision = useCallback(async (action) => {
		try {
			playback.pause?.();
			const response = await acceptSimulationDecision(action, currentLap);
			if (!response.tick) throw new Error("Simulation decision returned no projected tick");
			recordProjectedTick(response.tick);
			acceptCounterfactual(currentLap, action);
			const summary = await fetchCounterfactualSummary();
			setCounterfactualSummary(summary);
			console.info(`[PitSense] Counterfactual transition accepted at Lap ${currentLap}: ${action}`);
		} catch (err) {
			setReoptError(`Counterfactual fork failed: ${err.message}`);
		}
	}, [acceptCounterfactual, currentLap, playback, recordProjectedTick, setCounterfactualSummary]);

	const handleSimulationTick = useCallback((tick) => {
		recordProjectedTick(tick);
		setCurrentLap(tick.lap);
	}, [recordProjectedTick, setCurrentLap]);

	const triggerShockEvent = async (requestedEventType) => {
		if (reoptStatus === "recomputing") return; // one re-optimization in flight at a time
		playback.pause?.();
		const eventType = requestedEventType || SHOCK_CYCLE[shockIndexRef.current % SHOCK_CYCLE.length];
		shockIndexRef.current += 1;
		setReoptStatus("recomputing");
		setReoptError(null);

		const budgetTimer = window.setTimeout(() => {
			setReoptStatus("stale_timeout");
		}, REOPT_BUDGET_MS);

		try {
			const exactLap = currentLapRef.current;
			const shockResponse = await injectShockEvent(eventType, exactLap);
			await refreshTimeline();

			const nextEvents = uncertaintyEvents.includes(eventType) ? uncertaintyEvents : [...uncertaintyEvents, eventType];
			const nextLap = exactLap;
			const nextTyreAge = currentTyreAgeRef.current;
			const fresh = await fetchRecommendation({
				...BASE_CONFIG,
				current_compound: currentCompound,
				end_lap: totalLaps,
				start_lap: nextLap,
				current_tyre_age: nextTyreAge,
				lap_time_seconds: strategyLapTimes,
				uncertainty_events: nextEvents,
				rival_cover_stop_probability: 0.0,
			});

			window.clearTimeout(budgetTimer);
			setRecommendation(fresh);
			setUncertaintyEvents(nextEvents);
			recordShockEvent(
				eventType,
				exactLap,
				{ lap: exactLap, tyreAge: currentTyreAgeRef.current, mode: "HISTORICAL" },
				shockResponse.tick?.decisions ?? [],
			);
			currentLapRef.current = nextLap;
			currentTyreAgeRef.current = nextTyreAge;
			setCurrentLap(nextLap);
			setCurrentTyreAge(nextTyreAge);
			// Only clear the stale indicator once a real response has arrived,
			// even if it arrived after the 1 second budget was already flagged.
			setReoptStatus("synced");
		} catch (err) {
			window.clearTimeout(budgetTimer);
			setReoptError(err.message);
			setReoptStatus("error");
		}
	};

	const statusLabel = {
		loading: "LOADING…",
		synced: "ENGINE SYNCHRONIZED",
		recomputing: "RE-OPTIMIZING…",
		stale_timeout: "RE-OPTIMIZATION STALE (>1s BUDGET)",
		error: "RE-OPTIMIZATION FAILED",
	}[reoptStatus];

	const header = (
		<AppHeader
			races={races}
			onRaceChange={handleRaceChange}
			onReset={handleReset}
			isPlaying={playback.isPlaying}
			onPlayToggle={() => (playback.isPlaying ? playback.pause?.() : playback.play?.())}
		/>
	);
	const whatIfRequest = useMemo(() => ({
		...BASE_CONFIG,
		current_compound: currentCompound,
		end_lap: totalLaps,
		start_lap: currentLap,
		current_tyre_age: currentTyreAge,
		lap_time_seconds: strategyLapTimes,
		uncertainty_events: uncertaintyEvents,
		rival_cover_stop_probability: 0.0,
	}), [totalLaps, currentLap, currentTyreAge, currentCompound, strategyLapTimes, uncertaintyEvents]);
	const historicalLapTimes = useMemo(() => {
		const recorded = [...(raceMetadata?.p2_lap_states ?? [])]
			.sort((a, b) => a.lap_number - b.lap_number)
			.map((lap) => lap.lap_time_seconds);
		return recorded;
	}, [raceMetadata]);
	const projectedLapTimes = useMemo(
		() => Array.from({ length: Math.max(1, totalLaps - (forkLap ?? 1) + 1) }, () => null),
		[totalLaps, forkLap],
	);
	const historicalTick = useMemo(() => {
		if (!raceMetadata || forkLap == null) return null;
		const p1 = raceMetadata.p1_lap_states?.find((item) => item.lap_number === forkLap);
		const p2 = raceMetadata.p2_lap_states?.find((item) => item.lap_number === forkLap);
		return { cars: [{ car: "P1", gap_to_leader_seconds: p1?.gap_to_leader_seconds }, { car: "P2", gap_to_leader_seconds: p2?.gap_to_leader_seconds }] };
	}, [raceMetadata, forkLap]);
	const historicalPitLap = useMemo(() => {
		if (!raceMetadata || forkLap == null) return null;
		const stops = raceMetadata.p2_pit_stops ?? [];
		return stops.find((stop) => stop.lap_number >= forkLap)?.lap_number ?? stops.at(-1)?.lap_number ?? null;
	}, [raceMetadata, forkLap]);
	const projectedTick = projectedTicks.find((tick) => tick.lap === forkLap) ?? projectedTicks.at(-1);
	const projectedFinished = replayMode === "counterfactual" && projectedTicks.some((tick) => tick.lap >= totalLaps);

	if (loadError && !recommendation) {
		return (
			<main className="console-shell">
				{header}
				<p className="error-note">Failed to load initial recommendation: {loadError}</p>
			</main>
		);
	}
	if (!recommendation) {
		return (
			<main className="console-shell">
				{header}
				<p className="data-note">Loading strategy console…</p>
			</main>
		);
	}

	return (
		<main className="console-shell">
			{header}
			<header className="topbar">
				<div><p className="eyebrow">PITSENSE / STRATEGY CONSOLE</p><h1>Race strategy, with its work shown.</h1></div>
				<div className={`mode-badge ${replayMode === "counterfactual" ? "mode-badge-projected" : "mode-badge-historical"}`}>
					{replayMode === "counterfactual" ? "COUNTERFACTUAL — PROJECTED" : "HISTORICAL REPLAY"}
				</div>
			</header>
			<section className="status-strip">
				<span><i className="live-dot" /> {selectedRace?.year} {selectedRace?.event} / Lap {currentLap} of {totalLaps}</span>
				<span>{currentTyreAge ? `${currentCompound} / ${currentTyreAge} laps` : "Tyre state not yet observed"}</span>
				<span className={`status-${reoptStatus}`}>{statusLabel}</span>
			</section>
			{reoptError && <p className="error-note">Re-optimization error: {reoptError}</p>}
			<section className="decision-layout">
				<RaceCarPanels
					metadata={raceMetadata}
					replayMode={replayMode}
					recommendation={recommendation}
					isUpdating={recommendationPending}
					currentLap={currentLap}
					currentTyreAge={currentTyreAge}
				/>
				{recommendation && <PrimaryDecision recommendation={recommendation} currentLap={currentLap} replayMode={replayMode} isUpdating={recommendationPending} onAction={handleDecision} />}
			</section>
			<TrackVisualization metadata={raceMetadata} currentLap={currentLap} replayMode={replayMode} projectedTicks={projectedTicks} />
			<section className="assembly-row">
				<TyreDegradationView currentLap={currentLap} currentTyreAge={currentTyreAge} recommendation={recommendation} />
				<WhatIfPanel request={whatIfRequest} />
			</section>
			<section className="counterfactual-section">
				{replayMode === "counterfactual" && <ForkTransition forkLap={forkLap} action={acceptedAction} />}
				{replayMode === "counterfactual" && <CounterfactualSimulation forkLap={forkLap} currentLap={currentLap} projectedTicks={projectedTicks} />}
				{replayMode === "counterfactual" && <PostDecisionImpact forkLap={forkLap} acceptedAction={acceptedAction} historicalLap={historicalPitLap} historicalTick={historicalTick} projectedTick={projectedTick} />}
				<FinalResult summary={counterfactualSummary} visible={projectedFinished} />
			</section>
			<HeadToHead
				replayMode={replayMode}
				completed={projectedFinished}
				totalLaps={totalLaps}
				forkLap={forkLap}
				raceMetadata={raceMetadata}
				projectedTicks={projectedTicks}
				summary={counterfactualSummary}
			/>
			<section className="workspace-grid assembly-lower" id="comparison">
				<StrategyTimeline events={timelineEvents} loading={timelineLoading} error={timelineError} currentLap={currentLap} />
				{replayMode === "counterfactual" && <DualLayerTimeline forkLap={forkLap} currentLap={currentLap} totalLaps={totalLaps} />}
				<ShockEventConsole currentLap={currentLap} isRecomputing={reoptStatus === "recomputing"} activeEvent={shockEvent} onShock={triggerShockEvent} />
				<DecisionComparison
					eventType={shockEvent}
					lap={shockLap}
					recommendation={recommendation}
					baselineDecision={shockDecisions.find((decision) => decision.car === "P1")}
					onAccept={handleDecision}
				/>
				<ReplayControls
					key={`${replayInstanceKey}-${replayMode}-${forkLap ?? 0}`}
					lapTimes={replayMode === "counterfactual" ? projectedLapTimes : historicalLapTimes}
					startLap={replayMode === "counterfactual" ? forkLap : 1}
					endLap={totalLaps}
					startTyreAge={0}
					onTick={handleTick}
					simulation={replayMode === "counterfactual"}
					onSimulationTick={handleSimulationTick}
					onPlaybackStateChange={handlePlaybackStateChange}
				/>
			</section>
			<footer className="footer-line"><span>Replay data: FastF1 cache</span><span>Historical = solid · Projected = dashed</span><span>Data quality: 2 flagged gaps</span></footer>
		</main>
	);
}
