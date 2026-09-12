export default function TyreDegradationView({ currentLap, currentTyreAge, recommendation }) {
	const tyreRisk = recommendation?.explainability?.tyre_delta_risk;
	const riskWidth = tyreRisk == null ? 0 : Math.min(100, Math.max(0, tyreRisk * 4));

	return (
		<article className="panel tyre-degradation-panel data-historical">
			<div className="panel-label">TYRE DEGRADATION</div>
			<h2>Live stint condition</h2>
			<div className="tyre-degradation-metric"><span>Replay lap</span><strong>LAP {currentLap}</strong></div>
			<div className="tyre-degradation-metric"><span>Observed tyre age</span><strong>{currentTyreAge ? `${currentTyreAge} laps` : "Not yet observed"}</strong></div>
			<div className="tyre-degradation-metric"><span>Tyre delta risk</span><strong>{tyreRisk == null ? "Unavailable" : `${tyreRisk.toFixed(1)}s`}</strong></div>
			<div className="tyre-risk-track" aria-label="Observed tyre delta risk">
				<span style={{ width: `${riskWidth}%` }} />
			</div>
			<p className="data-note">Historical replay state; no sub-lap degradation precision is inferred.</p>
		</article>
	);
}
