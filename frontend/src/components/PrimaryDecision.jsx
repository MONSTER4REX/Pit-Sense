import StatusBadge from "./StatusBadge";

function actionLabel(action) {
	return action === "pit_now" ? "PIT NOW" : action === "extend_stint" ? "EXTEND" : "STAY OUT";
}

function formatConfidence(confidence) {
	const low = Math.min(confidence.lower, confidence.upper);
	const high = Math.max(confidence.lower, confidence.upper);
	return `${Math.round(low * 100)}–${Math.round(high * 100)}%`;
}

export default function PrimaryDecision({ recommendation, currentLap, replayMode, isUpdating, onAction }) {
	if (!recommendation) return null;
	const { explainability: factors, confidence } = recommendation;
	const recommendationLabel = actionLabel(recommendation.action);
	const sentence = `Stay-out loss: ${(factors.tyre_delta_risk / 10).toFixed(1)}s vs Pit loss: ${factors.pit_lane_time_loss.toFixed(1)}s. Undercut gain: ${(factors.tyre_delta_risk / 10 - factors.traffic_rejoin_risk).toFixed(1)}s.`;

	return (
		<article className={`panel primary-decision ${replayMode === "counterfactual" ? "data-projected" : "data-historical"}`}>
			<div className="panel-label">PRIMARY DECISION</div>
			{isUpdating && <p className="data-note">Recalculating recommendation from replay Lap {currentLap}…</p>}
			{!isUpdating && <>
			<div className="decision-heading">
				<div>
					<p className="decision-kicker">CURRENT RECOMMENDATION / LAP {currentLap}</p>
					<h2>{recommendationLabel}</h2>
				</div>
				<StatusBadge tone="neutral">{recommendation.undercut_risk_tier.toUpperCase()}</StatusBadge>
			</div>
			<div className="decision-target">Target: Lap {recommendation.pit_lap}</div>
			<div className="decision-confidence">Confidence: {formatConfidence(confidence)}</div>
			<p className="decision-why"><strong>Why:</strong> {sentence}</p>
			<div className="decision-options">
				<button className="decision-action decision-action-primary" onClick={() => onAction("PIT")} type="button">ACCEPT PIT</button>
				<button className="decision-action" onClick={() => onAction("STAY_OUT")} type="button">STAY OUT</button>
				<button className="decision-action" onClick={() => onAction("EXTEND")} type="button">EXTEND</button>
			</div>
			<a className="comparison-link" href="#comparison">↓ Comparison</a>
			</>}
		</article>
	);
}
