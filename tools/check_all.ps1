# Run everything that guards the build: pytest, Ren'Py lint, font coverage,
# and the UI walkthrough. Prints a summary at the end.
#
#   powershell -File tools/check_all.ps1
#
# KEEP THIS FILE ASCII-ONLY (Windows PowerShell 5.1 reads BOM-less files as the
# system codepage and mangles non-ASCII literals).

$ErrorActionPreference = 'Continue'
$root = Split-Path -Parent $PSScriptRoot
Set-Location $root

$results = @()

function Step($name, $script) {
    Write-Output ""
    Write-Output ("=" * 68)
    Write-Output ("  " + $name)
    Write-Output ("=" * 68)
    & powershell -NoProfile -ExecutionPolicy Bypass -File (Join-Path $PSScriptRoot $script)
    $script:results += [pscustomobject]@{ Step = $name; Exit = $LASTEXITCODE }
}

Step "pytest (pure-Python core)"                  "pytest.ps1"
Step "Ren'Py lint (script static check)"          "lint.ps1"
Step "font coverage (no tofu characters)"         "font_check.ps1"
Step "save / load round-trip (real Ren'Py)"       "test_save.ps1"
Step "UI walkthrough (renders + screenshots)"     "run_tests.ps1"

Write-Output ""
Write-Output ("=" * 68)
Write-Output "  SUMMARY"
Write-Output ("=" * 68)
$failed = 0
foreach ($row in $results) {
    $mark = if ($row.Exit -eq 0) { "OK  " } else { "FAIL" }
    if ($row.Exit -ne 0) { $failed++ }
    Write-Output ("  {0}  {1}  (exit {2})" -f $mark, $row.Step, $row.Exit)
}

Write-Output ""
if ($failed -eq 0) {
    Write-Output "ALL CHECKS PASSED"
} else {
    Write-Output ("{0} CHECK(S) FAILED" -f $failed)
}
exit $failed
