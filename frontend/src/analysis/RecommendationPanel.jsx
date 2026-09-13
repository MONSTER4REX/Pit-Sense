import { MetricRow, Note, Panel, StatusBadge } from "../shared/primitives";
import { actionLabel, confidenceBand, seconds } from "../shared/format";
import { useRaceAnalysis } from "./RaceAnalysisProvider";

/*
 * The recommendation, its confidence, and the engine's own reasoning.
 *
 * The reasoning sentence is whatever the backend generated from the factors it
 * actually computed. This component never writes an explanation of its own -
 * doing so would put words in the engine's mouth for a decision the frontend did
 * not make (PRD FR-8, FR-10).
 */
export default function RecommendationPanel() {
	const { recommendation, recommendationPending, currentLap } = useRaceAnalysis();

	if (!recommendation) {
		return (
			<Panel label="PITSENSE RECOMMENDATION" tone="historical">
				<Note>Waiting for the engine's first computation…</Note>
			</Panel>
		);
	}

	const { action, pit_lap, undercut_risk_tier, confidence, reasoning } = recommendation;
	// A path with no stop on it has no pit lap. It used to report the final lap of
	// the race, which read as an instruction to act on that lap.
	const callDetail = pit_lap == null ? "NO STOP ON THIS PATH" : `TARGET LAP ${pit_lap}`;
	const riskTone = undercut_risk_tier === "critical" ? "critical" : "neutral";

	return (
		<Panel label="PITSENSE RECOMMENDATION" tone="historical" className="recommendation-panel">
			<div className="recommendation-call">
				<span className="call-action">{actionLabel(action)}</span>
				<span className="call-lap">{callDetail}</span>
			</div>

			{recommendationPending && <Note>Recomputing for lap {currentLap}…</Note>}

			<div className="recommendation-meta">
				<StatusBadge tone={riskTone}>
					UNDERCUT RISK: {(undercut_risk_tier ?? "").toUpperCase()}
				</StatusBadge>
				<StatusBadge tone="neutral">
					CONFIDENCE {confidenceBand(confidence)} · {(confidence?.uncertainty ?? "").toUpperCase()}
				</StatusBadge>
			</div>

			{/* The band is never presented as a bare number: what widened it is
			    listed alongside it. */}
			{confidence?.drivers?.length > 0 && (
				<ul className="confidence-drivers">
					{confidence.drivers.map((driver) => (
						<li key={driver}>{driver}</li>
					))}
				</ul>
			)}

			<section className="reasoning">
				<div className="panel-label">WHY</div>
				<p>{reasoning}</p>
			</section>

			<MetricRow label="Projected total race time on this path" value={seconds(recommendation.projected_total_time_seconds, 1)} />
			{recommendation.degradation_rate_seconds_per_lap != null && (
				<MetricRow
					label={`Measured tyre degradation (${recommendation.degradation_model})`}
					value={`${recommendation.degradation_rate_seconds_per_lap.toFixed(3)}s per lap of tyre age`}
				/>
			)}
		</Panel>
	);
}
