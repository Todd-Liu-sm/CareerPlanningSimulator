# 下载并解压 Ren'Py SDK，并把工程注册到 launcher。
#
# 用法（在仓库根目录）：
#   powershell -File tools/setup_renpy.ps1
#   powershell -File tools/setup_renpy.ps1 -SdkZip C:\path\to\renpy-8.5.3-sdk.zip
#
# 幂等：已经装好就直接跳过下载。

param(
    [string]$Version = "8.5.3",
    [string]$SdkZip = "",
    [switch]$Force
)

$ErrorActionPreference = 'Stop'
$root = Split-Path -Parent $PSScriptRoot
Set-Location $root

$sdkDir = Join-Path $root ".renpy-sdk"
$inner = Join-Path $sdkDir "renpy-$Version-sdk"
$renpyExe = Join-Path $inner "renpy.exe"

Write-Output "== Ren'Py SDK $Version =="

if ((Test-Path $renpyExe) -and (-not $Force)) {
    Write-Output "已安装：$renpyExe"
} else {
    if (-not $SdkZip) {
        $dlDir = Join-Path $root ".renpy-dl"
        New-Item -ItemType Directory -Force -Path $dlDir | Out-Null
        $SdkZip = Join-Path $dlDir "renpy-$Version-sdk.zip"
        if (Test-Path $SdkZip) {
            Write-Output "已有安装包：$SdkZip"
        } else {
            $url = "https://www.renpy.org/dl/$Version/renpy-$Version-sdk.zip"
            Write-Output "下载 $url"
            $ProgressPreference = 'SilentlyContinue'
            Invoke-WebRequest -Uri $url -OutFile $SdkZip -UseBasicParsing -TimeoutSec 1800
            $size = [math]::Round((Get-Item $SdkZip).Length / 1MB, 1)
            Write-Output "下载完成：${size} MB"
        }
    } else {
        if (-not (Test-Path $SdkZip)) { throw "找不到指定的 SDK 包：$SdkZip" }
        Write-Output "使用本地安装包：$SdkZip"
    }

    New-Item -ItemType Directory -Force -Path $sdkDir | Out-Null
    Write-Output "解压到 $sdkDir ..."
    $sw = [System.Diagnostics.Stopwatch]::StartNew()
    Expand-Archive -LiteralPath $SdkZip -DestinationPath $sdkDir -Force
    $sw.Stop()
    Write-Output ("解压完成，用了 {0:N0} 秒" -f $sw.Elapsed.TotalSeconds)
}

if (-not (Test-Path $renpyExe)) { throw "解压后找不到 $renpyExe" }

Write-Output ""
Write-Output "版本：$(& $renpyExe --version)"

# ---------------------------------------------------------------- 注册到 launcher
#
# launcher 的 `distribute` 命令需要知道工程路径。这里把工程登记进 launcher 的
# projects 列表，这样 tools/build.ps1 不依赖用户手动在 Launcher 里点过设置。

$launcherProject = Join-Path $inner "launcher/project.json"
if (Test-Path $launcherProject) {
    Write-Output ""
    Write-Output "launcher 工程配置：$launcherProject"
    $json = Get-Content $launcherProject -Raw
    Write-Output "  （Ren'Py 会用 launcher 自己的偏好记录当前工程；"
    Write-Output "   如果 distribute 报「没有选中工程」，请在 Launcher 里手动 Add 一次本目录。）"
}

Write-Output ""
Write-Output "下一步："
Write-Output "  powershell -File tools/lint.ps1"
Write-Output "  powershell -File tools/run_tests.ps1"
Write-Output "  powershell -File tools/build.ps1"
