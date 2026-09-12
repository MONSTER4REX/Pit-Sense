const JSON_HEADERS = { "Content-Type": "application/json" };

async function parseOrThrow(response) {
	if (!response.ok) {
		const body = await response.text().catch(() => "");
		throw new Error(`${response.status} ${response.statusText}: ${body}`);
	}
	return response.json();
}

export function fetchRecommendation(request, signal) {
	return fetch("/api/strategy/recommendation", {
		method: "POST",
		headers: JSON_HEADERS,
		body: JSON.stringify(request),
		signal,
	}).then(parseOrThrow);
}

export function fetchWhatIf(request, signal) {
	return fetch("/api/strategy/what-if", {
		method: "POST",
		headers: JSON_HEADERS,
		body: JSON.stringify(request),
		signal,
	}).then(parseOrThrow);
}

export function injectShockEvent(eventType, lapNumber, signal) {
	const params = new URLSearchParams({ event_type: eventType, lap_number: String(lapNumber) });
	return fetch(`/api/timeline/shock?${params.toString()}`, { method: "POST", signal }).then(parseOrThrow);
}

export function fetchTimeline(signal) {
	return fetch("/api/timeline", { signal }).then(parseOrThrow);
}

export function fetchAvailableRaces(signal) {
	return fetch("/api/races/available", { signal }).then(parseOrThrow);
}

export function loadRaceSession(year, eventName, signal) {
	return fetch(`/api/race/${year}/${encodeURIComponent(eventName)}/session`, { signal }).then(parseOrThrow);
}

export function injectSimulationShock(eventType, lap, signal) {
	return fetch("/api/simulation/shock", {
		method: "POST",
		headers: JSON_HEADERS,
		body: JSON.stringify({ event_type: eventType, lap }),
		signal,
	}).then(parseOrThrow);
}

export function acceptSimulationDecision(action, lap, signal) {
	return fetch("/api/simulation/decision", {
		method: "POST",
		headers: JSON_HEADERS,
		body: JSON.stringify({ action, lap }),
		signal,
	}).then(parseOrThrow);
}

export function fetchCounterfactualSummary(signal) {
	return fetch("/api/simulation/counterfactual", { signal }).then(parseOrThrow);
}
