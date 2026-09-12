import StatusBadge from "./StatusBadge";

const EVENTS = [
	["safety_car", "SAFETY CAR"],
	["vsc", "VSC"],
	["rain", "RAIN"],
];

export default function ShockEventConsole({ currentLap, isRecomputing, activeEvent, onShock }) {
	return (
		<article className={`panel shock-console ${activeEvent ? "shock-console-active data-projected" : "data-historical"}`}>
			<div className="shock-console-heading">
				<div>
					<div className="panel-label">SHOCK EVENT CONSOLE</div>
					<h2>Change the race conditions</h2>
				</div>
				<StatusBadge tone={activeEvent ? "projected" : "neutral"}>{activeEvent ? "FORK OPPORTUNITY" : `CURRENT LAP ${currentLap}`}</StatusBadge>
			</div>
			<p className="shock-console-copy">Capture the historical state at Lap {currentLap}, then compare both strategy policies against the same event.</p>
			<div className="shock-buttons">
				{EVENTS.map(([value, label]) => (
					<button key={value} type="button" className="shock-event-button" disabled={isRecomputing} onClick={() => onShock(value)}>
						{label}
					</button>
				))}
			</div>
			{activeEvent && <p className="shock-console-status">Shock event recorded. PitSense and Baseline have recalculated from the captured historical reference.</p>}
		</article>
	);
}
