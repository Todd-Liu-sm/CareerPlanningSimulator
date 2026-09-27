# 界面走查 + 截图。
#
# 跑法：powershell -File tools/test_visual.ps1
#
# 为什么不用 Ren'Py 的 test 框架：它在 headless 下会卡死（见 game/testcases.rpy 顶部说明）。
# 这里改为启动游戏并设 DSH_SELFCHECK=1，由 game/script.rpy 里的 label selfcheck
# 把每个界面渲染出来、截图、然后自己退出。
#
# 产物：tests/screenshots/*.png + selfcheck_report.txt

param(
    [switch]$EndingOnly,
    [int]$TimeoutSeconds = 90
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

# 先清掉上一轮的进程，避免抢窗口
Get-Process renpy -ErrorAction SilentlyContinue | Stop-Process -Force -ErrorAction SilentlyContinue
Start-Sleep -Milliseconds 400

$env:DSH_SELFCHECK = '1'
if ($EndingOnly) { $env:DSH_SELFCHECK_ENDING = '1' } else { Remove-Item Env:DSH_SELFCHECK_ENDING -ErrorAction SilentlyContinue }
$env:PYTHONUTF8 = '1'
$env:PYTHONIOENCODING = 'utf-8'

# 自检必须在真实视频驱动下跑：dummy 驱动画不出帧，截图全是空的。
# 代价是会闪一个窗口。
Remove-Item Env:SDL_VIDEODRIVER -ErrorAction SilentlyContinue
Remove-Item Env:SDL_AUDIODRIVER -ErrorAction SilentlyContinue

$mode = if ($EndingOnly) { "只跑到结局" } else { "全部界面" }
Write-Output "界面走查（$mode），最多等 $TimeoutSeconds 秒..."

$shots = Join-Path $root "tests/screenshots"
Start-Process -FilePath (Join-Path $sdk.FullName "renpy.exe") -ArgumentList "`"$root`"" -NoNewWindow
Start-Sleep -Seconds $TimeoutSeconds
Get-Process renpy -ErrorAction SilentlyContinue | Stop-Process -Force -ErrorAction SilentlyContinue

Write-Output ""
Write-Output "--- selfcheck_report.txt ---"
$report = Join-Path $shots "selfcheck_report.txt"
if (Test-Path $report) {
    Get-Content $report -Encoding UTF8
} else {
    Write-Output "（没有报告。检查 traceback.txt / game/errors.log）"
}

Write-Output ""
Write-Output "--- 截图 ---"
$pngs = Get-ChildItem $shots -Filter "*.png" -ErrorAction SilentlyContinue | Sort-Object Name
if ($pngs) {
    $pngs | Format-Table Name, @{ n = 'KB'; e = { [math]::Round($_.Length / 1KB, 1) } } -AutoSize
    Write-Output ("共 {0} 张，目录：{1}" -f $pngs.Count, $shots)
} else {
    Write-Output "没有截图。"
    exit 1
}

# 失败的条目当成错误上报，方便 CI 用
$failed = @()
if (Test-Path $report) {
    $failed = Select-String -Path $report -Pattern "FAILED|MISSING" -Encoding UTF8
}
if ($failed) {
    Write-Output ""
    Write-Output "有失败项："
    $failed | ForEach-Object { Write-Output ("  " + $_.Line) }
    exit 1
}

Write-Output "全部通过。"
exit 0
