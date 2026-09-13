import { Button } from "./primitives";
import { SPEEDS } from "./usePlayback";

/*
 * Transport controls. Presentational only - it renders whatever the calling
 * product's own usePlayback instance hands it and owns no state of its own,
 * which is what keeps it a shared primitive rather than shared behaviour.
 */
export default function PlaybackControls({
	isPlaying,
	speed,
	setSpeed,
	toggle,
	step,
	currentLap,
	totalLaps,
	setLap,
	startLap = 1,
	disabled = false,
	tone = "historical",
}) {
	return (
		<div className={`playback playback-${tone}`}>
			<Button
				variant={isPlaying ? "active" : "commit"}
				onClick={toggle}
				disabled={disabled || !totalLaps}
				aria-label={isPlaying ? "Pause replay" : "Play replay"}
			>
				{isPlaying ? "❚❚  PAUSE" : "▶  PLAY"}
			</Button>

			<Button variant="ghost" onClick={() => step(-1)} disabled={disabled || currentLap <= startLap}>
				◀ LAP
			</Button>
			<Button variant="ghost" onClick={() => step(1)} disabled={disabled || currentLap >= totalLaps}>
				LAP ▶
			</Button>

			<div className="speed-group" role="group" aria-label="Playback speed">
				{SPEEDS.map((option) => (
					<button
						key={option}
						type="button"
						className={`speed-button ${speed === option ? "speed-active" : ""}`.trim()}
						onClick={() => setSpeed(option)}
						disabled={disabled}
					>
						{option}x
					</button>
				))}
			</div>

			<input
				className="playback-scrubber"
				type="range"
				min={startLap}
				max={Math.max(startLap, totalLaps || startLap)}
				value={currentLap}
				disabled={disabled || !totalLaps}
				aria-label="Lap"
				onChange={(event) => setLap(Number(event.target.value))}
			/>

			<output className="playback-lap">
				LAP {currentLap} / {totalLaps || "—"}
			</output>
		</div>
	);
}
