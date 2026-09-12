# PitSense — Master Implementation Task
## Two-mode product: Race Analysis + Simulation Lab

**Purpose:** canonical implementation specification for the next PitSense build. It combines the backend, frontend, simulation behavior, UI specification, sequencing gates, proof requirements, strict non-goals, and the AI implementation prompt.

## 0. Governing rule

> **Do not build the next phase until the current phase is implemented, directly verified, and proven working.**

No phase may be marked done because the code looks plausible, the page renders, or a unit test passes. The running application and actual data flow must be checked.

The current plans already identify the core defect: replay ticks can move while recommendation, confidence, risk, and What-If remain frozen; the fix is to drive strategy state from the real tick state, preferably with the backend owning the recomputation. fileciteturn1file0L14-L22 The frontend plan likewise requires live state updates and proof through a full replay. fileciteturn1file1L95-L102

---

# 1. PRODUCT STRUCTURE

PitSense has two separate experiences.

## Mode A — Race Analysis

The existing/base product remains first and stable.

Purpose:
- replay a real historical race;
- show the actual race state;
- show PitSense recommendation, confidence, risk, explainability and What-If analysis;
- inspect real historical strategy.

Do not turn this page into the full counterfactual laboratory.

## Mode B — Simulation Lab

A separate route/page/workspace.

Purpose:

> Start from a real historical race, replay real history to a selected fork point, inject a Shock Event, then run an adaptive counterfactual simulation in which P2 uses PitSense and P1 uses a separate adaptive Baseline Strategy.

The Simulation Lab is the main interactive judge/demo experience.

---

# 2. CORE SIMULATION MODEL

## Before the Shock Event

Historical data is ground truth.

At every displayed historical tick, verify:
- lap;
- P1 position/progress;
- P2 position/progress;
- gap;
- tyre compound;
- tyre age;
- pit status/history;
- available event state.

Do not simulate a fictional race before the fork.

## At the Shock Event

Record:
- event type;
- lap;
- user/source = `USER_INJECTED`;
- simulation/session ID.

The historical future stops being the active future from this point onward.

## After the Shock Event

Run two adaptive strategy systems in the same simulated environment:

### P2 — PitSense
Uses the existing PitSense intelligence:
1. tyre condition/degradation;
2. traffic/rejoin risk;
3. rival response;
4. pit-lane loss.

Evaluates:
- PIT NOW;
- STAY OUT;
- EXTEND.

### P1 — Baseline Strategy
A separate, simpler adaptive strategy model.

Use terms such as:
- Baseline Strategy;
- Conventional Strategy Model;
- Baseline Opponent.

Do **not** call it the “official F1 strategist” unless direct, auditable evidence exists. An artificial Shock Event has no real historical team decision to reproduce.

The point is a controlled comparison:

> same race + same shock + same simulated environment + different strategy intelligence.

---

# 3. MOST IMPORTANT BEHAVIOR: ROLLING RE-OPTIMIZATION

Do **not** make one recommendation at the Shock Event and then follow it forever.

The system must repeatedly answer:

> **“Given the current simulated state, what is the best decision from this point forward?”**

Example:

```text
Lap 16
Shock Event
    ↓
PitSense recommends PIT for Lap 20
    ↓
User chooses STAY OUT
    ↓
Simulation advances
    ↓
Lap 20
    ↓
CURRENT STATE HAS CHANGED
    ↓
PitSense re-optimizes
    ↓
New recommendation
    ↓
User can choose again
```

This must be implemented as a rolling/receding-horizon decision process.

## Re-optimization triggers

Recalculate strategy when materially relevant events happen, including:
- Shock Event;
- user PIT/STAY OUT/EXTEND decision;
- planned decision/target lap reached;
- P1 or P2 pits;
- opponent strategy changes materially;
- tyre condition changes materially;
- traffic/rejoin state changes materially;
- significant gap change;
- another material race event.

Do not visually spam a new recommendation for trivial noise. Continuous ticks update continuous state; strategic recommendations update at meaningful checkpoints.

---

# 4. PIT / STAY OUT / EXTEND SEMANTICS

## PIT NOW

P2 enters the modeled pit lane at the next valid simulation opportunity.

