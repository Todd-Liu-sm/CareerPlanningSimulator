# 改一处就重跑：pytest + lint + Ren'Py 走查，最后汇总。
#
# 用法：powershell -File tools/check_all.ps1

$ErrorActionPreference = 'Continue'
$root = Split-Path -Parent $PSScriptRoot
Set-Location $root

$results = @()

function Step($name, $script) {
    Write-Output ""
    Write-Output ("=" * 68)
    Write-Output "  $name"
    Write-Output ("=" * 68)
    & powershell -NoProfile -ExecutionPolicy Bypass -File (Join-Path $PSScriptRoot $script)
    $script:results += [pscustomobject]@{ Step = $name; Exit = $LASTEXITCODE }
}

Step "pytest（纯 Python 内核）" "pytest.ps1"
Step "Ren'Py lint（脚本静态检查）" "lint.ps1"
Step "Ren'Py 走查（界面 + 截图）" "run_tests.ps1"

Write-Output ""
Write-Output ("=" * 68)
Write-Output "  汇总"
Write-Output ("=" * 68)
$failed = 0
foreach ($row in $results) {
    $mark = if ($row.Exit -eq 0) { "OK  " } else { "FAIL" }
    if ($row.Exit -ne 0) { $failed++ }
    Write-Output ("  {0}  {1}（exit {2}）" -f $mark, $row.Step, $row.Exit)
}

Write-Output ""
if ($failed -eq 0) {
    Write-Output "全部通过。"
} else {
    Write-Output "$failed 个环节失败。"
}
exit $failed
