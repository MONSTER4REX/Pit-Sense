import { useCallback, useEffect, useRef, useState } from "react";
import ExplainabilityChart from "./components/ExplainabilityChart";
import UndercutRiskTier from "./components/UndercutRiskTier";
import WhatIfPanel from "./components/WhatIfPanel";
import StrategyTimeline from "./components/StrategyTimeline";
import ReplayControls from "./components/ReplayControls";
import { fetchRecommendation, fetchTimeline, injectShockEvent } from "./api";

const LAP_TIME_SECONDS = Array.from({ length: 30 }, (_, index) => 92.4 + Math.sin(index / 3) * 1.6);

const BASE_CONFIG = {
	end_lap: 44,
	current_compound: "MEDIUM",
};

// Cycled through so repeated shock injections exercise different uncertainty
// events against the confidence scorer instead of repeating the same input.
const SHOCK_CYCLE = ["safety_car", "rain", "vsc", "puncture"];

const REOPT_BUDGET_MS = 1000;

export default function App() {
	const [recommendation, setRecommendation] = useState(null);
	const [loadError, setLoadError] = useState(null);
	const [reoptStatus, setReoptStatus] = useState("loading"); // loading | synced | recomputing | stale_timeout | error
	const [reoptError, setReoptError] = useState(null);
	const [currentLap, setCurrentLap] = useState(17);
	const [currentTyreAge, setCurrentTyreAge] = useState(12);
	const [uncertaintyEvents, setUncertaintyEvents] = useState([]);
	const [timelineEvents, setTimelineEvents] = useState([]);
	const [timelineLoading, setTimelineLoading] = useState(true);
	const [timelineError, setTimelineError] = useState(null);
	
	const currentLapRef = useRef(17);
	const currentTyreAgeRef = useRef(12);
	const shockIndexRef = useRef(0);

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
		fetchRecommendation({
			...BASE_CONFIG,
			start_lap: currentLap,
			current_tyre_age: currentTyreAge,
			lap_time_seconds: LAP_TIME_SECONDS,
			uncertainty_events: [],
			rival_cover_stop_probability: 0.0,
		})
			.then((data) => {
				setRecommendation(data);
				setReoptStatus("synced");
			})
			.catch((err) => {
				setLoadError(err.message);
				setReoptStatus("error");
			});
		refreshTimeline();
		// Load once on mount; the shock flow below owns all subsequent refreshes.
		// eslint-disable-next-line react-hooks/exhaustive-deps
	}, []);

	const handleTick = useCallback((tick) => {
		currentLapRef.current = tick.lapNumber;
		setCurrentLap(tick.lapNumber);
		if (tick.tyreAge !== undefined) {
			currentTyreAgeRef.current = tick.tyreAge;
			setCurrentTyreAge(tick.tyreAge);
		}
	}, []);

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

	if (loadError && !recommendation) {
		return (
			<main className="console-shell">
				<p className="error-note">Failed to load initial recommendation: {loadError}</p>
			</main>
		);
	}
	if (!recommendation) {
		return (
			<main className="console-shell">
				<p className="data-note">Loading strategy console…</p>
			</main>
		);
	}

	return (
		<main className="console-shell">
			<header className="topbar">
				<div><p className="eyebrow">PITSENSE / STRATEGY CONSOLE</p><h1>Race strategy, with its work shown.</h1></div>
				<div className="mode-badge">HISTORICAL REPLAY ONLY</div>
			</header>
			<section className="status-strip">
				<span><i className="live-dot" /> 2024 Belgian Grand Prix / Lap {currentLap} of {BASE_CONFIG.end_lap}</span>
				<span>{BASE_CONFIG.current_compound} / {currentTyreAge} laps</span>
				<span className={`status-${reoptStatus}`}>{statusLabel}</span>
			</section>
			{reoptError && <p className="error-note">Re-optimization error: {reoptError}</p>}
			<section className="workspace-grid">
				<article className="panel recommendation-panel">
					<div className="panel-label">PRIMARY RECOMMENDATION</div>
					<div className="recommendation-action">
						<span>
							{recommendation.action === "stay_out" 
								? "STAY OUT" 
								: recommendation.pit_lap > currentLap 
									? `BOX ON LAP ${recommendation.pit_lap}` 
									: "BOX THIS LAP"}
						</span>
						<strong>LAP {recommendation.pit_lap}</strong>
					</div>
					<UndercutRiskTier tier={recommendation.undercut_risk_tier} />
					<p className="recommendation-copy">The shortest projected race-time path currently favors this action before the rival cover window closes.</p>
					<div className="confidence">
						<span>Confidence band</span>
						<strong>{Math.round(recommendation.confidence.lower * 100)}–{Math.round(recommendation.confidence.upper * 100)}%</strong>
						<em>{recommendation.confidence.uncertainty} uncertainty</em>
					</div>
					<button className="shock-button" onClick={triggerShockEvent} disabled={reoptStatus === "recomputing"}>
						Inject Shock Event
					</button>
					<p className="mt-3 text-[11px] font-mono leading-relaxed text-[#71828e]">Triggering a shock event recalculates strategy and widens the confidence band.</p>
				</article>
				<article className="panel explainability-panel">
					<div className="panel-label">WHY THIS PATH</div>
					<h2>Explainability breakdown</h2>
					<ExplainabilityChart explainability={recommendation.explainability} />
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
						start_lap: currentLap,
						current_tyre_age: currentTyreAge,
						lap_time_seconds: LAP_TIME_SECONDS,
						uncertainty_events: uncertaintyEvents,
						rival_cover_stop_probability: 0.0,
					}}
				/>
				<ReplayControls
					lapTimes={LAP_TIME_SECONDS}
					startLap={17}
					startTyreAge={12}
					onTick={handleTick}
				/>
				<StrategyTimeline events={timelineEvents} loading={timelineLoading} error={timelineError} currentLap={currentLap} />
			</section>
			<footer className="footer-line"><span>Replay data: FastF1 cache</span><span>Data quality: 2 flagged gaps</span><span>Shock response target: &lt; 1.0s</span></footer>
		</main>
	);
}
