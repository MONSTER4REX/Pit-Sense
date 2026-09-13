import { Note, Panel, StatusBadge } from "../shared/primitives";
import { seconds } from "../shared/format";
import AnalysisTimeline from "./AnalysisTimeline";
import AnalysisWhatIf from "./AnalysisWhatIf";
import FactorBreakdown from "./FactorBreakdown";
import RaceAnalysisHeader from "./RaceAnalysisHeader";
import RecommendationPanel from "./RecommendationPanel";
import { useRaceAnalysis } from "./RaceAnalysisProvider";

/*
 * Race Analysis - the always-available strategist dashboard.
 *
 * The section order below is binding (PRD 8.2):
 *   race selector -> recommendation -> confidence -> why -> what-if ->
 *   factor breakdown -> timeline / race context
 *
 * The selector, and the confidence and reasoning that sit with the
 * recommendation, are inside RaceAnalysisHeader and RecommendationPanel
 * respectively, so the visible order on screen follows that sequence exactly.
 *
 * Nothing from the Simulation Lab appears here: no shock injection, no fork, no
 * decision history, and no projected value of any kind (PRD 8.4).
 */
export default function RaceAnalysisPage({ onOpenSimulationLab }) {
	const { session, selectedRace, currentLap, totalLaps, lapState, error, status, tyreModel } =
		useRaceAnalysis();

	if (error && !session) {
		return (
			<main className="product-shell analysis-shell">
				<RaceAnalysisHeader onOpenSimulationLab={onOpenSimulationLab} />
				<Note tone="error">{error}</Note>
			</main>
		);
	}

	if (!session) {
		return (
			<main className="product-shell analysis-shell">
				<RaceAnalysisHeader onOpenSimulationLab={onOpenSimulationLab} />
				<Note>Loading race data from FastF1…</Note>
			</main>
		);
	}

	const dataGaps = (session.p2_data_gaps ?? []).length;

	return (
		<main className="product-shell analysis-shell">
			<RaceAnalysisHeader onOpenSimulationLab={onOpenSimulationLab} />

			<section className="context-strip">
				<span>
					<strong>{session.p2_driver}</strong> · {session.p2_team} · our car (P2)
				</span>
				<span>
					{selectedRace?.year} {selectedRace?.event} · lap {currentLap} of {totalLaps}
				</span>
				<span>
					{lapState?.compound ?? "tyre not recorded"}
					{lapState?.tyre_life != null ? ` · ${lapState.tyre_life} laps old` : ""}
				</span>
				<span>Gap to leader {seconds(lapState?.gap_to_leader_seconds)}</span>
				<StatusBadge tone={status === "error" ? "critical" : "historical"}>
					{status === "error" ? "ENGINE ERROR" : "HISTORICAL REPLAY"}
				</StatusBadge>
			</section>

			{/* PRD 8.2: recommendation, with its confidence and reasoning, first. */}
			<RecommendationPanel />

			{/* Then the complete What-If. */}
			<AnalysisWhatIf />

			{/* Then the factor breakdown. */}
			<FactorBreakdown />

			{/* Then timeline and race context. */}
			<AnalysisTimeline />

			<Panel label="DATA PROVENANCE" tone="historical" className="provenance">
				<ul>
					<li>
						Historical replay of a completed FastF1 session. PitSense does not connect to live car
						telemetry or a live timing feed.
					</li>
					<li>
						{dataGaps === 0
							? "No gaps were flagged in our car's lap data for this race."
							: `${dataGaps} gap${dataGaps === 1 ? "" : "s"} flagged in our car's source lap data. Missing values are reported, never interpolated.`}
					</li>
					{tyreModel?.active_model && (
						<li>
							Tyre degradation model in use: <strong>{tyreModel.active_model}</strong>. {tyreModel.note}
						</li>
					)}
				</ul>
			</Panel>
		</main>
	);
}
