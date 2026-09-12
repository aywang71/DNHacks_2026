# wake.ai

> Final public archive of the 2026 DNHacks project. This repository is a
> research prototype and is no longer under active development.

wake.ai is an evidence-conscious maritime-analysis demonstration with two
separate browser workspaces:

- **GapPair candidates**: a static, inspectable queue of 434 paired AIS-gap
  candidates from the 2017-2019 Global Fishing Watch AIS-disabling corpus.
- **Presence replay**: a viewer for optional, locally generated Global Fishing
  Watch Presence exports. Those large inputs and exports are deliberately not
  included in this public archive.

The workspaces do not form an identity bridge. A GapPair MMSI must not be
treated as a Presence vessel merely because both appear in the same UI.

## Run the archived demo

Use Node 22-24. The dependency lockfile is part of the archive.

```bash
npm --prefix code/frontend ci
npm --prefix code/frontend run dev
```

Open the **GapPair candidates** workspace. It uses the committed static export
and works without credentials or the omitted Presence data. The Presence tab
correctly reports missing data in a fresh clone; it can only be recreated from
locally acquired GFW source material.

To run the optional local AI service, copy `.env.example` to an ignored `.env`,
set only your own server-side Gemini credentials, then run:

```bash
npm --prefix code/backend run dev
```

Never commit `.env`, provider tokens, or generated reports containing them.

## Verification

The release checks that do not require locally acquired data are:

```bash
npm --prefix code/backend test
npm --prefix code/frontend test
npm --prefix code/frontend run build
```

The Python tooling targets Python 3.11-3.13. Its complete pipeline needs the
source corpus plus local acquisition output; see [the data policy](docs/data.md)
before attempting a rebuild.

## What is retained

| Path | Contents |
| --- | --- |
| `code/frontend/` | Vite/React browser application and its frozen GapPair/static-model assets. |
| `code/backend/` | Local-only static exporter and optional AI service. |
| `pipeline/`, `src/`, `scripts/` | GapPair, ingestion, and experiment source code. |
| `data/raw/`, `data/reference/`, `data/derived/*.json` | Compact source archive, reference inputs, and reproducible summary checkpoints. |
| `docs/` | Architecture, methods, source limits, and historical project context. |
| `presentation/` and `submission/` | Pitch-deck source/final PDF and hackathon-submission screenshots. |

## Important limits

- A paired AIS gap is a screening signal, not proof of a rendezvous, transfer,
  intentional disabling, or crime.
- The public queue is retrospective, covers fishing vessels only, and has no
  coordinate-level ground truth for a transfer.
- Estimated routes, meeting points, and reachable areas are model outputs;
  only endpoints are observations.
- The separate ship-suspicion snapshot is experimental and must not be used as
  an operational risk score.

## Data and rights

The committed GapPair snapshot attributes the **Global Fishing Watch
AIS-disabling corpus (Welch et al. 2022), CC BY-NC 4.0**. The full GFW API
retrievals, normalized tables, model-training outputs, and Presence replay
assets are intentionally excluded from this archive. See [NOTICE.md](NOTICE.md)
and [docs/data.md](docs/data.md) for scope and provenance. Original project
code is MIT-licensed under [LICENSE](LICENSE); third-party material retains
its own terms.

## Archive handoff

[ARCHIVE.md](ARCHIVE.md) records the public-archive boundary and the remaining
GitHub-side steps. Start with [the documentation index](docs/README.md) for
architecture and methods.