## STAY OUT

P2 remains on the current stint and continues until another strategic checkpoint/material event causes reconsideration.

## EXTEND

P2 intentionally extends the stint by a small selectable amount such as +1 / +2 / +3 laps.

An EXTEND decision is an intention, not an unbreakable command. A new major event can override it and trigger re-optimization.

Every user decision must become actual backend simulation state. A button may never only change text in the UI.

---

# 5. P1 MUST ALSO ADAPT

This is mandatory.

After the Shock Event, P1 must not simply continue following the historical pit/strategy timeline.

P1 must:
1. read current simulated state;
2. evaluate with Baseline Strategy;
3. choose baseline PIT / STAY OUT / EXTEND;
4. advance through the simulation;
5. reconsider at later material checkpoints.

This prevents the unfair comparison:

```text
P2 adapts
P1 is frozen
```

The intended experiment is:

```text
P2 = PitSense adaptive strategy
P1 = Baseline adaptive strategy
```

---

# 6. HISTORICAL REFERENCE AFTER THE FORK

After the fork, retain the actual historical trajectory only as a reference.

Recommended visual legend:
- **solid** = active PitSense projected path;
- **dashed** = active Baseline projected path;
- **faint/ghost** = actual historical reference.

Never make the historical future look like the active simulated future.

---

# 7. MODE SWITCH / ENTRY UI

The top-level application should expose:

```text
PITSense

[ RACE ANALYSIS ]      [ SIMULATION LAB ]
```

Race Analysis = existing/base experience.

Simulation Lab = dedicated simulation experience.

Do not combine both complete interfaces into one overloaded dashboard.

---

# 8. SIMULATION LAB — SETUP PAGE

The user should configure the simulation before starting it.

## 8.1 Race selector

Load from real backend-supported races. At minimum, use the validated/cache-backed races when actually available:
- 2024 Canada;
- 2023 Netherlands;
- 2024 Australia;
- 2024 British GP;
- 2024 Azerbaijan.

Selecting a race must change the underlying data, not merely the header text. The existing backend plan explicitly requires different race payloads to differ in lap counts, tyre strategies, pit laps, etc. fileciteturn1file0L24-L31

## 8.2 Race preview

Show actual available:
- race name;
- circuit;
- date/season;
- total laps;
- P1 finisher;
- P2 finisher;
- tyre stints;
- pit history.

## 8.3 Track preview

Use actual verified circuit geometry/assets if available.

If exact geometry is not available, use a clearly labeled stylized representation based on the selected circuit.

Never invent a precise-looking map and imply it is exact.

## 8.4 Car roles

For Simulation Lab:
- **OUR CAR = actual historical P2 finisher**;
- **OPPONENT = actual historical P1 finisher**.

This gives the simulation the intended “can P2 change the result?” story.

## 8.5 Fork lap

Allow:
- Lap 1;
- manual fork-lap selection;
- optionally a real-evidence-based “strategic moment” shortcut.

## 8.6 Shock event

Provide:
- Safety Car;
- VSC;
- Rain;
- Custom event only if actually supported by the simulation model.

---

# 9. SIMULATION LAB — MAIN UI

Recommended information hierarchy:

1. Where are we?
2. What is happening?
3. What does PitSense recommend?
4. What does Baseline recommend?
5. What can the strategist choose?
6. What happened because of the choice?
7. How do the strategies compare?

Suggested layout:

