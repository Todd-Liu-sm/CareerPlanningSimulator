# Run the automated UI walkthrough and capture screenshots.
#
#   powershell -File tools/run_tests.ps1                 # all screens
#   powershell -File tools/run_tests.ps1 -EndingOnly     # just the ending screen
#
# --------------------------------------------------------------------------
# KEEP THIS FILE ASCII-ONLY. Windows PowerShell 5.1 reads BOM-less files as the
# system codepage (GBK here), which mangles non-ASCII literals and can break the
# parser. Every tool that rewrites a .ps1 may drop the BOM, so the safe rule is
# no Chinese in .ps1 files.
# --------------------------------------------------------------------------
#
# Why this is a thin wrapper around test_visual.ps1 instead of Ren'Py's `test`
# command: the Ren'Py test framework hangs under headless (SDL dummy) drivers --
# repeated "ui.interact called with non-empty widget/layer stack" followed by an
# indefinite wait. The working approach is the in-game self-check
# (DSH_SELFCHECK / DSH_SELFCHECK_ENDING, see game/script.rpy label selfcheck),
# which renders each screen, screenshots it, and quits on its own.
#
# Note the test-framework id separator is '::' not '.', if it is ever used again:
#   global::screens::startup   correct
#   global.screens.startup     "TestCase not found"

param(
    [switch]$EndingOnly,
    [int]$TimeoutSeconds = 70
)

$ErrorActionPreference = 'Stop'

$forward = @('-NoProfile', '-ExecutionPolicy', 'Bypass',
             '-File', (Join-Path $PSScriptRoot 'test_visual.ps1'),
             '-TimeoutSeconds', "$TimeoutSeconds")
if ($EndingOnly) { $forward += '-EndingOnly' }

& powershell @forward
exit $LASTEXITCODE
