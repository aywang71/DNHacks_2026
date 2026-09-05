[CmdletBinding()]
param(
    [datetime]$StartDate = [datetime]'2021-09-05',
    [datetime]$EndDate = [datetime]'2026-09-05',
    [ValidateRange(1, 2147483647)]
    [int]$RegionId = 5690,
    [ValidateSet('HIGH', 'LOW')]
    [string]$SpatialResolution = 'HIGH',
    [string]$RegionDataset = 'public-eez-areas',
    [ValidateRange(0, 2147483647)]
    [int]$MaxDays = 0,
    [ValidateRange(0, 300)]
    [int]$PauseSeconds = 1,
    [switch]$DryRun
)

$ErrorActionPreference = 'Stop'

if ($StartDate.Date -ge $EndDate.Date) {
    throw 'StartDate must precede EndDate.'
}
$repoRoot = Split-Path -Parent $PSScriptRoot

function Import-LocalGfwToken {
    # A process variable wins.  Read the ignored local .env only when needed;
    # do not write or log its value.
    if (-not [string]::IsNullOrWhiteSpace($env:GFW_API_TOKEN)) {
        return
    }
    $envPath = Join-Path $repoRoot '.env'
    if (-not (Test-Path -LiteralPath $envPath)) {
        return
    }
    foreach ($line in Get-Content -LiteralPath $envPath) {
        if ($line -match '^\s*GFW_API_TOKEN\s*=\s*(.+?)\s*$') {
            $token = $matches[1].Trim().Trim('"').Trim("'")
            if (-not [string]::IsNullOrWhiteSpace($token)) {
                $env:GFW_API_TOKEN = $token
                return
            }
        }
    }
}

Import-LocalGfwToken
if (-not $DryRun -and [string]::IsNullOrWhiteSpace($env:GFW_API_TOKEN)) {
    throw 'Set GFW_API_TOKEN in this process or secret manager before starting the Presence backfill. The script never persists or logs the token.'
}

$python = Join-Path $repoRoot '.venv313\Scripts\python.exe'
if (-not (Test-Path -LiteralPath $python)) {
    $python = 'python'
}

$safeDataset = $RegionDataset -replace '[^A-Za-z0-9_.-]', '_'
$runLabel = "gfw_presence_${safeDataset}_region_${RegionId}_$($SpatialResolution.ToLowerInvariant())"
$logDirectory = Join-Path $repoRoot 'data\logs'
$logPath = Join-Path $logDirectory "$runLabel.log"
$statePath = Join-Path $logDirectory "$runLabel.state.json"
$bronzeRoot = Join-Path $repoRoot 'data\bronze\gfw_presence'

New-Item -ItemType Directory -Force -Path $logDirectory | Out-Null

function Write-BackfillLog {
    param([string]$Message)
    $line = "$(Get-Date -Format o) $Message"
    Write-Host $line
    Add-Content -LiteralPath $logPath -Value $line
}

function Resolve-RepoPath {
    param([string]$PathValue)
    if ([System.IO.Path]::IsPathRooted($PathValue)) {
        return $PathValue
    }
    return Join-Path $repoRoot $PathValue
}

function Get-CompletedDays {
    # Only accept a day when Bronze, Silver, and both manifests agree. A
    # partially written prior attempt stays on disk and is retried with a new
    # retrieval id rather than being deleted or overwritten.
    $result = [System.Collections.Generic.HashSet[string]]::new([System.StringComparer]::Ordinal)
    if (-not (Test-Path -LiteralPath $bronzeRoot)) {
        return $result
    }
    Get-ChildItem -LiteralPath $bronzeRoot -Filter manifest.json -File -Recurse | ForEach-Object {
        try {
            $bronzeManifest = Get-Content -LiteralPath $_.FullName -Raw | ConvertFrom-Json
            $request = $bronzeManifest.request
            if ($null -eq $request -or $null -eq $bronzeManifest.raw_response_sha256 -or
                [string]::IsNullOrWhiteSpace([string]$bronzeManifest.normalized_path)) {
                return
            }
            if ($request.'region-id' -ne $RegionId -or
                $request.'region-dataset' -ne $RegionDataset -or
                $request.'spatial-resolution' -ne $SpatialResolution -or
                $request.'temporal-resolution' -ne 'HOURLY') {
                return
            }
            $dateRange = [string]$request.'date-range'
            if ($dateRange -notmatch '^(\d{4}-\d{2}-\d{2})T00:00:00Z,(\d{4}-\d{2}-\d{2})T00:00:00Z$') {
                return
            }
            $day = [datetime]::ParseExact($matches[1], 'yyyy-MM-dd', [cultureinfo]::InvariantCulture)
            $nextDay = [datetime]::ParseExact($matches[2], 'yyyy-MM-dd', [cultureinfo]::InvariantCulture)
            if ($nextDay -ne $day.AddDays(1)) {
                return
            }
            $rawPath = Join-Path $_.DirectoryName 'report.json'
            $silverPath = Resolve-RepoPath ([string]$bronzeManifest.normalized_path)
            $silverManifestPath = Join-Path (Split-Path -Parent $silverPath) 'manifest.json'
            if (-not (Test-Path -LiteralPath $rawPath) -or -not (Test-Path -LiteralPath $silverPath) -or
                -not (Test-Path -LiteralPath $silverManifestPath)) {
                return
            }
            $silverManifest = Get-Content -LiteralPath $silverManifestPath -Raw | ConvertFrom-Json
            if ($silverManifest.raw_response_sha256 -ne $bronzeManifest.raw_response_sha256 -or
                $silverManifest.position_semantics -ne 'gfw_presence_grid_center_hourly') {
                return
            }
            [void]$result.Add($day.ToString('yyyy-MM-dd'))
        }
        catch {
            # Bad manifests are deliberately not treated as complete. The
            # next retrieval remains append-only and leaves evidence intact.
        }
    }
    return $result
}

