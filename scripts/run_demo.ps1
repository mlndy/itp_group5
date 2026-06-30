param(
    [string]$PythonPath = ".\.venv\Scripts\python.exe"
)

$ErrorActionPreference = "Stop"
$Root = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path
Set-Location $Root

if (!(Test-Path $PythonPath)) {
    $PythonPath = "python"
}

$oldPythonPath = $env:PYTHONPATH
$env:PYTHONPATH = Join-Path $Root "timetable_scheduler"
try {
    & $PythonPath scripts/run_controlled_demo.py
    exit $LASTEXITCODE
} finally {
    $env:PYTHONPATH = $oldPythonPath
}
