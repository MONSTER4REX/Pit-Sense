/*
 * The only place the frontend talks to the backend.
 *
 * Every strategy call takes a lap number and nothing else. The backend derives
 * that lap's compound, tyre age, gaps, rival state, and stint history from the
 * loaded session itself (PRD section 5), so the frontend cannot assemble - and
 * therefore cannot get wrong - any authoritative race state.
 */

let sessionToken = null;

async function parseOrThrow(response) {
	const responseToken = response.headers.get("X-PitSense-Session");
	if (responseToken) sessionToken = responseToken;
	if (!response.ok) {
		const body = await response.text().catch(() => "");
		let message = "";
		try {
			const payload = JSON.parse(body);
			message = typeof payload.detail === "string" ? payload.detail : "";
		} catch {
			// Gateway errors are often HTML, so keep that implementation detail
			// out of the product UI.
		}
		if (!message && response.status === 502) {
			message = "The strategy service is temporarily unavailable. Please retry.";
		}
		if (!message) message = response.statusText || "Request failed";
		throw new Error(message);
	}
	return response.json();
}

function getJson(path, signal) {
	return fetch(path, {
		signal,
		credentials: "include",
		headers: sessionToken ? { "X-PitSense-Session": sessionToken } : undefined,
	}).then(parseOrThrow);
}

function postJson(path, body, signal) {
	return fetch(path, {
		method: "POST",
		headers: {
			"Content-Type": "application/json",
			...(sessionToken ? { "X-PitSense-Session": sessionToken } : {}),
		},
		body: JSON.stringify(body),
		signal,
		credentials: "include",
	}).then(parseOrThrow);
}

export const fetchAvailableRaces = (signal) => getJson("/api/races/available", signal);

export const loadRaceSession = (year, eventName, signal) =>
	getJson(`/api/race/${year}/${encodeURIComponent(eventName)}/session`, signal);

export const fetchCircuitData = (year, eventName, signal) =>
	getJson(`/api/circuit/${year}/${encodeURIComponent(eventName)}`, signal);

export const fetchRecommendation = (lap, signal) =>
	getJson(`/api/strategy/recommendation?lap=${lap}`, signal);

const waitBeforeRetry = (delayMs, signal) =>
	new Promise((resolve, reject) => {
		const timer = setTimeout(resolve, delayMs);
		signal?.addEventListener(
			"abort",
			() => {
				clearTimeout(timer);
				reject(new DOMException("The request was aborted", "AbortError"));
			},
			{ once: true },
		);
	});

export const fetchWhatIf = (lap, signal) => {
	const path = `/api/strategy/what-if?lap=${lap}`;
	return getJson(path, signal).catch((cause) => {
		if (cause.message !== "Load a historical race session first") throw cause;
		return waitBeforeRetry(250, signal)
			.then(() => getJson(path, signal))
			.catch((retryCause) => {
				if (retryCause.message !== "Load a historical race session first") throw retryCause;
				return waitBeforeRetry(750, signal).then(() => getJson(path, signal));
			});
	});
};

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
