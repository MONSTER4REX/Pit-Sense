# PitSense — Frontend UI Specification

## 1. Two genuinely different products

### Race Analysis

A compact strategist/analysis dashboard.

### Simulation Lab

A dynamic race-control/simulation workspace.

Shared primitives such as buttons, cards, typography and icons are fine. Product-specific layouts and stateful components should remain separate.

---

# 2. Race Analysis UI

## Purpose

Answer:

> **What should the strategist do?**

Suggested hierarchy:

```text
PITSENSE
────────────────────────────────────────────
Race: [2024 Canadian GP ▼]
Lap: 32 / 70

┌──────────────────────────────────────────┐
│ RECOMMENDATION                           │
│ PIT                                      │
│ Confidence: 82%                          │
│ Why: tyre degradation + traffic + pitloss│
└──────────────────────────────────────────┘

┌──────────────────────────────────────────┐
│ WHAT-IF                                  │
│ PIT        STAY OUT        EXTEND        │
└──────────────────────────────────────────┘

┌──────────────────────────────────────────┐
│ FACTORS                                  │
│ ML         ███████                       │
│ Simulation █████                         │
│ History    ████                          │
│ Memory     ████                          │
└──────────────────────────────────────────┘

┌──────────────────────────────────────────┐
│ TIMELINE / RACE CONTEXT                  │
└──────────────────────────────────────────┘
```

The exact styling can differ, but the hierarchy must remain.

Race Analysis must retain:

- race selection;
- recommendation;
- confidence;
- reasoning;
- complete What-If;
- factor breakdown;
- timeline/replay;
- existing analysis functionality.

Do not replace its What-If with the Simulation Lab version.

---

# 3. Simulation Lab UI

Simulation Lab should feel like entering a different application.

Suggested structure:

```text
┌─────────────────────────────────────────────────────────────┐
│ PITSENSE                         SIMULATION LAB              │
│ Race: 2024 Canadian GP          LAP 16 / 70                 │
│ Mode: HISTORICAL                                             │
├─────────────────────────────────────────────────────────────┤
│ RACE SELECTOR                                                │
│ [ 2024 Canadian GP ▼ ]   [ Load / Restart ]                 │
├──────────────────────────────────────┬──────────────────────┤
│                                      │ RACE STATE           │
│              TRACK                   │ OUR CAR — P2         │
│                                      │ OPPONENT — P1        │
│          P1 ●                        │ Gap: ...             │
│                  ● P2                │ Tyre: ...            │
│                                      │ Tyre age: ...        │
│              PIT LANE                 │                      │
├──────────────────────────────────────┼──────────────────────┤
│ TIMELINE                             │ DECISION              │
│ HISTORICAL ─ SHOCK ─ PROJECTED       │ PIT                  │
│                                      │ STAY OUT             │
│                                      │ EXTEND               │
├──────────────────────────────────────┴──────────────────────┤
│ WHAT-IF COMPARISON                                          │
├─────────────────────────────────────────────────────────────┤
│ REASONING / CURRENT RECOMMENDATION                          │
└─────────────────────────────────────────────────────────────┘
```

This is a structural specification, not permission to draw the example track.

---

# 4. Simulation header

Always show:

- race;
- current lap/total laps;
- simulation mode.

Before the fork:

```text
2024 Canadian Grand Prix
Lap 16 / 70
HISTORICAL
```

After the fork:

```text
Lap 21 / 70
PROJECTED COUNTERFACTUAL
```

The mode distinction must be visually obvious.

---

# 5. Race selector

Simulation Lab must allow selection of supported historical races.

Availability comes from backend/project metadata.

Distinguish:

```text
Historical data available
```

from:

```text
Verified simulation geometry available
```

A race can be usable in Race Analysis while disabled in geometry-backed Simulation Lab.

Example:

```text
2024 Australia
Race Analysis: available
Simulation geometry: unavailable
```

Never create fake geometry just to enable the option.

---

# 6. Main track area

The track should be the largest visual element of Simulation Lab.

It must be:

- race-specific;
- recognizable;
- based on verified geometry;
- able to display both cars;
- able to display pit entry;
- able to display pit lane;
- able to display pit exit.

Do not squeeze it into a tiny card.

---

# 7. Historical state

Before shock:

```text
MODE: HISTORICAL
```

Show P1/P2 following historical state.

Useful information:

- position/progress;
- gap;
- lap;
- tyre;
- pit state.

Do not create fake animation.

---

# 8. Shock visualization

Show a visible timeline event:

```text
HISTORICAL ───────── ● SHOCK ───────── PROJECTED
                    LAP 16
```

Include:

- shock type;
- lap;
- current effect/state;
- available decisions.

---

# 9. Decision panel

Example:

```text
PITSENSE RECOMMENDATION

PIT
Target Lap 20

Confidence
82%

Why:
Current tyre degradation, pit loss,
traffic and opponent state favour a stop.
```

Then:

```text
YOUR DECISION

[ PIT ]
[ STAY OUT ]
[ EXTEND ]
```

All values come from backend.

---

# 10. What-If

Before committing:

```text
WHAT-IF

PIT
Projected delta: +X.Xs

STAY OUT
Projected delta: +X.Xs

EXTEND
Projected delta: +X.Xs
```

