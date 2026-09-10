import { useState } from "react";

const initialRecommendation = {
	action: "pit_now",
	pit_lap: 18,
	projected_total_time_seconds: 5421.8,
	explainability: {
		tyre_delta_risk: 4.2,
		traffic_rejoin_risk: 7.1,
		rival_cover_stop_probability: 0.63,
		pit_lane_time_loss: 21.8,
	},
	confidence: { lower: 0.67, upper: 0.83, uncertainty: "medium" },
};

function FactorList({ explainability }) {
	const factors = [
		["Tyre delta risk", explainability.tyre_delta_risk, "s"],
		["Traffic / rejoin risk", explainability.traffic_rejoin_risk, "s"],
		["Rival cover-stop probability", explainability.rival_cover_stop_probability * 100, "%"],
		["Pit-lane time loss", explainability.pit_lane_time_loss, "s"],
	];
	return (
		<div className="factor-list">
			{factors.map(([label, value, unit]) => (
				<div className="factor" key={label}>
					<div className="factor-head"><span>{label}</span><strong>{value.toFixed(1)}{unit}</strong></div>
					<div className="bar"><span style={{ width: `${Math.min(100, value * (unit === "%" ? 1 : 4))}%` }} /></div>
				</div>
			))}
		</div>
	);
}

export default function App() {
	const [recommendation, setRecommendation] = useState(initialRecommendation);
	const [stale, setStale] = useState(false);

	const triggerShockEvent = () => {
		setStale(true);
		window.setTimeout(() => {
			setRecommendation((current) => ({
				...current,
				confidence: { lower: 0.48, upper: 0.79, uncertainty: "high" },
			}));
			setStale(false);
		}, 250);
	};

	return (
		<main className="console-shell">
			<header className="topbar">
				<div><p className="eyebrow">PITSENSE / STRATEGY CONSOLE</p><h1>Race strategy, with its work shown.</h1></div>
				<div className="mode-badge">HISTORICAL REPLAY ONLY</div>
			</header>
			<section className="status-strip">
				<span><i className="live-dot" /> 2024 Belgian Grand Prix / Lap 17 of 44</span>
				<span>Medium / 12 laps</span>
				<span>{stale ? "RE-OPTIMIZATION STALE" : "ENGINE SYNCHRONIZED"}</span>
			</section>
			<section className="workspace-grid">
				<article className="panel recommendation-panel">
					<div className="panel-label">PRIMARY RECOMMENDATION</div>
					<div className="recommendation-action"><span>BOX THIS LAP</span><strong>LAP {recommendation.pit_lap}</strong></div>
					<p className="recommendation-copy">The shortest projected race-time path currently favors a pit stop before the rival cover window closes.</p>
					<div className="confidence"><span>Confidence band</span><strong>{Math.round(recommendation.confidence.lower * 100)}–{Math.round(recommendation.confidence.upper * 100)}%</strong><em>{recommendation.confidence.uncertainty} uncertainty</em></div>
					<button className="shock-button" onClick={triggerShockEvent}>Inject Shock Event</button>
				</article>
				<article className="panel explainability-panel">
					<div className="panel-label">WHY THIS PATH</div>
					<h2>Explainability breakdown</h2>
					<FactorList explainability={recommendation.explainability} />
					<p className="data-note">Factors are calculated from the loaded historical session. Missing source fields are flagged, never interpolated.</p>
				</article>
				<article className="panel map-panel">
					<div className="panel-label">TRACK POSITION</div>
					<div className="track-map"><span className="track-line" /><span className="car-marker" /><span className="traffic-marker" /></div>
					<div className="map-legend"><span><i className="marker car" /> YOUR CAR</span><span><i className="marker traffic" /> TRAFFIC RISK</span></div>
				</article>
			</section>
			<footer className="footer-line"><span>Replay data: FastF1 cache</span><span>Data quality: 2 flagged gaps</span><span>Shock response target: &lt; 1.0s</span></footer>
		</main>
	);
}
