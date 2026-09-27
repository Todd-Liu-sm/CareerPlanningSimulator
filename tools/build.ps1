# Build the Windows release: clean zip, unpacked folder, and an installer.
#
#   powershell -File tools/build.ps1
#   powershell -File tools/build.ps1 -SkipInstaller
#
# Output (all under dist/):
#   <name>-<version>-pc/                  unpacked, ready to run
#   <name>-<version>-win64.zip            clean zip (no dev files)
#   <name>-<version>-setup.exe            self-extracting installer
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
    [switch]$SkipInstaller,
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
$devEntries = @(
    ".renpy-sdk", ".renpy-dl", ".tools", ".git", ".gitignore",
    "tools", "tests", "docs",
    "idea.txt", "README.md", "requirement.md",
    "log.txt", "errors.txt", "traceback.txt", "icon.ico"
)

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

# ---------------------------------------------------------------- installer
#
# A single self-contained setup .exe: a small C# stub (tools/installer_stub.cs)
# compiled with the csc.exe that ships with Windows, with the game zip appended
# as a trailer. Running it extracts to %LOCALAPPDATA%, makes a desktop shortcut,
# and offers to launch.
#
# Why not IExpress: it fails silently with /Q (exit 1, no output) and its SED
# format mishandles non-ASCII paths -- which this project's folder name has.
# csc + an appended payload has no such restriction.

$setupPath = $null
if (-not $SkipInstaller) {
    $setupName = $appName + "-" + $version + "-setup.exe"
    $setupPath = Join-Path $destPath $setupName
    Remove-Item -Force $setupPath -ErrorAction SilentlyContinue

    $csc = $null
    foreach ($candidate in @(
        (Join-Path $env:SystemRoot "Microsoft.NET\Framework64\v4.0.30319\csc.exe"),
        (Join-Path $env:SystemRoot "Microsoft.NET\Framework\v4.0.30319\csc.exe")
    )) {
        if (Test-Path $candidate) { $csc = $candidate; break }
    }

    $stubSrc = Join-Path $root "tools/installer_stub.cs"

    if (-not $csc) {
        Write-Output "csc.exe not found (no .NET Framework); skipping installer."
    } elseif (-not (Test-Path $stubSrc)) {
        Write-Output "tools/installer_stub.cs missing; skipping installer."
    } else {
        # Substitute the placeholders. Done in Python so the non-ASCII game name
        # is handled with a known-correct encoding rather than PowerShell's.
        $subst = Join-Path $root ".tools/installer_build.py"
        @'
import pathlib, sys
src_path, out_path, name, exe = sys.argv[1], sys.argv[2], sys.argv[3], sys.argv[4]
src = pathlib.Path(src_path).read_text(encoding="utf-8")
src = src.replace("__GAME_NAME__", name).replace("__GAME_EXE__", exe)
src = src.replace("__PAYLOAD_ZIP__", "")
pathlib.Path(out_path).write_text(src, encoding="utf-8")
'@ | Set-Content -LiteralPath $subst -Encoding UTF8

        $genCs = Join-Path $root ".tools/installer_gen.cs"
        $genExe = Join-Path $root ".tools/installer_gen.exe"
        Remove-Item -Force $genExe -ErrorAction SilentlyContinue

        & python $subst $stubSrc $genCs $appName ($appName + ".exe")
        if ($LASTEXITCODE -ne 0 -or -not (Test-Path $genCs)) {
            Write-Output "Failed to generate installer source; skipping installer."
        } else {
            $cscArgs = @(
                "/nologo", "/target:winexe", "/optimize+",
                ("/out:" + $genExe),
                "/r:System.IO.Compression.FileSystem.dll",
                "/r:System.Windows.Forms.dll",
                "/r:System.Drawing.dll",
                $genCs
            )
            & $csc @cscArgs | Out-Null
            if (-not (Test-Path $genExe)) {
                Write-Output "csc failed to build the installer stub; skipping installer."
            } else {
                # Append: [zip bytes][8-byte length][magic]  -- must match the C# side.
                $zipBytes = [System.IO.File]::ReadAllBytes($zipPath)
                $magic = [System.Text.Encoding]::ASCII.GetBytes("CSIMPAYLOADv1`0`0`0")
                $lengthBytes = [BitConverter]::GetBytes([int64]$zipBytes.Length)

                $outStream = [System.IO.File]::Create($setupPath)
                try {
                    $stubBytes = [System.IO.File]::ReadAllBytes($genExe)
                    $outStream.Write($stubBytes, 0, $stubBytes.Length)
                    $outStream.Write($zipBytes, 0, $zipBytes.Length)
                    $outStream.Write($lengthBytes, 0, $lengthBytes.Length)
                    $outStream.Write($magic, 0, $magic.Length)
                } finally {
                    $outStream.Close()
                }
                Write-Output ("Installer built: " + $setupName)
            }
        }

        Remove-Item -Force $genCs, $genExe, $subst -ErrorAction SilentlyContinue
    }
}

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
$leakNames = @("tools", "tests", "docs", ".renpy-sdk", ".renpy-dl", "idea.txt", "README.md", "requirement.md")
$leaks = @(Get-ChildItem $unpackedDir -Force -ErrorAction SilentlyContinue |
    Where-Object { $_.Name -in $leakNames })
$checks["no dev leakage"] = ($leaks.Count -eq 0)

$zipMB = [math]::Round((Get-Item $zipPath).Length / 1MB, 1)
$checks["zip size sane ($zipMB MB)"] = ($zipMB -gt 20 -and $zipMB -lt 120)
$checks["zip built"] = (Test-Path $zipPath)

if (-not $SkipInstaller) {
    $checks["installer built"] = ($null -ne $setupPath -and (Test-Path $setupPath))
}

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
