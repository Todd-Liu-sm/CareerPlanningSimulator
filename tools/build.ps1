# Build the Windows release: a clean zip plus an unpacked folder.
#
#   powershell -File tools/build.ps1
#
# Output (all under dist/):
#   <name>-<version>-pc/                  unpacked, ready to run
#   <name>-<version>-win64.zip            clean zip (no dev files)
#
# There is deliberately NO setup.exe.
#
# There used to be one: a C# stub with the zip appended as a trailer, which
# extracted to %LOCALAPPDATA% and dropped a desktop shortcut. It was removed
# because an unsigned self-extracting exe is exactly the shape of thing Windows
# and third-party security software like to interrogate, so players hit security
# prompts before they ever reached the game. The portable zip unpacks and runs
# with nothing in the way, which is all this project needs.
#
# If an installer is ever wanted again, `git show 4c3d038:tools/installer_stub.cs`
# has the stub and the commit before this one has the ~70 lines that drove it.
#
# --------------------------------------------------------------------------
# KEEP THIS FILE PURE ASCII.
#
# Windows PowerShell 5.1 reads BOM-less files as the system codepage (GBK on a
# Chinese Windows). Non-ASCII literals then get mis-decoded and the parser fails
# with confusing errors like "Missing closing '}'". Since any tool that rewrites
# this file may drop the BOM, the only robust rule is: no Chinese in .ps1.
# --------------------------------------------------------------------------
#
# Why this script post-processes Ren'Py's output instead of using build.classify:
#
#   Ren'Py 8.5 has no build.classify at all, and the launcher's `distribute`
#   command (whose basedir must be the SDK's launcher dir, NOT the project) packs
#   the ENTIRE project directory. That means tools/, tests/, docs/, .renpy-sdk/
#   and the 155 MB SDK zip all land in the player's download.
#
#   Earlier attempts to shape this via classify-style patterns all failed
#   SILENTLY: one build shipped a zip with no game data, another ballooned to
#   353 MB. So instead we let Ren'Py pack everything, then strip the dev-only
#   entries out of the extracted result, rebuild the zip ourselves, and verify.

param(
    [string]$Destination = "dist"
)

$ErrorActionPreference = 'Stop'
$root = Split-Path -Parent $PSScriptRoot
Set-Location $root

# ---------------------------------------------------------------- locate SDK

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
Start-Sleep -Milliseconds 800

# Pre-flight: refuse to start if a Ren'Py process survived (a leftover one holds
# the launcher lock and makes distribute return immediately with no output).
$still = Get-Process renpy -ErrorAction SilentlyContinue
if ($still) {
    Write-Output "A Ren'Py process is still running (pid $($still.Id -join ', ')); kill it and retry."
    exit 1
}

# __pycache__ would ride along into the distribution; drop it up front.
$cacheDirs = Get-ChildItem (Join-Path $root "game") -Recurse -Directory -Filter "__pycache__" -ErrorAction SilentlyContinue
foreach ($dir in $cacheDirs) { Remove-Item -Recurse -Force $dir.FullName -ErrorAction SilentlyContinue }

# ---------------------------------------------------------------- read version

$optionsText = Get-Content (Join-Path $root "game/options.rpy") -Raw -Encoding UTF8
$versionMatch = [regex]::Match($optionsText, 'config\.version\s*=\s*"([^"]+)"')
if (-not $versionMatch.Success) {
    Write-Output "Could not read config.version from game/options.rpy"
    exit 1
}
$version = $versionMatch.Groups[1].Value
$appName = [char]0x672C + [char]0x79D1 + [char]0x804C + [char]0x4E1A + [char]0x53D1 + [char]0x5C55 + [char]0x6A21 + [char]0x62DF + [char]0x5668
# ^ the game title, built from codepoints so this file stays ASCII.

Write-Output ("Building " + $appName + " " + $version)

$destPath = Join-Path $root $Destination
New-Item -ItemType Directory -Force -Path $destPath | Out-Null

# Pre-flight: nothing may be running FROM dist/.
#
# This is not hypothetical. A copy launched out of dist/ holds an open handle on
# game/fonts/*.otf. The failure surfaces much later as "The process cannot access
# the file ... because it is being used by another process" from Compress-Archive,
# and by then the whole build has been wasted.
#
# Scope matters: only processes whose executable lives under dist/ are a problem.
# Do NOT match on process name -- the player may legitimately be running an
# installed copy from somewhere else (e.g. D:\game\...), and refusing to build
# because of that is just wrong.
$busy = @()
foreach ($proc in (Get-Process -ErrorAction SilentlyContinue)) {
    if ($proc.Id -eq $PID) { continue }
    $path = $null
    try { $path = $proc.Path } catch { continue }
    if (-not $path) { continue }
    if ($path.StartsWith($destPath, [StringComparison]::OrdinalIgnoreCase)) { $busy += $proc }
}
if ($busy.Count -gt 0) {
    Write-Output "These processes are running out of dist/ -- close them and retry:"
    foreach ($proc in $busy) {
        Write-Output ("  pid " + $proc.Id + "  " + $proc.ProcessName)
    }
    exit 1
}

