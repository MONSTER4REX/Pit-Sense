import { Note, Panel, StatusBadge } from "../shared/primitives";
import { confidenceBand, seconds, signedSeconds } from "../shared/format";
import { PHASES, useSimulationLab } from "./SimulationLabProvider";

/*
 * The Simulation Lab's own What-If.
 *
 * Deliberately a different component from Race Analysis's AnalysisWhatIf, which
 * must not be replaced or degraded by this one (PRD 9.9, section 10). The
 * difference is not cosmetic: every delta here is labelled a projection, because
 * in this product it is compared against a counterfactual rather than read off
 * the real race.
 */
const BRANCH_ORDER = ["pit_now", "stay_out", "extend_stint"];
const BRANCH_LABEL = { pit_now: "PIT", stay_out: "STAY OUT", extend_stint: "EXTEND" };

export default function SimulationWhatIf() {
	const { whatIf, phase, currentLap, whatIfLap } = useSimulationLab();
	const projected = phase === PHASES.PROJECTED;

	if (!whatIf) {
		return (
			<Panel label="WHAT-IF" tone={projected ? "projected" : "historical"}>
				<Note>Branch projections appear once a race is loaded.</Note>
			</Panel>
		);
	}

	const entries = BRANCH_ORDER.filter((key) => whatIf[key]).map((key) => [key, whatIf[key]]);
	const best = Math.min(...entries.map(([, branch]) => branch.projected_total_time_seconds));

	return (
		<Panel
			label="WHAT-IF — PROJECTED"
			title={`Branches from lap ${whatIfLap ?? currentLap}`}
			tone={projected ? "projected" : "historical"}
			className="lab-whatif"
		>
			<Note tone="warning">
				Every figure below is a projection from the engine's model, not a recorded race outcome.
				{whatIfLap != null && whatIfLap !== currentLap
					? ` These branches were computed at lap ${whatIfLap}, the last point a decision could be committed; the next set arrives at the next review.`
					: ""}
			</Note>

			<div className="lab-branch-row">
				{entries.map(([key, branch]) => {
					const delta = branch.projected_total_time_seconds - best;
					return (
						<div key={key} className={`lab-branch ${delta === 0 ? "lab-branch-best" : ""}`.trim()}>
							<div className="lab-branch-head">
								<span>{BRANCH_LABEL[key]}</span>
								<StatusBadge tone={delta === 0 ? "best" : "neutral"}>
									{delta === 0 ? "FASTEST" : signedSeconds(delta, 1)}
								</StatusBadge>
							</div>
							<div className="lab-branch-metric">
								<span>Projected race time</span>
								<strong>{seconds(branch.projected_total_time_seconds, 1)}</strong>
							</div>
							<div className="lab-branch-metric">
								<span>Confidence</span>
								<strong>{confidenceBand(branch.confidence)}</strong>
							</div>
							<div className="lab-branch-metric">
								<span>Undercut risk</span>
								<strong>{(branch.undercut_risk_tier ?? "").toUpperCase()}</strong>
							</div>
							<p className="lab-branch-why">{branch.reasoning}</p>
						</div>
					);
				})}
			</div>
		</Panel>
	);
}
