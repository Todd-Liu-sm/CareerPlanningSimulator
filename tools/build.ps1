# 打包成 Windows 发行版。
#
# 用法：
#   powershell -File tools/build.ps1
#   powershell -File tools/build.ps1 -Package win   # 指定包名
#
# 产物落在 dist/。默认出 zip（解压即玩）。Ren'Py 8.5 的 zip 包是最稳的分发形态，
# 对外发布时把它作为「绿色版」给玩家即可。

param(
    [string[]]$Package = @("pc"),
    [string]$Destination = "dist",
    [string]$Format = "zip"
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

$destPath = Join-Path $root $Destination
New-Item -ItemType Directory -Force -Path $destPath | Out-Null

$env:SDL_VIDEODRIVER = 'dummy'
$env:SDL_AUDIODRIVER = 'dummy'
$env:PYTHONUTF8 = '1'
$env:PYTHONIOENCODING = 'utf-8'

$args = @("launcher", "distribute", $root, "--destination", $destPath)
foreach ($p in $Package) { $args += @("--package", $p) }
if ($Format) { $args += @("--format", $Format) }

Write-Output "打包中：renpy.exe $($args -join ' ')"
Write-Output ""

$renpy = Join-Path $sdk.FullName "renpy.exe"
& $renpy @args
$code = $LASTEXITCODE

Write-Output ""
Write-Output "--- dist/ 产物 ---"
if (Test-Path $destPath) {
    Get-ChildItem -Recurse -Path $destPath | Where-Object { -not $_.PSIsContainer } |
        Sort-Object Name |
        Format-Table Name, @{ n = 'MB'; e = { [math]::Round($_.Length / 1MB, 2) } }, LastWriteTime -AutoSize
} else {
    Write-Output "（没有产物。检查 build.name / build.package 配置，或者先跑一次 lint）"
}

Write-Output "exit $code"
exit $code
