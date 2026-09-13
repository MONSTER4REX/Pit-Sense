# PitSense — Submission Notes

Written against PRD v2.0. Every figure below comes from a script in this
repository that can be re-run; nothing here is quoted from memory.

## What ships

Two separate products over one backend engine.

**Race Analysis** — the always-available strategist dashboard. Race selector,
recommendation, confidence band, generated reasoning, complete What-If
(pit / stay out / extend), factor breakdown, and race context with a lap
scrubber. No simulation controls and no projected values appear anywhere on it.

**Simulation Lab** — the counterfactual workspace. Two-tier race selector, a
circuit drawn only from verified telemetry, head-to-head against the opponent,
shock injection, PitSense versus a named baseline, a committed decision that
forks the run into a projected counterfactual, rolling re-optimisation, decision
history, and the final historical-versus-projected result with its full
assumption trail.

## Validation results

`python -m scripts.validation_report` → `docs/validation_report.json`

**Blocking criteria — all pass**

| Criterion | Result |
|---|---|
| Explainability breakdown on 100% of recommendations | PASS |
| Confidence band on 100% of recommendations | PASS |
| Recommendation recomputes per lap (not frozen) | PASS |
| Re-optimisation within the 1s budget | PASS — max measured **0.101s** |
| Two-tier availability metadata correct for all 5 races | PASS |
| Opponent post-fork path driven by a stated baseline model | PASS |

**Reported, not blocking**

| Criterion | Target | Result |
|---|---|---|
| Directional pit-window agreement | ≥3 of 5 | **4 of 5** |
| Tyre-cliff prediction within ±2 laps | reported | **7 of 19** scorable stints |
| Safety car / VSC evidence | reported | 4 of 5 races |
| Wet / intermediate evidence | reported | 5 of 5 races |
| Source data gaps flagged (not interpolated) | reported | 8 |

Both figures improve on the v1.0 record carried in PRD §13.1 (3/5 directional,
1/4 cliff), and the improvement is attributable to a specific modelling change
described below rather than to threshold tuning.

## The tyre-cliff limitation, and what fixed part of it

PRD §13.1 recorded the detector missing most cliffs, with Canada as the clearest
case. Root cause, found during this build: **raw race lap times are dominated by
effects that are not tyre wear.** A car gets faster as fuel burns off and faster
again as the track rubbers in, while the tyre makes it slower. The first two
usually win — at Melbourne, a stint's lap times fall about seven seconds from
start to end. A detector reading raw laps sees a stint getting *quicker* and
correctly reports no degradation.

Fuel burn and track evolution share one property that makes them separable: they
act on **every car on track at the same lap**, while tyre age does not. So wear is
now measured as each car's pace relative to the field's median lap for that lap
number (`app/tyre_model/field_pace.py`). That is what moved cliff detection from
1/4 to 7/19 and directional agreement from 3/5 to 4/5.

It does not fix everything. Canada 2024 still yields no measurable degradation
for our car, and is kept in the validated set as the honest limitation case.

A separate fuel-effect estimator (`app/tyre_model/fuel.py`) was also built, which
solves a driver's own race for shared fuel and degradation slopes. It is retained
as the fallback where the field baseline does not cover a stint, and it reports
honestly that it **fails to identify the effect on most of these races** — their
stint structures do not separate lap number from tyre age. Where it cannot, a
nominal era figure stands in and is labelled an assumption, never a measurement.

## Two-model comparison (PRD §5.J)

`python -m scripts.tyre_model_report` → `docs/tyre_model_comparison.json`

Both models are scored on the same 33 real stints against an independently
derived drop-off lap, on the same normalised lap times the live engine uses.

| Model | Scorable stints | Within ±2 laps | Mean error |
|---|---|---|---|
| `statistical_median_mad` | 19 | 7 (37%) | 2.63 laps |
| `regression_curve_fit` | 3 | 3 (100%) | 1.67 laps |

The statistical detector is selected, on a stated criterion: most correct calls
in absolute terms. This is a coverage-versus-precision trade — the regression
model is more precise but declines to predict on most stints, leaving the engine
with no degradation input at all. Both rows are reported in the UI, and the
selection criterion is printed with them rather than presented as a bare verdict.

## Feasibility gates

**Circuit and pit-lane geometry — available for all five races.** The pit lane is
traced from a real in-lap and out-lap, with the lane located as the longest run
under the pit speed limit. No circuit is drawn from assumption; a race that failed
this check would show the geometry-unavailable state, which is implemented and
reachable.

**Energy / fuel / ERS — not available.** FastF1 exposes only
`RPM, Speed, nGear, Throttle, Brake, DRS` for 2023–2024 race sessions: no fuel,
energy-store, or ERS channel. Per PRD §5.K, **no energy UI was built.**

## Deliberately not built

- **The four-source ML / Simulation / History / Memory blend.** Scoped out in PRD
  §2.2 and genuinely absent: the factor breakdown shows only the four factors the
  engine computes, and says so on screen. Phase 2 direction only.
- **Full-grid simulation.** One tracked car against one modelled rival, per §4.3.
- **Live telemetry.** Historical replay only, and the UI says so in its
  provenance panel.

## Known limitations, stated plainly

1. **Projected margins compound a per-lap pace difference.** Two cars' measured
   pace delta carried across a race distance produces gaps larger than real races
   show, because a sampled delta contains traffic and conditions as well as pace.
   The delta is capped at 0.25s/lap for the projection and **the cap is printed in
   the assumption trail** whenever it binds. The projected *position* is more
   trustworthy than the projected *margin*.
2. **Degradation is unmeasurable on some races**, Canada 2024 most clearly. The
   engine reports the factor as not measured, widens the confidence band, and
   names the gap in its reasoning rather than substituting a plausible rate.
3. **Track position is lap-resolution.** The source data supports discrete per-lap
   positions, so the track shows discrete movement. No sub-lap interpolation is
   invented.
4. **The opponent baseline is a comparator, not a claim** about what the real team
   would have decided. Its assumptions travel with every projection it produces.

## Reproducing everything

```bash
cd backend
python -m pytest -q                      # 31 tests
python -m scripts.geometry_feasibility   # PRD 5.G gate
python -m scripts.energy_feasibility     # PRD 5.K gate
python -m scripts.tyre_model_report      # PRD 5.J comparison
python -m scripts.validation_report      # PRD 13 suite
python -m scripts.end_to_end_proof "Azerbaijan Grand Prix" 2024
```
