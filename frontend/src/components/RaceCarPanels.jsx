import StatusBadge from "./StatusBadge";
import { REPLAY_MODES } from "../state/SimulationContext";

function formatPercent(value) {
	return `${Math.round(value * 100)}%`;
}

function RiskMeter({ label, value, displayValue }) {
	return (
		<div className="risk-meter">
			<div className="risk-meter-head"><span>{label}</span><strong>{displayValue}</strong></div>
			<div className="risk-meter-track"><span style={{ width: `${Math.min(100, Math.max(0, value * 100))}%` }} /></div>
		</div>
	);
}

export default function RaceCarPanels({ metadata, replayMode, recommendation, currentLap, currentTyreAge, currentGap, isUpdating }) {
	const projected = replayMode === REPLAY_MODES.COUNTERFACTUAL;
	const factors = recommendation?.explainability;
	const confidence = recommendation?.confidence;
	const baselineAction = recommendation?.action === "pit_now" ? "PIT" : "STAY_OUT";

	return (
		<section className="car-panels-grid">
			<article className={`panel car-panel pitsense-panel ${projected ? "data-projected" : "data-historical"}`}>
				<div className="panel-label">{projected ? "YOUR CAR — PITSENSE" : "YOUR CAR"}</div>
				<h2>{metadata?.p2_driver || metadata?.p2 || "P2 driver loading…"}</h2>
				<p className="car-team">{metadata?.p2_team || "Team data loading…"}</p>
				<StatusBadge tone={projected ? "projected" : "historical"}>
					{projected ? "PITSENSE — PROJECTED" : "P2 — HISTORICAL FINISH"}
				</StatusBadge>
				{projected && recommendation && !isUpdating && (
					<div className="car-decision">
						<div className="car-decision-action">{baselineAction === "PIT" ? "PIT NOW" : "STAY OUT"}</div>
						<div className="car-metric-row"><span>Lap {currentLap} recommendation</span><strong>{recommendation.pit_lap}</strong></div>
						<div className="car-metric-row"><span>Confidence</span><strong>{formatPercent(confidence.lower)}–{formatPercent(confidence.upper)}</strong></div>
						<div className="car-metric-row"><span>Risk</span><StatusBadge tone="neutral">{recommendation.undercut_risk_tier.toUpperCase()}</StatusBadge></div>
						<div className="risk-meters">
							<RiskMeter label="Tyre risk" value={Math.min(1, factors.tyre_delta_risk / 100)} displayValue={`${factors.tyre_delta_risk.toFixed(1)}s`} />
							<RiskMeter label="Traffic risk" value={Math.min(1, factors.traffic_rejoin_risk / 10)} displayValue={`${factors.traffic_rejoin_risk.toFixed(1)}s`} />
							<RiskMeter label="Rival response" value={factors.rival_cover_stop_probability} displayValue={formatPercent(factors.rival_cover_stop_probability)} />
							<RiskMeter label="Pit loss" value={Math.min(1, factors.pit_lane_time_loss / 30)} displayValue={`${factors.pit_lane_time_loss.toFixed(1)}s`} />
						</div>
					</div>
				)}
				{projected && isUpdating && <p className="data-note">Recalculating PitSense state for replay Lap {currentLap}…</p>}
				<p className="data-note">{projected ? `Projected state at replay Lap ${currentLap}.` : "Observed historical result; no projection is shown before the fork."}</p>
			</article>

			<article className={`panel car-panel baseline-panel ${projected ? "data-projected" : "data-historical"}`}>
				<div className="panel-label">{projected ? "OPPONENT — BASELINE" : "OPPONENT"}</div>
				<h2>{metadata?.p1_driver || metadata?.p1 || "P1 driver loading…"}</h2>
				<p className="car-team">{metadata?.p1_team || "Team data loading…"}</p>
				<StatusBadge tone={projected ? "projected" : "historical"}>
					{projected ? "BASELINE — PROJECTED" : "P1 — HISTORICAL FINISH"}
				</StatusBadge>
				{projected && recommendation && !isUpdating && (
					<div className="car-decision baseline-decision">
						<div className="car-decision-action">{baselineAction === "PIT" ? "PIT" : "STAY OUT"}</div>
						<p className="model-label">Baseline Strategy</p>
						<div className="car-metric-row"><span>Tyre state</span><strong>{currentTyreAge} laps / {recommendation.action === "pit_now" ? "pit window" : "current stint"}</strong></div>
						<div className="car-metric-row"><span>Pit loss estimate</span><strong>{factors.pit_lane_time_loss.toFixed(1)}s</strong></div>
						<div className="car-metric-row"><span>Current gap to car ahead</span><strong>{currentGap == null ? "Unavailable" : `${currentGap.toFixed(2)}s`}</strong></div>
					</div>
				)}
				{projected && isUpdating && <p className="data-note">Recalculating baseline comparison for replay Lap {currentLap}…</p>}
				<p className="data-note">{projected ? "A conventional comparator model, not the historical team's internal strategy." : "Observed historical result; baseline projection begins only after the fork."}</p>
			</article>
		</section>
	);
}
