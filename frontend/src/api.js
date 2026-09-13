/*
 * The only place the frontend talks to the backend.
 *
 * Every strategy call takes a lap number and nothing else. The backend derives
 * that lap's compound, tyre age, gaps, rival state, and stint history from the
 * loaded session itself (PRD section 5), so the frontend cannot assemble - and
 * therefore cannot get wrong - any authoritative race state.
 */

async function parseOrThrow(response) {
	if (!response.ok) {
		const body = await response.text().catch(() => "");
		throw new Error(`${response.status} ${response.statusText}: ${body}`);
	}
	return response.json();
}

function getJson(path, signal) {
	return fetch(path, { signal }).then(parseOrThrow);
}

function postJson(path, body, signal) {
	return fetch(path, {
		method: "POST",
		headers: { "Content-Type": "application/json" },
		body: JSON.stringify(body),
		signal,
	}).then(parseOrThrow);
}

export const fetchAvailableRaces = (signal) => getJson("/api/races/available", signal);

export const loadRaceSession = (year, eventName, signal) =>
	getJson(`/api/race/${year}/${encodeURIComponent(eventName)}/session`, signal);

export const fetchCircuitData = (year, eventName, signal) =>
	getJson(`/api/circuit/${year}/${encodeURIComponent(eventName)}`, signal);

export const fetchRecommendation = (lap, signal) =>
	getJson(`/api/strategy/recommendation?lap=${lap}`, signal);

export const fetchWhatIf = (lap, signal) => getJson(`/api/strategy/what-if?lap=${lap}`, signal);

export const fetchTimeline = (signal) => getJson("/api/timeline", signal);

export const fetchTyreModelStatus = (signal) => getJson("/api/model/tyre", signal);

export const injectSimulationShock = (eventType, lap, signal) =>
	postJson("/api/simulation/shock", { event_type: eventType, lap }, signal);

export const acceptSimulationDecision = (action, lap, signal) =>
	postJson("/api/simulation/decision", { action, lap }, signal);

export const fetchSimulationTick = (lap, signal) =>
	getJson(`/api/simulation/tick?lap=${lap}`, signal);

export const fetchCounterfactualSummary = (signal) =>
	getJson("/api/simulation/counterfactual", signal);

export const fetchSimulationAssumptions = (signal) =>
	getJson("/api/simulation/assumptions", signal);

export const fetchReoptimizations = (signal) => getJson("/api/simulation/reoptimizations", signal);
