[CmdletBinding()]
param(
    [datetime]$StartDate = [datetime]'2017-01-01',
    [datetime]$EndDate = [datetime]::UtcNow.Date,
    [ValidateRange(1, 5000)]
    [int]$PageSize = 500,
    [switch]$AllGaps
)

$ErrorActionPreference = 'Stop'

if ([string]::IsNullOrWhiteSpace($env:GFW_API_TOKEN)) {
    throw 'Set GFW_API_TOKEN in this shell or your secret manager before starting the backfill.'
}
if ($StartDate.Date -ge $EndDate.Date) {
    throw 'StartDate must precede EndDate.'
}

$repoRoot = Split-Path -Parent $PSScriptRoot
$python = Join-Path $repoRoot '.venv313\Scripts\python.exe'
if (-not (Test-Path -LiteralPath $python)) {
    $python = 'python'
}

$cursor = $StartDate.Date
while ($cursor -lt $EndDate.Date) {
    $windowEnd = [datetime]::new($cursor.Year + 1, 1, 1)
    if ($windowEnd -gt $EndDate.Date) {
        $windowEnd = $EndDate.Date
    }
    $arguments = @(
        '-m', 'dark_rendezvous.cli', 'gfw-gaps-pull',
        '--start-date', $cursor.ToString('yyyy-MM-dd'),
        '--end-date', $windowEnd.ToString('yyyy-MM-dd'),
        '--window-days', '31',
        '--page-size', "$PageSize",
        '--bronze-only'
    )
    if ($AllGaps) {
        $arguments += '--all-gaps'
    }

    Write-Host "Starting GFW Bronze window $($cursor.ToString('yyyy-MM-dd')) to $($windowEnd.ToString('yyyy-MM-dd'))"
    & $python @arguments
    if ($LASTEXITCODE -ne 0) {
        throw "GFW Bronze backfill stopped for the window beginning $($cursor.ToString('yyyy-MM-dd')). Existing page artifacts were preserved."
    }
    $cursor = $windowEnd
}