# PowerShell enumerates collections emitted by functions.  Rebuild a mutable
# HashSet here rather than assigning the function output directly, which can
# otherwise become a fixed-size Object[] once completed days exist.
$completedDays = [System.Collections.Generic.HashSet[string]]::new([System.StringComparer]::Ordinal)
Get-CompletedDays | ForEach-Object {
    [void]$completedDays.Add([string]$_)
}
$requestedDays = 0
$skippedDays = 0
$loadedDays = 0
$cursor = $StartDate.Date

Write-BackfillLog "started start=$($StartDate.Date.ToString('yyyy-MM-dd')) end_exclusive=$($EndDate.Date.ToString('yyyy-MM-dd')) region_id=$RegionId region_dataset=$RegionDataset spatial_resolution=$SpatialResolution already_complete=$($completedDays.Count) dry_run=$DryRun"

while ($cursor -lt $EndDate.Date) {
    if ($MaxDays -gt 0 -and $requestedDays -ge $MaxDays) {
        break
    }
    $dayKey = $cursor.ToString('yyyy-MM-dd')
    $nextCursor = $cursor.AddDays(1)
    if ($completedDays.Contains($dayKey)) {
        $skippedDays++
        $requestedDays++
        Write-BackfillLog "skipped_complete day=$dayKey"
        $cursor = $nextCursor
        continue
    }

    $requestedDays++
    $compactDay = $dayKey -replace '-', ''
    $retrievalId = "presence_${safeDataset}_region_${RegionId}_$($SpatialResolution.ToLowerInvariant())_${compactDay}_$(Get-Date -Format 'yyyyMMddTHHmmssZ')"
    $arguments = @(
        '-m', 'dark_rendezvous.cli', 'gfw-presence',
        '--start', "$dayKey`T00:00:00Z",
        '--end', "$($nextCursor.ToString('yyyy-MM-dd'))`T00:00:00Z",
        '--region-id', "$RegionId",
        '--region-dataset', $RegionDataset,
        '--spatial-resolution', $SpatialResolution,
        '--retrieval-id', $retrievalId
    )
    if ($DryRun) {
        Write-BackfillLog "would_load day=$dayKey retrieval_id=$retrievalId"
        $cursor = $nextCursor
        continue
    }

    Write-BackfillLog "loading day=$dayKey retrieval_id=$retrievalId"
    # Python writes tracebacks to stderr.  Treat those lines as loader output
    # long enough to capture the native exit code and write resumable state;
    # the script's normal Stop preference would otherwise terminate the
    # PowerShell pipeline before its failure handler runs.
    $priorErrorActionPreference = $ErrorActionPreference
    try {
        $ErrorActionPreference = 'Continue'
        $loaderOutput = & $python @arguments 2>&1
        $loaderExitCode = $LASTEXITCODE
    }
    finally {
        $ErrorActionPreference = $priorErrorActionPreference
    }
    $loaderOutput | ForEach-Object {
        $message = $_.ToString()
        Write-Host $message
        Add-Content -LiteralPath $logPath -Value "$(Get-Date -Format o) loader $message"
    }
    if ($loaderExitCode -ne 0) {
        $state = [ordered]@{
            status = 'failed'
            stopped_at = (Get-Date).ToUniversalTime().ToString('o')
            next_day = $dayKey
            loaded_days_this_process = $loadedDays
            skipped_complete_days_this_process = $skippedDays
            log_path = $logPath
        } | ConvertTo-Json
        Set-Content -LiteralPath $statePath -Value $state -Encoding utf8
        Write-BackfillLog "failed day=$dayKey exit_code=$loaderExitCode; preserve_artifacts=true; rerun_the_same_command_to_resume"
        exit $loaderExitCode
    }
    $loadedDays++
    [void]$completedDays.Add($dayKey)
    $state = [ordered]@{
        status = 'running'
        updated_at = (Get-Date).ToUniversalTime().ToString('o')
        next_day = $nextCursor.ToString('yyyy-MM-dd')
        loaded_days_this_process = $loadedDays
        skipped_complete_days_this_process = $skippedDays
        log_path = $logPath
    } | ConvertTo-Json
    Set-Content -LiteralPath $statePath -Value $state -Encoding utf8
    Write-BackfillLog "completed day=$dayKey loaded_days_this_process=$loadedDays"
    if ($PauseSeconds -gt 0 -and $nextCursor -lt $EndDate.Date) {
        Start-Sleep -Seconds $PauseSeconds
    }
    $cursor = $nextCursor
}

$status = if ($cursor -ge $EndDate.Date) { 'complete' } else { 'stopped_at_max_days' }
$state = [ordered]@{
    status = $status
    finished_at = (Get-Date).ToUniversalTime().ToString('o')
    next_day = if ($cursor -lt $EndDate.Date) { $cursor.ToString('yyyy-MM-dd') } else { $null }
    loaded_days_this_process = $loadedDays
    skipped_complete_days_this_process = $skippedDays
    log_path = $logPath
} | ConvertTo-Json
Set-Content -LiteralPath $statePath -Value $state -Encoding utf8
Write-BackfillLog "$status loaded_days_this_process=$loadedDays skipped_complete_days_this_process=$skippedDays"
