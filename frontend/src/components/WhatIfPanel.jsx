import { useState, useEffect } from "react";
import { fetchWhatIf } from "../api";

const BRANCH_LABEL = { pit_now: "PIT NOW", stay_out: "STAY OUT", extend_stint: "EXTEND" };

function formatTimeEffect(seconds) {
	if (seconds == null || !Number.isFinite(seconds)) return "—";
	if (Math.abs(seconds) < 0.05) return "BEST";
	return `${seconds > 0 ? "+" : ""}${seconds.toFixed(1)}s`;
}

export default function WhatIfPanel({ request }) {
	const [branches, setBranches] = useState(null);
	const [loading, setLoading] = useState(false);
	const [error, setError] = useState(null);

	useEffect(() => {
		const controller = new AbortController();
		const runComparison = async () => {
			setLoading(true);
			setError(null);
			setBranches(null);
			try {
				const data = await fetchWhatIf(request, controller.signal);
				setBranches(data);
			} catch (err) {
				if (err.name !== "AbortError") setError(err.message);
			} finally {
				if (!controller.signal.aborted) setLoading(false);
			}
		};
		runComparison();
		return () => controller.abort();
	}, [request]);

	const entries = branches ? Object.entries(branches) : [];
	const pitNow = branches?.pit_now?.projected_total_time_seconds;

	return (
		<article className="panel whatif-panel">
			<div className="panel-label">WHAT-IF SIMULATOR</div>
			<h2>WHAT-IF — CURRENT STATE: LAP {request.start_lap}</h2>
			<p className="data-note">Each branch is recalculated from the current lap, tyre age, and active shock-event state.</p>
			{loading && <p className="data-note">Running current-state projections…</p>}
			{error && <p className="error-note">What-if comparison failed: {error}</p>}
			{entries.length > 0 && (
				<div className="whatif-table">
					<div className="whatif-table-row whatif-table-head">
						<span>ACTION</span><span>TIME EFFECT</span><span>PROJECTED POSITION</span>
					</div>
					{entries.map(([key, branch]) => {
						return (
							<div className="whatif-table-row" key={key}>
								<strong>{BRANCH_LABEL[key] ?? key.toUpperCase()}</strong>
								<span>{formatTimeEffect(branch.projected_total_time_seconds - pitNow)}</span>
								<span className="insufficient-data">— <em>insufficient position model</em></span>
							</div>
						);
					})}
				</div>
			)}
		</article>
	);
}
