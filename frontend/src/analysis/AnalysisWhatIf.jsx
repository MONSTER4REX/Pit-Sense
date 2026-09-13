import { useEffect, useState } from "react";

import { Meter, Note, Panel, StatusBadge } from "../shared/primitives";
import { confidenceBand, percent, seconds, signedSeconds } from "../shared/format";
import { fetchWhatIf } from "../api";
import { useRaceAnalysis } from "./RaceAnalysisProvider";

/*
 * Race Analysis's complete What-If (PRD 8.1, FR-14, FR-15).
 *
 * This is the analysis product's own component and must not be replaced by the
 * Simulation Lab's version, which answers a different question against projected
 * state (PRD 8.4, 9.9, section 10). All three branches are real backend
 * optimisations, each with its own time, confidence, and factor breakdown.
 */
const BRANCH_ORDER = ["pit_now", "stay_out", "extend_stint"];
const BRANCH_LABEL = {
	pit_now: "PIT NOW",
	stay_out: "STAY OUT",
	extend_stint: "EXTEND STINT",
};
const TYRE_METER_CEILING_SECONDS = 60;
const TRAFFIC_METER_CEILING_SECONDS = 10;

export default function AnalysisWhatIf() {
	const { currentLap, totalLaps, session } = useRaceAnalysis();
	const [branches, setBranches] = useState(null);
	const [error, setError] = useState(null);
	const [loading, setLoading] = useState(false);

	useEffect(() => {
		if (!session || !totalLaps) return undefined;
		const controller = new AbortController();
		setLoading(true);
		setError(null);
		fetchWhatIf(Math.min(currentLap, totalLaps), controller.signal)
			.then((data) => {
				setBranches(data.branches);
				setLoading(false);
			})
			.catch((cause) => {
				if (cause.name === "AbortError") return;
				setError(cause.message);
				setLoading(false);
			});
		return () => controller.abort();
	}, [session, currentLap, totalLaps]);

	const entries = branches
		? BRANCH_ORDER.filter((key) => branches[key]).map((key) => [key, branches[key]])
		: [];
	const best = entries.length
		? Math.min(...entries.map(([, branch]) => branch.projected_total_time_seconds))
		: 0;

	return (
		<Panel label="WHAT-IF" title="Pit now / stay out / extend" tone="historical">
			{loading && !entries.length && <Note>Running all three branches…</Note>}
			{error && <Note tone="error">What-if comparison failed: {error}</Note>}

			<div className="branch-grid">
				{entries.map(([key, branch]) => {
					const delta = branch.projected_total_time_seconds - best;
					const isBest = delta === 0;
					const measured = branch.explainability?.measured ?? {};
					return (
						<div key={key} className={`branch ${isBest ? "branch-best" : ""}`.trim()}>
							<div className="branch-head">
								<span className="branch-name">{BRANCH_LABEL[key]}</span>
								{isBest ? (
									<StatusBadge tone="best">FASTEST PATH</StatusBadge>
								) : (
									<StatusBadge tone="neutral">{signedSeconds(delta, 1)}</StatusBadge>
								)}
							</div>

							<div className="branch-metrics">
								<div>
									<span>Projected race time</span>
									<strong>{seconds(branch.projected_total_time_seconds, 1)}</strong>
								</div>
								<div>
									<span>Confidence</span>
									<strong>{confidenceBand(branch.confidence)}</strong>
								</div>
								<div>
									<span>Undercut risk</span>
									<strong>{(branch.undercut_risk_tier ?? "").toUpperCase()}</strong>
								</div>
							</div>

							{/* FR-15: every branch carries its own breakdown, not just the winner. */}
							<div className="factor-list compact">
								<Meter
									label="Tyre delta"
									value={branch.explainability.tyre_delta_risk / TYRE_METER_CEILING_SECONDS}
									displayValue={seconds(branch.explainability.tyre_delta_risk, 1)}
									tone="tyre"
									unavailable={measured.tyre_degradation === false}
								/>
								<Meter
									label="Rejoin traffic"
									value={branch.explainability.traffic_rejoin_risk / TRAFFIC_METER_CEILING_SECONDS}
									displayValue={seconds(branch.explainability.traffic_rejoin_risk, 1)}
									tone="traffic"
									unavailable={measured.rejoin_traffic === false}
								/>
								<Meter
									label="Rival cover stop"
									value={branch.explainability.rival_cover_stop_probability}
									displayValue={percent(branch.explainability.rival_cover_stop_probability)}
									tone="rival"
									unavailable={measured.rival_cover_stop === false}
								/>
							</div>
						</div>
					);
				})}
			</div>

			<Note>
				Each branch is a separate optimisation run from this lap's real state. Finishing position
				is not shown here because the engine models one car against one rival, not the full grid.
			</Note>
		</Panel>
	);
}
