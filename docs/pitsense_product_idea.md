# PitSense — Product & Simulation Idea

## 1. Product vision

PitSense has two distinct experiences:

- **Race Analysis** — analyze a historical race and answer: “What should the strategist do?”
- **Simulation Lab** — replay a real historical race, inject a strategic shock, make a decision, and branch into a projected counterfactual: “What happens if we actually do it?”

These must remain separate products architecturally and visually.

## 2. Race Analysis

Race Analysis is the base PitSense experience. It should provide:

- historical race selection;
- current race/lap context;
- PitSense recommendation;
- confidence;
- reasoning;
- strategy alternatives;
- What-If analysis;
- factor breakdown;
- timeline/replay.

It is an analysis/decision-support dashboard, not the simulation control room.

## 3. Simulation Lab

Simulation Lab is a dedicated simulation workspace.

The user selects a real historical race and starts from its real recorded state. Before a shock, the simulation follows historical data:

```text
Lap 1 → Lap 2 → ... → Shock
```

Historical lap, gap, tyre, pit and track-progress information should come from the available historical data.

## 4. Shock event

The user can inject a supported event such as:

- Safety Car;
- Rain;
- tyre degradation;
- traffic/track incident.

The shock changes the strategic environment. PitSense and the baseline strategy independently calculate what to do next.

No strategy result may be hardcoded.

## 5. P2 is Our Car

For the counterfactual demonstration, use the real historical P2 as **Our Car** and P1 as the **Opponent**.

This allows a strong, honest comparison:

```text
Historical result: P2
PitSense projected result: P1
```

The result is a counterfactual projection, not a claim that actual history changed.

## 6. Opponent behavior

Before the shock, both cars follow historical state.

After the shock, do not simply replay the historical future as if the shock never happened. The opponent should follow the configured baseline/opponent model under the changed environment. Its assumptions must be explicit.

## 7. User decisions

At a decision point the user can choose:

- PIT;
- STAY OUT;
- EXTEND.

If PIT is selected, the car should transition:

```text
Track → Pit Entry → Pit Lane → Pit Stop → Pit Exit → Track
```

It must not teleport.

STAY OUT and EXTEND keep the car on track with the appropriate simulated tyre/strategy state.

## 8. Counterfactual branch

After the user accepts a strategy following a shock, the state changes from:

**HISTORICAL**

to:

**PROJECTED COUNTERFACTUAL**

Everything after the fork is a model projection. The UI must make this unmistakable.

## 9. Rolling re-optimization

The simulation must not blindly follow the first recommendation forever.

Example:

```text
Shock: Lap 16
Initial recommendation: PIT Lap 20

User chooses: STAY OUT

Simulation reaches a review point:
Lap 20/21

PitSense recalculates using the current simulated state.
```

The fresh recommendation should consider the actual state available to the model, including lap, tyres, gap/traffic, pit loss, shock state, opponent state, historical context and the project's intelligence inputs.

Meaningful re-optimization triggers can include:

- scheduled review;
- P1 pit;
- P2 pit;
- material tyre change;
- material traffic/gap change;
- material shock/state change.

The backend owns this logic.

## 10. Intelligence sources

The conceptual explainable weighting discussed for PitSense is:

- ML: 0.35
- Simulation: 0.25
- History: 0.20
- Memory: 0.20

If the actual implementation uses different weights, the product must display the implemented values rather than pretending these are active.

The principle is transparent combination of multiple approaches into a confidence-weighted recommendation.

## 11. Track visualization

Simulation Lab requires race-specific geometry.

Do not use:

- generic oval/loop tracks;
- random SVG curves;
- arbitrary frontend coordinates;
- a straight line with two dots;
- fabricated pit lanes.

The backend should provide validated circuit/pit geometry when available. The frontend renders that geometry.

If geometry is unavailable or not validated, do not fake it. Disable/pending the geometry-backed simulation for that race or use only an explicitly approved non-geometric representation.

## 12. Historical movement

Before the shock, P1 and P2 should follow their historical track progress, gap and pit events where supported.

The visual message is:

> “This is what actually happened.”

## 13. Projected movement

After the fork:

- Our Car follows the selected strategy/model;
- Opponent follows the configured opponent/baseline model;
- positions and gaps evolve according to the simulation;
- pit decisions produce pit-lane transitions where validated geometry/timing supports them.

## 14. Final result

Show:

```text
Historical result: P2
PitSense projected result: P1
Projected advantage: +X.Xs
```

Also show decisions, decision laps and assumptions.

Never say PitSense “changed the actual race.”

## 15. Backend architecture

Conceptually:

```text
Historical Data
      ↓
Simulation State
      ↓
Historical Replay
      ↓
Shock Event
      ↓
PitSense + Baseline Decisions
      ↓
User Decision
      ↓
Counterfactual Fork
      ↓
Projected Simulation
      ↓
Re-optimization
      ↓
Finish Summary
```

Backend state is authoritative. React renders it and should not invent authoritative laps, tyres, gaps, positions or outcomes.

## 16. Implementation gates

Work in dependency order:

1. Audit current architecture.
2. Separate Race Analysis and Simulation Lab.
3. Verify Race Analysis is intact.
4. Build Simulation Lab shell.
5. Verify historical replay.
6. Validate geometry.
7. Implement shock/decision flow.
8. Implement counterfactual branch.
9. Implement re-optimization.
10. Implement final comparison.
11. Integration/regression testing.

After every gate: run tests, build, run the relevant browser workflow, inspect the actual UI, then continue.

## 17. Integrity rules

Never fabricate data, geometry, lap values, risk tiers, energy/fuel information or counterfactual results.

Never make projected data look historical.

Never hardcode one race as the universal simulation.

Never reuse stale recommendations after simulation state changes.

Never declare success because code compiles.

## 18. Core demonstration

```text
1. Select a real historical race.
2. Start simulation.
3. Watch P1/P2 reproduce historical state.
4. Inject a shock.
5. Compare PitSense vs baseline.
6. Inspect PIT/STAY OUT/EXTEND What-If choices.
7. Choose a strategy.
8. Watch the simulation fork.
9. Watch cars use verified track/pit geometry.
10. Reach a re-optimization point.
11. Get a fresh recommendation.
12. Continue to finish.
13. Compare historical P2 with projected PitSense result.
14. Show projected advantage and assumptions.
```
