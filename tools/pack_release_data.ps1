#Requires -Version 5.1
<#
.SYNOPSIS
    Pack the large regenerable data - verification dumps and per-scenario
    result figures - into zip archives for distribution as GitHub Release
    assets.

.DESCRIPTION
    The scripts and the reference figures are tracked in git. The bulk data is
    not, and ships as Release assets instead:

      * verification/**/*.npz|.mat        per-scenario numeric dumps (~5.8 GB)
      * verification/plot_comparison/     generated HTML report (~220 MB)
      * results_auralization/<scenario>/  per-scenario figures + wavs (~450 MB)
      * input_data/results_auralization/  stray output of an earlier run

    One archive per scenario keeps every asset well under the 2 GB per-file
    limit for GitHub Release assets.

    Archives are written to dist/ (gitignored). Unpack them back over the
    repository root with tools/unpack_release_data.ps1, or by hand - the paths
    inside each archive are relative to the repository root.

.PARAMETER OutDir
    Where to write the archives. Default: <repo>/dist.

.PARAMETER Scenario
    Pack only scenarios whose directory name matches this wildcard.

.PARAMETER IncludePlots
    Also pack verification/plot_comparison (the generated HTML report and its
    ~220 MB of PDF/PNG assets).

.PARAMETER IncludeResults
    Also pack the per-scenario auralization outputs under
    results_auralization/<scenario>/ and the stray
    input_data/results_auralization/ directory.

.PARAMETER ResultsOnly
    Pack only the result figures, skipping the verification dumps.

.EXAMPLE
    powershell -ExecutionPolicy Bypass -File tools/pack_release_data.ps1 -IncludePlots -IncludeResults

.EXAMPLE
    powershell -ExecutionPolicy Bypass -File tools/pack_release_data.ps1 -Scenario 'scenario_0*'
#>
[CmdletBinding()]
param(
    [string]$OutDir,
    [string]$Scenario = '*',
    [switch]$IncludePlots,
    [switch]$IncludeResults,
    [switch]$ResultsOnly
)

$ErrorActionPreference = 'Stop'
Add-Type -AssemblyName System.IO.Compression.FileSystem

$RepoRoot = Split-Path -Parent $PSScriptRoot
$VerifDir = Join-Path $RepoRoot 'verification'
if (-not $OutDir) { $OutDir = Join-Path $RepoRoot 'dist' }

if (-not (Test-Path $VerifDir)) { throw "No verification/ directory at $VerifDir" }
if (-not (Test-Path $OutDir)) { New-Item -ItemType Directory -Path $OutDir -Force | Out-Null }

$dataExt = @('.npz', '.mat')
$GitHubAssetLimit = 2GB

