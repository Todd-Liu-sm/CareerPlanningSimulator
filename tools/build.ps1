# Build the Windows distribution.
#
#   powershell -File tools/build.ps1
#   powershell -File tools/build.ps1 -Package pc,sdk
#
# Output goes to dist/.
#
# --------------------------------------------------------------------------
# KEEP THIS FILE PURE ASCII.
#
# Windows PowerShell 5.1 reads BOM-less files as the system codepage (GBK on a
# Chinese Windows). Any non-ASCII literal then gets mis-decoded and can break
# the parser with confusing errors like "Missing closing '}'". Since every tool
# that rewrites this file may drop the BOM, the only robust rule is: no Chinese
# inside .ps1. Chinese output belongs in the game/Python layer.
# --------------------------------------------------------------------------
#
# Correct invocation (learned the hard way): `distribute` is registered by the
# LAUNCHER, not by base Ren'Py, so basedir must point at the SDK launcher dir:
#     renpy.exe <sdk>\launcher distribute <project> --destination <out>
# Using `renpy.exe <project> distribute ...` fails with "Command distribute is unknown".
#
# And: build.classify patterns are relative to game/. Getting them wrong fails
# SILENTLY -- one attempt shipped a zip with no game data at all, another swept
# the whole .renpy-sdk into the zip (353 MB). So this script always extracts the
# produced zip and verifies it. Do not remove that step.

param(
    [string[]]$Package = @("pc"),
    [string]$Destination = "dist",
    [string]$Format = "zip"
)

$ErrorActionPreference = 'Stop'
$root = Split-Path -Parent $PSScriptRoot
Set-Location $root

$sdkRoot = Join-Path $root ".renpy-sdk"
$sdk = $null
if (Test-Path $sdkRoot) {
    $sdk = Get-ChildItem $sdkRoot -Directory |
        Where-Object { Test-Path (Join-Path $_.FullName "launcher\game") } |
        Select-Object -First 1
}
if (-not $sdk) {
    Write-Output "Ren'Py SDK not found. Run tools/setup_renpy.ps1 first."
    exit 1
}

Get-Process renpy -ErrorAction SilentlyContinue | Stop-Process -Force -ErrorAction SilentlyContinue
Start-Sleep -Milliseconds 400

# Drop __pycache__ before packaging: with no classify rule they ride along
# into the distribution (pointless) and pollute the verification below.
$cacheDirs = Get-ChildItem (Join-Path $root "game") -Recurse -Directory -Filter "__pycache__" -ErrorAction SilentlyContinue
foreach ($dir in $cacheDirs) {
    Remove-Item -Recurse -Force $dir.FullName -ErrorAction SilentlyContinue
}

$destPath = Join-Path $root $Destination
New-Item -ItemType Directory -Force -Path $destPath | Out-Null

# Remove a previous zip first: a stale one can be locked by a running process.
Get-ChildItem $destPath -Filter "*.zip" -ErrorAction SilentlyContinue |
    Remove-Item -Force -ErrorAction SilentlyContinue

$env:SDL_VIDEODRIVER = 'dummy'
$env:SDL_AUDIODRIVER = 'dummy'
$env:PYTHONUTF8 = '1'
$env:PYTHONIOENCODING = 'utf-8'

$renpyExe = Join-Path $sdk.FullName "renpy.exe"
$launcherDir = Join-Path $sdk.FullName "launcher"

# Do not name this $args: that is a PowerShell automatic variable.
$renpyArgs = @($launcherDir, "distribute", $root, "--destination", $destPath)
foreach ($p in $Package) { $renpyArgs += @("--package", $p) }
if ($Format) { $renpyArgs += @("--format", $Format) }

Write-Output "Building distribution, this takes about a minute..."

# Ren'Py writes progress/summary lines to stderr. Under
# $ErrorActionPreference = 'Stop', Windows PowerShell 5.1 turns native stderr
# output into a terminating NativeCommandError and the script dies right after
# the build -- before verification ever runs (that is why the verify output
# went missing). Relax the preference around the call only.
$previousPreference = $ErrorActionPreference
$ErrorActionPreference = 'Continue'
& $renpyExe @renpyArgs
$code = $LASTEXITCODE
$ErrorActionPreference = $previousPreference

