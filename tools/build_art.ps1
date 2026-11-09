#Requires -Version 5.1
<#
.SYNOPSIS
    Build the ART native module (_art_core) and stage it, with the ITA DLLs,
    into bin/ where the toolbox looks for it by default.

.DESCRIPTION
    Steps:
      1. check for Visual Studio 2019 / git / cmake / python / nanobind
      2. git submodule update --init --recursive
      3. apply the local ITA patches (tools/apply_ita_patches.ps1)
      4. configure ITAGeometricalAcoustics, verify the dependency lock, build (Release)
      5. configure + build the nanobind module in bindings/
      6. copy _art_core*.pyd and the ITA DLLs into bin/

    Windows x64 only, and it requires the Visual Studio 2019 Build Tools
    (MSVC v142). ITA's CMake preset hard-codes the 'Visual Studio 16 2019'
    generator, so no other Visual Studio version works. The resulting .pyd is
    tied to the Python minor version used to build it.

    Step 4 is long (it fetches and compiles assimp, OpenMesh, netcdf, HDF5,
    Vista and more) and needs several GB of disk. Use -SkipIta to rebuild only
    the bindings against an existing ITA build.

.PARAMETER Preset
    ITA CMake configure preset. Default 'full-win-vs-msvc'.

.PARAMETER SkipIta
    Skip steps 2-4 and reuse the existing ITA build tree.

.PARAMETER Clean
    Delete the bindings build tree before configuring.

.PARAMETER CleanIta
    Delete the ITA build tree (ITAGeometricalAcoustics/out/build/<preset>)
    before configuring, so ITA is configured and rebuilt from scratch. Needed
    after an INTERRUPTED first configure; see the note in the script.

.EXAMPLE
    powershell -ExecutionPolicy Bypass -File tools/build_art.ps1

.EXAMPLE
    powershell -ExecutionPolicy Bypass -File tools/build_art.ps1 -SkipIta
#>
[CmdletBinding()]
param(
    [string]$Preset = 'full-win-vs-msvc',
    [switch]$SkipIta,
    [switch]$Clean,
    [switch]$CleanIta
)

$ErrorActionPreference = 'Stop'

$RepoRoot = Split-Path -Parent $PSScriptRoot
$ItaRoot = Join-Path $RepoRoot 'ITAGeometricalAcoustics'
$ItaBuild = Join-Path $ItaRoot "out\build\$Preset"
$BindingsDir = Join-Path $RepoRoot 'bindings'
$BindingsBuild = Join-Path $BindingsDir 'build'
$BinDir = Join-Path $RepoRoot 'bin'

function Invoke-Step {
    param([string]$Name, [scriptblock]$Body)
    Write-Host ''
    Write-Host "=== $Name" -ForegroundColor Cyan
    & $Body
    if ($LASTEXITCODE -ne 0 -and $null -ne $LASTEXITCODE) {
        throw "$Name failed (exit $LASTEXITCODE)"
    }
}

# --- 1. Tool checks -------------------------------------------------------
Write-Host '=== Checking prerequisites' -ForegroundColor Cyan
foreach ($exe in 'git', 'cmake') {
    $cmd = Get-Command $exe -ErrorAction SilentlyContinue
    if (-not $cmd) { throw "'$exe' not found on PATH." }
    Write-Host "  $exe : $($cmd.Source)"
}

