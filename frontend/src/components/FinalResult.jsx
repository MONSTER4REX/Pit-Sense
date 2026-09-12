export default function FinalResult({ summary, visible }) {
	if (!visible || !summary) return null;
	const historical = summary.historical_finish?.P2;
	const projected = summary.pitsense_projected_finish;
	const advantage = summary.projected_advantage_seconds;

	return (
		<section className="final-result panel data-projected">
			<div className="panel-label">COUNTERFACTUAL FINALE</div>
			<div className="final-result-grid">
				<div className="historical-result"><span>HISTORICAL FINISH</span><strong>{historical ? `P${historical}` : "Unavailable"}</strong></div>
				<div><span>PITSENSE PROJECTED FINISH</span><strong>{projected ? `P${projected}` : "Unavailable"}</strong></div>
				<div><span>PROJECTED ADVANTAGE</span><strong>{advantage == null ? "Unavailable" : `${advantage >= 0 ? "+" : ""}${advantage.toFixed(2)}s`}</strong></div>
			</div>
			<p className="final-warning">⚠ COUNTERFACTUAL PROJECTION — NOT HISTORICAL RESULT</p>
			<details className="assumptions"><summary>Assumptions &amp; Limitations</summary><ul>{summary.assumptions.map((item) => <li key={item}>{item}</li>)}</ul></details>
		</section>
	);
}
