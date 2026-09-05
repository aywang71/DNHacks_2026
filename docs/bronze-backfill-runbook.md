# GFW Bronze backfill runbook

## Purpose and boundary

This run retrieves only immutable GFW GAP API responses and manifests. It does
not create Silver tables, so it can run independently while schema and feature
work continues. Each raw page lands beneath a unique UTC retrieval ID:

```text
data/bronze/gfw_gaps/retrieval_id=<UTC-run-id>/
  window_start=YYYY-MM-DD/window_end=YYYY-MM-DD/offset=000000000/
    response.json
    manifest.json
```

The default keeps GFW events classified as intentional AIS disabling. Add
`-AllGaps` only when the broader, unclassified GAP population is required.

## Agent handoff prompt

Give a separate coding agent the following instruction:

> In `C:\Users\hyper\Documents\GitHub\DNHacks_2026`, run the GFW Bronze-only
> backfill from 2017-01-01 through today. The secret is available as the
> `GFW_API_TOKEN` environment variable; never print it, write it to a file,
> commit it, or include it in logs. Run `scripts\run_gfw_bronze_backfill.ps1`.
> Do not modify source code or create Silver datasets. If a yearly window fails,
> stop, report the start/end dates and error, and preserve the existing Bronze
> files. At completion, report every `pull_manifest.json` retrieval ID, event
> count, page count, and whether `complete` is true.

## Operator steps

1. Install runtime packages and set the secret only in the active shell or
   your secret manager.

    ```powershell
    py -3.13 -m pip install -r requirements.txt
    $env:GFW_API_TOKEN = '<token supplied through a secret channel>'
    ```

2. Start the default 2017-to-current, intentional-classified GAP backfill.

    ```powershell
    .\scripts\run_gfw_bronze_backfill.ps1
    ```

3. To stop at a fixed historical boundary, use an exclusive end date.

    ```powershell
    .\scripts\run_gfw_bronze_backfill.ps1 -StartDate 2022-01-01 -EndDate 2026-01-01
    ```

4. Validate each completed run from the manifest, not from directory size.

    ```powershell
    Get-ChildItem data\bronze\gfw_gaps -Recurse -Filter pull_manifest.json |
      ForEach-Object { Get-Content $_.FullName | ConvertFrom-Json } |
      Select-Object retrieval_id, request_start, request_end, pages_written, events_written, complete
    ```

The GFW Events API is paginated. The loader uses `START-DATE` mode and follows
the API's `nextOffset`; it never depends on a guessed page count. GFW's current
GAP product is derived/prototype data, not raw AIS messages.
