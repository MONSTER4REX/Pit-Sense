import { Note, Panel, StatusBadge } from "../shared/primitives";
import { seconds, signedSeconds } from "../shared/format";
import { PHASES, useSimulationLab } from "./SimulationLabProvider";

/*
 * The final historical-vs-projected result (PRD 9.8, 5.I).
 *
 * The wording here matters as much as the numbers. PitSense never "changed" a
 * race: it projects what its strategy would have produced under a stated model,
 * and the full assumption trail is printed underneath so the figure is never
 * read as a claim about the recorded result.
 */
export default function SimulationSummary() {
	const { summary, assumptions, phase, session } = useSimulationLab();

	if (phase !== PHASES.PROJECTED) return null;

	if (!summary) {
		return (
			<Panel label="COUNTERFACTUAL RESULT" tone="projected">
				<Note>Running the projection to the finish…</Note>
			</Panel>
		);
	}

	const historical = summary.historical_finish?.P2;
	const projectedFinish = summary.pitsense_projected_finish;
	const improved = historical != null && projectedFinish != null && projectedFinish < historical;

	return (
		<Panel label="COUNTERFACTUAL RESULT" tone="projected" className="summary-panel">
			<div className="summary-headline">
				<div className="summary-figure">
					<span>Historical finish</span>
					<strong>P{historical}</strong>
					<em>recorded</em>
				</div>
				<div className="summary-arrow">→</div>
				<div className="summary-figure projected-figure">
					<span>PitSense projected finish</span>
					<strong>P{projectedFinish}</strong>
					<em>projected</em>
				</div>
			</div>

			<StatusBadge tone={improved ? "best" : "neutral"}>
				{improved
					? `PROJECTED GAIN OF ${historical - projectedFinish} POSITION${historical - projectedFinish === 1 ? "" : "S"}`
					: "NO PROJECTED POSITION GAIN"}
			</StatusBadge>

			{/* The margins are unsigned, so each is labelled with which side of the
			    opponent our car is on. Otherwise "61s" reads the same whether we
			    finished a minute up the road or a minute adrift. */}
			<div className="summary-metrics">
				<div>
					<span>Historical margin to the opponent</span>
					<strong>
						{seconds(summary.historical_finishing_gap_seconds)}{" "}
						{historical > (summary.historical_finish?.P1 ?? 1) ? "behind" : "ahead"}
					</strong>
				</div>
				<div>
					<span>Projected margin to the opponent</span>
					<strong>
						{seconds(summary.projected_finishing_gap_seconds)}{" "}
						{projectedFinish > summary.baseline_projected_finish ? "behind" : "ahead"}
					</strong>
				</div>
				<div>
					<span>Projected advantage</span>
					<strong>{signedSeconds(summary.projected_advantage_seconds)}</strong>
				</div>
			</div>

			<Note tone="warning">
				This is a projection of what PitSense's strategy would have produced for{" "}
				{session?.p2_driver} under the model stated below. It is not a claim that the recorded race
				would have ended differently.
			</Note>

			<section className="assumption-trail">
				<div className="panel-label">MODEL ASSUMPTIONS</div>
				<ul>
					{(assumptions.length ? assumptions : summary.assumptions ?? []).map((line) => (
						<li key={line}>{line}</li>
					))}
				</ul>
			</section>
		</Panel>
	);
}
