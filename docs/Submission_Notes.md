# PitSense Submission Notes

## Section 9 Results

Five completed FastF1 Race sessions were loaded and replayed through 303 real
lap ticks:

| Race | Model pit lap | Actual pit laps | Directional result | Shock evidence | Max re-optimization |
| --- | ---: | --- | --- | --- | ---: |
| 2024 Canada | 18 | 46 | Miss | Yes, 5 events | 0.230s |
| 2023 Netherlands | 15 | 3, 12, 62, 64, 65 | Consistent | Yes, 5 events | 0.203s |
| 2024 Australia | 15 | 17 | Consistent | Yes, 3 events | 0.213s |
| 2024 British Grand Prix | 19 | 28, 39 | Miss | No event | N/A |
| 2024 Azerbaijan | 18 | 16 | Consistent | Yes, 9 events | 0.129s |

Aggregate results:

- Directional agreement: **3/5**, meeting the PRD target.
- Tyre-cliff benchmark: **1/4 detected cliff onsets within +/-2 laps**.
- Wet/intermediate evidence: **5/5**.
- Safety Car/VSC evidence: **4/5**.
- Maximum measured real shock re-optimization: **0.22966s**, within the
  required one-second budget.
- Confidence and explainability contracts: present in the automated backend
  validation suite; **10 tests passed**.

## Tyre-Cliff Root Cause

The current detector uses a per-contiguous-stint median baseline, MAD-derived
threshold, and three consecutive threshold-crossing laps. The diagnostic over
all 15 real stints found:

- 3 stints too short for a curve estimate.
- 8 stints with no threshold crossing.
- 0 early false positives beyond the recorded Canada condition-driven onset.
- 0 late/wrong threshold crossings among the threshold events; the issue is
  primarily non-detection and condition contamination, not a single offset.

Canada is the clearest miss: the model recommended lap 18 while the actual
winner stop was lap 46. The Intermediate stint contains wet-condition pace
changes, and the later Medium stint does not represent a clean isolated tyre
life curve. The Netherlands also contains multiple weather/compound changes.

This is a known scope limitation, not a hidden success. The next improvement
is a condition-aware degradation model that separates wet pace, compound
transitions, and gradual wear before applying a cliff detector.

## Demo Plan

Primary walkthrough: **2024 Azerbaijan**, because it was directionally
consistent, included nine real Safety Car/VSC evidence events, and placed the
recommendation two laps from the actual stop.

Limitation discussion: **2024 Canada**. Show the recommendation/actual-stop
gap and explain that the current model does not yet disentangle wet-condition
pace from tyre degradation.

The machine-readable report is
[`data/validation/section9_real_races.json`](../data/validation/section9_real_races.json),
and the diagnostic artifact is
[`data/validation/tyre_cliff_root_cause.json`](../data/validation/tyre_cliff_root_cause.json).