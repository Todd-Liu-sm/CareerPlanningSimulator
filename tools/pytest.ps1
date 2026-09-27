# 跑 pytest（纯 Python 内核测试）。
#
# 依赖装在 .tools/pylibs 里（不污染系统 Python）。
# 用法：
#   powershell -File tools/pytest.ps1                       # 全部
#   powershell -File tools/pytest.ps1 tests/test_effects.py
#   powershell -File tools/pytest.ps1 tests -q --cov=game/core

$ErrorActionPreference = 'Stop'
$root = Split-Path -Parent $PSScriptRoot
Set-Location $root

$libs = Join-Path $root ".tools/pylibs"
if (-not (Test-Path $libs)) {
    Write-Output "缺少 .tools/pylibs，先装测试依赖："
    Write-Output "  python -m pip install --target .tools/pylibs pytest coverage"
    exit 1
}

$env:PYTHONPATH = $libs
$env:PYTHONIOENCODING = 'utf-8'
$env:PYTHONUTF8 = '1'

$targets = if ($args.Count -gt 0) { $args } else { @('tests', '-q') }
& python -m pytest @targets
exit $LASTEXITCODE
