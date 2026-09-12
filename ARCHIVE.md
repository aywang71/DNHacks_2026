# Public archive notes

This repository is the final public archive of the wake.ai DNHacks 2026
prototype. It accepts no new feature work and carries no service-level or
security-response commitment.

## Archive contents

The archive preserves the source code, compact reference material, final
GapPair browser export, documentation, deck source/final PDF, and submission
screenshots. It deliberately excludes raw GFW retrievals, Parquet derivatives,
Presence replay shards, operational logs, model-training outputs, temporary
research captures, and intermediate deck renders. Those files remain local to
the original workspace after the index cleanup but are ignored and must not be
added to a public release.

## Before enabling GitHub's archive setting

1. Review the staged deletion set and confirm the local-only data is backed up
   outside the repository if it must be retained.
2. Run the three Node checks listed in the root [README](README.md).
3. Review `git diff --cached --stat` and `git diff --check`, then create a
   clearly named final commit and an annotated release tag.
4. Create a GitHub Release from that tag with the final deck PDF and any
   intended screenshots as release assets, if desired.
5. In GitHub repository settings, disable unused collaboration surfaces and use
   **Archive this repository** only after the final commit and release are
   visible. GitHub's archive setting is intentionally a manual owner action.

Archiving prevents normal repository changes. Keep the original raw data in a
separate, access-controlled location subject to its upstream terms rather than
trying to preserve it in the public Git history.

## History-size decision

This cleanup removes bulk files from the final tree, but the existing Git
history still contains them. A normal commit and GitHub's archive setting do
not make prior blobs unavailable or materially shrink a fresh clone. If that
is required, an owner must separately approve a history rewrite in a backed-up
clone (for example with `git filter-repo`) and a force-push of every affected
branch and tag. That irreversible publication change is deliberately outside
this archive-preparation pass.
