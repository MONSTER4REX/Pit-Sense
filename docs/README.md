# Documentation index

`PitSense_PRD_v2.docx` in the repository root is the **single source of truth**.
Anything that contradicts it is superseded, and this file records which is which
so no reader has to guess.

## Current

| Document | What it is |
|---|---|
| [`../PitSense_PRD_v2.docx`](../PitSense_PRD_v2.docx) | **PRD v2.0 — the source of truth.** |
| [`Architecture_Audit.md`](Architecture_Audit.md) | Gate 1 audit: what was real versus assumed in the pre-v2.0 build, and what changed. |
| [`Submission_Notes.md`](Submission_Notes.md) | What shipped, the validation results, what was scoped out, and the known limitations. |
| [`validation_report.json`](validation_report.json) | Output of `scripts.validation_report` — the PRD §13 suite. |
| [`tyre_model_comparison.json`](tyre_model_comparison.json) | Output of `scripts.tyre_model_report` — the PRD §5.J two-model comparison. |
| [`feasibility_geometry.json`](feasibility_geometry.json) | Output of `scripts.geometry_feasibility` — the PRD §5.G gate. |
| [`feasibility_energy.json`](feasibility_energy.json) | Output of `scripts.energy_feasibility` — the PRD §5.K gate. |

## Superseded

PRD v2.0 states that it supersedes v1.0 and the earlier planning documents. These
are kept for provenance only. **Where any of them disagrees with v2.0, v2.0 wins.**

| Document | Superseded by |
|---|---|
| `PitSense_PRD.docx` (v1.0) | PRD v2.0 |
| `../scratch_prd.txt` (a v1.0 text dump) | PRD v2.0 |
| `PitSense_Master_Implementation_Task.md` | PRD v2.0 §11 implementation gates |
| `backend-updated-idea.md`, `frontend-updated-idea.md` | PRD v2.0 §5 and §7 |
| `pitsense_product_idea.md` | PRD v2.0 §1–§4 |
| `pitsense_frontend_ui_spec.md` | PRD v2.0 §7–§9 |

In particular, the four-source **ML / Simulation / History / Memory** intelligence
blend described in the older material is **not implemented and not displayed**.
PRD v2.0 §2.2 scopes it out explicitly as a Phase 2 direction. The factor
breakdown in the running app shows only the four factors the engine actually
computes, and says so on screen.
