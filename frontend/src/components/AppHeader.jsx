import StatusBadge from "./StatusBadge";
import { REPLAY_MODES, useSimulation } from "../state/SimulationContext";

const SPEEDS = [1, 2, 5];

export default function AppHeader({ races, onRaceChange, onReset, isPlaying, onPlayToggle }) {
	const { replayMode, forkLap, currentLap, totalLaps, selectedRace, speed, setSpeed } = useSimulation();
	const isCounterfactual = replayMode === REPLAY_MODES.COUNTERFACTUAL;

	return (
		<header className="app-header">
			<div className="app-header-brand">
				<p className="eyebrow">F1 RACE-STRATEGY SIMULATOR</p>
				<strong>PITSENSE</strong>
			</div>
			<div className="app-header-controls">
				<label className="race-selector">
					<span className="sr-only">Select race</span>
					<select
						value={selectedRace ? `${selectedRace.year}:${selectedRace.event}` : ""}
						onChange={(event) => {
							const race = races.find((candidate) => `${candidate.year}:${candidate.event}` === event.target.value);
							if (race) onRaceChange(race);
						}}
						disabled={!races.length}
					>
						<option value="" disabled>Loading races…</option>
						{races.map((race) => (
							<option key={`${race.year}:${race.event}`} value={`${race.year}:${race.event}`}>
								{race.year} {race.event.replace(" Grand Prix", " GP")}
							</option>
						))}
					</select>
				</label>
				<div className="lap-indicator">LAP {currentLap} / {totalLaps || "—"}</div>
				<StatusBadge tone={isCounterfactual ? "projected" : "historical"}>
					● {isCounterfactual ? "COUNTERFACTUAL — PROJECTED" : "HISTORICAL REPLAY"}
				</StatusBadge>
				<button
					className="play-button"
					onClick={onPlayToggle}
					disabled={!totalLaps}
					type="button"
					aria-label={isPlaying ? "Pause race replay" : "Play race replay"}
				>
					{isPlaying ? "PAUSE" : "PLAY"}
				</button>
				<div className="speed-controls" aria-label="Playback speed">
					{SPEEDS.map((candidate) => (
						<button
							key={candidate}
							className={speed === candidate ? "speed-button speed-active" : "speed-button"}
							onClick={() => setSpeed(candidate)}
							type="button"
						>
							{candidate}x
						</button>
					))}
				</div>
				<button className="reset-button" onClick={onReset} type="button">RESET</button>
			</div>
			<div className="app-header-subline">
				{isCounterfactual
					? `Historical race data until Lap ${forkLap} | Projected from Lap ${forkLap}`
					: "Starting from Lap 1 — historical replay"}
			</div>
		</header>
	);
}
