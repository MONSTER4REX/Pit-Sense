import { useTickStream } from "../hooks/useTickStream";

const SPEEDS = [1, 2, 5];

export default function ReplayControls({ lapTimes, startLap, startTyreAge = 12, onTick, simulation = false, onSimulationTick }) {
	const { isPlaying, speed, currentTick, error, complete, play, pause, scrubToLap, changeSpeed } = useTickStream({
		lapTimes,
		startLap,
		startTyreAge,
		onTick,
		simulation,
		onSimulationTick,
	});
	const endLap = startLap + lapTimes.length - 1;
	const scrubValue = currentTick?.lapNumber ?? startLap;

	return (
		<article className="panel replay-panel">
			<div className="panel-label">REPLAY CONTROLS</div>
			<h2>Tick-stream playback</h2>
			<div className="flex items-center gap-4 mt-4">
				<button 
					className="px-4 py-2 bg-slate-800 border border-slate-600 rounded hover:bg-slate-700 transition-colors text-sm font-mono uppercase tracking-wide cursor-pointer text-slate-200" 
					onClick={isPlaying ? pause : play}
				>
					{isPlaying ? "Pause" : "Play"}
				</button>
				<div className="flex gap-1.5 bg-slate-800 p-1 rounded border border-slate-700">
					{SPEEDS.map((candidate) => (
						<button
							key={candidate}
							className={`px-3 py-1.5 text-xs font-mono rounded transition-all cursor-pointer ${speed === candidate ? "bg-orange-500 text-black font-bold shadow-sm" : "text-slate-300 hover:bg-slate-700 hover:text-white"}`}
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
