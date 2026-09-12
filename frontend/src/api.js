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