# ITA's preset uses the 'Visual Studio 16 2019' generator. Find that exact toolset.
$vswhere = Join-Path ${env:ProgramFiles(x86)} 'Microsoft Visual Studio\Installer\vswhere.exe'
$vs2019 = $null
if (Test-Path $vswhere) {
    $vs2019 = & $vswhere -version '[16.0,17.0)' -products * `
        -requires Microsoft.VisualStudio.Component.VC.Tools.x86.x64 -property installationPath |
        Select-Object -First 1
}
if (-not $vs2019) {
    throw @"
Visual Studio 2019 with the C++ toolset was not found.

ART is built with Visual Studio 2019 (MSVC v142) - the version it was developed
and tested with, and the one ITA's CMake preset requires. Install the
'Build Tools for Visual Studio 2019' and select the workload
'Desktop development with C++' (MSVC v142 - VS 2019 C++ x64/x86 build tools).
"@
}
Write-Host "  Visual Studio 2019 : $vs2019"

$python = Get-Command python -ErrorAction SilentlyContinue
if (-not $python) { throw "'python' not found on PATH. Activate your virtual environment first." }
$pyVer = (& python -c "import sys; print('%d.%d' % sys.version_info[:2])")
Write-Host "  python : $($python.Source) (Python $pyVer)"

& python -c 'import nanobind' 2>$null
if ($LASTEXITCODE -ne 0) {
    throw "nanobind is not installed for this interpreter. Run: pip install -r requirements-build.txt"
}
Write-Host '  nanobind : ok'

if (-not $SkipIta) {
    # --- 2. Submodules ---------------------------------------------------
    Invoke-Step 'Updating submodules' {
        Push-Location $RepoRoot
        try { & git submodule update --init --recursive } finally { Pop-Location }
    }

    # --- 3. Patches ------------------------------------------------------
    Invoke-Step 'Applying ITA patches' {
        & powershell -NoProfile -ExecutionPolicy Bypass -File (Join-Path $PSScriptRoot 'apply_ita_patches.ps1')
    }

    # --- 4. Build ITA ----------------------------------------------------
    if ($CleanIta -and (Test-Path $ItaBuild)) {
        Write-Host "Removing $ItaBuild" -ForegroundColor DarkGray
        Remove-Item -Recurse -Force $ItaBuild
    }

    # CMake re-runs the PATCH step of every patched dependency (vista, nanoflann,
    # netcdf-c, netcdf-cxx4, reflect-cpp) each time it configures, and a patch
    # cannot be applied twice, so re-configuring a tree whose dependencies are
    # already downloaded fails with "Reversed (or previously applied) patch
    # detected". For a tree that has been configured before, run in local-only
    # mode instead: nothing is fetched or patched again. A tree counts as
    # configured if an earlier run finished configuring it (the stamp file) or if
    # it has already produced the ITA libraries.
    $itaStamp = Join-Path $ItaBuild '.configured-ok'
    $itaLib = Join-Path $ItaBuild 'Release\lib\ITAGeo.lib'
    $localOnly = @()
    if ((Test-Path $itaStamp) -or (Test-Path $itaLib)) {
        Write-Host '  ITA was configured before: re-configuring in local-only mode' -ForegroundColor DarkGray
        $localOnly = @('-DFETCHCONTENT_FULLY_DISCONNECTED=ON')
    }

    try {
        Invoke-Step "Configuring ITAGeometricalAcoustics (preset $Preset)" {
            Push-Location $ItaRoot
            try { & cmake --preset $Preset @localOnly } finally { Pop-Location }
        }
    }
    catch {
        Write-Host ''
        Write-Host 'ITA configuration failed.' -ForegroundColor Red
        Write-Host 'If an EARLIER configure was interrupted (network error, Ctrl+C) and the message above' -ForegroundColor Yellow
        Write-Host 'mentions "previously applied" patches, the half-finished tree cannot be reused:' -ForegroundColor Yellow
        Write-Host '  rerun with -CleanIta to configure ITA from scratch.' -ForegroundColor Yellow
        throw
    }
    Invoke-Step 'Verifying the dependency lock' {
        & python (Join-Path $PSScriptRoot 'verify_dependency_lock.py') $ItaBuild
        if ($LASTEXITCODE -ne 0) {
            throw 'Fetched dependencies differ from patches/ita/dependency-lock.json. See BUILD.md, "Reproducibility".'
        }
    }
    # Configure + lock verified: later runs may re-configure in local-only mode.
    Set-Content -Path $itaStamp -Value (Get-Date -Format s)
    Invoke-Step 'Building the ITA libraries ART needs (Release) - this takes a while' {
        Push-Location $ItaRoot
        # Only the two libraries the bindings link against. Everything else ART
        # needs (ITABase, Vista, OpenMesh, assimp, DAFF, ...) is built as their
        # dependency. Building ALL of ITA also builds apps and netcdf-cxx4, which
        # ART does not use and which does not compile in this configuration.
        try { & cmake --build $ItaBuild --config Release --target ITAGeo ITAPropagationPathSim } finally { Pop-Location }
    }
}

$itaLibDir = Join-Path $ItaBuild 'Release\lib'
$itaBinDir = Join-Path $ItaBuild 'Release\bin'
if (-not (Test-Path $itaLibDir)) {
    throw "ITA import libraries not found in $itaLibDir. Build ITA first (drop -SkipIta)."
}

# --- 5. Build the bindings -----------------------------------------------
if ($Clean -and (Test-Path $BindingsBuild)) {
    Write-Host "Removing $BindingsBuild" -ForegroundColor DarkGray
    Remove-Item -Recurse -Force $BindingsBuild
}

Invoke-Step 'Configuring _art_core bindings' {
    Push-Location $BindingsDir
    try {
        # Same generator as ITA (Visual Studio 2019) so the module and the ITA
        # DLLs are built by the same MSVC toolset.
        # Python_EXECUTABLE makes CMake use the interpreter that is first on PATH
        # (your activated virtual environment). Without it CMake may pick a
        # different Python from the registry and build the module for the wrong
        # Python version.
        & cmake -B build -G 'Visual Studio 16 2019' -A x64 -DCMAKE_BUILD_TYPE=Release `
            "-DPython_EXECUTABLE=$($python.Source)" `
            "-DITA_ROOT=$ItaRoot" "-DITA_BUILD_DIR=$ItaBuild"
    }
    finally { Pop-Location }
}
Invoke-Step 'Building _art_core' {
    Push-Location $BindingsDir
    try { & cmake --build build --config Release } finally { Pop-Location }
}

# --- 6. Stage into bin/ ---------------------------------------------------
Write-Host ''
Write-Host '=== Staging into bin/' -ForegroundColor Cyan

$pyd = Get-ChildItem -Path $BindingsBuild -Recurse -Filter '_art_core*.pyd' -ErrorAction SilentlyContinue |
    Sort-Object LastWriteTime -Descending | Select-Object -First 1
if (-not $pyd) { throw "No _art_core*.pyd was produced under $BindingsBuild." }

if (-not (Test-Path $BinDir)) { New-Item -ItemType Directory -Path $BinDir | Out-Null }

Copy-Item $pyd.FullName -Destination $BinDir -Force
Write-Host "  $($pyd.Name)"

$dlls = Get-ChildItem -Path $itaBinDir -Filter '*.dll' -ErrorAction SilentlyContinue
if (-not $dlls) { throw "No DLLs found in $itaBinDir." }
foreach ($dll in $dlls) {
    Copy-Item $dll.FullName -Destination $BinDir -Force
    Write-Host "  $($dll.Name)"
}

# --- Verify --------------------------------------------------------------
Write-Host ''
Write-Host '=== Verifying' -ForegroundColor Cyan
Push-Location $RepoRoot
try {
    & python -c "from auralization.private.propagation.art_bindings import art_core_available; import sys; ok=art_core_available(); print('  _art_core importable:', ok); sys.exit(0 if ok else 1)"
    if ($LASTEXITCODE -ne 0) { throw 'Built, but _art_core could not be imported.' }
}
finally { Pop-Location }

Write-Host ''
Write-Host "Done. ART staged in $BinDir (Python $pyVer, win-amd64)." -ForegroundColor Green
Write-Host 'bin/ is gitignored. To update the committed binaries, see BUILD.md.' -ForegroundColor DarkGray
