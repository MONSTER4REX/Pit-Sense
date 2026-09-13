import { Button, StatusBadge } from "../shared/primitives";
import { PHASES, useSimulationLab } from "./SimulationLabProvider";

/*
 * The phase must be unmistakable at a glance (PRD 9.3).
 *
 * Text alone is not enough - a viewer can miss a label - so the projected phase
 * also changes the header's colour treatment and puts a persistent watermark
 * behind the whole page (see .lab-shell.phase-projected in styles.css).
 */
export default function SimulationHeader({ onOpenRaceAnalysis }) {
	const { selectedRace, currentLap, totalLaps, phase, forkLap, resetRun } = useSimulationLab();
	const projected = phase === PHASES.PROJECTED;

	return (
		<header className={`product-header lab-header ${projected ? "header-projected" : "header-historical"}`}>
			<div className="product-identity">
				<p className="eyebrow">PITSENSE / SIMULATION LAB</p>
				<h1>What happens if we do it?</h1>
			</div>

			<div className="phase-banner">
				<span className="phase-race">
					{selectedRace ? `${selectedRace.year} ${selectedRace.event}` : "No race selected"}
				</span>
				<span className="phase-lap">
					Lap {currentLap}/{totalLaps || "—"}
				</span>
				<StatusBadge tone={projected ? "projected" : "historical"}>
					{projected ? "PROJECTED COUNTERFACTUAL" : "HISTORICAL"}
				</StatusBadge>
			</div>

			<div className="header-controls">
				{projected && (
					<span className="fork-note">
						Historical through lap {forkLap} · projected from lap {forkLap} onward
					</span>
				)}
				<Button variant="ghost" onClick={resetRun}>
					RESET RUN
				</Button>
				<Button variant="ghost" onClick={onOpenRaceAnalysis}>
					← RACE ANALYSIS
				</Button>
			</div>
		</header>
	);
}
