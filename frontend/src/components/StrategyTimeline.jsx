function formatTimestamp(isoString) {
	try {
		return new Date(isoString).toLocaleTimeString();
	} catch {
		return isoString;
	}
}

export default function StrategyTimeline({ events, loading, error, currentLap = 17 }) {
	const pastEvents = (events ?? []).filter(e => e.lap_number < currentLap);
	
	return (
		<article className="panel timeline-panel">
			<div className="panel-label">STRATEGY TIMELINE</div>
			<h2>Event log</h2>
			{error && <p className="error-note">Timeline failed to load: {error}</p>}
			{loading && !pastEvents.length && <p className="data-note">Loading timeline…</p>}
			{!loading && pastEvents.length === 0 && <p className="data-note">No past events logged yet this session.</p>}
			<ul className="timeline-list">
				{[...pastEvents].reverse().map((event, index) => (
					<li className="timeline-row" key={`${event.timestamp}-${index}`}>
						<span className="timeline-lap">LAP {event.lap_number}</span>
						<span className="timeline-type">{event.event_type.replace(/_/g, " ").toUpperCase()}</span>
						<span className="timeline-detail">{event.detail}</span>
						<span className="timeline-time">{formatTimestamp(event.timestamp)}</span>
					</li>
				))}
			</ul>
		</article>
	);
}
