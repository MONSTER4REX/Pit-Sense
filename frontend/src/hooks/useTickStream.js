import { useCallback, useRef, useState } from "react";

// The backend /ws/replay protocol has no seek/pause frames: a client sends one
// {speed, lap_times} message and receives a one-shot stream of ticks. To offer
// play/pause/scrub against that real capability (rather than inventing a fake
// backend feature), we reconnect with a lap-times slice whenever the user
// pauses, scrubs, or changes speed, and reconstruct the true lap number
// client-side since the server always numbers ticks from 1 within the slice.
export function useTickStream({ lapTimes, startLap = 1, startTyreAge = 12, onTick }) {
	const socketRef = useRef(null);
	const lapIndexRef = useRef(0);
	const onTickRef = useRef(onTick);
	onTickRef.current = onTick;

	const [isPlaying, setIsPlaying] = useState(false);
	const [speed, setSpeed] = useState(1);
	const [currentTick, setCurrentTick] = useState(null);
	const [error, setError] = useState(null);
	const [complete, setComplete] = useState(false);

	const closeSocket = useCallback(() => {
		if (socketRef.current) {
			socketRef.current.onclose = null;
			socketRef.current.close();
			socketRef.current = null;
		}
	}, []);

	const connect = useCallback(
		(lapIndex, playbackSpeed) => {
			closeSocket();
			setError(null);
			setComplete(false);
			lapIndexRef.current = lapIndex;
			const protocol = window.location.protocol === "https:" ? "wss" : "ws";
			const socket = new WebSocket(`${protocol}://${window.location.host}/ws/replay`);
			socketRef.current = socket;
			socket.onopen = () => {
				socket.send(
					JSON.stringify({
						speed: playbackSpeed,
						lap_times: lapTimes.slice(lapIndex),
						start_lap: startLap + lapIndex,
						start_tyre_age: startTyreAge + lapIndex,
					}),
				);
				setIsPlaying(true);
			};
			socket.onmessage = (messageEvent) => {
				const payload = JSON.parse(messageEvent.data);
				if (payload.type === "tick") {
					const trueLapNumber = payload.lap_number;
					lapIndexRef.current = trueLapNumber - startLap;
					const tickData = {
						lapNumber: trueLapNumber,
						timestampSeconds: payload.timestamp_seconds,
						lapTimeSeconds: payload.lap_time_seconds,
						rivalCoverStopProbability: payload.rival_cover_stop_probability,
						trafficRejoinRisk: payload.traffic_rejoin_risk,
						tyreAge: payload.tyre_age,
						distanceToDriverAhead: payload.distance_to_driver_ahead,
					};
					setCurrentTick(tickData);
					if (onTickRef.current) {
						onTickRef.current(tickData);
					}
				} else if (payload.type === "complete") {
					setComplete(true);
					setIsPlaying(false);
				} else if (payload.type === "error") {
					setError(payload.message);
					setIsPlaying(false);
				}
			};
			socket.onerror = () => setError("WebSocket connection error");
			socket.onclose = () => setIsPlaying(false);
		},
		[closeSocket, lapTimes, startLap, startTyreAge],
	);

	const play = useCallback(() => connect(lapIndexRef.current, speed), [connect, speed]);

	const pause = useCallback(() => {
		closeSocket();
		setIsPlaying(false);
	}, [closeSocket]);

	const scrubToLap = useCallback(
		(lapNumber) => {
			const lapIndex = Math.max(0, Math.min(lapTimes.length - 1, lapNumber - startLap));
			lapIndexRef.current = lapIndex;
			const scrubTick = {
				lapNumber,
				timestampSeconds: 0,
				lapTimeSeconds: lapTimes[lapIndex] ?? null,
				tyreAge: startTyreAge + lapIndex,
			};
			setCurrentTick(scrubTick);
			if (onTickRef.current) {
				onTickRef.current(scrubTick);
			}
			if (isPlaying) connect(lapIndex, speed);
		},
		[connect, isPlaying, lapTimes, speed, startLap, startTyreAge],
	);

	const changeSpeed = useCallback(
		(nextSpeed) => {
			setSpeed(nextSpeed);
			if (isPlaying) connect(lapIndexRef.current, nextSpeed);
		},
		[connect, isPlaying],
	);

	return { isPlaying, speed, currentTick, error, complete, play, pause, scrubToLap, changeSpeed };
}