# Build a zip from a list of files, storing paths relative to the repo root.
function New-DataArchive {
    param(
        [string]$ZipPath,
        [System.IO.FileInfo[]]$Files,
        [string]$Label
    )

    if (-not $Files -or $Files.Count -eq 0) {
        Write-Host "  [skip]  $Label - no data files" -ForegroundColor DarkGray
        return
    }

    $raw = ($Files | Measure-Object -Property Length -Sum).Sum
    if (Test-Path $ZipPath) { Remove-Item $ZipPath -Force }

    $zip = [System.IO.Compression.ZipFile]::Open($ZipPath, 'Create')
    try {
        foreach ($f in $Files) {
            $rel = $f.FullName.Substring($RepoRoot.Length).TrimStart('\', '/').Replace('\', '/')
            [System.IO.Compression.ZipFileExtensions]::CreateEntryFromFile(
                $zip, $f.FullName, $rel, [System.IO.Compression.CompressionLevel]::Optimal) | Out-Null
        }
    }
    finally {
        $zip.Dispose()
    }

    $packed = (Get-Item $ZipPath).Length
    $ratio = if ($raw -gt 0) { 100 - [math]::Round(100 * $packed / $raw) } else { 0 }
    Write-Host ("  [ok]    {0}  {1} files, {2:N0} MB -> {3:N0} MB ({4}% smaller)" -f `
            $Label, $Files.Count, ($raw / 1MB), ($packed / 1MB), $ratio) -ForegroundColor Green

    if ($packed -gt $GitHubAssetLimit) {
        Write-Host ("          WARNING: {0:N1} GB exceeds the 2 GB GitHub Release asset limit." -f ($packed / 1GB)) -ForegroundColor Yellow
    }
}

Write-Host "=== Packing release data into $OutDir" -ForegroundColor Cyan

$scenarioRoot = Join-Path $VerifDir 'scenarios'

if (-not $ResultsOnly) {
    # --- One archive per scenario -----------------------------------------
    if (Test-Path $scenarioRoot) {
        foreach ($dir in Get-ChildItem -Path $scenarioRoot -Directory -Filter $Scenario) {
            $files = Get-ChildItem -Path $dir.FullName -Recurse -File |
                Where-Object { $dataExt -contains $_.Extension.ToLower() }
            New-DataArchive -ZipPath (Join-Path $OutDir "verification-data-$($dir.Name).zip") `
                -Files $files -Label $dir.Name
        }
    }

    # --- Top-level step dumps (everything outside scenarios/) -------------
    if ($Scenario -eq '*') {
        $topFiles = Get-ChildItem -Path $VerifDir -Recurse -File |
            Where-Object {
                ($dataExt -contains $_.Extension.ToLower()) -and
                ($_.FullName -notlike (Join-Path $scenarioRoot '*'))
            }
        New-DataArchive -ZipPath (Join-Path $OutDir 'verification-data-steps.zip') `
            -Files $topFiles -Label 'top-level step dumps'
    }

    # --- Generated plot-comparison report ---------------------------------
    if ($IncludePlots) {
        $plotDir = Join-Path $VerifDir 'plot_comparison'
        if (Test-Path $plotDir) {
            $plotFiles = Get-ChildItem -Path $plotDir -Recurse -File
            New-DataArchive -ZipPath (Join-Path $OutDir 'verification-plot-comparison.zip') `
                -Files $plotFiles -Label 'plot_comparison report'
        }
    }
}

# --- Per-scenario auralization results (figures + wavs) -------------------
if ($IncludeResults -or $ResultsOnly) {
    $resultsRoot = Join-Path $RepoRoot 'results_auralization'
    if (Test-Path $resultsRoot) {
        # Only the subdirectories; the reference figures sitting directly in
        # results_auralization/ are tracked in git and stay out of the archive.
        foreach ($dir in Get-ChildItem -Path $resultsRoot -Directory -Filter $Scenario) {
            $files = Get-ChildItem -Path $dir.FullName -Recurse -File
            New-DataArchive -ZipPath (Join-Path $OutDir "results-$($dir.Name).zip") `
                -Files $files -Label "results/$($dir.Name)"
        }
    }

    if ($Scenario -eq '*') {
        $stray = Join-Path $RepoRoot 'input_data\results_auralization'
        if (Test-Path $stray) {
            $strayFiles = Get-ChildItem -Path $stray -Recurse -File
            New-DataArchive -ZipPath (Join-Path $OutDir 'results-input_data-stray.zip') `
                -Files $strayFiles -Label 'input_data/results_auralization (stray)'
        }
    }
}

Write-Host ''
Write-Host 'Archives:' -ForegroundColor Cyan
$all = Get-ChildItem -Path $OutDir -Filter '*.zip' | Sort-Object Name
if (-not $all) {
    Write-Host '  (none - did you mean -IncludeResults or -IncludePlots?)' -ForegroundColor Yellow
}
else {
    $all | ForEach-Object { Write-Host ("  {0,-58} {1,8:N0} MB" -f $_.Name, ($_.Length / 1MB)) }
    Write-Host ("  {0,-58} {1,8:N0} MB" -f 'TOTAL', (($all | Measure-Object -Property Length -Sum).Sum / 1MB)) -ForegroundColor Cyan
}

Write-Host ''
Write-Host 'Attach these to a GitHub Release. Unpack with:' -ForegroundColor DarkGray
Write-Host '  powershell -File tools/unpack_release_data.ps1 -Archive dist\<name>.zip' -ForegroundColor DarkGray
