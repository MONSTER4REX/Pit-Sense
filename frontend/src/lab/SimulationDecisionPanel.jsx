import { Button, Note, Panel, StatusBadge } from "../shared/primitives";
import { actionLabel, confidenceBand, seconds } from "../shared/format";
import { PHASES, REOPTIMIZATION_BUDGET_SECONDS, useSimulationLab } from "./SimulationLabProvider";

/*
 * Shock injection, PitSense vs. baseline, and the strategist's own decision
 * (PRD 9.1, 9.7, FR-18).
 *
 * The panel keeps two things visibly separate: what PitSense recommends, and
 * what the user chooses. Committing a decision is what forks the simulation.
 */
const SHOCKS = [
	{ id: "safety_car", label: "SAFETY CAR" },
	{ id: "vsc", label: "VIRTUAL SAFETY CAR" },
	{ id: "rain", label: "RAIN" },
	{ id: "puncture", label: "PUNCTURE" },
];

const DECISIONS = [
	{ id: "PIT", label: "PIT" },
	{ id: "STAY_OUT", label: "STAY OUT" },
	{ id: "EXTEND", label: "EXTEND" },
];

export default function SimulationDecisionPanel() {
	const {
		phase,
		currentLap,
		shock,
		recommendation,
		reoptimizationStatus,
		projectedTick,
		injectShock,
		commitDecision,
		committedAction,
		isReviewLap,
		busy,
		geometryVerified,
	} = useSimulationLab();

	const projected = phase === PHASES.PROJECTED;
	const baseline =
		projectedTick?.decisions?.find((decision) => decision.car === "P1") ??
		shock?.tick?.decisions?.find((decision) => decision.car === "P1") ??
		null;

	return (
		<Panel
			label="STRATEGY DECISION"
			tone={projected ? "projected" : "historical"}
			className="decision-panel"
		>
			{!projected && (
				<section className="shock-console">
					<div className="panel-label">INJECT A SHOCK AT LAP {currentLap}</div>
					<div className="shock-buttons">
						{SHOCKS.map((option) => (
							<Button
								key={option.id}
								variant={shock?.eventType === option.id ? "active" : "default"}
								disabled={busy || !geometryVerified}
								onClick={() => injectShock(option.id)}
							>
								{option.label}
							</Button>
						))}
					</div>
					{shock && (
						<Note>
							{shock.eventType.replace("_", " ").toUpperCase()} injected at lap {shock.lap}.
						</Note>
					)}
					{/* FR-7: a recomputation over budget is shown as stale, not as fresh. */}
					{reoptimizationStatus && (
						<StatusBadge tone={reoptimizationStatus.withinBudget ? "verified" : "critical"}>
							{reoptimizationStatus.withinBudget
								? `RE-OPTIMISED IN ${reoptimizationStatus.seconds.toFixed(3)}s`
								: `STALE — ${reoptimizationStatus.seconds.toFixed(3)}s EXCEEDS THE ${REOPTIMIZATION_BUDGET_SECONDS.toFixed(1)}s BUDGET`}
						</StatusBadge>
					)}
				</section>
			)}

			<section className="decision-columns">
				<div className="decision-column">
					<div className="panel-label">PITSENSE RECOMMENDATION</div>
					{recommendation ? (
						<>
							<div className="decision-call">{actionLabel(recommendation.action)}</div>
							<div className="decision-detail">
								<span>Target lap</span>
								<strong>{recommendation.pit_lap}</strong>
							</div>
							<div className="decision-detail">
								<span>Confidence</span>
								<strong>{confidenceBand(recommendation.confidence)}</strong>
							</div>
							<p className="decision-why">{recommendation.reasoning}</p>
						</>
					) : (
						<Note>Waiting for the engine.</Note>
					)}
				</div>

				<div className="decision-column baseline-column">
					<div className="panel-label">BASELINE STRATEGY</div>
					{baseline ? (
						<>
							<div className="decision-call">{actionLabel(baseline.action)}</div>
							<div className="decision-detail">
								<span>Target lap</span>
								<strong>{baseline.target_lap}</strong>
							</div>
							<div className="decision-detail">
								<span>Projected cost</span>
								<strong>{seconds(baseline.projected_time_cost, 1)}</strong>
							</div>
							<p className="decision-why">{baseline.explanation}</p>
						</>
					) : (
						<Note>The baseline comparator runs once a shock is injected.</Note>
					)}
				</div>
			</section>

			{/* After the fork the strategist is not locked out: at every scheduled
			    review the engine produces a fresh recommendation, and a fresh
			    recommendation you cannot act on is just a notification (PRD 5.H). */}
			<section className="your-decision">
				<div className="panel-label">
					{projected ? "CHANGE THE PLAN" : "YOUR DECISION"}
				</div>

				{projected && !isReviewLap && (
					<Note>
						Committed to {actionLabel(committedAction)}. The engine re-optimises on its own at
						each scheduled review — play on to the next one to change the call.
					</Note>
				)}

				{(!projected || isReviewLap) && (
					<>
						<div className="decision-buttons">
							{DECISIONS.map((option) => (
								<Button
									key={option.id}
									variant="commit"
									disabled={busy || (!projected && !shock) || !geometryVerified}
									onClick={() => commitDecision(option.id)}
								>
									{option.label}
								</Button>
							))}
						</div>
						<Note>
							{!geometryVerified
								? "This race has no verified geometry, so the counterfactual run is disabled for it."
								: projected
									? `Strategy review due at lap ${currentLap}. Committing here changes the plan from this lap on; the fork stays where it was.`
									: shock
										? "Committing a decision forks the simulation into a projected counterfactual."
										: "Inject a shock first — the counterfactual starts from a changed race."}
						</Note>
					</>
				)}
			</section>
		</Panel>
	);
}
