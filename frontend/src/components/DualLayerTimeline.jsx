export default function DualLayerTimeline({ forkLap, currentLap, totalLaps }) {
	const actualWidth = `${Math.max(2, Math.min(100, (forkLap / totalLaps) * 100))}%`;
	const projectionWidth = `${Math.max(2, Math.min(100, ((currentLap - forkLap + 1) / Math.max(1, totalLaps - forkLap + 1)) * 100))}%`;
	return (
		<article className="panel dual-timeline data-projected">
			<div className="panel-label">DUAL-LAYER TIMELINE</div>
			<h2>Historical reference and projected branches</h2>
			<div className="timeline-legend"><span><i className="legend-line legend-solid" /> Solid = historical</span><span><i className="legend-line legend-dashed" /> Dashed = projected</span></div>
			<div className="dual-timeline-row"><span>ACTUAL HISTORY</span><div className="dual-track"><i className="dual-history-line" style={{ width: actualWidth }} /><b>FORK LAP {forkLap}</b></div></div>
			<div className="dual-timeline-row"><span>PITSENSE PROJECTION</span><div className="dual-track"><i className="dual-projection-line" style={{ width: projectionWidth }} /></div></div>
			<div className="dual-timeline-row"><span>BASELINE PROJECTION</span><div className="dual-track"><i className="dual-projection-line baseline-line" style={{ width: projectionWidth }} /></div></div>
		</article>
	);
}
