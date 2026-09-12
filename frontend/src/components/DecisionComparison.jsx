import StatusBadge from "./StatusBadge";

function confidenceText(confidence) {
	if (!confidence) return "Unavailable";
	const low = Math.min(confidence.lower, confidence.upper);
	const high = Math.max(confidence.lower, confidence.upper);
	return `${Math.round(low * 100)}–${Math.round(high * 100)}%`;
}

function decisionLabel(action) {
	return action === "pit_now" ? "PIT NOW" : action === "extend_stint" ? "EXTEND" : action || "STAY OUT";
}

export default function DecisionComparison({ eventType, lap, recommendation, baselineDecision, onAccept }) {
	if (!eventType) return null;
	const eventLabel = eventType.replace(/_/g, " ").toUpperCase();
	return (
		<article className="panel decision-comparison data-projected">
			<div className="panel-label">CONTROLLED EXPERIMENT</div>
			<h2>SHOCK EVENT: {eventLabel} — LAP {lap}</h2>
			<p className="data-note">Both policies received the same event at the same historical reference lap. Only PitSense can be accepted as the user-controlled fork.</p>
			<div className="comparison-columns">
				<section className="comparison-column comparison-pitsense">
					<div className="panel-label">YOUR CAR — PITSENSE</div>
					<strong>{decisionLabel(recommendation?.action)}</strong>
					<div className="comparison-metric"><span>Confidence</span><b>{confidenceText(recommendation?.confidence)}</b></div>
					<div className="comparison-metric"><span>Target lap</span><b>{recommendation?.pit_lap ?? "Unavailable"}</b></div>
					<div className="decision-options">
						<button className="decision-action decision-action-primary" type="button" onClick={() => onAccept("PIT")}>ACCEPT PIT</button>
						<button className="decision-action" type="button" onClick={() => onAccept("STAY_OUT")}>REJECT — STAY OUT</button>
						<button className="decision-action" type="button" onClick={() => onAccept("EXTEND")}>EXTEND</button>
					</div>
				</section>
				<section className="comparison-column comparison-baseline">
					<div className="panel-label">OPPONENT — BASELINE</div>
					<strong>{baselineDecision?.action || "Unavailable"}</strong>
					<div className="model-label">Baseline decision</div>
					<div className="comparison-metric"><span>Target lap</span><b>{baselineDecision?.target_lap ?? "Unavailable"}</b></div>
					<div className="comparison-metric"><span>Model</span><b>Baseline Strategy</b></div>
				</section>
			</div>
		</article>
	);
}