# OneDrive (or any sync client) can hold a transient handle on a fresh dist/ tree.
# Nothing we can do about it up front, so just give it a moment.
Start-Sleep -Milliseconds 500

$rawDir = Join-Path $root ".tools/build_raw"
Remove-Item -Recurse -Force $rawDir -ErrorAction SilentlyContinue
New-Item -ItemType Directory -Force -Path $rawDir | Out-Null

# ---------------------------------------------------------------- run Ren'Py

$env:SDL_VIDEODRIVER = 'dummy'
$env:SDL_AUDIODRIVER = 'dummy'
$env:PYTHONUTF8 = '1'
$env:PYTHONIOENCODING = 'utf-8'

$renpyExe = Join-Path $sdk.FullName "renpy.exe"
$launcherDir = Join-Path $sdk.FullName "launcher"

$renpyArgs = @($launcherDir, "distribute", $root, "--destination", $rawDir, "--package", "pc")
if (Test-Path (Join-Path $root "icon.ico")) {
    Write-Output "Using icon.ico for the exe."
} else {
    Write-Output "WARNING: no icon.ico at project root; the exe will use the default Ren'Py icon."
}

Write-Output "Packing with Ren'Py (about 30 seconds)..."

# Run Ren'Py as a tracked process and WAIT for it to actually exit.
#
# Why not just `& $renpyExe @renpyArgs`: renpy.exe relaunches itself as a GUI
# subsystem process, so the call returns while the real work is still going --
# the zip only appears at the very end of the run. That made an earlier version
# of this script report "no zip produced" and bail out before the build finished
# (the file showed up seconds later). Start-Process -Wait -PassThru blocks until
# the process tree is done, which is what we actually need.
$proc = Start-Process -FilePath $renpyExe -ArgumentList $renpyArgs -NoNewWindow -PassThru -Wait
$code = $proc.ExitCode

$rawZips = @(Get-ChildItem $rawDir -Filter "*.zip" -ErrorAction SilentlyContinue)
if ($rawZips.Count -eq 0) {
    Write-Output ("Ren'Py produced no zip (exit code " + $code + "); cannot continue.")
    exit 1
}
Write-Output ("Ren'Py produced: " + $rawZips[0].Name)

# ---------------------------------------------------------------- extract

$extractDir = Join-Path $root ".tools/build_extract"
Remove-Item -Recurse -Force $extractDir -ErrorAction SilentlyContinue
Expand-Archive -LiteralPath $rawZips[0].FullName -DestinationPath $extractDir -Force

$inner = Get-ChildItem $extractDir -Directory | Select-Object -First 1
if (-not $inner) {
    Write-Output "Extracted archive has no top-level folder."
    exit 1
}
$staging = Join-Path $root ".tools/build_clean"
Remove-Item -Recurse -Force $staging -ErrorAction SilentlyContinue
Move-Item -LiteralPath $inner.FullName -Destination $staging

# ---------------------------------------------------------------- strip dev files

# Everything here is development-only and must not reach players.
#
# **Build outputs must be in this list too.** Ren'Py 8.5 has no build.classify
# (see the top of this file), so `distribute` packs the WHOLE project directory
# via its catch-all `("**", "all")` rule -- including `dist/` itself. That is not
# hypothetical: building twice in a row put the previous release folder and its
# 45 MB zip INSIDE the new zip, taking it from 43 MB to 130 MB. Nothing failed;
# the size check is the only thing that caught it.
$devEntries = @(
    ".renpy-sdk", ".renpy-dl", ".tools", ".git", ".gitignore",
    "tools", "tests", "docs",
    "idea.txt", "README.md", "requirement.md",
    "log.txt", "errors.txt", "traceback.txt", "icon.ico",
    "dist", "build-out", ".vscode", ".idea", "node_modules"
)

# ...plus whatever directory this run is writing to, in case it is something else.
$destLeaf = Split-Path -Leaf $destPath
if ($destLeaf -and $destLeaf -ne ".") { $devEntries += $destLeaf }

$removed = @()
foreach ($entry in $devEntries) {
    $target = Join-Path $staging $entry
    if (Test-Path $target) {
        Remove-Item -Recurse -Force $target -ErrorAction SilentlyContinue
        $removed += $entry
    }
}

# Also sweep stray dev artifacts anywhere in the tree.
Get-ChildItem $staging -Recurse -Directory -ErrorAction SilentlyContinue |
    Where-Object { $_.Name -in @("__pycache__", ".pytest_cache") } |
    ForEach-Object { Remove-Item -Recurse -Force $_.FullName -ErrorAction SilentlyContinue }
Get-ChildItem $staging -Recurse -File -ErrorAction SilentlyContinue |
    Where-Object { $_.Name -in @("errors.log", "log.txt", "traceback.txt") -or $_.Extension -eq ".pyo" } |
    ForEach-Object { Remove-Item -Force $_.FullName -ErrorAction SilentlyContinue }

