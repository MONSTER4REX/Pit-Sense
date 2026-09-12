import StatusBadge from "./StatusBadge";
import { REPLAY_MODES } from "../state/SimulationContext";

function lapState(states, lap) {
	return states?.find((state) => state.lap_number === lap) || null;
}

function pitState(stops, lap) {
	return stops?.some((stop) => stop.lap_number === lap) ? "IN PIT LANE" : "ON TRACK";
}

function markerPosition(car, state, opponentState) {
	const gap = Math.max(0, (state?.gap_to_leader_seconds || 0) - (opponentState?.gap_to_leader_seconds || 0));
	const base = car === "P1" ? 52 : 52 - Math.min(18, gap * 2);
	return `${Math.max(18, Math.min(82, base))}%`;
}

export default function TrackVisualization({ metadata, currentLap, replayMode }) {
	const projected = replayMode === REPLAY_MODES.COUNTERFACTUAL;
	const p1 = projected ? null : lapState(metadata?.p1_lap_states, currentLap);
	const p2 = projected ? null : lapState(metadata?.p2_lap_states, currentLap);
	const previousP1 = projected ? null : lapState(metadata?.p1_lap_states, currentLap - 1);
	const previousP2 = projected ? null : lapState(metadata?.p2_lap_states, currentLap - 1);
	const gap = Math.abs((p2?.gap_to_leader_seconds || 0) - (p1?.gap_to_leader_seconds || 0));
	const previousGap = Math.abs((previousP2?.gap_to_leader_seconds || 0) - (previousP1?.gap_to_leader_seconds || 0));
	const delta = gap - previousGap;
	const hasGap = p1?.gap_to_leader_seconds != null && p2?.gap_to_leader_seconds != null;
	const trend = delta < 0 ? "↓ closing" : delta > 0 ? "↑ opening" : "→ stable";
	const p1Pit = pitState(metadata?.p1_pit_stops, currentLap);
	const p2Pit = pitState(metadata?.p2_pit_stops, currentLap);
	const dataClass = projected ? "data-projected" : "data-historical";

	return (
		<article className={`panel track-panel ${dataClass}`}>
			<div className="panel-label">TRACK POSITION</div>
			<div className="track-heading">
				<div>
					<h2>Race position map</h2>
					<p className="track-note">Stylized track · markers use recorded lap position and gap data</p>
				</div>
				<StatusBadge tone={replayMode === REPLAY_MODES.COUNTERFACTUAL ? "projected" : "historical"}>
					{replayMode === REPLAY_MODES.COUNTERFACTUAL ? "PROJECTED POSITION" : "HISTORICAL POSITION"}
				</StatusBadge>
			</div>
			<div className="track-layout">
				<div className="stylized-track" aria-label="Stylized track with pit lane">
					<div className="racing-line" />
					<div className="pit-lane-line"><span>PIT LANE</span></div>
					{!projected && <div className="track-marker p1-marker" style={{ left: markerPosition("P1", p1, p2) }}>
						<span>P1</span>
					</div>}
					{!projected && <div className="track-marker p2-marker" style={{ left: markerPosition("P2", p2, p1) }}>
						<span>P2</span>
					</div>}
					{projected && <div className="track-unavailable">Projected track positions will appear when the counterfactual replay starts.</div>}
				</div>
				<div className="gap-readout">
					<div className="panel-label">GAP BETWEEN P1 / P2</div>
					<strong>{hasGap ? `${gap.toFixed(2)}s` : "Unavailable"}</strong>
					<span>{hasGap ? `${trend} | ${Math.abs(delta).toFixed(2)}s/lap` : "Recorded gap data unavailable"}</span>
					<div className="pit-status-list">
						<div><span>P1 status</span><StatusBadge tone={p1Pit === "IN PIT LANE" ? "projected" : "historical"}>{p1Pit}</StatusBadge></div>
						<div><span>P2 status</span><StatusBadge tone={p2Pit === "IN PIT LANE" ? "projected" : "historical"}>{p2Pit}</StatusBadge></div>
					</div>
				</div>
			</div>
			<p className="data-note">{projected ? "Projected position and pit stages are not shown until the simulation backend supplies projected ticks." : "Pit events are lap-level historical data; sub-lap entry, stop, and exit timing is not available."}</p>
		</article>
	);
}
