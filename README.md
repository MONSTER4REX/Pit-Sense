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
- Backend suite: **10 tests passed**

The complete per-race record is in
[`data/validation/section9_real_races.json`](data/validation/section9_real_races.json).

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
