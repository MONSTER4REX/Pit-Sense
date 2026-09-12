# PitSense

PitSense is an explainable pit-strategy decision-support console for historical
F1 race replay. It uses FastF1 session data, a hand-rolled Dijkstra strategy
engine, mandatory factor breakdowns, confidence bands, replay ticks, rival
modelling, and What-If branches.

## Validation Snapshot

Section 9 was run against five real FastF1 Race sessions: 2024 Canada, 2023
Netherlands, 2024 Australia, 2024 British Grand Prix, and 2024 Azerbaijan.

- Directional pit-window agreement: **3/5**
- Tyre-cliff accuracy: **1/4 detected cliffs within +/-2 laps**
- Maximum re-optimization latency after real Safety Car/VSC evidence: **0.230s**
- Real replay ticks processed: **303**
- Backend suite: **15 tests passed**

The complete per-race record is in
[`data/validation/section9_real_races.json`](data/validation/section9_real_races.json).

## Updated Simulation Plan

PitSense is being extended from historical replay into a controlled
counterfactual simulation. Before a fork, both cars follow the observed
FastF1 race data. After a user-injected Shock Event, both cars adapt to the
same changed environment:

- **P2 / PitSense** uses the strategy graph, tyre degradation, pit-lane loss,
  traffic and rival-response signals, confidence, and explainability.
- **P1 / Baseline Strategy** uses a deterministic conventional pit-window
  model. It is an adaptive comparator, not an official F1 strategy model.
- The original race remains available as the **Historical** reference. The
  two adaptive paths are labelled **Counterfactual Projection** and are never
  presented as what actually happened.

### Simulation Flow

1. Select a supported historical race and load the actual P1 and P2 finishers,
  lap states, tyre data, pit events, and recorded race-control messages.
2. Replay the historical race from Lap 1. Every tick identifies its mode as
  `HISTORICAL` or `PROJECTED` and includes car state and backend-owned
  strategy decisions.
3. Inject a Safety Car, VSC, rain, or other supported Shock Event. Both
  policies reconsider the same state and return comparable decisions.
4. Accept or override the PitSense action with `PIT`, `STAY_OUT`, or `EXTEND`.
  This creates a recorded counterfactual fork.
5. Continue the projected race lap by lap while P1 and P2 adapt independently.
  Projected tyre age, lap time, position, gap, pit status, and decisions remain
  explicitly distinguishable from historical values.
6. Compare the historical finish with the PitSense and Baseline projected
  outcomes, including assumptions and limitations.

### Simulation API

The backend exposes the current simulation boundaries through:

- `GET /api/races/available`
- `GET /api/race/{year}/{event}/session`
- `POST /api/simulation/shock`
- `POST /api/simulation/decision`
- `GET /api/simulation/counterfactual`
- `/ws/replay` with simulation tick payloads

The implementation deliberately uses explicit approximations where FastF1
does not provide sub-lap pit-lane timing. It does not fabricate fuel or energy
data, claim that PitSense changed history, or call the comparator an official
team strategist.

### Roadmap

The current backend foundation includes dual policy decisions, historical vs
projected contracts, user-controlled forks, FastF1 P1/P2 loading, and
counterfactual summaries. Remaining work is to connect the full race-selection
and fork workflow to the frontend, improve stateful projected tyre and gap
modelling, expose the three timelines visually, add overtake-lap reporting,
and validate recommendation changes across every supported real race.

## Known Limitations

The tyre-cliff result is a reported limitation, not a suppressed metric. The
current diagnostic uses the median lap time for each contiguous compound stint,
an MAD-based threshold, and requires three consecutive laps above that
threshold. The root-cause diagnostic found:

- Three stints were too short to estimate a degradation curve.
- Eight stints never crossed the hard threshold, including long stints whose
  lap-time changes were gradual or dominated by race conditions.
- Canada produced an early threshold crossing on the wet Intermediate stint
  and a later crossing on the Medium stint, but neither matched the reported
  target onset. Its actual pit call was lap 46 while the model recommended lap
  18.
- The Netherlands and British Grand Prix data contain multiple compound and
	weather transitions; those changes make a single-stint threshold a weak
	proxy for a pure tyre cliff.

This means the current cliff metric is better understood as a conservative
within-stint degradation alarm than as a complete tyre-life model. The next
model improvement should separate wet-condition pace, compound transitions,
and gradual degradation before fitting a cliff detector. The misses remain in
the validation report and are part of the demo discussion.

## Demo Preparation

Use the 2024 Azerbaijan replay for the primary walkthrough: it was directionally
consistent, exercised nine real Safety Car/VSC evidence events, and kept the
recommendation within two laps of the actual pit stop.
Use 2024 Canada as the deliberate limitation case: show the lap-18 versus
lap-46 disagreement and explain why wet-condition compound data is the next
modeling priority.

No PowerPoint file is present in this repository. The same verified numbers and
talking points are captured in
[`docs/Submission_Notes.md`](docs/Submission_Notes.md).
