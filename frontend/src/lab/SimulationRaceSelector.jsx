import { Note, Panel, StatusBadge } from "../shared/primitives";
import { shortRaceLabel } from "../shared/format";
import { useSimulationLab } from "./SimulationLabProvider";

/*
 * Two-tier race selector (PRD 9.4, FR-21/FR-22).
 *
 * Every race with historical data is listed and every one stays selectable. A
 * race without verified geometry is labelled as such and, when chosen, shows the
 * geometry-unavailable state rather than being hidden, disabled without
 * explanation, or quietly swapped for a different race.
 */
export default function SimulationRaceSelector() {
	const { races, selectedRace, selectRace } = useSimulationLab();

	return (
		<Panel label="RACE" title="Select a race to simulate" tone="lab" className="lab-selector">
			<ul className="race-list">
				{races.map((race) => {
					const verified = race.simulation_geometry_available;
					const isSelected =
						selectedRace?.year === race.year && selectedRace?.event === race.event;
					return (
						<li key={`${race.year}:${race.event}`}>
							<button
								type="button"
								className={`race-option ${isSelected ? "race-selected" : ""}`.trim()}
								onClick={() => selectRace(race)}
							>
								<span className="race-name">{shortRaceLabel(race)}</span>
								<StatusBadge tone={verified ? "verified" : "unavailable"}>
									{verified ? "GEOMETRY VERIFIED" : "ANALYSIS ONLY"}
								</StatusBadge>
								{!verified && (
									<span className="race-caveat">
										Race Analysis is available; Simulation Lab geometry is not.
									</span>
								)}
							</button>
						</li>
					);
				})}
			</ul>
			{!races.length && <Note>Loading available races…</Note>}
		</Panel>
	);
}
