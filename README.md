# PitSense

[![tests](https://github.com/MONSTER4REX/Pit-Sense/actions/workflows/tests.yml/badge.svg)](https://github.com/MONSTER4REX/Pit-Sense/actions/workflows/tests.yml)
[![license: MIT](https://img.shields.io/badge/license-MIT-blue.svg)](LICENSE)

**Predictive pit strategy and undercut intelligence.** Two products, one engine:
*Race Analysis* answers "what should we do right now?", *Simulation Lab* answers
"what would have happened if we had done X?"

PitSense models tyre degradation, track position, and rival behaviour as a graph
optimisation, and returns an explainable, confidence-scored recommendation for the
pit window and the undercut decision. It replays completed historical races
through FastF1 — it does not connect to live car telemetry, and the UI says so.

## The two products

**Race Analysis** — the always-available strategist dashboard. Select a race,
scrub to any lap, and see the engine's call for that lap's real state: the
recommendation, its confidence band and what widened it, the reasoning the engine
generated from its own factors, all three What-If branches, and the factor
breakdown. No simulation controls; no projected values.

**Simulation Lab** — the counterfactual workspace. Replay a real race, inject a
shock, compare PitSense against a named baseline strategy, commit a decision, and
watch the run fork from HISTORICAL into PROJECTED COUNTERFACTUAL — where *both*
cars are projected forward by a stated model, including the opponent. Ends with
the historical result against the projected one and the full assumption trail.

## What makes the numbers trustworthy

Every factor is either measured from the loaded session or reported as not
measured. There is no third option, and nothing is quietly defaulted.

- **Tyre degradation** is fitted to the car's own stint by whichever of two models
  won a recorded head-to-head comparison — not a constant.
- **Rejoin traffic** comes from observed gaps to cars ahead. With no gap data the
  cost is zero *and flagged*, which widens the confidence band.
- **Rival cover-stop probability** comes from the rival's own recorded pit stops
  up to the current lap.
- **Pit-lane loss** is measured from each car's real in-lap and out-lap penalty,
  compared against the field on those same laps.
- **Gaps** are derived from real lap timestamps. On 2024 Canada this reproduces
  the actual 3.879s winning margin.
- **The circuit and pit lane** are traced from this session's positional
  telemetry. A race without verified geometry shows an explicit empty state rather
  than a substituted track.

Separating tyre wear from fuel burn and track evolution is the core modelling
problem, and `app/tyre_model/field_pace.py` explains how it is done and where it
still falls short. See [Submission_Notes.md](docs/Submission_Notes.md) for the
honest limitations, including the race where degradation is not measurable at all.

## Tech stack

| Layer | Choice | Why |
|---|---|---|
| Language | Python 3.11+ | FastF1, the only realistic historical F1 data source, is Python-only |
| API | FastAPI | Native async and WebSockets for the tick stream; heavy endpoints run off the event loop |
| Data | FastF1 | Lap times, compounds, pit timestamps, positional telemetry for real sessions |
| Optimisation | NumPy + hand-rolled Dijkstra (heapq) | Edge weights recomputed every tick under a 1s budget; NetworkX was rejected as too slow and too opaque for an explainability-led product |
| Validation | Pydantic v2 | Schema-validates every race-state and recommendation at the boundary, rejecting bad data loudly |
| Testing | pytest + pytest-asyncio | The validation suite runs as real automated tests |
| Frontend | React 18 + Vite | Fast rebuild loop for a two-page operator console |
| Styling | Tailwind CSS + component CSS | Tailwind is in the build; the dense, repeated console furniture is expressed as named component classes so each product's distinct treatment lives in one place |
| State | React Context, one provider per product | `RaceAnalysisProvider` and `SimulationLabProvider` never share state |
| Storage | FastF1 file cache + SQLite | Read-only race data needs no database; SQLite holds the strategy timeline |

## Running it

Requires Python 3.11+ and Node 18+.

```bash
cd backend && pip install -r requirements.txt
python -m uvicorn app.main:app --reload --port 8000
```

```bash
cd frontend && npm install && npm run dev
```

Open http://localhost:5173. The first call to `/api/races/available` verifies
circuit geometry for each race and takes around 30 seconds; the result is cached
to `data/geometry_verification.json`, after which it is instant.

## Deploying it

The app deploys as **one container on one port**: FastAPI serves both the API and
the built frontend, so there is no second service and no CORS to configure.

It carries the five validated races as an exported bundle
(`backend/app/data/races`, ~490 KB, written by `scripts.export_race_bundle`), so
a deployed instance needs **no FastF1 cache, no downloads at request time, and no
dependency on an upstream API staying up during a demo**. That is what keeps the
image at ~350 MB and the first page load instant rather than a 30-second stall.

```bash
docker build -t pitsense .
docker run -p 8000:8000 pitsense     # then open http://localhost:8000
```

**On Render** — the repository contains `render.yaml`, so: New → Blueprint →
point it at this repo → Apply. It builds the Dockerfile and gives you a URL.

**Two constraints any host has to respect:**

1. **One instance, one worker.** Each visitor's loaded race lives in that
   process's memory (`backend/app/session_store.py`), so a second worker would
   serve some visitors an empty slot. `render.yaml` pins `numInstances: 1`.
2. **No persistent disk needed.** The only runtime write is the strategy
   timeline, which goes to `PITSENSE_DB_PATH` (default `/tmp`) and is not
   expected to survive a restart.

Visitors are isolated from each other by a session cookie, so two people on the
same URL can load different races without overwriting one another.

## Verifying the claims

Each script prints its evidence and writes a JSON report under `docs/`.

```bash
cd backend
python -m pytest -q                      # unit and contract tests
python -m scripts.geometry_feasibility   # what geometry FastF1 really exposes
python -m scripts.energy_feasibility     # energy/ERS availability (it is not)
python -m scripts.tyre_model_report      # the two-model comparison
python -m scripts.validation_report      # the historical validation suite
python -m scripts.end_to_end_proof "Azerbaijan Grand Prix" 2024
```

Current validation, over five real races (2024 Canada, 2023 Netherlands, 2024
Australia, 2024 Britain, 2024 Azerbaijan):

| Criterion | Result |
|---|---|
| Explainability + confidence band on every recommendation | PASS |
| Recommendation recomputes per lap, never frozen | PASS |
| Re-optimisation inside the 1s budget | PASS — max **0.294s** |
| Directional pit-window agreement | **3 of 5** (target 3 of 5) |
| Tyre-cliff onset within ±2 laps | 7 of 19 scorable stints |
| Source data gaps flagged rather than interpolated | 8 |

Cliff accuracy improves on the v1.0 record carried in the PRD (1 of 4), and the
improvement comes from the field-pace change described above rather than from
moving a threshold. Directional agreement matches the 3-of-5 target, and is
scored only against laps where the engine actually called a stop - a run where it
recommends staying out has made no pit-window call and is not credited with one.

## Layout

```
backend/app/
  ingestion/     FastF1 loading, normalisation, gap-flagging, circuit + pit-lane geometry
  tyre_model/    two degradation models, their comparison, and field-pace normalisation
  engine/        strategy graph, Dijkstra, re-optimisation, opponent baseline
  explainability/ factor breakdown and generated reasoning
  rival_model/   cover-stop probability, rejoin projection
  simulation/    counterfactual fork, forward projection, rolling re-optimisation
  validation/    the PRD section 13 suite
frontend/src/
  analysis/      Race Analysis: its own provider and component tree
  lab/           Simulation Lab: its own provider and component tree
  shared/        presentational primitives only — no shared stateful components
```

## Documentation

[PRD v2.0](PitSense_PRD_v2.docx) is the single source of truth for this build.

- [Architecture audit](docs/Architecture_Audit.md) — what was real versus assumed
  in the pre-v2.0 build, and what changed.
- [Submission notes](docs/Submission_Notes.md) — validation results, what was
  deliberately not built, and the known limitations stated plainly.
- [Documentation index](docs/README.md) — which documents are current and which
  are superseded.

## Scope, stated up front

Not built, and not claimed anywhere in the UI:

- **No four-source ML / Simulation / History / Memory blend.** The factor
  breakdown shows only the four factors the engine computes, and says so on
  screen. The blend is a Phase 2 direction, per PRD §2.2.
- **No energy / ERS modelling.** FastF1 exposes no fuel, energy-store, or ERS
  channel for 2023–2024 races; the gate was checked before any UI work and the
  result is in [`docs/feasibility_energy.json`](docs/feasibility_energy.json).
- **No live telemetry.** Historical replay only.
- **One tracked car against one modelled rival**, not the full grid.

## Licence

[MIT](LICENSE).
