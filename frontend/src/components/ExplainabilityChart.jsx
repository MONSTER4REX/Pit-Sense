export default function ExplainabilityChart({ explainability }) {
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
