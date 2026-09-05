# GFW Bronze backfill resume notes

Snapshot: 2026-09-05 UTC. This document is derived from the Bronze page and
pull manifests. It records coverage only; it does not create or imply any
Silver dataset.

## Completed retrievals

| Retrieval ID | Requested range | Pages | Events | Complete |
| --- | --- | ---: | ---: | --- |
| `20260905T200519Z` | 2021-01-01 to 2022-01-01 | 695 | 343,857 | yes |
| `20260905T210748Z` | 2026-08-01 to 2026-09-01 | 60 | 29,538 | yes |

Both retrievals contain only intentional-classified GFW GAP events and use
`START-DATE` filtering.

## Preserved incomplete retrievals

The following raw pages are immutable and remain available, but their
retrievals do **not** have a completed `pull_manifest.json`.

| Retrieval ID | Confirmed complete page windows | First incomplete window | Resume boundary |
| --- | --- | --- | --- |
| `20260905T202100Z` | 2022-01-01 through 2022-10-07 | 2022-10-07 to 2022-11-07; 62 pages, next offset 31,000 of reported total 41,397 | 2022-10-07 |
| `20260905T210211Z` | 2026-01-01 through 2026-03-04 | 2026-03-04 to 2026-04-04; 60 pages, next offset 30,000 of reported total 33,561 | 2026-03-04 |

The 2022 incomplete retrieval has valid, complete page windows through
2022-10-07, and the 2026 incomplete retrieval has valid, complete page
windows through 2026-03-04. Begin any replacement pull at the stated resume
boundary to avoid depending on a partial API cursor. A new retrieval ID is
expected and safely preserves these partial artifacts.

## Remaining coverage gaps

- 2022-10-07 through 2022-12-31: incomplete or absent.
- 2023-01-01 through 2025-12-31: not pulled.
- 2026-03-04 through 2026-07-31: incomplete or absent.
- 2026-08-01 through 2026-08-31: complete via `20260905T210748Z`.
- 2026-09-01 through the current UTC date: not pulled.

## Safe resume sequence

Run each range independently and validate its `pull_manifest.json` before
starting the next one. Keep `GFW_API_TOKEN` only in the active shell; never
put it in a repository file.

```powershell
.\scripts\run_gfw_bronze_backfill.ps1 -StartDate 2022-10-07 -EndDate 2023-01-01
.\scripts\run_gfw_bronze_backfill.ps1 -StartDate 2023-01-01 -EndDate 2024-01-01
.\scripts\run_gfw_bronze_backfill.ps1 -StartDate 2024-01-01 -EndDate 2025-01-01
.\scripts\run_gfw_bronze_backfill.ps1 -StartDate 2025-01-01 -EndDate 2026-01-01
.\scripts\run_gfw_bronze_backfill.ps1 -StartDate 2026-03-04 -EndDate 2026-08-01
.\scripts\run_gfw_bronze_backfill.ps1 -StartDate 2026-09-01
```

There is also an older pre-existing incomplete retrieval,
`20260905T193330Z`, whose 2017-01-01 to 2017-02-01 page window is complete,
but it has no annual completion manifest. It is outside the 2021-to-present
scope above.
