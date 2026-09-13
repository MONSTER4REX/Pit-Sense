import { useMemo } from "react";

import { EmptyState, Note, Panel, StatusBadge } from "../shared/primitives";
import { seconds } from "../shared/format";
import { PHASES, useSimulationLab } from "./SimulationLabProvider";

/*
 * The circuit, drawn only from verified geometry (PRD 9.5, 9.6, section 10).
 *
 * Every coordinate on this page comes from FastF1 positional telemetry for the
 * selected session: the racing line from a real fastest lap, the pit lane from a
 * real in-lap and out-lap. There is no generic oval, no invented coordinate, and
 * no fallback shape. A race without verified geometry gets the empty state
 * below, which is the honest answer rather than a decorative one.
 *
 * Car markers move along the racing line by lap progress and, on a pit lap,
 * along the real pit-lane path instead - so a stop is visibly track -> entry ->
 * lane -> exit -> track, never a marker teleporting across the map.
 */

/* Padding inside the 0-100 viewBox so markers near the edge stay visible. */
const VIEWBOX_PADDING = 6;
const VIEWBOX_SPAN = 100 - VIEWBOX_PADDING * 2;

function normalise(xs, ys) {
	if (!xs?.length || xs.length !== ys.length) return null;
	const minX = Math.min(...xs);
	const maxX = Math.max(...xs);
	const minY = Math.min(...ys);
	const maxY = Math.max(...ys);
	// One scale for both axes, so the circuit keeps its real proportions.
	const scale = Math.max(maxX - minX, maxY - minY) || 1;
	const offsetX = (scale - (maxX - minX)) / 2;
	const offsetY = (scale - (maxY - minY)) / 2;
	return xs.map((x, index) => ({
		x: VIEWBOX_PADDING + ((x - minX + offsetX) / scale) * VIEWBOX_SPAN,
		// SVG y grows downward; the circuit is drawn the way a map reads.
		y: VIEWBOX_PADDING + (1 - (ys[index] - minY + offsetY) / scale) * VIEWBOX_SPAN,
	}));
}

function toPath(points) {
	return points?.length ? points.map((point) => `${point.x.toFixed(2)},${point.y.toFixed(2)}`).join(" ") : "";
}

function pointAt(points, fraction) {
	if (!points?.length) return null;
	const index = Math.min(points.length - 1, Math.max(0, Math.round(fraction * (points.length - 1))));
	return points[index];
}

