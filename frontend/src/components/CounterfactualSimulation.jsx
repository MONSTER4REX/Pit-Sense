import StatusBadge from "./StatusBadge";

function carAt(tick, role) {
	return tick?.cars?.find((car) => car.car === role) ?? null;
}

function actionFor(tick, role) {
	return tick?.decisions?.find((decision) => decision.car === role)?.action ?? "Unavailable";
}

function positionText(car) {
	return car?.position ? `P${car.position} PROJECTED` : "Unavailable";
}

function gapText(car) {
	return car?.gap_to_leader_seconds == null ? "Unavailable" : `${car.gap_to_leader_seconds.toFixed(2)}s`;
}

export default function CounterfactualSimulation({ forkLap, currentLap, projectedTicks }) {
	const currentTick = projectedTicks.at(-1);
	const pitsense = carAt(currentTick, "P2");
	const baseline = carAt(currentTick, "P1");

	return (
		<section className="counterfactual-view data-projected">
			<div className="panel-label">COUNTERFACTUAL SIMULATION — PROJECTED FROM LAP {forkLap}</div>
			<p className="data-note">Historical race data remains the reference. Every value below is a projection from the accepted fork.</p>
			<div className="counterfactual-columns">
				<article className="counterfactual-card pitsense-counterfactual">
					<div className="panel-label">YOUR CAR — PITSENSE</div>
					<StatusBadge tone="projected">PROJECTED</StatusBadge>
					<strong>{positionText(pitsense)}</strong>
					<div className="counterfactual-metric"><span>Fork action</span><b>{actionFor(currentTick, "P2")}</b></div>
					<div className="counterfactual-metric"><span>Current projected gap</span><b>{gapText(pitsense)}</b></div>
				</article>
				<article className="counterfactual-card baseline-counterfactual">
					<div className="panel-label">OPPONENT — BASELINE</div>
					<StatusBadge tone="projected">PROJECTED</StatusBadge>
					<strong>{positionText(baseline)}</strong>
					<div className="counterfactual-metric"><span>Fork action</span><b>{actionFor(currentTick, "P1")}</b></div>
					<div className="counterfactual-metric"><span>Current projected gap</span><b>{gapText(baseline)}</b></div>
				</article>
			</div>
			<p className="data-note">Projected ticks available: {projectedTicks.length} · Current replay lap: {currentLap}</p>
		</section>
	);
}
