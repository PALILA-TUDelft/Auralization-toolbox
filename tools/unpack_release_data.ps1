#Requires -Version 5.1
<#
.SYNOPSIS
    Unpack release data archives back into the repository.

.DESCRIPTION
    Counterpart to tools/pack_release_data.ps1. Paths inside each archive are
    relative to the repository root, so the contents land back where the
    comparison scripts and the README expect them.

.PARAMETER Archive
    One or more .zip files to unpack. Accepts wildcards. Defaults to every
    .zip in dist/.

.PARAMETER Force
    Overwrite files that already exist. Without it, existing files are kept
    and reported.

.EXAMPLE
    powershell -ExecutionPolicy Bypass -File tools/unpack_release_data.ps1

.EXAMPLE
    powershell -ExecutionPolicy Bypass -File tools/unpack_release_data.ps1 -Archive ~\Downloads\verification-data-scenario_0*.zip -Force
#>
[CmdletBinding()]
param(
    [string[]]$Archive,
    [switch]$Force
)

$ErrorActionPreference = 'Stop'
Add-Type -AssemblyName System.IO.Compression.FileSystem

$RepoRoot = Split-Path -Parent $PSScriptRoot

if (-not $Archive) {
    $Archive = @(Join-Path $RepoRoot 'dist\*.zip')
}

$zips = @()
foreach ($pattern in $Archive) {
    $resolved = Get-ChildItem -Path $pattern -File -ErrorAction SilentlyContinue
    if ($resolved) { $zips += $resolved }
    else { Write-Host "  no match: $pattern" -ForegroundColor Yellow }
}

if ($zips.Count -eq 0) { throw 'No archives found. Pass -Archive, or download the assets into dist/.' }

$totalWritten = 0
$totalSkipped = 0

foreach ($zipFile in $zips) {
    Write-Host "=== $($zipFile.Name)" -ForegroundColor Cyan
    $written = 0
    $skipped = 0

    $zip = [System.IO.Compression.ZipFile]::OpenRead($zipFile.FullName)
    try {
        foreach ($entry in $zip.Entries) {
            if ([string]::IsNullOrEmpty($entry.Name)) { continue }  # directory entry

            # Reject absolute paths and traversal before touching the disk.
            $rel = $entry.FullName -replace '/', '\'
            if ([System.IO.Path]::IsPathRooted($rel) -or $rel -match '(^|\\)\.\.(\\|$)') {
                Write-Host "  [skip]  unsafe path in archive: $($entry.FullName)" -ForegroundColor Yellow
                $skipped++
                continue
            }

            $target = Join-Path $RepoRoot $rel
            $resolvedRoot = [System.IO.Path]::GetFullPath($RepoRoot + [System.IO.Path]::DirectorySeparatorChar)
            $resolvedTarget = [System.IO.Path]::GetFullPath($target)
            if (-not $resolvedTarget.StartsWith($resolvedRoot, [StringComparison]::OrdinalIgnoreCase)) {
                Write-Host "  [skip]  escapes repository: $($entry.FullName)" -ForegroundColor Yellow
                $skipped++
                continue
            }

            if ((Test-Path $resolvedTarget) -and -not $Force) {
                $skipped++
                continue
            }

            $dir = Split-Path -Parent $resolvedTarget
            if (-not (Test-Path $dir)) { New-Item -ItemType Directory -Path $dir -Force | Out-Null }

            [System.IO.Compression.ZipFileExtensions]::ExtractToFile($entry, $resolvedTarget, $true)
            $written++
        }
    }
    finally {
        $zip.Dispose()
    }

    Write-Host "  $written extracted, $skipped skipped" -ForegroundColor Green
    $totalWritten += $written
    $totalSkipped += $skipped
}

Write-Host ''
Write-Host "Done: $totalWritten files extracted, $totalSkipped skipped." -ForegroundColor Cyan
if ($totalSkipped -gt 0 -and -not $Force) {
    Write-Host 'Some files already existed. Re-run with -Force to overwrite them.' -ForegroundColor DarkGray
}
