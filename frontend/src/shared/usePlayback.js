import { useCallback, useEffect, useRef, useState } from "react";

/*
 * Lap playback.
 *
 * A hook, not a component, and deliberately not shared *state* - each product
 * calls it with its own lap setter and its own bounds, so Race Analysis and
 * Simulation Lab never drive one another (PRD 2.1). What is shared is the
 * mechanism, which is the same kind of thing as a shared button.
 *
 * The timer advances the lap; every panel already recomputes from the backend
 * when the lap changes, so playback needs no separate data path of its own.
 */

/* Wall-clock milliseconds per lap at 1x. Fast enough to watch a 70-lap race
 * without waiting, slow enough to read the panels as they change. */
const BASE_LAP_INTERVAL_MS = 1400;
export const SPEEDS = [1, 2, 5];

export function usePlayback({ currentLap, totalLaps, setLap, startLap = 1 }) {
	const [isPlaying, setIsPlaying] = useState(false);
	const [speed, setSpeed] = useState(1);

	// The timer reads the lap through a ref so that changing lap does not tear
	// down and rebuild the interval on every tick.
	const lapRef = useRef(currentLap);
	lapRef.current = currentLap;

	const atEnd = totalLaps > 0 && currentLap >= totalLaps;

	const play = useCallback(() => {
		if (!totalLaps) return;
		// Playing from the final lap restarts, rather than doing nothing.
		if (lapRef.current >= totalLaps) setLap(startLap);
		setIsPlaying(true);
	}, [setLap, startLap, totalLaps]);

	const pause = useCallback(() => setIsPlaying(false), []);
	const toggle = useCallback(() => (isPlaying ? pause() : play()), [isPlaying, pause, play]);

	const step = useCallback(
		(delta) => {
			setIsPlaying(false);
			const next = Math.min(totalLaps || 1, Math.max(startLap, lapRef.current + delta));
			setLap(next);
		},
		[setLap, startLap, totalLaps],
	);

	useEffect(() => {
		if (!isPlaying || !totalLaps) return undefined;
		const timer = window.setInterval(() => {
			const next = lapRef.current + 1;
			if (next > totalLaps) {
				setIsPlaying(false);
				return;
			}
			setLap(next);
		}, BASE_LAP_INTERVAL_MS / speed);
		return () => window.clearInterval(timer);
	}, [isPlaying, speed, totalLaps, setLap]);

	// Stop at the flag rather than sitting on a running timer with nowhere to go.
	useEffect(() => {
		if (atEnd) setIsPlaying(false);
	}, [atEnd]);

	return { isPlaying, speed, setSpeed, play, pause, toggle, step, atEnd };
}