```text
┌────────────────────────────────────────────────────────────────────────────┐
│ PITSENSE SIMULATION LAB       2024 Azerbaijan GP      LAP 16 / 51          │
│ [HISTORICAL REPLAY]          1x 2x 5x                 [PAUSE] [RESET]     │
├────────────────────────────────────────────────────────────────────────────┤
│ OUR CAR — P2 / PITSense          OPPONENT — P1 / BASELINE                │
│ Driver / Team                    Driver / Team                            │
│ Position / Tyre / Age            Position / Tyre / Age                    │
│ Gap / Status                     Gap / Status                             │
├────────────────────────────────────────────────────────────────────────────┤
│                                                                            │
│                              TRACK MAP                                     │
│                                                                            │
│                real selected circuit + pit-lane branch                    │
│                                                                            │
│                         P1 ●                                               │
│                                                                            │
│                 ======== PIT LANE ========                                 │
│                                                                            │
│                     P2 ●                                                   │
│                                                                            │
│      numeric gap | closing/opening | pit status | sector                 │
├──────────────────────────────────────┬─────────────────────────────────────┤
│ PITSense DECISION                    │ BASELINE DECISION                  │
│ PIT NOW                              │ STAY OUT                            │
│ Confidence 82–89%                    │ baseline rationale                 │
│ Tyre: HIGH                           │ next review                         │
│ Traffic: LOW                         │                                     │
│ Rival: HIGH                          │                                     │
│                                      │                                     │
│ [PIT] [STAY OUT] [EXTEND]            │                                     │
├──────────────────────────────────────┴─────────────────────────────────────┤
│ WHY? | DECISION IMPACT | HEAD-TO-HEAD                                    │
├────────────────────────────────────────────────────────────────────────────┤
│ STRATEGY TIMELINE / EVENT LOG / HISTORICAL vs PROJECTED                   │
└────────────────────────────────────────────────────────────────────────────┘
```

The exact visual styling may change, but the hierarchy must remain.

---

# 10. STATUS / MODE INDICATOR

Before fork:

`● HISTORICAL REPLAY — REAL RECORDED DATA`

At fork:

`⚡ DECISION FORK — SHOCK EVENT`

After fork:

`◉ COUNTERFACTUAL SIMULATION — PROJECTED`

This status must be persistent and unmistakable.

---

# 11. TRACK MAP REQUIREMENTS

The map is a data visualization, not decoration.

It must show:
- selected race circuit;
- main racing line;
- pit-lane branch;
- P1 marker;
- P2 marker;
- numeric gap;
- gap direction/trend;
- position;
- pit status;
- historical/projected state.

Before the Shock:
- car progress follows real historical data.

After the Shock:
- car progress follows simulated state.

When either car pits:

```text
RACING LINE
    ↓
PIT ENTRY
    ↓
PIT LANE
    ↓
PIT STOP
    ↓
PIT EXIT
    ↓
RACING LINE
```

Both cars must be independently capable of this.

If the source only supports lap-level pit timing, do not fabricate sub-lap timestamps; the existing plan explicitly requires an honest approximation instead. fileciteturn1file0L43-L48

---

# 12. CAR STATUS CARDS

For P2:
- real driver/team;
- P2 historical result;
- current position;
- current tyre/age;
- gap;
- pit status;
- strategy source = PitSense.

For P1:
- real driver/team;
- P1 historical result;
- current position;
- current tyre/age;
- gap;
- pit status;
- strategy source = Baseline.

---

# 13. PITSense DECISION PANEL

Show:
- recommendation;
- confidence band;
- risk tier;
- four factor bars;
- one-line reasoning;
- expected strategic effect if available;
- “calculated at Lap X” / freshness.

Example one-line explanation:

`Stay-out loss: X.XXs vs Pit loss: Y.YYs. Undercut gain: Z.ZZs.`

Only display values that actually came from the backend/model.

---

# 14. BASELINE DECISION PANEL

Show:
- current baseline decision;
- simplified reason;
- next review/checkpoint;
- current simulated P1 state.

Do not expose PitSense-only information as if it were part of the baseline.

---

# 15. HUMAN DECISION PANEL

When a new PitSense strategic decision is ready:

```text
┌────────────────────────────────────────────────┐
│ STRATEGIC DECISION — LAP 20                   │
│                                                │
│ PitSense recommends: PIT NOW                   │
│ Confidence: 78–84%                             │
│                                                │
│ [ PIT NOW ] [ STAY OUT ] [ EXTEND ]            │
└────────────────────────────────────────────────┘
```

The simulation should pause or clearly enter a decision state if required for the demo.

---

# 16. DECISION IMPACT PANEL

After a pit/strategic action, show real or projected numbers from backend state:
- gap before;
- action taken;
- pit-loss if supported;
- rejoin position;
- gap after;
- later projected effect.

Never produce the result from hardcoded UI values.

---

# 17. HEAD-TO-HEAD PANEL

