# Architecture Audit — Gate 1 (PRD §11)

What was real versus assumed in the pre-v2.0 build, and what changed. This is the
"confirm exactly what's real" gate the PRD requires before any other work, and it
is kept as a record rather than deleted once the fixes landed.

## Findings: fabricated or misattributed data

These were the serious ones. Each produced a number that looked measured and was
not, which is the specific failure mode PRD §10 and §14 exist to prevent.

| # | Finding | Evidence | Resolution |
|---|---------|----------|------------|
| 1 | `rival_model/rejoin_traffic.estimate_track_gaps()` generated gaps to cars ahead from modular arithmetic on the lap number (`18.2 + ((lap*3+1) % 7) * 0.7`). Traffic cost was therefore always non-zero and always invented. | Function body; asserted by a test that required `traffic_rejoin_risk > 0` with no gap data supplied. | Deleted. Traffic cost is now computed only from observed gaps; with no gap data it is `0.0` **and flagged unmeasured**, which widens the confidence band. |
| 2 | `replay/fastf1_live.py` loaded a hardcoded **2024 Belgian Grand Prix** session and used NOR/VER data to "enrich" replays of *every other race*. | `fastf1.get_session(2024, 'Belgium', 'R')`, `main_driver='NOR'`, `rival_driver='VER'`. | Module deleted. Rival state now comes from the loaded session's own P1. |
| 3 | Rival cover-stop probability fell back to a hardcoded response-lap list `(16, 17, 18, 19, 21)` in three places. | `reoptimizer.py`, `tick_stream.py`, `session_context.py`. | Removed. Cover-stop probability is computed from the rival's own recorded pit laps *up to the current lap*, or reported unmeasured. |
| 4 | `simulation/engine.projected_tick()` assigned tyre ages by constant (`age_since_fork + 12` for P1, `+ 8` for P2), added `0.2s` per lap to lap times, and closed the gap by `0.25s/lap` capped at `1.5s` — a hand-tuned advantage for our car. | Function body, including a comment describing it as a "documented deterministic approximation". | Replaced by `simulation/projection.py`: a measured forward model (pace offset to the field, fitted degradation, measured pit loss, race time accumulated from real gaps, positions derived from accumulated time). |
| 5 | The opponent's post-fork state was read from `_historical_car(self.p1, ...)` — its real recorded future. This is exactly what PRD §5.F forbids. | `projected_tick()`. | Opponent now runs the named **Measured stint-length baseline** (`engine/baseline.py`), with assumptions surfaced in the UI. |
| 6 | Graph edge degradation cost was the constant `0.18 s/lap`. | `graph_builder.py`. | Now the rate fitted by the active tyre model to that car's own stint, or no degradation charge at all with the factor flagged unmeasured. |
| 7 | `PrimaryDecision.jsx` printed a fixed sentence ("The shortest projected race-time path currently favors this action before the rival cover window closes") and a hardcoded "high uncertainty" label regardless of the actual recommendation. | Component body. | The frontend no longer authors explanations. Reasoning is generated in `explainability/reasoning.py` from the factors the engine actually computed. |

## Findings: correctness

| # | Finding | Resolution |
|---|---------|------------|
| 8 | `gap_to_leader_seconds` was never populated — the normalizer looked for a `GapToLeader` column that FastF1 does not provide. Every gap in the product read "not measured", and the counterfactual summary reported a historical margin of `0.00s`. | Gaps are derived from FastF1's real `Time` column: leader time per lap is the field minimum, and each car's gap is its own session time minus that. Verified against 2024 Canada, where it reproduces the actual 3.879s margin. |
| 9 | `confidence/scorer.py` returned `"high"` for both the narrowest and widest bands; `"medium"` was unreachable. | Rewritten. Width is driven by shock conditions *and* by unmeasured factors, with the reasons returned alongside the band. |
| 10 | The strategy graph allowed pitting on consecutive laps, so a high fitted degradation rate produced six-stop "optimal" paths charging 132s of pit loss. | `MIN_LAPS_BETWEEN_STOPS` — a stop is only offered once the current set has run its minimum stint. |
| 11 | Heavy endpoints (`/api/races/available`, session and circuit loads) ran as `async def`, blocking the event loop for ~30s and stalling every other request. The UI hung on "Loading races…". | Declared as `def` so FastAPI dispatches them to its threadpool, and geometry verification is cached to `data/geometry_verification.json` (31s → 55ms). |
| 12 | Projected pit phases were marked one lap late, so a car appeared to jump from track to track with no visible pit sequence. | Pit phases marked on the lap the stop happens; the projection always resolves one lap past the fork so ordering cannot affect it. |

## Findings: product shape (PRD §2.1, §7)

| # | Finding | Resolution |
|---|---------|------------|
| 13 | Both products shared one `SimulationContext` provider and shared stateful components (`WhatIfPanel`, `PrimaryDecision`, `StrategyTimeline`, `ReplayControls`, `AppHeader`). | Split into `analysis/` and `lab/` with one provider each. Only presentational primitives are shared (`shared/primitives.jsx`). |
| 14 | Simulation Lab **silently switched away** from any race without verified geometry, so a user could not see that a race was analysis-only. | The race stays selected and shows the `SIMULATION GEOMETRY UNAVAILABLE` state (PRD §9.6). |
| 15 | Component names did not match the PRD §7 tree. | Renamed to the specified tree. |
| 16 | Three component files were empty (`RaceMap.jsx`, `StrategistConsole.jsx`, `DegradationCountdown.jsx`). | Deleted. |

## Feasibility gates (PRD §2.3, §5.G, §5.K)

Both were checked before any dependent work, as the PRD requires.

**Geometry — PASSED for all five races.** `scripts/geometry_feasibility.py`;
results in `feasibility_geometry.json`. FastF1 exposes positional telemetry
(560–817 samples per lap) and CircuitInfo corners (14–20) for every validated
race. Pit-lane geometry is derived from *real* in-lap and out-lap traces, with the
lane itself located as the longest run under the pit speed limit — so the pit lane
shown is one a car actually drove, not a drawn path.

**Energy / ERS — UNAVAILABLE.** `scripts/energy_feasibility.py`; results in
`feasibility_energy.json`. FastF1 car telemetry for these sessions exposes only
`RPM, Speed, nGear, Throttle, Brake, DRS`. There is no fuel, energy-store, or
ERS-deployment channel. Per PRD §5.K **no energy UI was built** and nothing was
fabricated.
