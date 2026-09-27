# Check that every character the game renders has a glyph in the bundled font.
#
#   powershell -File tools/font_check.ps1
#   powershell -File tools/font_check.ps1 -All      # also scan comments (noisy)
#
# Catches a real class of bug that lint and the unit tests miss: the bundled
# SourceHanSansLite has no glyph for the middle dot U+00B7, so a contest card
# title like "CCPC<dot>national" rendered with a tofu box on screen. That is
# only visible in a screenshot -- or by reading the font's cmap, which is what
# this does. tools/fix_font_glyphs.py holds the replacement table used to fix
# the ones that were already in the data.
#
# KEEP THIS FILE ASCII-ONLY. Windows PowerShell 5.1 reads BOM-less files as the
# system codepage (GBK here), which mangles non-ASCII literals and can break the
# parser. Only tools that carry an explicit UTF-8 BOM may contain Chinese.

param(
    [switch]$All
)

$ErrorActionPreference = 'Stop'
$root = Split-Path -Parent $PSScriptRoot
Set-Location $root

$libs = Join-Path $root ".tools/pylibs"
if (-not (Test-Path $libs)) {
    Write-Output "Missing .tools/pylibs. Install test deps first:"
    Write-Output "  python -m pip install --target .tools/pylibs pytest coverage fonttools"
    exit 1
}

$env:PYTHONPATH = $libs
$env:PYTHONUTF8 = '1'
$env:PYTHONIOENCODING = 'utf-8'

$pyArgs = @('tools/check_font_coverage.py')
if ($All) { $pyArgs += '--all' }

& python @pyArgs
exit $LASTEXITCODE