Constantly compare:

| Metric | P2 / PitSense | P1 / Baseline |
|---|---|---|
| Position | current | current |
| Tyre | current | current |
| Tyre age | current | current |
| Strategy | current | current |
| Gap | current | current |
| Pit status | current | current |
| Projected finish | current | current |

All values must come from current simulation state.

---

# 18. STRATEGY TIMELINE / EVENT LOG

Record:
- race load;
- historical start;
- shock injection;
- PitSense recalculation;
- baseline recalculation;
- user choice;
- pit entry;
- pit stop;
- pit exit;
- recommendation changes;
- strategy changes;
- projected overtake;
- final result.

Every event should have a source classification:
- HISTORICAL;
- USER_INJECTED;
- PITSense;
- BASELINE;
- PROJECTED.

---

# 19. FINAL RESULT UI

Show:

```text
SIMULATION RESULT

Historical result:
P2

PitSense counterfactual:
Projected P1

Projected advantage:
+X.XXs

Projected overtake:
Lap XX

Key decision:
Lap XX — PitSense recommendation followed/rejected
```

Always include:

`Counterfactual projection — not an actual historical result.`

---

# 20. BACKEND ARCHITECTURE

Conceptual flow:

```text
Historical Data Loader
        ↓
Historical Race State
        ↓
Simulation Orchestrator
   ├── Historical Reference
   ├── P1 Baseline Engine
   ├── P2 PitSense Engine
   ├── Pit Event Model
   ├── Track Progress Model
   ├── User Decision / Branch State
   └── Counterfactual State
        ↓
Simulation Tick Stream
        ↓
WebSocket
        ↓
Simulation Lab UI
```

The frontend should render authoritative simulation state; it should not independently invent or reconstruct race state.

---

# 21. BACKEND ORDER OF WORK

## B0 — Protect the existing system

Verify Mode A works before Simulation Lab changes.

**Gate:** base Race Analysis still runs correctly.

## B1 — Fix real tick-driven state

The current plan requires the backend to expose fresh recommendations based on each tick's actual current inputs, preferably computed server-side and included in the WebSocket payload. fileciteturn1file0L18-L22

**Gate:** sample multiple laps and prove recommendation/confidence/risk genuinely differ because the underlying state differs.

## B2 — Race selection

Implement/verify:

`GET /api/races/available`

and a selected-race session loader.

**Gate:** two different races must return demonstrably different data, not different labels. fileciteturn1file0L24-L31

## B3 — P2/P1 identity

For Simulation Lab:
- P2 = OUR CAR;
- P1 = OPPONENT.

Expose real driver/team/result/history.

**Gate:** verify against real session results for at least two races.

## B4 — Track progress + pit state

Provide normalized progress and pit state for both cars.

Must support, where data allows:
- racing;
- pit entry;
- pit lane;
- pit stop;
- pit exit;
- rejoin.

**Gate:** prove one real historical pit sequence end-to-end.

## B5 — PitSense current-state decision API

PitSense must accept current simulated state, not a fixed initial payload.

Output:
- recommendation;
- confidence;
- risk;
- four-factor breakdown;
- reasoning;
- expected effect when supported.

**Gate:** same state → same result; materially different state → result may change and must be explainable.

## B6 — Baseline Strategy engine

Build a separate adaptive baseline strategy service.

Do not call it official F1 strategy.

**Gate:** after a Shock Event, prove P1 can change its strategy based on its current state.

## B7 — Simulation Orchestrator

Own:
- session ID;
- selected race;
- current mode;
- current lap;
- P1 state;
- P2 state;
- shock events;
- user decisions;
- decision epochs;
- historical reference;
- projected state.

**Gate:** create, advance, pause/review, resume, and reset a simulation deterministically.

## B8 — Rolling re-optimization

Mandatory scenario:
1. shock at Lap 16;
2. PitSense says PIT;
3. user chooses STAY OUT;
4. simulation reaches Lap 20;
5. system re-optimizes from the NEW state;
6. recommendation is refreshed;
7. user can choose again.

**Gate:** recorded proof of the scenario above.

## B9 — Simulation WebSocket

