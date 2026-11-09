#Requires -Version 5.1
<#
.SYNOPSIS
    Apply the Auralization-toolbox local modifications to the
    ITAGeometricalAcoustics submodules.

.DESCRIPTION
    The toolbox needs a handful of changes to the upstream ITA CMake files
    (disabling the Qt/MATLAB apps, dropping the netcdf-cxx4 dependency of
    pelican, and guarding the SketchUp DLL copy). A git submodule only records
    an upstream commit, so these changes cannot be committed here directly.
    They are therefore stored as patches under patches/ita/ and replayed by
    this script.

    The script is idempotent: a patch that is already applied is skipped.
    Patches are applied with --ignore-whitespace, because a Windows clone with
    core.autocrlf=true checks the ITA sources out with CRLF endings while the
    stored patches use LF.

.EXAMPLE
    powershell -ExecutionPolicy Bypass -File tools/apply_ita_patches.ps1
#>
[CmdletBinding()]
param()

$ErrorActionPreference = 'Stop'

# Run `git apply` and return only its exit code.
#
# A failing `git apply --check` is a normal, expected answer here ("this patch is
# not applied yet"), but it prints to stderr. Under $ErrorActionPreference='Stop'
# Windows PowerShell 5.1 turns native stderr output into a terminating error
# whenever it is redirected, which would abort the very first run on a pristine
# checkout. So relax it for just this call and look at the exit code instead.
function Test-GitApply {
    param([string[]]$GitArgs)
    $previous = $ErrorActionPreference
    $ErrorActionPreference = 'Continue'
    try {
        & git apply @GitArgs 2>$null | Out-Null
        return $LASTEXITCODE
    }
    finally {
        $ErrorActionPreference = $previous
    }
}

$RepoRoot = Split-Path -Parent $PSScriptRoot
$PatchDir = Join-Path $RepoRoot 'patches\ita'
$ItaRoot = Join-Path $RepoRoot 'ITAGeometricalAcoustics'

if (-not (Test-Path (Join-Path $ItaRoot 'CMakePresets.json'))) {
    throw "ITAGeometricalAcoustics is not checked out. Run: git submodule update --init --recursive"
}

# Submodule directory (relative to $ItaRoot), patch file name.
$Targets = @(
    @('.',                    'ITAGeometricalAcoustics.patch'),
    @('ITAGeo',               'ITAGeo.patch'),
    @('ITAPropagationModels', 'ITAPropagationModels.patch')
)

$failed = @()

foreach ($target in $Targets) {
    $sub = $target[0]
    $patchName = $target[1]
    $patch = Join-Path $PatchDir $patchName
    $dir = if ($sub -eq '.') { $ItaRoot } else { Join-Path $ItaRoot $sub }
    $label = if ($sub -eq '.') { 'ITAGeometricalAcoustics' } else { $sub }
    $label = "$label [$patchName]"

    if (-not (Test-Path $patch)) { throw "Missing patch file: $patch" }
    if (-not (Test-Path $dir)) {
        throw "Submodule '$label' is not checked out. Run: git submodule update --init --recursive"
    }

    Push-Location $dir
    try {
        # Already applied?
        if ((Test-GitApply '--reverse','--check','--ignore-whitespace',$patch) -eq 0) {
            Write-Host "  [skip]  $label - already applied" -ForegroundColor DarkGray
            continue
        }

        # Cleanly appliable?
        if ((Test-GitApply '--check','--ignore-whitespace',$patch) -ne 0) {
            Write-Host "  [FAIL]  $label - patch does not apply" -ForegroundColor Red
            $failed += $label
            continue
        }

        if ((Test-GitApply '--ignore-whitespace','--whitespace=nowarn',$patch) -ne 0) {
            Write-Host "  [FAIL]  $label - apply failed" -ForegroundColor Red
            $failed += $label
        }
        else {
            Write-Host "  [ok]    $label - patched" -ForegroundColor Green
        }
    }
    finally {
        Pop-Location
    }
}

if ($failed.Count -gt 0) {
    throw ("Could not patch: {0}. The submodule may be at a different commit than expected, " +
        "or already locally modified. Expected ITAGeometricalAcoustics at the commit recorded " +
        "in this repo (git submodule status).") -f ($failed -join ', ')
}

# --- New files that are not part of any upstream file (copied verbatim) ---
$filesRoot = Join-Path $PatchDir 'files'
if (Test-Path $filesRoot) {
    foreach ($subDir in Get-ChildItem -Path $filesRoot -Directory) {
        $dest = Join-Path $ItaRoot $subDir.Name
        if (-not (Test-Path $dest)) {
            throw "Submodule '$($subDir.Name)' is not checked out."
        }
        foreach ($src in Get-ChildItem -Path $subDir.FullName -Recurse -File) {
            $rel = $src.FullName.Substring($subDir.FullName.Length).TrimStart('\')
            $target = Join-Path $dest $rel
            $targetDir = Split-Path -Parent $target
            if (-not (Test-Path $targetDir)) {
                New-Item -ItemType Directory -Path $targetDir -Force | Out-Null
            }
            Copy-Item -Path $src.FullName -Destination $target -Force
            Write-Host "  [ok]    $($subDir.Name)/$($rel -replace '\\','/')" -ForegroundColor Green
        }
    }
}

# --- Preflight: every PATCH_COMMAND / PATCHES file the CMake files reference
# must actually exist, or a fresh CMake configure fails at the populate step. ---
$missing = @()
foreach ($cmakeFile in Get-ChildItem -Path $ItaRoot -Recurse -File -Filter 'CMakeLists.txt' `
        -ErrorAction SilentlyContinue | Where-Object { $_.FullName -notmatch '\\out\\' }) {
    $text = Get-Content -Raw $cmakeFile.FullName
    foreach ($m in [regex]::Matches($text, 'patches/([A-Za-z0-9._-]+\.(?:cmake|patch))')) {
        $needed = Join-Path $cmakeFile.DirectoryName ('patches\' + $m.Groups[1].Value)
        if (-not (Test-Path $needed)) {
            $missing += "$($cmakeFile.FullName.Substring($ItaRoot.Length).TrimStart('\')) -> patches/$($m.Groups[1].Value)"
        }
    }
}
if ($missing.Count -gt 0) {
    Write-Host ''
    Write-Host 'WARNING: these CMake files reference patch files that do not exist.' -ForegroundColor Yellow
    Write-Host '         A fresh CMake configure will fail at the dependency populate step.' -ForegroundColor Yellow
    foreach ($m in ($missing | Sort-Object -Unique)) { Write-Host "         $m" -ForegroundColor Yellow }
}

Write-Host ''
Write-Host 'ITA patches applied.' -ForegroundColor Cyan
