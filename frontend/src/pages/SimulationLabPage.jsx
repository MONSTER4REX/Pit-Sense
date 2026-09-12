import AppHeader from "../components/AppHeader";
import CounterfactualSimulation from "../components/CounterfactualSimulation";
import DecisionComparison from "../components/DecisionComparison";
import DualLayerTimeline from "../components/DualLayerTimeline";
import FinalResult from "../components/FinalResult";
import ForkTransition from "../components/ForkTransition";
import HeadToHead from "../components/HeadToHead";
import PostDecisionImpact from "../components/PostDecisionImpact";
import RaceCarPanels from "../components/RaceCarPanels";
import ReplayControls from "../components/ReplayControls";
import ShockEventConsole from "../components/ShockEventConsole";
import StrategyTimeline from "../components/StrategyTimeline";
import TrackVisualization from "../components/TrackVisualization";
import TyreDegradationView from "../components/TyreDegradationView";

export default function SimulationLabPage({
	headerProps,
	selectedRace,
	currentLap,
	totalLaps,
	replayMode,
	forkLap,
	acceptedAction,
	raceMetadata,
	recommendation,
	recommendationPending,
	currentTyreAge,
	projectedTicks,
	counterfactualSummary,
	projectedFinished,
	shockEvent,
	shockLap,
	shockDecisions,
	reoptStatus,
	timelineEvents,
	timelineLoading,
	timelineError,
	historicalLapTimes,
	projectedLapTimes,
	replayInstanceKey,
	historicalPitLap,
	historicalTick,
	handleDecision,
	handleShock,
	handleTick,
	handleSimulationTick,
	handlePlaybackStateChange,
}) {
	return (
		<main className="console-shell simulation-lab-page">
			<AppHeader {...headerProps} />
			<header className="topbar">
				<div>
					<p className="eyebrow">PITSENSE / SIMULATION LAB</p>
					<h1>Controlled counterfactual race laboratory.</h1>
				</div>
				<div className={`mode-badge ${replayMode === "counterfactual" ? "mode-badge-projected" : "mode-badge-historical"}`}>
					{replayMode === "counterfactual" ? "COUNTERFACTUAL — PROJECTED" : "HISTORICAL REPLAY"}
				</div>
			</header>
			<section className="status-strip">
				<span><i className="live-dot" /> {selectedRace?.year} {selectedRace?.event} / Lap {currentLap} of {totalLaps}</span>
				<span>P2 = PitSense · P1 = Baseline Strategy</span>
				<span className={`status-${reoptStatus}`}>{replayMode === "counterfactual" ? "PROJECTED STATE" : "HISTORICAL STATE"}</span>
			</section>
			<section className="simulation-lab-hero">
				<RaceCarPanels metadata={raceMetadata} replayMode={replayMode} recommendation={recommendation} isUpdating={recommendationPending} currentLap={currentLap} currentTyreAge={currentTyreAge} />
				<TrackVisualization metadata={raceMetadata} currentLap={currentLap} replayMode={replayMode} projectedTicks={projectedTicks} />
			</section>
			<section className="simulation-lab-strategy">
				<TyreDegradationView currentLap={currentLap} currentTyreAge={currentTyreAge} recommendation={recommendation} />
				<ShockEventConsole currentLap={currentLap} isRecomputing={reoptStatus === "recomputing"} activeEvent={shockEvent} onShock={handleShock} />
				<DecisionComparison eventType={shockEvent} lap={shockLap} recommendation={recommendation} baselineDecision={shockDecisions.find((decision) => decision.car === "P1")} onAccept={handleDecision} />
			</section>
			{replayMode === "counterfactual" && <section className="counterfactual-section">
				<ForkTransition forkLap={forkLap} action={acceptedAction} />
				<CounterfactualSimulation forkLap={forkLap} currentLap={currentLap} projectedTicks={projectedTicks} />
				<PostDecisionImpact forkLap={forkLap} acceptedAction={acceptedAction} historicalLap={historicalPitLap} historicalTick={historicalTick} projectedTick={projectedTicks.at(-1)} />
				<FinalResult summary={counterfactualSummary} visible={projectedFinished} />
			</section>}
			<HeadToHead replayMode={replayMode} completed={projectedFinished} totalLaps={totalLaps} forkLap={forkLap} raceMetadata={raceMetadata} projectedTicks={projectedTicks} summary={counterfactualSummary} />
			<section className="workspace-grid simulation-lab-lower">
				<StrategyTimeline events={timelineEvents} loading={timelineLoading} error={timelineError} currentLap={currentLap} />
				{replayMode === "counterfactual" && <DualLayerTimeline forkLap={forkLap} currentLap={currentLap} totalLaps={totalLaps} />}
				<ReplayControls key={`${replayInstanceKey}-${replayMode}-${forkLap ?? 0}`} lapTimes={replayMode === "counterfactual" ? projectedLapTimes : historicalLapTimes} startLap={replayMode === "counterfactual" ? forkLap : 1} endLap={totalLaps} startTyreAge={0} onTick={handleTick} simulation={replayMode === "counterfactual"} onSimulationTick={handleSimulationTick} onPlaybackStateChange={handlePlaybackStateChange} />
			</section>
		</main>
	);
}