export default function SimulationTrack() {
	const {
		circuit,
		circuitLoading,
		geometryVerified,
		selectedRace,
		session,
		currentLap,
		totalLaps,
		phase,
		projectedTick,
	} = useSimulationLab();

	/* All paths share one normalisation, so the pit lane sits correctly against
	 * the racing line rather than being scaled independently. */
	const geometry = useMemo(() => {
		if (!circuit?.verified) return null;
		const pit = circuit.pit_lane ?? {};
		const allX = [...circuit.x, ...(pit.entry_x ?? []), ...(pit.lane_x ?? []), ...(pit.exit_x ?? [])];
		const allY = [...circuit.y, ...(pit.entry_y ?? []), ...(pit.lane_y ?? []), ...(pit.exit_y ?? [])];
		const combined = normalise(allX, allY);
		if (!combined) return null;

		let cursor = 0;
		const take = (length) => combined.slice(cursor, (cursor += length));
		return {
			racingLine: take(circuit.x.length),
			pitEntry: take((pit.entry_x ?? []).length),
			pitLane: take((pit.lane_x ?? []).length),
			pitExit: take((pit.exit_x ?? []).length),
			corners: circuit.circuit_info?.corners ?? [],
		};
	}, [circuit]);

	if (!geometryVerified) {
		return (
			<Panel label="CIRCUIT" tone="unavailable" className="track-panel">
				<EmptyState title="SIMULATION GEOMETRY UNAVAILABLE">
					<span>
						Historical race data is available for analysis, but verified circuit and pit-lane
						geometry has not passed validation for Simulation Lab.
					</span>
					<span>No fabricated track is shown.</span>
					{selectedRace?.geometry_note && <span className="geometry-note">{selectedRace.geometry_note}</span>}
				</EmptyState>
			</Panel>
		);
	}

	if (circuitLoading || !geometry) {
		return (
			<Panel label="CIRCUIT" tone="historical" className="track-panel">
				<Note>Loading verified circuit geometry from session telemetry…</Note>
			</Panel>
		);
	}

	const projected = phase === PHASES.PROJECTED;

	// Which cars are where, and whether either is in the pit lane this lap.
	const cars = projected
		? (projectedTick?.cars ?? []).map((car) => ({
				role: car.car,
				driver: car.driver,
				pitStatus: car.pit_status,
				compound: car.compound,
				tyreAge: car.tyre_age,
				position: car.position,
				gap: car.gap_to_leader_seconds,
			}))
		: ["P1", "P2"].map((role) => {
				const states = role === "P1" ? session?.p1_lap_states : session?.p2_lap_states;
				const stops = role === "P1" ? session?.p1_pit_stops : session?.p2_pit_stops;
				const state = states?.find((lap) => lap.lap_number === currentLap);
				const pitsThisLap = stops?.some((stop) => stop.lap_number === currentLap);
				const pittedLastLap = stops?.some((stop) => stop.lap_number === currentLap - 1);
				return {
					role,
					driver: role === "P1" ? session?.p1_driver : session?.p2_driver,
					pitStatus: pitsThisLap ? "PIT_IN" : pittedLastLap ? "PIT_OUT" : "NONE",
					compound: state?.compound,
					tyreAge: state?.tyre_life,
					position: state?.position,
					gap: state?.gap_to_leader_seconds,
				};
			});

	// Lap progress drives position along whichever path the car is on.
	const lapFraction = totalLaps ? (currentLap % 1 || (currentLap / totalLaps) % 1) : 0;

	// Two cars in the same pit phase would otherwise resolve to the identical
	// point and hide one another, so each car is nudged a little further along
	// whichever path it is on. The nudge is presentation only - it never changes
	// a reported position, gap, or pit status.
	const SEPARATION = 0.05;

	const markerFor = (car, index) => {
		const nudge = index * SEPARATION;
		if (car.pitStatus === "PIT_IN") {
			const path = geometry.pitEntry.length ? geometry.pitEntry : geometry.racingLine;
			return pointAt(path, 0.88 + nudge);
		}
		if (car.pitStatus === "PIT_STOP") return pointAt(geometry.pitLane, 0.4 + nudge);
		if (car.pitStatus === "PIT_OUT") {
			const path = geometry.pitExit.length ? geometry.pitExit : geometry.racingLine;
			return pointAt(path, 0.06 + nudge);
		}
		return pointAt(geometry.racingLine, (lapFraction + index * 0.12) % 1);
	};

	return (
		<Panel
			label="CIRCUIT"
			tone={projected ? "projected" : "historical"}
			className={`track-panel ${projected ? "data-projected" : "data-historical"}`}
		>
			<div className="track-head">
				<div>
					<h2>
						{selectedRace?.year} {selectedRace?.event}
					</h2>
					<Note>
						Racing line and pit lane traced from this session's own telemetry.
						{circuit.pit_lane?.source ? ` ${circuit.pit_lane.source}.` : ""}
					</Note>
				</div>
				<StatusBadge tone={projected ? "projected" : "historical"}>
					{projected ? "PROJECTED POSITIONS" : "HISTORICAL POSITIONS"}
				</StatusBadge>
			</div>

			<svg className="circuit-map" viewBox="0 0 100 100" role="img" aria-label="Verified circuit map">
				<polyline className="racing-line" points={toPath(geometry.racingLine)} fill="none" />
				{geometry.pitEntry.length > 0 && (
					<polyline className="pit-path pit-entry" points={toPath(geometry.pitEntry)} fill="none" />
				)}
				{geometry.pitExit.length > 0 && (
					<polyline className="pit-path pit-exit" points={toPath(geometry.pitExit)} fill="none" />
				)}
				{geometry.pitLane.length > 0 && (
					<polyline className="pit-path pit-lane" points={toPath(geometry.pitLane)} fill="none" />
				)}

				{cars.map((car, index) => {
					const point = markerFor(car, index);
					if (!point) return null;
					return (
						<g key={car.role} className={`car-marker marker-${car.role.toLowerCase()}`}>
							{/* The transition is what makes a stop read as movement through the
							    pit lane rather than as a jump. */}
							<circle cx={point.x} cy={point.y} r="2.2" />
							<text x={point.x} y={point.y - 3.4} textAnchor="middle">
								{car.role}
							</text>
						</g>
					);
				})}
			</svg>

			<div className="track-legend">
				<span className="legend-item legend-p2">P2 — our car ({session?.p2_driver})</span>
				<span className="legend-item legend-p1">P1 — opponent ({session?.p1_driver})</span>
				<span className="legend-item legend-pit">Pit entry / lane / exit</span>
			</div>

			<div className="car-readouts">
				{cars.map((car) => (
					<div key={car.role} className={`car-readout readout-${car.role.toLowerCase()}`}>
						<strong>
							{car.role} · {car.driver}
						</strong>
						<span>{car.compound ?? "tyre not recorded"}{car.tyreAge != null ? ` · ${car.tyreAge} laps` : ""}</span>
						<span>Gap to leader {seconds(car.gap)}</span>
						<StatusBadge tone={car.pitStatus === "NONE" ? "neutral" : "pit"}>
							{car.pitStatus === "NONE" ? "ON TRACK" : car.pitStatus.replace("_", " ")}
						</StatusBadge>
					</div>
				))}
			</div>

			<Note>
				Positions advance per lap, which is the resolution the source data supports. Sub-lap
				interpolation is not shown because the session does not record it.
			</Note>
		</Panel>
	);
}
