import { useTickStream } from "../hooks/useTickStream";

const SPEEDS = [1, 2, 5];

export default function ReplayControls({ lapTimes, startLap }) {
	const { isPlaying, speed, currentTick, error, complete, play, pause, scrubToLap, changeSpeed } = useTickStream({
		lapTimes,
		startLap,
	});
	const endLap = startLap + lapTimes.length - 1;
	const scrubValue = currentTick?.lapNumber ?? startLap;

	return (
		<article className="panel replay-panel">
			<div className="panel-label">REPLAY CONTROLS</div>
			<h2>Tick-stream playback</h2>
			<div className="replay-controls-row">
				<button className="shock-button" onClick={isPlaying ? pause : play}>
					{isPlaying ? "Pause" : "Play"}
				</button>
				<div className="speed-group">
					{SPEEDS.map((candidate) => (
						<button
							key={candidate}
							className={`speed-button ${speed === candidate ? "speed-active" : ""}`}
							onClick={() => changeSpeed(candidate)}
						>
							{candidate}x
						</button>
					))}
				</div>
			</div>
			<input
				className="replay-scrub"
				type="range"
				min={startLap}
				max={endLap}
				value={scrubValue}
				onChange={(event) => scrubToLap(Number(event.target.value))}
			/>
			<div className="replay-readout">
				<span>Lap {scrubValue} / {endLap}</span>
				<span>{currentTick ? `${currentTick.lapTimeSeconds?.toFixed(1) ?? "—"}s lap time` : "No ticks yet"}</span>
			</div>
			{complete && <p className="data-note">Replay reached the end of the loaded stint.</p>}
			{error && <p className="error-note">Tick stream error: {error}</p>}
		</article>
	);
}
