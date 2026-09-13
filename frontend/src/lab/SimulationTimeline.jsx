import { Note, Panel, StatusBadge } from "../shared/primitives";
import PlaybackControls from "../shared/PlaybackControls";
import { usePlayback } from "../shared/usePlayback";
import { PHASES, useSimulationLab } from "./SimulationLabProvider";

/*
 * The dual-layer timeline (PRD 9.8).
 *
 * The historical portion, the shock, the fork, the projected portion, every
 * re-optimisation, each pit event, and the finish are all visually separated.
 * Projected laps are never drawn in the same treatment as historical ones.
 */
export default function SimulationTimeline() {
	const { totalLaps, currentLap, setCurrentLap, forkLap, shock, phase, projectedTicks, session } =
		useSimulationLab();

	// The Lab drives its own playback, separate from Race Analysis's.
	const playback = usePlayback({ currentLap, totalLaps, setLap: setCurrentLap });

	if (!totalLaps) return null;
	const projected = phase === PHASES.PROJECTED;

	const reoptimizationLaps = new Set(
		projectedTicks.filter((tick) => tick.triggers?.length > 0).map((tick) => tick.lap),
	);
	const historicalPits = new Set((session?.p2_pit_stops ?? []).map((stop) => stop.lap_number));
	const projectedPits = new Set(
		projectedTicks
			.filter((tick) => tick.cars?.some((car) => car.car === "P2" && car.pit_status === "PIT_IN"))
			.map((tick) => tick.lap),
	);

	const laps = Array.from({ length: totalLaps }, (_, index) => index + 1);

	return (
		<Panel
			label="TIMELINE"
			tone={projected ? "projected" : "historical"}
			className="lab-timeline"
		>
			<div className="timeline-track">
				{laps.map((lap) => {
					const isProjected = forkLap != null && lap >= forkLap;
					const classes = ["timeline-lap"];
					if (isProjected) classes.push("lap-projected");
					else classes.push("lap-historical");
					if (lap === shock?.lap) classes.push("lap-shock");
					if (lap === forkLap) classes.push("lap-fork");
					if (reoptimizationLaps.has(lap)) classes.push("lap-reopt");
					if (isProjected ? projectedPits.has(lap) : historicalPits.has(lap)) classes.push("lap-pit");
					if (lap === currentLap) classes.push("lap-current");
					if (lap === totalLaps) classes.push("lap-finish");

					const title = [
						`Lap ${lap}`,
						isProjected ? "projected" : "historical",
						lap === shock?.lap ? `shock: ${shock.eventType}` : null,
						lap === forkLap ? "fork point" : null,
						reoptimizationLaps.has(lap) ? "re-optimisation" : null,
						(isProjected ? projectedPits : historicalPits).has(lap) ? "pit stop" : null,
					]
						.filter(Boolean)
						.join(" · ");

					return (
						<button
							key={lap}
							type="button"
							className={classes.join(" ")}
							title={title}
							aria-label={title}
							onClick={() => setCurrentLap(lap)}
						/>
					);
				})}
			</div>

			<div className="timeline-legend">
				<span className="legend-historical">Historical</span>
				{forkLap != null && <span className="legend-projected">Projected</span>}
				{shock && <span className="legend-shock">Shock</span>}
				{forkLap != null && <span className="legend-fork">Fork</span>}
				<span className="legend-reopt">Re-optimisation</span>
				<span className="legend-pit">Pit stop</span>
				<span className="legend-finish">Finish</span>
			</div>

			<div className="timeline-controls">
				<PlaybackControls
					{...playback}
					currentLap={currentLap}
					totalLaps={totalLaps}
					setLap={setCurrentLap}
					tone={projected ? "projected" : "historical"}
				/>
				<StatusBadge tone={projected ? "projected" : "historical"}>
					{projected ? "PROJECTED" : "HISTORICAL"}
				</StatusBadge>
			</div>

			{forkLap != null && (
				<Note>
					Laps 1–{forkLap - 1} are the real race. Lap {forkLap} onward is a projection and never a
					record of what happened.
				</Note>
			)}
		</Panel>
	);
}
