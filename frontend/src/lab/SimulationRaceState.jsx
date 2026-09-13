import { Note, Panel, StatusBadge } from "../shared/primitives";
import { actionLabel, seconds } from "../shared/format";
import { PHASES, useSimulationLab } from "./SimulationLabProvider";

/*
 * Head-to-head: our car against the opponent (PRD 9.2, 9.7).
 *
 * In the historical phase both sides show recorded data and nothing else. In the
 * projected phase our car shows the committed strategy and the opponent shows
 * its own post-fork baseline decision - never a copy of what it really did after
 * this lap. The opponent's model is named on its own panel so its projected
 * behaviour is never read as fact.
 */
export default function SimulationRaceState() {
	const { session, currentLap, phase, projectedTick, committedAction, recommendation } =
		useSimulationLab();

	if (!session) return null;
	const projected = phase === PHASES.PROJECTED;

	const historicalState = (role) => {
		const states = role === "P1" ? session.p1_lap_states : session.p2_lap_states;
		return states?.find((lap) => lap.lap_number === currentLap) ?? null;
	};

	const projectedCar = (role) => projectedTick?.cars?.find((car) => car.car === role) ?? null;
	const opponentDecision = projectedTick?.decisions?.find((decision) => decision.car === "P1") ?? null;

	const ourCar = projected ? projectedCar("P2") : historicalState("P2");
	const opponent = projected ? projectedCar("P1") : historicalState("P1");

	return (
		<section className="head-to-head">
			<Panel
				label={projected ? "OUR CAR — PROJECTED" : "OUR CAR — HISTORICAL"}
				tone={projected ? "projected" : "historical"}
				className="car-panel ours"
			>
				<h2>{session.p2_driver}</h2>
				<p className="car-team">{session.p2_team} · started this comparison as the race's real P2</p>
				<StatusBadge tone={projected ? "projected" : "historical"}>
					{projected ? "PITSENSE STRATEGY — PROJECTED" : "RECORDED DATA"}
				</StatusBadge>

				<div className="car-metrics">
					<div>
						<span>Position</span>
						<strong>{ourCar?.position != null ? `P${ourCar.position}` : "not recorded"}</strong>
					</div>
					<div>
						<span>Tyre</span>
						<strong>
							{(projected ? ourCar?.compound : ourCar?.compound) ?? "not recorded"}
							{(projected ? ourCar?.tyre_age : ourCar?.tyre_life) != null
								? ` · ${projected ? ourCar.tyre_age : ourCar.tyre_life} laps`
								: ""}
						</strong>
					</div>
					<div>
						<span>Gap to leader</span>
						<strong>{seconds(ourCar?.gap_to_leader_seconds)}</strong>
					</div>
					{projected && (
						<div>
							<span>Committed strategy</span>
							<strong>{actionLabel(committedAction)}</strong>
						</div>
					)}
				</div>

				{projected && recommendation && (
					<Note>Engine's standing call at this lap: {actionLabel(recommendation.action)}.</Note>
				)}
			</Panel>

			<Panel
				label={projected ? "OPPONENT — PROJECTED" : "OPPONENT — HISTORICAL"}
				tone={projected ? "projected" : "historical"}
				className="car-panel theirs"
			>
				<h2>{session.p1_driver}</h2>
				<p className="car-team">{session.p1_team} · the race's real P1</p>
				<StatusBadge tone={projected ? "projected" : "historical"}>
					{projected ? "BASELINE MODEL — PROJECTED" : "RECORDED DATA"}
				</StatusBadge>

				<div className="car-metrics">
					<div>
						<span>Position</span>
						<strong>{opponent?.position != null ? `P${opponent.position}` : "not recorded"}</strong>
					</div>
					<div>
						<span>Tyre</span>
						<strong>
							{opponent?.compound ?? "not recorded"}
							{(projected ? opponent?.tyre_age : opponent?.tyre_life) != null
								? ` · ${projected ? opponent.tyre_age : opponent.tyre_life} laps`
								: ""}
						</strong>
					</div>
					<div>
						<span>Gap to leader</span>
						<strong>{seconds(opponent?.gap_to_leader_seconds)}</strong>
					</div>
					{projected && opponentDecision && (
						<div>
							<span>Its own call</span>
							<strong>{actionLabel(opponentDecision.action)}</strong>
						</div>
					)}
				</div>

				{/* FR-25: the opponent's assumptions travel with its projected behaviour. */}
				{projected && opponentDecision && (
					<Note tone="model">{opponentDecision.explanation}</Note>
				)}
				{!projected && (
					<Note>Recorded result only. The opponent is not projected before the fork.</Note>
				)}
			</Panel>
		</section>
	);
}
