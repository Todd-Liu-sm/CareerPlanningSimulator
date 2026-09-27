# Verify save / load end to end, through real Ren'Py (not just the Python core).
#
#   powershell -File tools/test_save.ps1
#
# Why this needs its own script: the pure-Python tests prove the engine state can
# be serialized, but they cannot catch the failure mode that actually bit us --
# Ren'Py pickles the ENTIRE store, so a stray `import os` inside a label makes
# every save fail with "Could not pickle <module 'os' (frozen)>" while the game
# keeps running normally.
#
# The flow is two process runs, because renpy.load() replaces the execution stack
# instead of returning:
#   run 1  DSH_SAVECHECK=1     build a known state, autosave, manual save, quit
#   run 2  DSH_LOADCHECK=1-1   load that save, compare the restored state
#
# KEEP THIS FILE ASCII-ONLY (PowerShell 5.1 reads BOM-less files as the system
# codepage, which mangles non-ASCII literals).

param(
    [int]$TimeoutSeconds = 30,
    [string]$Slot = "1-1"
)

$ErrorActionPreference = 'Stop'
$root = Split-Path -Parent $PSScriptRoot
Set-Location $root

$sdk = Get-ChildItem (Join-Path $root ".renpy-sdk") -Directory -ErrorAction SilentlyContinue |
    Where-Object { Test-Path (Join-Path $_.FullName "renpy.exe") } |
    Select-Object -First 1
if (-not $sdk) {
    Write-Output "Ren'Py SDK not found. Run tools/setup_renpy.ps1 first."
    exit 1
}
$renpyExe = Join-Path $sdk.FullName "renpy.exe"

$report = Join-Path $root "tests/screenshots/savecheck_report.txt"
$saveDir = Join-Path $env:APPDATA "RenPy/BenKeZhiYeFaZhan-1.0"

# Start from a clean slate so the result cannot be leftover from a previous run.
Remove-Item -Recurse -Force (Join-Path $root "tests/screenshots") -ErrorAction SilentlyContinue
Get-ChildItem $saveDir -Filter "*.save" -ErrorAction SilentlyContinue | Remove-Item -Force -ErrorAction SilentlyContinue

Get-Process renpy -ErrorAction SilentlyContinue | Stop-Process -Force -ErrorAction SilentlyContinue
Start-Sleep -Milliseconds 600

$env:PYTHONUTF8 = '1'
$env:PYTHONIOENCODING = 'utf-8'
Remove-Item Env:SDL_VIDEODRIVER -ErrorAction SilentlyContinue
Remove-Item Env:SDL_AUDIODRIVER -ErrorAction SilentlyContinue

function Run-Game([string]$label) {
    Write-Output ("  " + $label)
    $proc = Start-Process -FilePath $renpyExe -ArgumentList "`"$root`"" -PassThru
    Start-Sleep -Seconds $TimeoutSeconds
    if (-not $proc.HasExited) { Stop-Process -Id $proc.Id -Force -ErrorAction SilentlyContinue }
    Get-Process renpy -ErrorAction SilentlyContinue | Stop-Process -Force -ErrorAction SilentlyContinue
}

Write-Output "--- run 1: build state and save ---"
$env:DSH_SAVECHECK = '1'
Remove-Item Env:DSH_LOADCHECK -ErrorAction SilentlyContinue
Remove-Item Env:DSH_SELFCHECK -ErrorAction SilentlyContinue
Run-Game "savecheck"

$saves = @(Get-ChildItem $saveDir -Filter "*.save" -ErrorAction SilentlyContinue)
Write-Output ("  saves on disk: " + $saves.Count)

Write-Output "--- run 2: load and verify ---"
Remove-Item Env:DSH_SAVECHECK -ErrorAction SilentlyContinue
$env:DSH_LOADCHECK = $Slot
Run-Game "loadcheck"

Write-Output ""
Write-Output "--- savecheck_report.txt ---"
$failed = $false
if (Test-Path $report) {
    # Report validation lives in Python: PowerShell 5.1 mangles UTF-8 Chinese in
    # BOM-less .ps1 files, and the report is Chinese. Keeping the .ps1 ASCII-only
    # avoids a whole class of parser failures.
    & python (Join-Path $PSScriptRoot "check_save_report.py") $report
    if ($LASTEXITCODE -ne 0) { $failed = $true }
} else {
    Write-Output "  report missing -- the check never ran"
    $failed = $true
}

if ($saves.Count -lt 2) {
    Write-Output ("  expected at least 2 save files (manual + autosave), found " + $saves.Count)
    $failed = $true
}

$tb = Join-Path $root "traceback.txt"
if (Test-Path $tb) {
    Write-Output ""
    Write-Output "--- traceback.txt ---"
    Get-Content $tb -TotalCount 25
    $failed = $true
}

Write-Output ""
if ($failed) {
    Write-Output "SAVE CHECK FAILED"
    exit 1
}
Write-Output "SAVE CHECK PASSED"
exit 0
