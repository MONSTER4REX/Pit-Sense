/*
 * Formatting helpers. These convert backend values into display strings and do
 * nothing else - in particular they never fill in a missing value. A value the
 * backend could not measure renders as "not measured", never as 0.0s.
 */

export const UNAVAILABLE = "not measured";

export function seconds(value, digits = 2) {
	return value == null || Number.isNaN(value) ? UNAVAILABLE : `${value.toFixed(digits)}s`;
}

export function signedSeconds(value, digits = 2) {
	if (value == null || Number.isNaN(value)) return UNAVAILABLE;
	return `${value >= 0 ? "+" : ""}${value.toFixed(digits)}s`;
}

export function percent(value, digits = 0) {
	return value == null || Number.isNaN(value) ? UNAVAILABLE : `${(value * 100).toFixed(digits)}%`;
}

export function confidenceBand(confidence) {
	if (!confidence) return UNAVAILABLE;
	const low = Math.min(confidence.lower, confidence.upper);
	const high = Math.max(confidence.lower, confidence.upper);
	return `${Math.round(low * 100)}-${Math.round(high * 100)}%`;
}

export function position(value) {
	return value == null ? UNAVAILABLE : `P${value}`;
}

export function raceLabel(race) {
	return race ? `${race.year} ${race.event}` : "";
}

export function shortRaceLabel(race) {
	return race ? `${race.year} ${race.event.replace(" Grand Prix", " GP")}` : "";
}

/* The engine's action codes, spelled the way a strategist says them. */
export const ACTION_LABEL = {
	pit_now: "PIT NOW",
	stay_out: "STAY OUT",
	extend_stint: "EXTEND STINT",
	PIT: "PIT",
	STAY_OUT: "STAY OUT",
	EXTEND: "EXTEND",
};

export function actionLabel(action) {
	return ACTION_LABEL[action] ?? String(action ?? "").toUpperCase();
}
