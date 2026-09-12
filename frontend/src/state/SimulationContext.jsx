import { createContext, useCallback, useContext, useMemo, useState } from "react";

export const REPLAY_MODES = {
	HISTORICAL: "historical",
	COUNTERFACTUAL: "counterfactual",
};

const INITIAL_REPLAY_STATE = {
	replayMode: REPLAY_MODES.HISTORICAL,
	forkLap: null,
	acceptedAction: null,
	currentLap: 1,
	totalLaps: 0,
	speed: 1,
	selectedRace: null,
	raceMetadata: null,
	shockEvent: null,
	shockLap: null,
	shockReference: null,
	shockDecisions: [],
	projectedTicks: [],
	counterfactualSummary: null,
};

const SimulationContext = createContext(null);

export function SimulationProvider({ children }) {
	const [state, setState] = useState(INITIAL_REPLAY_STATE);

	const resetSimulation = useCallback(() => {
		setState((current) => ({
			...INITIAL_REPLAY_STATE,
			selectedRace: current.selectedRace,
			raceMetadata: current.raceMetadata,
			totalLaps: current.totalLaps,
		}));
	}, []);

	const selectRace = useCallback((race) => {
		setState({
			...INITIAL_REPLAY_STATE,
			selectedRace: race,
		});
	}, []);

	const setRaceMetadata = useCallback((metadata) => {
		setState((current) => ({
			...current,
			raceMetadata: metadata,
			totalLaps: metadata.total_laps,
			currentLap: 1,
		}));
	}, []);

	const setCurrentLap = useCallback((currentLap) => {
		setState((current) => ({ ...current, currentLap }));
	}, []);

	const setSpeed = useCallback((speed) => {
		setState((current) => ({ ...current, speed }));
	}, []);

	const acceptCounterfactual = useCallback((forkLap, acceptedAction) => {
		setState((current) => ({
			...current,
			replayMode: REPLAY_MODES.COUNTERFACTUAL,
			forkLap,
			acceptedAction,
		}));
	}, []);

	const recordShockEvent = useCallback((eventType, lap, reference, decisions) => {
		setState((current) => ({
			...current,
			shockEvent: eventType,
			shockLap: lap,
			shockReference: reference,
			shockDecisions: decisions,
		}));
	}, []);

	const recordProjectedTick = useCallback((tick) => {
		setState((current) => ({
			...current,
			projectedTicks: [...current.projectedTicks.filter((item) => item.lap !== tick.lap), tick].sort((a, b) => a.lap - b.lap),
		}));
	}, []);

	const setCounterfactualSummary = useCallback((summary) => {
		setState((current) => ({ ...current, counterfactualSummary: summary }));
	}, []);

	const value = useMemo(
		() => ({
			...state,
			resetSimulation,
			selectRace,
			setRaceMetadata,
			setCurrentLap,
			setSpeed,
			acceptCounterfactual,
			recordShockEvent,
			recordProjectedTick,
			setCounterfactualSummary,
		}),
		[state, resetSimulation, selectRace, setRaceMetadata, setCurrentLap, setSpeed, acceptCounterfactual, recordShockEvent, recordProjectedTick, setCounterfactualSummary],
	);

	return <SimulationContext.Provider value={value}>{children}</SimulationContext.Provider>;
}

export function useSimulation() {
	const context = useContext(SimulationContext);
	if (!context) {
		throw new Error("useSimulation must be used within SimulationProvider");
	}
	return context;
}
