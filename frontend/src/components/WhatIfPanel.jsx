import { useState, useEffect } from "react";
import ExplainabilityChart from "./ExplainabilityChart";
import UndercutRiskTier from "./UndercutRiskTier";
import { fetchWhatIf } from "../api";

const BRANCH_LABEL = { pit_now: "PIT NOW", stay_out: "STAY OUT", extend_stint: "EXTEND" };
// Backend branches only expose projected total time; positions are estimated
// client-side from the time delta since the engine does not model grid order.
const SECONDS_PER_POSITION = 3.0;

export default function WhatIfPanel({ request, currentPosition = 4 }) {
	const [branches, setBranches] = useState(null);
	const [loading, setLoading] = useState(false);
	const [error, setError] = useState(null);

	useEffect(() => {
		let isCancelled = false;
		const runComparison = async () => {
			setLoading(true);
			setError(null);
			try {
				const data = await fetchWhatIf(request);
				if (!isCancelled) setBranches(data);
			} catch (err) {
				if (!isCancelled) setError(err.message);
			} finally {
				if (!isCancelled) setLoading(false);
			}
		};
		runComparison();
		return () => { isCancelled = true; };
	}, [request]);

	const entries = branches ? Object.entries(branches) : [];
	const bestTime = entries.length ? Math.min(...entries.map(([, branch]) => branch.projected_total_time_seconds)) : 0;

	return (
		<article className="panel whatif-panel">
			<div className="panel-label">WHAT-IF SIMULATOR</div>
			<h2>Branch comparison</h2>
			{loading && !branches && <p className="data-note">Running what-if simulations...</p>}
			{error && <p className="error-note">What-if comparison failed: {error}</p>}
			{entries.length > 0 && (
				<div className="grid grid-cols-1 md:grid-cols-3 gap-4 mt-5">
					{entries.map(([key, branch]) => {
						const delta = branch.projected_total_time_seconds - bestTime;
						const position = Math.min(20, Math.max(1, Math.round(currentPosition + delta / SECONDS_PER_POSITION)));
						return (
							<div className="whatif-branch" key={key}>
								<div className="whatif-branch-head">
									<span>{BRANCH_LABEL[key] ?? key.toUpperCase()}</span>
									<UndercutRiskTier tier={branch.undercut_risk_tier} />
								</div>
								<div className="whatif-metric">
									<span>Projected time delta</span>
									<strong>{delta === 0 ? "BEST" : `+${delta.toFixed(1)}s`}</strong>
								</div>
								<div className="whatif-metric">
									<span>
										Projected finishing position <em className="estimate-flag" title="Estimated client-side from time delta; the backend does not model grid position">(estimated)</em>
									</span>
									<strong>P{position}</strong>
								</div>
								<ExplainabilityChart explainability={branch.explainability} />
							</div>
						);
					})}
				</div>
			)}
		</article>
	);
}
