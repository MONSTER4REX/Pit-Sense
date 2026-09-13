import { Button, StatusBadge } from "../shared/primitives";
import { shortRaceLabel } from "../shared/format";
import { useRaceAnalysis } from "./RaceAnalysisProvider";

/*
 * Race Analysis header, including this product's own race selector.
 *
 * The Simulation Lab has a different selector with different rules, so the two
 * are deliberately not the same component (PRD 2.1). This one lists every race
 * with historical data and enables all of them: Race Analysis does not need
 * circuit geometry, so geometry never gates anything here.
 */
export default function RaceAnalysisHeader({ onOpenSimulationLab }) {
	const { races, selectedRace, selectRace, currentLap, totalLaps } = useRaceAnalysis();

	return (
		<header className="product-header analysis-header">
			<div className="product-identity">
				<p className="eyebrow">PITSENSE / RACE ANALYSIS</p>
				<h1>What should the strategist do?</h1>
			</div>

			<div className="header-controls">
				<label className="race-selector">
					<span className="sr-only">Select race</span>
					<select
						value={selectedRace ? `${selectedRace.year}:${selectedRace.event}` : ""}
						disabled={!races.length}
						onChange={(event) => {
							const next = races.find(
								(race) => `${race.year}:${race.event}` === event.target.value,
							);
							if (next) selectRace(next);
						}}
					>
						{!races.length && <option value="">Loading races…</option>}
						{races.map((race) => (
							<option key={`${race.year}:${race.event}`} value={`${race.year}:${race.event}`}>
								{shortRaceLabel(race)}
							</option>
						))}
					</select>
				</label>

				<div className="lap-indicator">
					LAP {currentLap} / {totalLaps || "—"}
				</div>

				<StatusBadge tone="historical">HISTORICAL ANALYSIS</StatusBadge>

				<Button variant="ghost" onClick={onOpenSimulationLab}>
					OPEN SIMULATION LAB →
				</Button>
			</div>
		</header>
	);
}