Stream authoritative state:
- lap;
- historical/projected mode;
- P1 progress;
- P2 progress;
- gap;
- tyres;
- pit status;
- current strategies;
- latest strategic event;
- current recommendation when applicable.

**Gate:** UI can render the full race state without inventing state locally.

## B10 — Counterfactual result

Return:
- historical finish;
- projected P2 finish;
- projected P1 finish;
- projected time/gap delta;
- decision history;
- projection caveat.

**Gate:** final report is internally consistent with the event/decision history.

---

# 22. FRONTEND ORDER OF WORK

## F0 — Preserve Mode A

Verify Race Analysis.

**Gate:** PASS before building Simulation Lab.

## F1 — Add mode switch

Add Race Analysis / Simulation Lab.

**Gate:** both routes work.

## F2 — Build Simulation Setup

Race selector, race preview, track preview, P1/P2 identities, fork lap, Shock Event selection.

**Gate:** race switching changes real data everywhere.

## F3 — Historical simulation view

Render real P1/P2 positions and data until the fork.

**Gate:** UI values match sampled backend/raw historical values.

## F4 — Pit-lane track behavior

Add circuit + pit lane + real state-driven movement.

**Gate:** prove a real historical pit sequence.

## F5 — PitSense + Baseline strategy panels

**Gate:** each panel is driven by live state.

## F6 — Human decision controls

PIT / STAY OUT / EXTEND.

**Gate:** click changes backend simulation state.

## F7 — Historical → Fork → Counterfactual visual transition

**Gate:** mode changes only when the actual Shock/Fork occurs.

## F8 — Rolling re-optimization UX

Show “Re-optimized at Lap X” and present a fresh decision.

**Gate:** mandatory Lap-16 → Lap-20 scenario passes.

## F9 — Head-to-Head

PitSense P2 vs Baseline P1.

**Gate:** both update independently.

## F10 — Decision impact

Before/after gap and projected effect.

**Gate:** backend values only.

## F11 — Historical ghost / projected path distinction

**Gate:** user can visually tell historical vs projected.

## F12 — Final result

**Gate:** projection disclaimer present and result traceable to simulation history.

## F13 — Visual polish

Only after all functional gates pass.

---

# 23. STRICT DO-NOT LIST

## Data

Never:
- hardcode Azerbaijan as the only race;
- hardcode Lap 25/Lap 32/etc.;
- use synthetic sine-wave race state in the real simulation path;
- fabricate tyres, positions, gaps, pit timing, energy, or results;
- silently interpolate missing critical data;
- pretend projected data is historical.

## Simulation

Never:
- freeze P1 after the Shock Event;
- freeze P2 on the first recommendation;
- compare adaptive P2 to frozen historical P1 as the headline experiment;
- make user decisions cosmetic;
- move cars independently of authoritative simulation state;
- fake an overtake;
- make the historical future the active future after the fork.

## Strategy

Never:
- claim the baseline is the official decision of an F1 team without direct evidence;
- reproduce proprietary F1 team reasoning as if known;
- invent numerical intelligence weights without evidence/calibration;
- show fabricated confidence;
- expose PitSense-only reasoning as baseline reasoning.

## UI

Never:
- build a “live” screen whose main panels remain frozen;
- let separate frontend components maintain conflicting race-state copies;
- calculate authoritative positions/gaps in React;
- create decorative indicators that look data-driven but are not;
- hide stale recommendations;
- mix historical and projected trajectories without labels;
- overload Race Analysis with every Simulation Lab feature.

## Process

Never:
- implement multiple phases at once;
- build frontend against unverified backend endpoints;
- mark done without proof;
- rely only on unit tests;
- accept “looks right” as evidence;
- patch symptoms in the UI when the real problem is stale backend state.

---

# 24. VERIFICATION GATES

For every completed phase, save evidence of:

### Backend
- endpoint/request;
- actual response/state;
- tests;
- data source checked;
- state transition proof.

### Frontend
- screenshot/screen recording;
- real race selection;
- lap progression;
- position/gap progression;
- pit-lane movement;
- strategy changes;
- user decision effect;
- fork mode transition.

### End-to-end

Mandatory proof flow:

