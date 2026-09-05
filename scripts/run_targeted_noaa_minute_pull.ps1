[CmdletBinding()]
param(
    [Parameter(Mandatory)]
    [string]$RequestFile,

    [string]$Python = ".\.venv313\Scripts\python.exe",

    [switch]$Force,

    [switch]$PlanOnly,

    [int]$MaximumDays = 3,

    [switch]$AllowMoreDays
)

$ErrorActionPreference = "Stop"

function Parse-Utc([string]$Value) {
    try {
        return [DateTimeOffset]::Parse(
            $Value,
            [Globalization.CultureInfo]::InvariantCulture,
            [Globalization.DateTimeStyles]::AssumeUniversal
        ).ToUniversalTime()
    }
    catch {
        throw "Expected an ISO-8601 UTC timestamp, received: $Value"
    }
}

$repoRoot = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path
$resolvedRequest = (Resolve-Path $RequestFile).Path
$request = Get-Content -Raw -Encoding utf8 $resolvedRequest | ConvertFrom-Json

if ($request.provider -ne "noaa_marine_cadastre") {
    throw "This runner only supports provider=noaa_marine_cadastre. Received: $($request.provider)"
}
if ($request.request_id -notmatch '^[A-Za-z0-9_-]+$') {
    throw "request_id may contain only letters, digits, underscore, and hyphen."
}
if ($null -eq $request.bbox_wgs84 -or $request.bbox_wgs84.Count -ne 4) {
    throw "bbox_wgs84 must contain min_lon, min_lat, max_lon, max_lat."
}

$bbox = @($request.bbox_wgs84 | ForEach-Object { [double]$_ })
if ($bbox[0] -ge $bbox[2] -or $bbox[1] -ge $bbox[3]) {
    throw "bbox_wgs84 must be min_lon,min_lat,max_lon,max_lat."
}

$start = Parse-Utc $request.window_start_utc
$end = Parse-Utc $request.window_end_utc
if ($end -le $start) {
    throw "window_end_utc must be after window_start_utc."
}

$days = @()
for ($day = $start.UtcDateTime.Date; $day -le $end.UtcDateTime.Date; $day = $day.AddDays(1)) {
    $days += $day
}
if ($days.Count -gt $MaximumDays -and -not $AllowMoreDays) {
    throw "Request spans $($days.Count) UTC days, above MaximumDays=$MaximumDays. Use -AllowMoreDays only after reviewing download size."
}

$pythonCandidate = if ([IO.Path]::IsPathRooted($Python)) { $Python } else { Join-Path $repoRoot $Python }
if (-not (Test-Path $pythonCandidate)) {
    throw "Python executable not found: $pythonCandidate"
}
$pythonPath = (Resolve-Path $pythonCandidate).Path

$bboxArgument = $bbox -join ','
foreach ($day in $days) {
    $dayText = $day.ToString("yyyy-MM-dd")
    $output = Join-Path $repoRoot "data\silver\ais_positions\source=noaa_marine_cadastre\request_id=$($request.request_id)\event_date=$dayText\positions.parquet"
    $arguments = @(
        "-m", "dark_rendezvous.cli", "ingest-noaa",
        "--date", $dayText,
        "--bbox=$bboxArgument",
        "--request-id", $request.request_id
    )

    if ((Test-Path $output) -and -not $Force) {
        Write-Output "[$dayText] Silver output exists; skipping. Use -Force to re-run."
        continue
    }
    Write-Output "[$dayText] $pythonPath $($arguments -join ' ')"
    if ($PlanOnly) {
        continue
    }
    & $pythonPath @arguments
    if ($LASTEXITCODE -ne 0) {
        throw "NOAA ingestion failed for $dayText with exit code $LASTEXITCODE. Earlier successful days remain intact."
    }
}