Write-Output ("Stripped dev entries: " + ($removed -join ", "))

# ---------------------------------------------------------------- assemble outputs

$unpackedName = $appName + "-" + $version + "-pc"
$unpackedDir = Join-Path $destPath $unpackedName
Remove-Item -Recurse -Force $unpackedDir -ErrorAction SilentlyContinue
Move-Item -LiteralPath $staging -Destination $unpackedDir

# A short readme inside the release folder, so the player knows what to click.
$readmeSrc = @(
    ($appName + " " + $version),
    "",
    ("Double-click " + $appName + ".exe to play."),
    "",
    "No install, no Python, no runtime, no network needed.",
    "Save files go to your user profile, next to the game title.",
    "",
    "Controls: mouse. Esc opens the menu, F toggles fullscreen."
) -join "`r`n"
# The lines above are ASCII; the app name is inserted from codepoints.
Set-Content -LiteralPath (Join-Path $unpackedDir "PLAY.txt") -Value $readmeSrc -Encoding UTF8

$zipName = $appName + "-" + $version + "-win64.zip"
$zipPath = Join-Path $destPath $zipName
Remove-Item -Force $zipPath -ErrorAction SilentlyContinue
Compress-Archive -Path (Join-Path $unpackedDir "*") -DestinationPath $zipPath -CompressionLevel Optimal

# ---------------------------------------------------------------- verify

Write-Output ""
Write-Output "--- verification ---"

$exeName = $appName + ".exe"
$checks = [ordered]@{}
$checks["exe present"]      = Test-Path (Join-Path $unpackedDir $exeName)
$checks["lib present"]      = Test-Path (Join-Path $unpackedDir "lib")
$checks["game data present"] = Test-Path (Join-Path $unpackedDir "game")

$coreCount = @(Get-ChildItem (Join-Path $unpackedDir "game/core") -Filter "*.py" -ErrorAction SilentlyContinue).Count
$rpycCount = @(Get-ChildItem (Join-Path $unpackedDir "game") -Filter "*.rpyc" -ErrorAction SilentlyContinue).Count
$fontCount = @(Get-ChildItem (Join-Path $unpackedDir "game/fonts") -Filter "NotoSansSC*" -ErrorAction SilentlyContinue).Count

$checks["core/*.py ($coreCount)"] = $coreCount -ge 8
$checks[".rpyc ($rpycCount)"]     = $rpycCount -ge 5
$checks["CJK font ($fontCount)"]  = $fontCount -ge 1

# Dev leakage must be zero in BOTH the folder and the zip.
#
# This list must stay in sync with $devEntries above. The size check below is a
# backstop: anything that sneaks past BOTH of them shows up as a fat zip.
$leakNames = @("tools", "tests", "docs", ".renpy-sdk", ".renpy-dl", "idea.txt",
               "README.md", "requirement.md", "dist", "build-out", $destLeaf)
$leaks = @(Get-ChildItem $unpackedDir -Force -ErrorAction SilentlyContinue |
    Where-Object { $_.Name -in $leakNames })
$checks["no dev leakage"] = ($leaks.Count -eq 0)

$zipMB = [math]::Round((Get-Item $zipPath).Length / 1MB, 1)
$checks["zip size sane ($zipMB MB)"] = ($zipMB -gt 20 -and $zipMB -lt 120)
$checks["zip built"] = (Test-Path $zipPath)

# No setup.exe should ever appear again; if one does, something re-added it.
$straySetup = @(Get-ChildItem $destPath -Filter "*-setup.exe" -ErrorAction SilentlyContinue)
$checks["no setup.exe (portable only)"] = ($straySetup.Count -eq 0)

$failed = @()
foreach ($key in $checks.Keys) {
    $mark = if ($checks[$key]) { "OK  " } else { "FAIL" }
    if (-not $checks[$key]) { $failed += $key }
    Write-Output ("  " + $mark + "  " + $key)
}

if ($leaks.Count -gt 0) {
    Write-Output "  leaked entries:"
    foreach ($item in $leaks) { Write-Output ("    - " + $item.Name) }
}

Write-Output ""
Write-Output "--- dist ---"
Get-ChildItem $destPath -Force | ForEach-Object {
    if ($_.PSIsContainer) {
        $size = [math]::Round((Get-ChildItem $_.FullName -Recurse -File | Measure-Object -Property Length -Sum).Sum / 1MB, 1)
        Write-Output ("  [dir] " + $_.Name + "   " + $size + " MB")
    } else {
        Write-Output ("        " + $_.Name + "   " + [math]::Round($_.Length / 1MB, 2) + " MB")
    }
}

# ---------------------------------------------------------------- clean scratch

Remove-Item -Recurse -Force $rawDir, $extractDir -ErrorAction SilentlyContinue

if ($failed.Count -gt 0) {
    Write-Output ""
    Write-Output "VERIFY FAILED"
    foreach ($item in $failed) { Write-Output ("  - " + $item) }
    exit 1
}

Write-Output ""
Write-Output "VERIFY OK"
exit 0
