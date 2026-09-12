import StatusBadge from "./StatusBadge";

function gapFor(tick, car) {
	const state = tick?.cars?.find((item) => item.car === car);
	return state?.gap_to_leader_seconds == null ? null : state.gap_to_leader_seconds;
}

function gapText(value) {
	return value == null ? "Unavailable" : `${value.toFixed(2)}s`;
}

export default function PostDecisionImpact({ forkLap, acceptedAction, historicalLap, historicalTick, projectedTick }) {
	if (!projectedTick) return null;
	const before = gapFor(historicalTick, "P2");
	const after = gapFor(projectedTick, "P2");
	const gain = before == null || after == null ? null : before - after;

	return (
		<section className="post-impact panel data-projected">
			<div className="panel-label">POST-DECISION IMPACT</div>
			<div className="impact-badges"><StatusBadge tone="projected">PROJECTED BRANCH</StatusBadge><StatusBadge tone="historical">HISTORICAL REFERENCE</StatusBadge></div>
			<div className="impact-grid">
				<div><span>PITSENSE CALL</span><strong>{acceptedAction ?? "Unavailable"} LAP {forkLap}</strong></div>
				<div><span>ACTUAL HISTORICAL CALL</span><strong>{historicalLap == null ? "Unavailable" : `LAP ${historicalLap}`}</strong></div>
				<div><span>HISTORICAL GAP BEFORE</span><strong>{gapText(before)}</strong></div>
				<div><span>PROJECTED GAP AFTER</span><strong>{gapText(after)}</strong></div>
				<div><span>PROJECTED GAIN</span><strong>{gain == null ? "Unavailable" : `${gain >= 0 ? "+" : ""}${gain.toFixed(2)}s`}</strong></div>
			</div>
			<p className="data-note">Gap before is historical; gap after and gain are counterfactual projections.</p>
		</section>
	);
}
