import { Note } from "../shared/primitives";
import DecisionHistory from "./DecisionHistory";
import SimulationDecisionPanel from "./SimulationDecisionPanel";
import SimulationHeader from "./SimulationHeader";
import SimulationRaceSelector from "./SimulationRaceSelector";
import SimulationRaceState from "./SimulationRaceState";
import SimulationSummary from "./SimulationSummary";
import SimulationTimeline from "./SimulationTimeline";
import SimulationTrack from "./SimulationTrack";
import SimulationWhatIf from "./SimulationWhatIf";
import { PHASES, useSimulationLab } from "./SimulationLabProvider";

/*
 * Simulation Lab - the counterfactual workspace (PRD section 9).
 *
 * A different application from Race Analysis, not a themed variant: different
 * layout, different components, its own provider, and a track as the largest
 * element on the page. The phase-projected class puts a persistent watermark
 * behind everything once the run forks, so projected state can never be mistaken
 * for the record (PRD 9.3).
 */
export default function SimulationLabPage({ onOpenRaceAnalysis }) {
	const { session, phase, error } = useSimulationLab();
	const projected = phase === PHASES.PROJECTED;

	return (
		<main className={`product-shell lab-shell ${projected ? "phase-projected" : "phase-historical"}`}>
			<SimulationHeader onOpenRaceAnalysis={onOpenRaceAnalysis} />

			{error && <Note tone="error">{error}</Note>}

			<div className="lab-layout">
				<aside className="lab-rail">
					<SimulationRaceSelector />
					<DecisionHistory />
				</aside>

				<div className="lab-main">
					{/* Largest element on the page, per PRD 9.5. */}
					<SimulationTrack />

					{session ? (
						<>
							<SimulationRaceState />
							<SimulationDecisionPanel />
							<SimulationWhatIf />
							<SimulationTimeline />
							<SimulationSummary />
						</>
					) : (
						<Note>Loading race data from FastF1…</Note>
					)}
				</div>
			</div>
		</main>
	);
}
