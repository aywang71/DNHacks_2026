# wake.ai decisions

This log records decisions that affect the current documentation and product
boundary. Open questions remain open until an explicit decision replaces them.

## Decision log

| Date | Decision | Why | Consequence | Where recorded |
| --- | --- | --- | --- | --- |
| 2026-09-05 | Idea 01, maritime dark rendezvous detection, is selected. | It is the chosen project direction. | GapPair and Dark Rendezvous address paired dark-gap candidates. | [Idea 01](../ideas/idea-01-maritime-dark-rendezvous.md) |
| 2026-09-05 | Skylight is prior art, not a platform dependency. | Its rendezvous definitions inform comparisons, but it is not part of this repository. | wake.ai does not claim to run on Skylight. | [Build plan](archive/plan/build-plan.md) §1 |
| 2026-09-05 | The build scope is T0 paired-dark candidates with one within-cell permutation null. | This is the limited implemented analytical scope. | T1 and T2 are designed only. | [Build plan](archive/plan/build-plan.md) §0 |
| 2026-09-05 | The GapPair contract preserves frontend field names, uses `[lon, lat]`, and uses ISO-8601 UTC timestamps. | The consumer contract must be unambiguous. | Any future bridge and viewer layer use those forms. | [Implementation plan](archive/plan/backend-implementation-plan.md) §2 |
| 2026-09-05 | GapPair lives in top-level `pipeline/`, not inside `src/dark_rendezvous/`. | The ingestion package has separate packaging constraints and the pipeline does not need to import it. | GFW enrichment, if built, reads Bronze JSON at the boundary. | [Implementation plan](archive/plan/backend-implementation-plan.md) §2.9 |
| 2026-09-05 | The loose pairing rule is a methods number, not a queue source. | The loose rule produces too broad a set for the operating queue. | The queue remains the operating-rule candidates. | [Implementation plan](archive/plan/backend-implementation-plan.md) §2.1 |
| 2026-09-05 | Jurisdiction comes from the API `regions` field, not downloaded polygons. | The API supplies regions and distance fields for the 2021 corpus. | The CSV corpus remains without API jurisdiction until it is enriched. | [Implementation plan](archive/plan/backend-implementation-plan.md) §2.2 |
| 2026-09-05 | The 2021 Andrew API pull is the integration corpus. The 2017–2019 CSV is the validation corpus. | The 2021 pull has GFW vessel IDs, names, flags, regions, and distances that can join to the viewer. | CSV headline results do not transfer to the 2021 corpus without a rerun. | [Archived handoff prompts](archive/plan/handoff-prompts.md) §14 |
| 2026-09-05 | Presence is requested per candidate window, not per region-month. | Candidate windows bound the needed data and avoid unrelated regional pulls. | The existing region-5690 assets do not provide replay for 2021 candidates. | [Archived handoff prompts](archive/plan/handoff-prompts.md) §14 |
| 2026-09-05 | The product surface is Will's presence viewer. GapPair is backend scaffolding. | The viewer is the implemented user-facing application. | Documentation does not describe GapPair as the whole project. | User direction |
| 2026-09-05 | The product name is wake.ai. | The user selected the name. | New documentation uses wake.ai. Existing frontend strings remain a known inconsistency. | User direction |
| 2026-09-05 | Bronze data remains in Git. No history rewrite occurs. | The current repository retains the data and its history. | The large tracked-data footprint is accepted. | User direction |
| 2026-09-05 | S4 keeps the union neighbor definition and 183 strict identity twins. The methods claim must match the implementation. | The explicit code definition produces those figures; older figures refer to a different count or exclude valid pairs. | Do not alter S4 merely to match stale assertions. | Orchestrator direction; [status](status.md#known-issues) |
| 2026-09-05 | Live documentation excludes calendar and timing commitments. | The user rejected those commitments. | Snapshot dates are allowed; future live docs do not state timing commitments. | User direction |
| 2026-09-05 | Current documentation is consolidated under `docs/`; superseded plans and handoffs are archived there. | The live and historical material needs separate locations. | New docs link to the archive for historical specifications. | This documentation pass; [archive](archive/README.md) |
| 2026-09-05 | Pushes go directly to `origin/main`. | The user selected the integration path. | Documentation records `origin/main` as the direct destination. | User direction |

## Open decisions

- Select an LLM for S9 narration and decide whether the deterministic verifier is in scope.
- Decide whether to enrich the CSV corpus. That requires complete 2017–2019 GAP Bronze.
- Decide whether to relax package pins or move the working venv to the pinned versions.
- Decide whether to delete or reuse the unreferenced frontend risk-panel, provider, and mock-data files.
- Decide how to reconcile the presentation's oil-tanker framing with the fishing-pair corpus.
- Decide whether to rename the frontend's Maritime Risk Intelligence brand string.
- Determine whether GFW 4Wings accepts a high-seas region identifier.
- Decide whether to pursue commercial raw-AIS vectors for candidate windows.
