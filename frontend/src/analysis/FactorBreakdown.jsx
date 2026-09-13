import { Meter, Note, Panel } from "../shared/primitives";
import { percent, seconds } from "../shared/format";
import { useRaceAnalysis } from "./RaceAnalysisProvider";

/*
 * The four real factors, and only those four.
 *
 * PRD 2.2 and section 10 forbid showing an ML / Simulation / History / Memory
 * blend, because those four sources are not implemented. What is implemented is
 * exactly this: tyre delta, rejoin traffic, rival cover-stop probability, and
 * pit-lane loss. A factor the engine could not measure renders as "not measured"
 * rather than as a confident zero.
 *
 * Meter scales below are display ceilings, chosen so a typical value fills a
 * readable part of the bar. They scale the drawing only - every number shown is
 * the backend's own.
 */
const TYRE_METER_CEILING_SECONDS = 60;
const TRAFFIC_METER_CEILING_SECONDS = 10;
const PIT_LOSS_METER_CEILING_SECONDS = 30;

export default function FactorBreakdown() {
	const { recommendation } = useRaceAnalysis();
	const factors = recommendation?.explainability;

	if (!factors) {
		return (
			<Panel label="FACTOR BREAKDOWN" tone="historical">
				<Note>No recommendation is on screen, so there is no breakdown to show.</Note>
			</Panel>
		);
	}

	const measured = factors.measured ?? {};

	return (
		<Panel label="FACTOR BREAKDOWN" title="What drove this call" tone="historical">
			<div className="factor-list">
				<Meter
					label="Tyre delta on the chosen path"
					value={factors.tyre_delta_risk / TYRE_METER_CEILING_SECONDS}
					displayValue={seconds(factors.tyre_delta_risk, 1)}
					tone="tyre"
					unavailable={measured.tyre_degradation === false}
				/>
				<Meter
					label="Rejoin traffic cost"
					value={factors.traffic_rejoin_risk / TRAFFIC_METER_CEILING_SECONDS}
					displayValue={seconds(factors.traffic_rejoin_risk, 1)}
					tone="traffic"
					unavailable={measured.rejoin_traffic === false}
				/>
				<Meter
					label="Rival cover-stop probability"
					value={factors.rival_cover_stop_probability}
					displayValue={percent(factors.rival_cover_stop_probability)}
					tone="rival"
					unavailable={measured.rival_cover_stop === false}
				/>
				<Meter
					label="Pit-lane time loss"
					value={factors.pit_lane_time_loss / PIT_LOSS_METER_CEILING_SECONDS}
					displayValue={seconds(factors.pit_lane_time_loss, 1)}
					tone="pit"
				/>
			</div>

			{factors.notes?.length > 0 && (
				<ul className="factor-notes">
					{factors.notes.map((note) => (
						<li key={note}>{note}</li>
					))}
				</ul>
			)}

			<Note>
				These are the four factors the engine computes. PitSense does not blend separate ML,
				simulation, history, and memory scores, and does not display one.
			</Note>
		</Panel>
	);
}