1. Select a real race.
2. Confirm P1/P2 identities.
3. Start historical replay.
4. Verify sampled lap/position/gap against real data.
5. Inject Shock Event.
6. Confirm both strategy systems recalculate.
7. Observe PitSense recommendation.
8. Choose a different user action if desired.
9. Advance to the decision lap.
10. Confirm re-optimization from the current state.
11. Make a second decision.
12. Continue simulation.
13. Verify both cars move on the selected circuit.
14. Verify pit lane behavior when a car pits.
15. Verify gap/position changes.
16. Complete simulation.
17. Compare actual historical result vs projected result.
18. Verify counterfactual disclaimer.

---

# 25. PERFORMANCE RULE

Maintain the existing project requirement that Shock Event re-optimization must stay within the documented 1-second target.

Measure actual:
- Shock Event processing;
- strategy calculation;
- simulation state update;
- total visible refresh.

If every raw replay tick is too expensive for full strategy recomputation, separate:
- continuous state updates;
- strategic recomputation checkpoints.

Document and prove the chosen strategy. Never silently reduce recalculation frequency.

---

# 26. DATA PROVENANCE

Every important state/output must have a source classification.

Examples:

`HISTORICAL` — real recorded race data.

`USER_INJECTED` — event added by the user.

`PITSense` — PitSense model output.

`BASELINE` — baseline strategy output.

`USER_DECISION` — user selected PIT/STAY OUT/EXTEND.

`PROJECTED` — counterfactual simulation output.

Do not mix these classifications silently.

---

# 27. MANDATORY DEMO SCENARIO

The main demonstration should use this pattern:

```text
1. Open Race Analysis.
2. Open Simulation Lab.
3. Select a real historical race.
4. Confirm P2 = our car and P1 = opponent.
5. Select a fork lap, e.g. Lap 16.
6. Replay historical data to that lap.
7. Verify real positions/gap.
8. Inject a Safety Car/VSC/Rain shock.
9. Show PitSense recommendation.
10. Show Baseline recommendation for P1.
11. Review What-If options.
12. Choose PIT / STAY OUT / EXTEND for P2.
13. Continue the simulation.
14. Re-optimize when the planned decision/checkpoint is reached.
15. Allow a second human decision.
16. Continue adaptive simulation for both cars.
17. Show pit-lane entry/stop/exit when applicable.
18. Show gap and positions change.
19. Finish the simulation.
20. Show historical result vs projected counterfactual result.
```

Illustrative values are examples only. Never hardcode the values from the example into the product.

---

# 28. AI IMPLEMENTATION AGENT PROMPT

Use this prompt when giving the specification to an AI coding agent:

