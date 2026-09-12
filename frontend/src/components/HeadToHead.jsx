function actionRecords(projectedTicks, car) {
	return projectedTicks.flatMap((tick) => tick.decisions?.filter((decision) => decision.car === car) ?? []);
}

function pitLaps(projectedTicks, car) {
	return projectedTicks
		.filter((tick) => tick.cars?.some((state) => state.car === car && state.pit_status === "PIT_IN"))
		.map((tick) => tick.lap);
}

function unique(values) {
	return [...new Set(values)];
}

function formatLaps(laps) {
	return laps.length ? laps.map((lap) => `L${lap}`).join(", ") : "—";
}

function totalProjectedTime(raceMetadata, projectedTicks, car, forkLap) {
	const historical = (car === "P2" ? raceMetadata?.p2_lap_states : raceMetadata?.p1_lap_states) ?? [];
	const beforeFork = historical.filter((lap) => lap.lap_number < forkLap);
	const afterFork = projectedTicks
		.filter((tick) => tick.lap >= forkLap)
		.map((tick) => tick.cars?.find((state) => state.car === car)?.lap_time_seconds);
	const values = [...beforeFork.map((lap) => lap.lap_time_seconds), ...afterFork];
	return values.length && values.every((value) => value != null) ? values.reduce((sum, value) => sum + value, 0) : null;
}

function decisionCount(records) {
	return unique(records.filter((record) => record.action !== "STAY_OUT").map((record) => `${record.lap}:${record.action}`)).length;
}

function overtakeLap(projectedTicks) {
	const lap = projectedTicks.find((tick) => {
		const p1 = tick.cars?.find((car) => car.car === "P1");
		const p2 = tick.cars?.find((car) => car.car === "P2");
		return p1?.position != null && p2?.position != null && p2.position < p1.position;
	});
	return lap?.lap ?? null;
}

export default function HeadToHead({ replayMode, completed, totalLaps, forkLap, raceMetadata, projectedTicks, summary }) {
	if (replayMode !== "counterfactual") {
		return <section className="head-to-head panel data-projected"><div className="panel-label">HEAD-TO-HEAD: PITSENSE VS BASELINE</div><p className="data-note">Awaiting a counterfactual run before comparing strategy policies.</p></section>;
	}
	if (!completed || !summary) {
		return <section className="head-to-head panel data-projected"><div className="panel-label">HEAD-TO-HEAD: PITSENSE VS BASELINE</div><p className="data-note">Comparison pending — projected replay must reach Lap {totalLaps} before full-race metrics are shown.</p></section>;
	}

	const pitsenseRecords = actionRecords(projectedTicks, "P2");
	const baselineRecords = actionRecords(projectedTicks, "P1");
	const finalTick = projectedTicks.find((tick) => tick.lap === totalLaps) ?? projectedTicks.at(-1);
	const pitsenseFinal = finalTick?.cars?.find((car) => car.car === "P2");
	const baselineFinal = finalTick?.cars?.find((car) => car.car === "P1");
	const pitsensePitLaps = pitLaps(projectedTicks, "P2");
	const baselinePitLaps = pitLaps(projectedTicks, "P1");
	const historicalPitLaps = (raceMetadata?.p2_pit_stops ?? []).map((stop) => stop.lap_number);
	const pitsenseTime = totalProjectedTime(raceMetadata, projectedTicks, "P2", forkLap);
	const baselineTime = totalProjectedTime(raceMetadata, projectedTicks, "P1", forkLap);
	const passLap = overtakeLap(projectedTicks);
	const differences = [
		`PitSense ${pitsensePitLaps.length ? `pitted on ${formatLaps(pitsensePitLaps)}` : "did not record a pit entry"}; Baseline ${baselinePitLaps.length ? `pitted on ${formatLaps(baselinePitLaps)}` : "did not record a pit entry"}.`,
		pitsenseRecords.at(-1)?.action !== baselineRecords.at(-1)?.action ? `The policies ended with different actions: ${pitsenseRecords.at(-1)?.action ?? "Unavailable"} vs ${baselineRecords.at(-1)?.action ?? "Unavailable"}.` : "The policies ended with the same recorded action.",
	].join(" ");

	const rows = [
		["Decision count", decisionCount(pitsenseRecords), decisionCount(baselineRecords)],
		["Pit timing", formatLaps(pitsensePitLaps), formatLaps(baselinePitLaps)],
		["Total projected time", pitsenseTime == null ? "Unavailable" : `${pitsenseTime.toFixed(2)}s`, baselineTime == null ? "Unavailable" : `${baselineTime.toFixed(2)}s`],
		["Projected finish position", `P${summary.pitsense_projected_finish}`, `P${summary.baseline_projected_finish}`],
		["Projected gap", pitsenseFinal ? `${pitsenseFinal.gap_to_leader_seconds.toFixed(2)}s` : "Unavailable", baselineFinal ? `${baselineFinal.gap_to_leader_seconds.toFixed(2)}s` : "Unavailable"],
		["Overtake lap", passLap == null ? "—" : `L${passLap}`, passLap == null ? "—" : `L${passLap}`],
	];

	return (
		<section className="head-to-head panel data-projected">
			<div className="panel-label">HEAD-TO-HEAD: PITSENSE VS BASELINE</div>
			<p className="data-note">Full-race counterfactual comparison · Projected from Lap {forkLap}. Historical PitSense car pit laps: {formatLaps(historicalPitLaps)}.</p>
			<div className="head-to-head-table">
				<div className="h2h-row h2h-head"><span>METRIC</span><strong>YOUR CAR — PITSENSE</strong><strong>OPPONENT — BASELINE</strong></div>
				{rows.map(([label, pitsense, baseline]) => <div className="h2h-row" key={label}><span>{label}</span><strong>{pitsense}</strong><strong>{baseline}</strong></div>)}
			</div>
			<div className="strategic-differences"><span>MAJOR STRATEGIC DIFFERENCES</span><p>{differences}</p></div>
		</section>
	);
}
