import { Note, Panel, StatusBadge } from "../shared/primitives";
import { actionLabel } from "../shared/format";
import { useSimulationLab } from "./SimulationLabProvider";

/*
 * Every shock, every user decision, and every re-optimisation, with lap numbers
 * (PRD 9.8, FR-27).
 *
 * Each re-optimisation shows the backend's own computation id and the reason it
 * fired, which is what makes a changed recommendation demonstrably a new
 * computation rather than an old value wearing a new label.
 */
export default function DecisionHistory() {
	const { shock, forkLap, committedAction, projectedTicks, summary } = useSimulationLab();

	const reoptimizations = (summary?.reoptimization_log ?? []).length
		? summary.reoptimization_log
		: projectedTicks
				.filter((tick) => tick.triggers?.length > 0)
				.map((tick) => ({
					lap: tick.lap,
					triggers: tick.triggers,
					p2_decision: tick.decisions?.find((decision) => decision.car === "P2"),
					p1_decision: tick.decisions?.find((decision) => decision.car === "P1"),
					computation_id: tick.decisions?.[0]?.computation_id ?? "",
					reason: "",
				}));

	const rows = [
		shock && {
			key: `shock-${shock.lap}`,
			lap: shock.lap,
			kind: "SHOCK",
			tone: "warning",
			detail: `${shock.eventType.replace("_", " ").toUpperCase()} injected`,
		},
		forkLap != null && {
			key: `fork-${forkLap}`,
			lap: forkLap,
			kind: "YOUR DECISION",
			tone: "projected",
			detail: `Committed to ${actionLabel(committedAction)} — simulation forked to projected`,
		},
		...reoptimizations.map((record) => ({
			key: `reopt-${record.lap}-${record.computation_id}`,
			lap: record.lap,
			kind: "RE-OPTIMISATION",
			tone: "neutral",
			detail: record.reason || `Triggered by ${(record.triggers ?? []).join(", ")}`,
			computationId: record.computation_id,
			ours: record.p2_decision,
			theirs: record.p1_decision,
		})),
	]
		.filter(Boolean)
		.sort((left, right) => left.lap - right.lap);

	return (
		<Panel label="DECISION HISTORY" tone="lab" className="decision-history">
			{rows.length === 0 ? (
				<Note>Nothing logged yet. Inject a shock to start a run.</Note>
			) : (
				<ol className="history-list">
					{rows.map((row) => (
						<li key={row.key} className={`history-row row-${row.tone}`}>
							<StatusBadge tone={row.tone}>LAP {row.lap}</StatusBadge>
							<div className="history-body">
								<span className="history-kind">{row.kind}</span>
								<span className="history-detail">{row.detail}</span>
								{row.ours && (
									<span className="history-calls">
										PitSense: {actionLabel(row.ours.action)} → lap {row.ours.target_lap}
										{row.theirs
											? ` · Opponent: ${actionLabel(row.theirs.action)} → lap ${row.theirs.target_lap}`
											: ""}
									</span>
								)}
								{row.computationId && (
									<span className="history-id">computation {row.computationId}</span>
								)}
							</div>
						</li>
					))}
				</ol>
			)}
		</Panel>
	);
}