> **You are implementing PitSense according to the attached Master Implementation Task. Treat that document as the source of truth. Do not improvise product behavior.**
>
> **1. Inspect before changing.** Read the existing repository, current routes, backend state models, WebSocket implementation, race ingestion path, strategy engine, frontend state management, and tests before making changes. Identify the actual current state flow.
>
> **2. Never guess.** If a field, API, FastF1 value, track coordinate, pit timestamp, or existing behavior is uncertain, inspect the real source/code/data first. Never fabricate a value merely to make the UI render.
>
> **3. Work in gates.** Implement exactly one phase at a time. After the phase is implemented, run tests, run the app, exercise the actual behavior, inspect network/backend state, and record proof. Do not start the next phase until the current phase is PASS.
>
> **4. Backend before dependent frontend.** If a UI feature requires state the backend does not yet expose, STOP frontend work, define/implement the backend state contract, verify it, then continue.
>
> **5. Historical ground truth before the Shock.** Until the selected fork event, use real historical race data for lap, positions, gaps, tyres, and pit events. Do not replace real data with generated/synthetic values.
>
> **6. After the Shock, run two adaptive strategies.** P2 is the PitSense car. P1 is the Baseline Strategy car. P1 must not stay frozen on historical strategy after the fork.
>
> **7. Human decisions are real simulation state.** PIT, STAY OUT, and EXTEND must affect the backend simulation path. Never implement them as frontend-only labels.
>
> **8. Rolling optimization is mandatory.** Never reuse the Shock Event recommendation indefinitely. Re-optimize from the CURRENT state at material decision points. If the user rejects PIT at Lap 16 and reaches Lap 20 still on track, run a NEW optimization using the Lap-20 state.
>
> **9. Keep authoritative state in the backend.** React displays simulation state; it does not invent positions, gaps, tyre ages, pit state, or projected outcomes.
>
> **10. Track map follows state.** Cars move because backend track progress changes. Pit-lane entry/stop/exit follows backend pit state. Do not animate a car into a pit simply because a button was clicked unless the simulation state confirms the pit transition.
>
> **11. Historical vs projected must be obvious.** Before fork = HISTORICAL. At fork = DECISION FORK. After fork = COUNTERFACTUAL/PROJECTED. The historical future is reference only.
>
> **12. Never claim baseline = official F1 strategy without evidence.** Use BASELINE STRATEGY or CONVENTIONAL STRATEGY MODEL.
>
> **13. Never fabricate precision.** If FastF1 does not expose sub-lap pit timing, do not invent exact timestamps. Use an explicit approximation and disclose it.
>
> **14. No synthetic placeholders in the real flow.** Temporary mocks may exist only in isolated tests/dev fixtures and must be clearly separated from the production simulation path.
>
> **15. Proof over claims.** For every phase, report exactly what changed, what was executed, what real data was observed, what tests ran, and what remains unresolved.
>
> **16. Stop on contradiction.** If automated tests say PASS but browser/network behavior contradicts them, treat the system as FAIL and investigate the actual state flow.
>
> **17. Do not perform visual polish on top of broken state.** Fix data/state/recomputation first. Only after functional gates pass should layout polish occur.
>
> **18. Final acceptance test.** The implementation is not complete until the mandatory scenario in this document works end-to-end: historical replay → Shock Event → PitSense recommendation + baseline recommendation → human decision → simulation → re-optimization from current state → second decision → adaptive P1/P2 simulation → pit-lane behavior → final projected result with explicit counterfactual labeling.
>
> **At the end of every phase, answer:**
> - What did you actually verify?
> - What exact data/state did you observe?
> - What proof exists?
> - What is still unverified?
>
> **Never answer “working” without evidence.**

---

# 29. DEFINITION OF DONE

Simulation Lab is DONE only when all are true:

- Race Analysis still works.
- Simulation Lab is a separate experience.
- Multiple real races can be selected.
- Race selection changes underlying session data.
- P2 is the actual historical P2 finisher.
- P1 is the actual historical P1 finisher.
- Historical positions/gaps/tyres are correct before the fork.
- Both cars move on the selected circuit.
- Both cars can independently enter/stop/exit the pit lane when their strategy calls for it.
- Shock Events change the state.
- P1 adapts with Baseline Strategy.
- P2 adapts with PitSense.
- PIT/STAY OUT/EXTEND affect the simulation.
- Recommendations are re-optimized from the current state.
- Historical and projected timelines are visually distinct.
- Head-to-Head updates live.
- Decision impact uses backend state.
- Final projected result is internally consistent with event/decision history.
- Counterfactual result is explicitly labeled as projected.
- No hardcoded race/lap/result remains in the real simulation path.
- No fabricated precision or energy data is presented.
- Every major feature has a recorded proof step.

---

# 30. FINAL PRODUCT STORY

The finished product should tell this story:

```text
REAL HISTORICAL RACE
        ↓
REPLAY WHAT ACTUALLY HAPPENED
        ↓
SHOCK EVENT
        ↓
P1 = BASELINE STRATEGY
P2 = PITSense
        ↓
P2 HUMAN DECISION
        ↓
COUNTERFACTUAL SIMULATION
        ↓
CURRENT STATE CHANGES
        ↓
RE-OPTIMIZE
        ↓
HUMAN DECISION AGAIN
        ↓
BOTH STRATEGIES ADAPT
        ↓
RACE FINISH
        ↓
COMPARE HISTORICAL vs PROJECTED RESULT
```

The product is **not** claiming to rewrite the real historical race.

It is demonstrating:

> **Given a real historical race state, a controlled Shock Event, and the same simulated environment, what happens when the historical P2 car uses PitSense while the historical P1 car uses an adaptive baseline strategy?**