Write-Output ""
Write-Output "--- dist artifacts ---"
Get-ChildItem -Recurse -Path $destPath -File -ErrorAction SilentlyContinue | ForEach-Object {
    $mb = [math]::Round($_.Length / 1MB, 2)
    Write-Output ("  {0}   {1} MB" -f $_.Name, $mb)
}

# ---------------------------------------------------------------- verify build

$zips = Get-ChildItem $destPath -Filter "*.zip" -ErrorAction SilentlyContinue
if (-not $zips) {
    Write-Output "No zip artifact; skipping verification."
    exit $code
}

$zip = $zips | Sort-Object LastWriteTime -Descending | Select-Object -First 1
$probe = Join-Path $root ".tools/build_probe"
Remove-Item -Recurse -Force $probe -ErrorAction SilentlyContinue

# Expand-Archive cannot overwrite, and the build may still hold the zip, so
# stage a copy first.
$staged = Join-Path $root ".tools/build_stage.zip"
Remove-Item -Force $staged -ErrorAction SilentlyContinue
Copy-Item -LiteralPath $zip.FullName -Destination $staged -Force
Expand-Archive -LiteralPath $staged -DestinationPath $probe -Force
Remove-Item -Force $staged -ErrorAction SilentlyContinue

$coreFiles = Get-ChildItem -Recurse -Path $probe -Filter "*.py" -ErrorAction SilentlyContinue |
    Where-Object { $_.DirectoryName -like "*core*" }
$fontFiles = Get-ChildItem -Recurse -Path $probe -Filter "NotoSansSC*" -ErrorAction SilentlyContinue
$exeFiles = Get-ChildItem -Recurse -Path $probe -Filter "*.exe" -ErrorAction SilentlyContinue
$scriptFiles = Get-ChildItem -Recurse -Path $probe -Filter "*.rpyc" -ErrorAction SilentlyContinue
$sdkLeak = Get-ChildItem -Recurse -Path $probe -Directory -ErrorAction SilentlyContinue |
    Where-Object { $_.Name -in @(".renpy-sdk", ".renpy-dl") }

$coreCount = @($coreFiles).Count
$fontCount = @($fontFiles).Count
$exeCount = @($exeFiles).Count
$scriptCount = @($scriptFiles).Count
$leakCount = @($sdkLeak).Count
$zipMB = [math]::Round($zip.Length / 1MB, 1)

Write-Output ""
Write-Output "--- package verification ---"
Write-Output ("  zip size   : {0} MB" -f $zipMB)
Write-Output ("  exe        : {0}" -f $exeCount)
Write-Output ("  core/*.py  : {0}" -f $coreCount)
Write-Output ("  .rpyc      : {0}" -f $scriptCount)
Write-Output ("  CJK font   : {0}" -f $fontCount)
Write-Output ("  SDK leak   : {0}" -f $leakCount)

Remove-Item -Recurse -Force $probe -ErrorAction SilentlyContinue

$bad = @()
if ($exeCount -lt 1) {
    $bad += 'no exe in package'
}
if ($coreCount -lt 8) {
    $bad += ('only {0} core .py files (expected ~13)' -f $coreCount)
}
if ($scriptCount -lt 5) {
    $bad += ('only {0} .rpyc compiled scripts; scripts were not packaged' -f $scriptCount)
}
if ($fontCount -lt 1) {
    $bad += 'no CJK font in package'
}
if ($leakCount -gt 0) {
    $bad += ('SDK directories leaked into the package ({0})' -f $leakCount)
}
# Size guard: a healthy build is ~45-55 MB. Over 120 MB means a classify rule is
# sweeping the SDK in; under 20 MB means the game data is missing.
if ($zipMB -gt 120) {
    $bad += ('zip is {0} MB; expected ~50 MB, check build.classify rules' -f $zipMB)
}
if ($zipMB -lt 20) {
    $bad += ('zip is only {0} MB; game data is probably missing' -f $zipMB)
}

Write-Output ""
if ($bad.Count -gt 0) {
    Write-Output "VERIFY FAILED"
    foreach ($item in $bad) { Write-Output ("  - " + $item) }
    exit 1
}

Write-Output "VERIFY OK"
exit $code
