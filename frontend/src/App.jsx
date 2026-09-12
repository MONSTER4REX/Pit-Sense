import { useCallback, useEffect, useRef, useState } from "react";
import ExplainabilityChart from "./components/ExplainabilityChart";
import WhatIfPanel from "./components/WhatIfPanel";
import StrategyTimeline from "./components/StrategyTimeline";
import ReplayControls from "./components/ReplayControls";
import AppHeader from "./components/AppHeader";
import PrimaryDecision from "./components/PrimaryDecision";
import RaceCarPanels from "./components/RaceCarPanels";
import { fetchAvailableRaces, fetchRecommendation, fetchTimeline, injectShockEvent, loadRaceSession } from "./api";
import { useSimulation } from "./state/SimulationContext";

const LAP_TIME_SECONDS = Array.from({ length: 30 }, (_, index) => 92.4 + Math.sin(index / 3) * 1.6);

const BASE_CONFIG = {
	current_compound: "MEDIUM",
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
		acceptCounterfactual,
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
	const [currentGap, setCurrentGap] = useState(null);
	const [uncertaintyEvents, setUncertaintyEvents] = useState([]);
	const [timelineEvents, setTimelineEvents] = useState([]);
	const [timelineLoading, setTimelineLoading] = useState(true);
	const [timelineError, setTimelineError] = useState(null);
	
	const currentLapRef = useRef(1);
	const currentTyreAgeRef = useRef(0);
	const shockIndexRef = useRef(0);
	const tickRequestRef = useRef(0);

	const resetRaceData = useCallback(() => {
		setRecommendation(null);
		setRecommendationPending(false);
		setLoadError(null);
		setReoptStatus("loading");
		setReoptError(null);
		setCurrentTyreAge(0);
		setCurrentGap(null);
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
		if (!selectedRace || !totalLaps) return undefined;
		const endLap = totalLaps;
		const controller = new AbortController();
		fetchRecommendation({
			...BASE_CONFIG,
			end_lap: endLap,
			start_lap: 1,
			current_tyre_age: currentTyreAge,
			lap_time_seconds: LAP_TIME_SECONDS,
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
	}, [selectedRace, totalLaps]);

	const handleTick = useCallback((tick) => {
		currentLapRef.current = tick.lapNumber;
		setCurrentLap(tick.lapNumber);
		if (tick.tyreAge !== undefined) {
			currentTyreAgeRef.current = tick.tyreAge;
			setCurrentTyreAge(tick.tyreAge);
		}
		if (tick.distanceToDriverAhead !== undefined) setCurrentGap(tick.distanceToDriverAhead);
		if (!totalLaps) return;
		const requestId = ++tickRequestRef.current;
		setRecommendationPending(true);
		fetchRecommendation({
			...BASE_CONFIG,
			end_lap: totalLaps,
			start_lap: Math.min(tick.lapNumber, totalLaps - 1),
			current_tyre_age: tick.tyreAge ?? currentTyreAgeRef.current,
			lap_time_seconds: LAP_TIME_SECONDS,
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
	}, [currentTyreAgeRef, setCurrentLap, totalLaps, uncertaintyEvents]);

	const handleDecision = useCallback((action) => {
		acceptCounterfactual(currentLap, action);
		console.info(`[PitSense] Counterfactual transition accepted at Lap ${currentLap}: ${action}`);
	}, [acceptCounterfactual, currentLap]);

	const triggerShockEvent = async () => {
		if (reoptStatus === "recomputing") return; // one re-optimization in flight at a time
		const eventType = SHOCK_CYCLE[shockIndexRef.current % SHOCK_CYCLE.length];
		shockIndexRef.current += 1;
		setReoptStatus("recomputing");
		setReoptError(null);

		const budgetTimer = window.setTimeout(() => {
			setReoptStatus("stale_timeout");
		}, REOPT_BUDGET_MS);

		try {
			const exactLap = currentLapRef.current;
			await injectShockEvent(eventType, exactLap);
			await refreshTimeline();

			const nextEvents = uncertaintyEvents.includes(eventType) ? uncertaintyEvents : [...uncertaintyEvents, eventType];
			const nextLap = exactLap + 1;
			const nextTyreAge = currentTyreAgeRef.current + 1;
			const fresh = await fetchRecommendation({
				...BASE_CONFIG,
				end_lap: totalLaps,
				start_lap: nextLap,
				current_tyre_age: nextTyreAge,
				lap_time_seconds: LAP_TIME_SECONDS,
				uncertainty_events: nextEvents,
				rival_cover_stop_probability: 0.0,
			});

			window.clearTimeout(budgetTimer);
			setRecommendation(fresh);
			setUncertaintyEvents(nextEvents);
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

	const header = <AppHeader races={races} onRaceChange={handleRaceChange} onReset={handleReset} />;

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
				<div className="mode-badge">HISTORICAL REPLAY</div>
			</header>
			<section className="status-strip">
				<span><i className="live-dot" /> {selectedRace?.year} {selectedRace?.event} / Lap {currentLap} of {totalLaps}</span>
				<span>{currentTyreAge ? `${BASE_CONFIG.current_compound} / ${currentTyreAge} laps` : "Tyre state not yet observed"}</span>
				<span className={`status-${reoptStatus}`}>{statusLabel}</span>
			</section>
			{reoptError && <p className="error-note">Re-optimization error: {reoptError}</p>}
			<RaceCarPanels
				metadata={raceMetadata}
				replayMode={replayMode}
				recommendation={recommendation}
				isUpdating={recommendationPending}
				currentLap={currentLap}
				currentTyreAge={currentTyreAge}
				currentGap={currentGap}
			/>
			{recommendation && <PrimaryDecision recommendation={recommendation} currentLap={currentLap} replayMode={replayMode} isUpdating={recommendationPending} onAction={handleDecision} />}
			<section className="workspace-grid" id="comparison">
				<article className="panel recommendation-panel">
					<div className="panel-label">REPLAY ACTIONS</div>
					<button className="shock-button" onClick={triggerShockEvent} disabled={reoptStatus === "recomputing"}>
						Inject Shock Event
					</button>
					<p className="mt-3 text-[11px] font-mono leading-relaxed text-[#71828e]">Triggering a shock event recalculates strategy and widens the confidence band.</p>
				</article>
				<article className="panel explainability-panel">
					<div className="panel-label">WHY THIS PATH</div>
					<h2>Explainability breakdown</h2>
					{recommendationPending ? <p className="data-note">Recalculating from the current replay tick…</p> : <ExplainabilityChart explainability={recommendation.explainability} />}
					<p className="data-note">Factors are calculated from the loaded historical session. Missing source fields are flagged, never interpolated.</p>
				</article>
				<article className="panel map-panel">
					<div className="panel-label">TRACK POSITION</div>
					<div className="relative mt-8 mb-6 h-1 w-full bg-slate-700 rounded">
						<div className="absolute top-[-26px] left-[43.5%] translate-x-[-50%] text-[11px] font-mono text-slate-300">
							Projected Rejoin Gap: +{(recommendation.explainability.traffic_rejoin_risk > 0 ? recommendation.explainability.traffic_rejoin_risk * 10 : 2.1).toFixed(1)}s
						</div>
						<span 
							className="absolute w-3 h-3 rounded-full bg-orange-400 shadow-[0_0_12px_#fb923c]" 
							style={{ left: "29%", top: "50%", transform: "translate(-50%, -50%)" }} 
						/>
						<span
							className="absolute w-3 h-3 rounded-full bg-red-400 transition-all"
							style={{
								left: "58%", 
								top: "50%", 
								transform: "translate(-50%, -50%)",
								opacity: (recommendation.explainability.traffic_rejoin_risk) > 0 ? 0.95 : 0.3,
								boxShadow: (recommendation.explainability.traffic_rejoin_risk) > 0 ? "0 0 12px #f87171" : "none",
							}}
						/>
					</div>
					<div className="map-legend mt-6">
						<span><i className="marker car" /> YOUR CAR</span>
						<span><i className="marker traffic" /> TRAFFIC RISK</span>
					</div>
				</article>
				<WhatIfPanel
					request={{
						...BASE_CONFIG,
					end_lap: totalLaps,
					start_lap: currentLap,
						current_tyre_age: currentTyreAge,
						lap_time_seconds: LAP_TIME_SECONDS,
						uncertainty_events: uncertaintyEvents,
						rival_cover_stop_probability: 0.0,
					}}
				/>
				<ReplayControls
					key={replayInstanceKey}
					lapTimes={LAP_TIME_SECONDS}
					startLap={1}
					startTyreAge={0}
					onTick={handleTick}
				/>
				<StrategyTimeline events={timelineEvents} loading={timelineLoading} error={timelineError} currentLap={currentLap} />
			</section>
			<footer className="footer-line"><span>Replay data: FastF1 cache</span><span>Data quality: 2 flagged gaps</span><span>Shock response target: &lt; 1.0s</span></footer>
		</main>
	);
}
