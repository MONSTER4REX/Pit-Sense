/*
 * The only place the frontend talks to the backend.
 *
 * Every strategy call takes a lap number and nothing else. The backend derives
 * that lap's compound, tyre age, gaps, rival state, and stint history from the
 * loaded session itself (PRD section 5), so the frontend cannot assemble - and
 * therefore cannot get wrong - any authoritative race state.
 */

/*
 * The visitor's session token.
 *
 * The server will mint one if the client does not send it, but letting it do
 * that is a race: the first page load fires several requests at once, each
 * arrives without a token, each gets a *different* one minted, and whichever
 * response lands last wins. A race loaded under one token was then queried
 * under another, and the second token's slot had no race in it - which is the
 * "load a historical race session first" error the what-if panel was hitting.
 *
 * Generating it on the client removes the race entirely: every request from the
 * very first one carries the same token, whatever order they complete in. It is
 * kept in sessionStorage so a reload keeps the visitor's loaded race, and a
 * second tab is treated as a second visitor.
 */
const SESSION_STORAGE_KEY = "pitsense.session";

function createToken() {
	if (globalThis.crypto?.randomUUID) return globalThis.crypto.randomUUID().replace(/-/g, "");
	return `${Date.now().toString(16)}${Math.random().toString(16).slice(2, 14)}`;
}

function readToken() {
	try {
		const existing = globalThis.sessionStorage?.getItem(SESSION_STORAGE_KEY);
		if (existing) return existing;
		const minted = createToken();
		globalThis.sessionStorage?.setItem(SESSION_STORAGE_KEY, minted);
		return minted;
	} catch {
		// Private modes and embedded webviews can refuse storage; a per-load token
		// still beats letting the server mint one per parallel request.
		return createToken();
	}
}

let sessionToken = readToken();

async function parseOrThrow(response) {
	// The server echoes the token back. It should always match the one sent; it
	// only differs if storage was unavailable and the server minted one instead.
	const responseToken = response.headers.get("X-PitSense-Session");
	if (responseToken && !sessionToken) sessionToken = responseToken;
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
		const error = new Error(message);
		error.status = response.status;
		throw error;
	}
	return response.json();
}

function getJson(path, signal) {
	return fetch(path, {
		signal,
		credentials: "include",
		headers: { "X-PitSense-Session": sessionToken },
	}).then(parseOrThrow);
}

function postJson(path, body, signal) {
	return fetch(path, {
		method: "POST",
		headers: {
			"Content-Type": "application/json",
			"X-PitSense-Session": sessionToken,
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
	const retryable = (cause) =>
		cause.message === "Load a historical race session first" ||
		[502, 503, 504].includes(cause.status);
	return getJson(path, signal)
		.catch((cause) => {
			if (!retryable(cause)) throw cause;
			return waitBeforeRetry(500, signal).then(() => getJson(path, signal));
		})
		.catch((cause) => {
			if (!retryable(cause)) throw cause;
			return waitBeforeRetry(1500, signal).then(() => getJson(path, signal));
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
