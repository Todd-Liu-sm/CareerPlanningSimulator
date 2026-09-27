# 跑 Ren'Py 的 lint（脚本静态检查）。退出码非 0 表示有问题。
#
# 用法：powershell -File tools/lint.ps1

$ErrorActionPreference = 'Stop'
$root = Split-Path -Parent $PSScriptRoot
Set-Location $root

$sdk = Get-ChildItem (Join-Path $root ".renpy-sdk") -Directory -ErrorAction SilentlyContinue |
    Where-Object { Test-Path (Join-Path $_.FullName "renpy.exe") } |
    Select-Object -First 1

if (-not $sdk) {
    Write-Output "找不到 Ren'Py SDK，先跑 tools/setup_renpy.ps1"
    exit 1
}

$env:SDL_VIDEODRIVER = 'dummy'
$env:SDL_AUDIODRIVER = 'dummy'
$env:PYTHONUTF8 = '1'
$env:PYTHONIOENCODING = 'utf-8'

& (Join-Path $sdk.FullName "renpy.exe") $root lint --error-code --check-unclosed-tags
$code = $LASTEXITCODE
Write-Output ""
if ($code -eq 0) { Write-Output "lint 通过 (exit 0)" } else { Write-Output "lint 失败 (exit $code)" }
exit $code