These are projections, not historical facts.

---

# 11. Head-to-head

Show:

```text
OUR CAR
P2 — Historical

vs

OPPONENT
P1 — Historical
```

During projection:

```text
OUR CAR
P2
Strategy: PIT
Tyre: Hard
Gap: ...

OPPONENT
P1
Strategy: ...
Tyre: ...
Gap: ...
```

Use backend state only.

---

# 12. Pit animation

A pit decision should visibly follow:

```text
TRACK
  ↓
PIT ENTRY
  ↓
PIT LANE
  ↓
PIT STOP
  ↓
PIT EXIT
  ↓
TRACK
```

Both cars must be able to use the pit lane where the validated geometry/model supports it.

Do not teleport markers.

---

# 13. Historical vs projected styling

Clearly distinguish:

```text
HISTORICAL
```

from:

```text
PROJECTED COUNTERFACTUAL
```

The projected section must not look like official recorded timing.

---

# 14. Re-optimization

When the engine recalculates:

```text
RE-OPTIMIZED
Lap 21

Previous decision:
STAY OUT

New recommendation:
PIT

Reason:
Current simulated state now favours a stop.
```

This must clearly be a new backend recommendation.

---

# 15. Decision history

Show:

```text
DECISION HISTORY

Lap 16
Shock: Safety Car

Lap 16
User: STAY OUT

Lap 21
PitSense: PIT

Lap 21
User: PIT
```

This makes the branch understandable.

---

# 16. Timeline

Show the complete simulation story:

```text
LAP 1 ───────── LAP 16 ───────── LAP 20 ───────── LAP 21 ─── FINISH
                │                 │
              SHOCK             REVIEW
                │
             FORK POINT
```

Separate:

- historical portion;
- shock;
- projected portion;
- re-optimization events;
- pit events;
- finish.

---

# 17. Final result

Show:

```text
COUNTERFACTUAL RESULT

Historical finish
P2

PitSense projected finish
P1

Projected advantage
+X.Xs
```

Then show strategy decisions and model assumptions.

Always label it a **Projected Counterfactual**.

---

# 18. Geometry unavailable state

If verified geometry is unavailable:

```text
SIMULATION GEOMETRY UNAVAILABLE

Historical race data is available for analysis,
but verified circuit/pit-lane geometry has not passed
validation for Simulation Lab.

No fabricated track is shown.
```

A truthful empty state is better than a fake track.

---

# 19. Component architecture

Prefer:

```text
App
├── RaceAnalysisPage
│   ├── RaceAnalysisHeader
│   ├── RecommendationPanel
│   ├── AnalysisWhatIf
│   ├── FactorBreakdown
│   └── AnalysisTimeline
│
└── SimulationLabPage
    ├── SimulationHeader
    ├── SimulationRaceSelector
    ├── SimulationTrack
    ├── SimulationRaceState
    ├── SimulationDecisionPanel
    ├── SimulationWhatIf
    ├── SimulationTimeline
    ├── DecisionHistory
    └── SimulationSummary
```

Shared primitives are fine. Product-specific stateful components should not be shared merely because they look similar.

---

# 20. State ownership

Backend owns:

- simulation lap;
- historical/projected mode;
- car positions;
- gaps;
- tyres;
- pit state;
- shock state;
- recommendations;
- confidence;
- re-optimization;
- decision history;
- final result.

Frontend owns presentation and local UI state.

Do not calculate authoritative race outcomes in React.

---

# 21. Things the UI must never do

Never:

- hardcode Lap 25 or Lap 32;
- hardcode Azerbaijan or another race;
- hardcode “Critical”;
- use a generic oval;
- invent track coordinates;
- use two dots on a line as the final visualization;
- fabricate pit lanes;
- teleport cars;
- display projected data as historical;
- reuse stale recommendations;
- replace/degrade Race Analysis What-If.

---

# 22. Visual acceptance checklist

## Race Analysis

- [ ] Looks like the analysis product.
- [ ] Race selector works.
- [ ] Recommendation works.
- [ ] Confidence works.
- [ ] Complete What-If remains.
- [ ] Factor breakdown remains.
- [ ] Timeline remains.
- [ ] No Simulation Lab controls leak in.
- [ ] No projected simulation UI leaks in.

## Simulation Lab

- [ ] Clearly looks different from Race Analysis.
- [ ] Race selector works.
- [ ] Historical replay works.
- [ ] Track is race-specific when geometry is verified.
- [ ] Both cars are represented.
- [ ] Both can use the pit lane where supported.
- [ ] Shock is visible.
- [ ] PIT/STAY OUT/EXTEND work.
- [ ] Historical → projected transition is obvious.
- [ ] Cars reflect backend state.
- [ ] Re-optimization is visible.
- [ ] Decision history is visible.
- [ ] Final counterfactual result is visible.
- [ ] Assumptions are visible.

## Definition of done

Compiling is not enough. Passing tests is not enough. A small CSS patch is not enough.

The browser must show two genuinely different products with the intended workflows.

Race Analysis answers:

> **What should we do?**

Simulation Lab answers:

> **What happens if we do it?**
