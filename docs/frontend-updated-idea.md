# PitSense — Updated Frontend & UI Plan

## 1. Product experience

The UI should no longer look like a dashboard sitting beside a replay.

It should feel like an actual **race-strategy simulator** where the user can:

1. select a real historical race
2. replay the real race from Lap 1
3. watch the race state update continuously
4. inject a Shock Event
5. see both cars reconsider the situation
6. inspect PitSense's recommendation for P2
7. choose Pit / Stay Out / Extend
8. watch the race fork into a counterfactual simulation
9. compare PitSense against the baseline strategy controlling P1
10. see the projected outcome versus the actual historical outcome

The main visual rule is:

> **Historical = what actually happened. Projected = what the simulation thinks would happen.**

The UI must make that distinction obvious at all times.

## 2. Main race framing

For each selected race:

**Our Car:** actual historical P2 finisher.

**Opponent:** actual historical P1 finisher.

The UI should show their real driver and team names.

Example:

```text
YOUR CAR
[Actual P2 Driver]
[Team]
P2 — HISTORICAL FINISH

OPPONENT
[Actual P1 Driver]
[Team]
P1 — HISTORICAL FINISH
```

After the counterfactual fork, the labels should become:

```text
YOUR CAR — PITSENSE
OPPONENT — BASELINE
```

This communicates the two strategy policies clearly.

## 3. Header

The header must establish the simulation context immediately.

```text
┌────────────────────────────────────────────────────────────────────────────┐
│ PITSENSE   Race: [2024 Azerbaijan GP ▼]   LAP 1 / 51   ● HISTORICAL REPLAY │
│                                  [ 1x ] [ 2x ] [ 5x ]   [ RESET ]           │
└────────────────────────────────────────────────────────────────────────────┘
```

Required controls:

- race selector
- current lap / total laps
- replay state
- speed controls
- reset simulation

The race selector must reload every race-dependent panel, not merely change the text label.

## 4. Mode indicator

A persistent mode badge must show:

### Before fork

`● HISTORICAL`

### After accepted counterfactual decision

`● COUNTERFACTUAL — PROJECTED`

A secondary label can state:

`Historical race data until Lap 25 | Projected from Lap 25`

This prevents the central demo from accidentally presenting a modelled outcome as historical fact.

## 5. Primary recommendation area

The most important content hierarchy should be:

**Recommendation → Confidence → Why → Options → Comparison**

Example:

```text
┌────────────────────────────────────────────────────────────┐
│ PRIMARY DECISION                                           │
│                                                            │
│ PIT NOW                                                    │
│ Target: Lap 25                                             │
│ Confidence: 82–89%                                         │
│                                                            │
│ Stay-out loss: 3.45s vs Pit loss: 22.00s.                │
│ Undercut gain: 4.12s.                                     │
│                                                            │
│ [ ACCEPT PIT ] [ STAY OUT ] [ EXTEND ]                   │
└────────────────────────────────────────────────────────────┘
```

The one-line reasoning statement should be dynamically generated from actual current-state numbers.

## 6. P2 PitSense panel

```text
┌───────────────────────────────┐
│ YOUR CAR — PITSENSE           │
│ P2 historical finisher        │
│                               │
│ Recommendation: PIT NOW       │
│ Confidence: 82–89%            │
│ Risk: OPTIMAL                 │
│                               │
│ Tyre risk      ████████       │
│ Traffic risk   ████           │
│ Rival response ███████        │
│ Pit loss       ███            │
└───────────────────────────────┘
```

This panel updates during replay.

## 7. P1 Baseline panel

Do not use the same visual treatment as PitSense because they are different decision systems.

```text
┌───────────────────────────────┐
│ OPPONENT — BASELINE           │
│ P1 historical finisher        │
│                               │
│ Current decision: STAY OUT    │
│ Model: Baseline Strategy      │
│                               │
│ Basic tyre state: OK          │
│ Pit loss: 22.0s               │
│ Current gap: 1.82s            │
└───────────────────────────────┘
```

The UI should never imply that this is the real proprietary F1 team's actual internal strategy.

Use terminology such as:

`Baseline Strategy`

or

`Conventional Strategy Model`.

## 8. Track visualization — major redesign

Replace the current two dots on a line.

Use a stylized but clearly labelled track visual with:

- main racing line
- pit-lane branch
- P1 marker
- P2 marker
- current position on track
- numeric gap
- gap trend
- pit status
- historical/projected styling

Example:

```text
                         MAIN CIRCUIT
              ┌──────────────────────────────┐
              │                              │
        P1 ●──┘                              └──●

              │     Gap: 1.82s ↓              │
              │                                │
        P2 ●──┐                                │
              │                                │
              └──────────┐   ┌─────────────────┘
                         │ PIT │
                         │ LANE │
                         └──────┘
```

It does not need to reproduce exact circuit geometry unless real circuit geometry becomes a later requirement. It must be explicitly described as a stylized track if it is not geographically accurate.

## 9. Pit-stop animation

When either car pits:

```text
RACING LINE
     ↓
PIT ENTRY
     ↓
PIT LANE
     ↓
STOP / TYRE CHANGE
     ↓
PIT EXIT
     ↓
REJOIN
```

The animation must be driven by backend pit-state events.

Do not animate a fictional sub-lap timeline if the source data does not support that precision.

## 10. Gap visualization

The track panel must show the actual numeric gap.

Example:

```text
Gap to P1: 1.82s ↓
Closing at: 0.14s/lap
```

or:

```text
Gap to P2: 2.31s ↑
Opening at: 0.09s/lap
```

This is more useful than relying on marker spacing alone.

## 11. Shock Event Console

The Shock Event control should be highly visible.

```text
┌──────────────────────────────────────────────────────────────┐
│ SHOCK EVENT                                                  │
│                                                              │
│ [ SAFETY CAR ] [ VSC ] [ RAIN ]                              │
│                                                              │
│ Current lap: 25                                             │
└──────────────────────────────────────────────────────────────┘
```

When clicked:

1. event appears in timeline
2. current historical state is captured
3. both strategy policies recalculate
4. P2 PitSense recommendation updates
5. P1 baseline decision updates
6. UI makes the fork opportunity explicit

## 12. Decision comparison panel

Immediately after a Shock Event:

```text
┌──────────────────────────────────────────────────────────────┐
│ SHOCK EVENT: SAFETY CAR — LAP 25                            │
├──────────────────────────────┬───────────────────────────────┤
│ YOUR CAR — PITSENSE          │ OPPONENT — BASELINE           │
│                              │                               │
│ PIT NOW                      │ STAY OUT                     │
│ Confidence 82–89%            │ Baseline decision            │
│                              │                               │
│ [ ACCEPT ]                   │                              │
└──────────────────────────────┴───────────────────────────────┘
```

This makes the controlled experiment obvious.

## 13. What-If panel

The What-If panel should stop being a static always-Critical widget.

It should show live, state-specific results.

```text
┌──────────────────────────────────────────────────────────────┐
│ WHAT-IF — CURRENT STATE: LAP 25                             │
├────────────────┬──────────────┬─────────────────────────────┤
│ ACTION         │ TIME EFFECT  │ PROJECTED POSITION          │
├────────────────┼──────────────┼─────────────────────────────┤
│ PIT NOW        │ -4.2s        │ P2 → P1 projected          │
│ STAY OUT       │ +2.8s        │ P2                         │
│ EXTEND         │ +1.1s        │ P2                         │
└────────────────┴──────────────┴─────────────────────────────┘
```

The panel should display:

`Computed at Lap 25`

or automatically refresh during playback according to the chosen update cadence.

## 14. Fork moment — centerpiece of the product

When the user accepts a PitSense action, show a clear visual transition.

```text
                 ⚡ DECISION FORK

        Historical race ends here as truth
                      │
                      ▼
             PitSense action accepted
                      │
          ┌───────────┴───────────┐
          ▼                       ▼
     HISTORICAL                PROJECTED
      REFERENCE                COUNTERFACTUAL
```

The timeline, track and cards should visually shift to indicate projection.

## 15. Counterfactual race view

After the fork, the screen should emphasize that two strategy policies are now competing.

```text
┌────────────────────────────────────────────────────────────────┐
│ COUNTERFACTUAL SIMULATION — PROJECTED FROM LAP 25              │
├─────────────────────────────┬──────────────────────────────────┤
│ YOUR CAR — PITSENSE         │ OPPONENT — BASELINE              │
│ P2 → P1 PROJECTED           │ P1 → P1 / P2 PROJECTED           │
│                             │                                  │
│ PIT LAP 25                  │ STAY OUT LAP 25                  │
│                             │                                  │
│ Current gap: 0.84s          │ Current gap: 0.84s               │
└─────────────────────────────┴──────────────────────────────────┘
```

## 16. Historical vs counterfactual timeline

The timeline should explicitly contain two layers.

```text
ACTUAL HISTORY
●────●────●────●────●────●────●
                    ↑
                  FORK

PITSENSE PROJECTION
                    ╲────●────●────●────●

BASELINE PROJECTION
                    ╲────●────●────●────●
```

Use clear legends:

- Solid = historical
- Dashed = projected

Do not depend only on colour; text/line-style differences must also convey the mode.

## 17. Post-decision impact panel

After a pit decision has completed:

```text
┌──────────────────────────────────────────────────────────────┐
│ POST-DECISION IMPACT                                        │
│                                                              │
│ PitSense call: PIT LAP 25                                   │
│ Actual historical call: LAP 46                              │
│                                                              │
│ Gap before: 2.14s                                           │
│ Gap after:  0.76s                                           │
│ Projected gain: +1.38s                                      │
└──────────────────────────────────────────────────────────────┘
```

Make the historical/projection distinction explicit.

## 18. Final result panel

At the projected finish:

```text
┌──────────────────────────────────────────────────────────────┐
│ COUNTERFACTUAL RESULT                                       │
│                                                              │
│ HISTORICAL FINISH                                            │
│ P2                                                           │
│                                                              │
│ PITSENSE PROJECTED FINISH                                    │
│ P1                                                           │
│                                                              │
│ PROJECTED ADVANTAGE                                          │
│ +2.31s                                                       │
│                                                              │
│ ⚠ COUNTERFACTUAL PROJECTION — NOT HISTORICAL RESULT          │
└──────────────────────────────────────────────────────────────┘
```

The final card must include the assumptions/limitations in expandable text.

## 19. Head-to-Head panel

A dedicated comparison should show:

```text
PITSense strategy vs Baseline strategy

Decision count
Pit timing
Total projected time
Projected finish
Projected gap
Overtake lap
Major strategic differences
```

This is the strongest place to answer the judge's question:

> "What did PitSense actually change?"

## 20. Race selector behaviour

Selecting another race must reset:

- race metadata
- P1/P2 identity
- lap count
- tyre state
- track position
- recommendation
- baseline strategy
- timeline
- What-If
- Shock Events
- counterfactual state

It must not preserve stale values from the previous race.

## 21. Starting state

Every simulation starts from Lap 1 unless the user deliberately chooses another labelled start point.

The UI should show:

`Starting from Lap 1 — historical replay`

No hardcoded Lap 25/Lap 32 or tyre age values should remain in the UI state.

## 22. Recommended full layout

```text
┌──────────────────────────────────────────────────────────────────────────────┐
│ PITSENSE | Race ▼ | LAP 1/51 | ● HISTORICAL | 1x 2x 5x | RESET              │
├──────────────────────┬──────────────────────────────┬────────────────────────┤
│ YOUR CAR              │ PRIMARY DECISION             │ OPPONENT                │
│ Actual P2             │ PIT / STAY / EXTEND          │ Actual P1               │
│ PitSense              │ Confidence                   │ Baseline Strategy       │
│ Risk                  │ Why this path                │ Current decision        │
├──────────────────────┴──────────────────────────────┴────────────────────────┤
│                                                                              │
│                    LIVE TRACK / PIT LANE VIEW                               │
│                                                                              │
│       P1 ●───────────────────────────────────────────────                  │
│                   gap 1.82s ↓                                               │
│       P2 ●──────────────┐                                                     │
│                         └── PIT LANE ──┐                                     │
│                                       └────────────────────                   │
│                                                                              │
├───────────────────────────────────────┬──────────────────────────────────────┤
│ TYRE DEGRADATION                      │ WHAT-IF / DECISION COMPARISON        │
│ Statistical vs regression model       │ PIT NOW / STAY OUT / EXTEND          │
├───────────────────────────────────────┴──────────────────────────────────────┤
│ POST-DECISION IMPACT / COUNTERFACTUAL FORK                                  │
├──────────────────────────────────────────────────────────────────────────────┤
│ HEAD-TO-HEAD: PITSENSE vs BASELINE                                          │
├──────────────────────────────────────────────────────────────────────────────┤
│ STRATEGY TIMELINE                                                            │
├──────────────────────────────────────────────────────────────────────────────┤
│ SHOCK EVENT CONSOLE                                                          │
├──────────────────────────────────────────────────────────────────────────────┤
│ REPLAY CONTROLS / HISTORICAL ↔ PROJECTED LEGEND                              │
└──────────────────────────────────────────────────────────────────────────────┘
```

## 23. Visual language

The visual language must make strategy state immediately readable.

Recommended semantic labels:

- HISTORICAL
- PROJECTED
- PITSENSE
- BASELINE
- DECISION FORK
- COUNTERFACTUAL
- CONFIDENCE
- RISK

Avoid using red simply because something is a different strategy. Red should represent a meaningful risk state.

Use line style, labels and badges as well as colour so the interface remains understandable without colour dependence.

## 24. Energy sidebar

Keep this optional.

Do not build a fuel/energy panel until backend data inspection proves real 2023–2024 telemetry is available and meaningful.

If unavailable, omit it instead of showing fabricated values.

## 25. Definition of done

A finished frontend must let a judge:

1. select a real historical race
2. see the real P1/P2 identities
3. start from Lap 1
4. watch the replay update continuously
5. see recommendation/confidence/risk change with the current state
6. inject a Shock Event
7. see both P2 PitSense and P1 Baseline reconsider the situation
8. choose Pit / Stay Out / Extend for P2
9. see an explicit decision fork
10. watch a projected race unfold after the fork
11. watch P1 adapt under the baseline policy
12. see the projected positions and gaps update
13. compare historical vs counterfactual outcomes
14. see the final result labelled as a projection

## 26. Non-negotiable honesty rules

Never:

- display a hardcoded race/lap as if it were live
- display a frozen recommendation while the replay is moving
- call the baseline model an official F1 team strategy
- present projected P1 as historical fact
- imply the historical race actually changed
- fabricate precise pit-lane timing
- fabricate energy data
- hide uncertainty in the counterfactual model

The central user story should always be:

> **Real history → Shock Event → two adaptive strategy policies → user accepts PitSense decision → counterfactual projection → compare with actual result.**
