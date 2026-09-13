import { Note, Panel, StatusBadge } from "../shared/primitives";
import PlaybackControls from "../shared/PlaybackControls";
import { usePlayback } from "../shared/usePlayback";
import { seconds } from "../shared/format";
import { useRaceAnalysis } from "./RaceAnalysisProvider";

/*
 * Race context and replay for the analysis dashboard.
 *
 * This is a lap scrubber over real recorded history plus the events logged this
 * session. It is deliberately not the Simulation Lab's timeline, which also has
 * to separate a historical portion from a projected one.
 */
export default function AnalysisTimeline() {
	const { session, currentLap, setCurrentLap, totalLaps, timelineEvents, lapState } =
		useRaceAnalysis();

	// Race Analysis drives its own playback; the Lab has a separate instance.
	const playback = usePlayback({ currentLap, totalLaps, setLap: setCurrentLap });
	const pitStops = session?.p2_pit_stops ?? [];
	const events = (timelineEvents ?? []).filter((event) => event.lap_number <= currentLap);

	return (
		<Panel label="RACE CONTEXT & REPLAY" tone="historical" className="timeline-panel">
			<PlaybackControls
				{...playback}
				currentLap={currentLap}
				totalLaps={totalLaps}
				setLap={setCurrentLap}
				tone="historical"
			/>

			{/* Real recorded pit stops, marked where they actually happened. */}
			<div className="stint-strip" aria-label="Recorded pit stops for our car">
				{Array.from({ length: Math.max(0, totalLaps) }, (_, index) => index + 1).map((lap) => {
					const isStop = pitStops.some((stop) => stop.lap_number === lap);
					const isCurrent = lap === currentLap;
					return (
						<span
							key={lap}
							className={`stint-lap ${isStop ? "stint-pit" : ""} ${isCurrent ? "stint-current" : ""}`.trim()}
							title={isStop ? `Recorded pit stop on lap ${lap}` : `Lap ${lap}`}
						/>
					);
				})}
			</div>

			<div className="lap-readout">
				<div>
					<span>Position</span>
					<strong>{lapState?.position != null ? `P${lapState.position}` : "not recorded"}</strong>
				</div>
				<div>
					<span>Gap to leader</span>
					<strong>{seconds(lapState?.gap_to_leader_seconds)}</strong>
				</div>
				<div>
					<span>Tyre</span>
					<strong>
						{lapState?.compound ?? "not recorded"}
						{lapState?.tyre_life != null ? ` · ${lapState.tyre_life} laps` : ""}
					</strong>
				</div>
				<div>
					<span>Lap time</span>
					<strong>{seconds(lapState?.lap_time_seconds, 3)}</strong>
				</div>
			</div>

			<div className="event-log">
				<div className="panel-label">EVENT LOG</div>
				{events.length === 0 ? (
					<Note>No events logged up to lap {currentLap}.</Note>
				) : (
					<ul>
						{[...events].reverse().map((event, index) => (
							<li key={`${event.timestamp}-${index}`}>
								<StatusBadge tone="neutral">LAP {event.lap_number}</StatusBadge>
								<span className="event-type">{event.event_type.replace(/_/g, " ").toUpperCase()}</span>
								<span className="event-detail">{event.detail}</span>
							</li>
						))}
					</ul>
				)}
			</div>
		</Panel>
	);
}
