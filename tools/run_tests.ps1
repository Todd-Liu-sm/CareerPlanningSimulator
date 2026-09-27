# 跑 Ren'Py 自动化走查。
#
# 用法：
#   powershell -File tools/run_tests.ps1                    # 全部
#   powershell -File tools/run_tests.ps1 -Testcase "global.screens::startup"

param(
    [string]$Testcase = "global.screens"
)

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

Write-Output "跑走查：$Testcase"
# 注意：--hide-execution 的值必须用 = 号连写。
# 写成 `--hide-execution all` 时，argparse 会把后面的工程路径当成它的值，
# 于是 Ren'Py 以为 basedir 叫 "all" 然后报「Base directory ... does not exist」。
& (Join-Path $sdk.FullName "renpy.exe") --enable-all --hide-header --hide-execution=all `
    $root test $Testcase
$code = $LASTEXITCODE

Write-Output ""
Write-Output "--- 走查截图 ---"
$shots = Get-ChildItem -Recurse -Path (Join-Path $root "tests") -Filter "*.png" -ErrorAction SilentlyContinue
if ($shots) {
    $shots | Sort-Object Name | Format-Table Name, @{ n = 'KB'; e = { [math]::Round($_.Length / 1KB, 1) } } -AutoSize
} else {
    Write-Output "（没有截图。检查 testcases.rpy 里有没有 screenshot 语句）"
}

Write-Output "exit $code"
exit $code
