# Documentation index

## Live docs

| Document | Purpose |
| --- | --- |
| [Root README](../README.md) | wake.ai overview, repository map, and subsystem entry points. |
| [This index](README.md) | Entry point for current, archive, and reference material. |
| [Architecture](architecture.md) | Subsystems, data contracts, ownership, and the unbuilt integration boundary. |
| [Status](status.md) | Verified current state, checks, missing work, and known issues. |
| [Decisions](decisions.md) | Decision log and accepted boundaries. |
| [Data](data.md) | Data inventory, provenance, coverage, and missing inputs. |
| [Candidate pipeline](candidate-pipeline.md) | GapPair stages, configuration, definitions, outputs, and commands. |
| [Ship-suspicion model](ship-suspicion-model.md) | Experimental individual-vessel model, evidence limits, and static export. |
| [Developer guide](development.md) | Subsystem ownership, generated-artifact rules, and safe cross-boundary work. |
| [Verification guide](verification.md) | Repeatable pipeline, export, browser, and documentation checks. |
| [Data-local README](../data/README.md) | Local data-directory notes. |
| [Reference tables README](../data/reference/README.md) | Static reference tables used by the GapPair pipeline. |

## Ingestion docs

| Document | Purpose |
| --- | --- |
| [AIS ingestion](ais-ingestion.md) | Dark Rendezvous outcome, sources, data contract, and CLI commands. |
| [Bronze backfill runbook](bronze-backfill-runbook.md) | GFW bronze retrieval procedure and operational checks. |
| [Bronze backfill resume notes](gfw-bronze-backfill-resume-notes.md) | Existing GAP retrieval boundaries and resume context. |
| [Targeted raw AIS plan](targeted-raw-ais-plan.md) | Candidate-window raw-AIS acquisition boundary. |
| [AIS-first rendezvous plan](ais-first-rendezvous-plan.md) | Earlier raw-AIS-first investigation approach. |

## Viewer docs

| Document | Purpose |
| --- | --- |
| [Frontend README](../code/frontend/README.md) | Local viewer entry point, static assets, and UI contract rules. |
| [Backend README](../code/backend/README.md) | Node importer and the unimplemented historical-risk API proposal. |
| [Viewer data flow](../code/backend/DATA_FLOW.md) | Implemented presence assets, semantics, and frontend behavior. |

## Archive

Archived material records earlier plans and handoffs. It is superseded by the live docs and is not updated.

| Document | What it was and why it is superseded |
| --- | --- |
| [Archive index](archive/README.md) | Archive guide; superseded context is retained for traceability. |
| [Build plan](archive/plan/build-plan.md) | Original candidate-build plan; replaced by current implementation status and pipeline reference. |
| [Backend implementation plan](archive/plan/backend-implementation-plan.md) | GapPair stage specifications, config values and output contract; replaced by [candidate pipeline](candidate-pipeline.md). |
| [Frontend notes](archive/plan/frontend-notes.md) | Earlier frontend ideas; replaced by the implemented viewer data flow. |
| [Handoff prompts](archive/plan/handoff-prompts.md) | Original detailed implementation prompts; retained as source context for unbuilt integration work. |
| [Research notes](archive/plan/research-notes.md) | Working research notes; replaced by curated live data and architecture docs. |
| [Branch audit handoff](archive/handoffs/branch_audit_handoff.md) | Branch survey handoff; branches are now merged. |
| [Orchestrator log](archive/handoffs/orchestrator_log.md) | Working coordination log; superseded by the current snapshot. |
| [Project status handoff](archive/handoffs/project_status_handoff.md) | Prior status handoff; replaced by [status](status.md). |
| [Sync review handoff](archive/handoffs/sync_review_handoff.md) | Prior synchronization review; replaced by the current repository state. |
| [Research session handoff](archive/research/maritime-idea-01-session-handoff.md) | Earlier research handoff; retained as history. |
| [Report source](archive/report-source.md) | Moved source report; retained for provenance. |

## History and reference

| Path | Contents |
| --- | --- |
| [ideas/](../ideas/) | Earlier ideas, papers, and source material. |
| [background/](../background/) | Event and research background plus experiment logs. |
| [tmp/skylight-ref/](../tmp/skylight-ref/) | Local visual reference captures. |
| [tmp/pdfs/](../tmp/pdfs/) | Extracted reference PDF material. |
| [output/pdf/](../output/pdf/) | Generated reference PDF output. |
| [presentation/](../presentation/) | Unwired Slidev pitch deck. |

## Documentation rules

Live docs contain no timetables. Snapshot dates are allowed. Numbers are reproducible from a command or labelled unverified. Archived files are not updated.
