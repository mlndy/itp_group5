param(
    [string]$PythonPath = ".\.venv\Scripts\python.exe"
)

$ErrorActionPreference = "Stop"
$Root = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path
$VerificationDir = Join-Path $Root "final_verification"
$SummaryPath = Join-Path $VerificationDir "final_verification_summary.md"
$MetricsJson = Join-Path $VerificationDir "final_release_metrics.json"
$MetricsCsv = Join-Path $VerificationDir "final_release_metrics.csv"
$TestOutput = Join-Path $VerificationDir "test_output.txt"
$PytestBaseTemp = "timetable_scheduler/generated/pytest_final_verification_$((Get-Date).ToString('yyyyMMdd_HHmmss'))"
$RunOutput = Join-Path $VerificationDir "engineering_run_output.txt"
$RunInfo = Join-Path $VerificationDir "run_info.json"
$ReleaseValidationOutput = Join-Path $VerificationDir "release_validation_output.txt"
$ReleaseValidationLatestOutput = Join-Path $VerificationDir "release_validation_latest_output.txt"
$ZipScanOutput = Join-Path $VerificationDir "zip_scan_output.txt"
$ZipHashOutput = Join-Path $VerificationDir "zip_sha256.txt"
$ExcelOutput = Join-Path $VerificationDir "excel_compatibility_output.txt"
$ZipPath = Join-Path $Root "dist\itp_group5_prototype_v1.1.0.zip"
$GateFailures = New-Object System.Collections.Generic.List[string]

function Add-GateFailure([string]$Message) {
    $script:GateFailures.Add($Message) | Out-Null
    Write-Host "GATE FAIL: $Message"
}

function Run-Native([string]$Description, [scriptblock]$Command, [string]$OutputPath = $null) {
    Write-Host "`n== $Description =="
    $previousPreference = $ErrorActionPreference
    $ErrorActionPreference = "Continue"
    try {
        if ($OutputPath) {
            & $Command 2>&1 | Tee-Object -FilePath $OutputPath
        } else {
            & $Command
        }
    } finally {
        $ErrorActionPreference = $previousPreference
    }
    if ($LASTEXITCODE -ne 0) {
        Add-GateFailure "$Description failed with exit code $LASTEXITCODE"
    }
}

function Get-SummaryValue([string]$WorkbookPath, [string]$SheetName, [string]$Metric) {
    $script = @"
from openpyxl import load_workbook
wb = load_workbook(r'''$WorkbookPath''', read_only=True, data_only=True)
try:
    ws = wb[r'''$SheetName''']
    for row in ws.iter_rows(min_row=2, values_only=True):
        if row and row[0] == r'''$Metric''':
            print(row[1])
            break
finally:
    wb.close()
"@
    return (& $PythonPath -c $script).Trim()
}

Set-Location $Root
New-Item -ItemType Directory -Force -Path $VerificationDir | Out-Null

if (!(Test-Path $PythonPath)) {
    Add-GateFailure "Python executable not found at $PythonPath"
    $PythonPath = "python"
}

$Branch = (git branch --show-current).Trim()
$Commit = (git rev-parse HEAD).Trim()
$PythonVersion = (& $PythonPath --version 2>&1).Trim()
Write-Host "Branch: $Branch"
Write-Host "Commit: $Commit"
Write-Host "Python: $PythonVersion"

Run-Native "Dependency import check" {
    & $PythonPath -c "import openpyxl, pandas; print('dependencies: PASS')"
}

Run-Native "Full pytest suite" {
    & $PythonPath -m pytest timetable_scheduler/tests -q -p no:cacheprovider --basetemp $PytestBaseTemp
} $TestOutput

$RunScript = Join-Path $VerificationDir "run_full_engineering.py"
@'
from __future__ import annotations

import json
import sys
from pathlib import Path

from pipeline import PipelineOptions, run_timetable_pipeline

output_path = Path(sys.argv[1])
result = run_timetable_pipeline(
    PipelineOptions(
        scope="eng",
        run_optimisation=False,
        max_candidate_patterns=300,
        max_retry_assignments=50,
        skip_unscheduled_diagnostics=True,
        progress_interval=25,
        audit_demand_metrics=True,
        enable_remark_interpretation=True,
        export_remarks_comparison=True,
    ),
    progress_callback=print,
)
run_dir = Path(result.output_paths["output_folder"])
payload = {
    "run_id": result.run_id,
    "run_dir": str(run_dir),
    "required_occurrences": result.required_occurrences,
    "scheduled_occurrences": result.scheduled_occurrences,
    "unscheduled_occurrences": result.unscheduled_occurrences,
    "scheduled_hard_violations": result.scheduled_hard_violations,
}
output_path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
print("FINAL_RUN_ID=" + result.run_id)
print("FINAL_RUN_DIR=" + str(run_dir))
'@ | Set-Content -Path $RunScript -Encoding UTF8

$oldPythonPath = $env:PYTHONPATH
$env:PYTHONPATH = Join-Path $Root "timetable_scheduler"
Run-Native "Fresh isolated Engineering run" {
    & $PythonPath $RunScript $RunInfo
} $RunOutput
$env:PYTHONPATH = $oldPythonPath

if (!(Test-Path $RunInfo)) {
    Add-GateFailure "Fresh Engineering run did not write run_info.json"
    $RunId = ""
    $RunDir = ""
} else {
    $RunInfoJson = Get-Content $RunInfo -Raw | ConvertFrom-Json
    $RunId = [string]$RunInfoJson.run_id
    $RunDir = [string]$RunInfoJson.run_dir
}

if ($RunDir -and (Test-Path $RunDir)) {
    Run-Native "Release validation for explicit run folder" {
        & $PythonPath validate_release.py --run-dir $RunDir
    } $ReleaseValidationOutput
    Run-Native "Release validation for latest complete run" {
        & $PythonPath validate_release.py
    } $ReleaseValidationLatestOutput
} else {
    Add-GateFailure "Fresh run folder missing: $RunDir"
}

$RemarksPath = if ($RunDir) { Join-Path $RunDir "remarks_coverage_comparison.xlsx" } else { "" }
if ($RemarksPath -and (Test-Path $RemarksPath)) {
    $RemarksStatus = Get-SummaryValue $RemarksPath "Attribution Reconciliation" "Attribution reconciliation"
    $RemarksDifference = Get-SummaryValue $RemarksPath "Attribution Reconciliation" "Calculated enhanced unscheduled"
    if ($RemarksStatus -ne "True") {
        Add-GateFailure "Remarks attribution reconciliation did not evaluate to True"
    }
} else {
    $RemarksStatus = "MISSING"
    Add-GateFailure "Remarks comparison workbook missing"
}

if ($RunDir) {
    $FixedStatus = Get-SummaryValue (Join-Path $RunDir "fixed_session_integrity_validation.xlsx") "Summary" "fixed-session integrity status"
    $TemplateStatus = Get-SummaryValue (Join-Path $RunDir "template2_programme_year_reconciliation.xlsx") "Summary" "Template 2 readiness status"
    $VisualStatus = Get-SummaryValue (Join-Path $RunDir "timetable_visualisation_validation.xlsx") "Summary" "visual export status"
    foreach ($pair in @(
        @("Fixed-session integrity", $FixedStatus),
        @("Template 2 readiness", $TemplateStatus),
        @("Visual validation", $VisualStatus)
    )) {
        if ($pair[1] -ne "PASS") {
            Add-GateFailure "$($pair[0]) is $($pair[1])"
        }
    }
}

Run-Native "Build clean release ZIP" {
    & $PythonPath scripts/build_clean_release.py
}

if (Test-Path $ZipPath) {
    Add-Type -AssemblyName System.IO.Compression.FileSystem
    $archive = [System.IO.Compression.ZipFile]::OpenRead((Resolve-Path $ZipPath))
    try {
        $entries = $archive.Entries | ForEach-Object { $_.FullName }
        $matches = $entries | Select-String -Pattern '(^|/)\.tmp/|__pycache__|\.pytest_cache|generated/|output_files/|\.pyc$'
        if ($matches) {
            $matches | ForEach-Object { $_.Line } | Set-Content -Path $ZipScanOutput -Encoding UTF8
            Add-GateFailure "ZIP cleanliness scan found excluded paths"
        } else {
            "ZIP cleanliness scan: PASS" | Set-Content -Path $ZipScanOutput -Encoding UTF8
        }
        $ZipFileCount = $entries.Count
    } finally {
        $archive.Dispose()
    }
    $ZipHash = (Get-FileHash $ZipPath -Algorithm SHA256).Hash
    $ZipHash | Set-Content -Path $ZipHashOutput -Encoding UTF8
    $ZipSize = (Get-Item $ZipPath).Length
} else {
    Add-GateFailure "Release ZIP missing at $ZipPath"
    $ZipFileCount = 0
    $ZipHash = ""
    $ZipSize = 0
}

if ($RunDir) {
    $ExcelTargets = @(
        "Proposed_Timetable.xlsx",
        "Template2_Submission_Ready.xlsx",
        "Template2_All_Valid_Scheduled_Rows.xlsx",
        "run_summary.xlsx",
        "guarded_generation_report.xlsx",
        "template2_submission_validation.xlsx",
        "template2_programme_year_reconciliation.xlsx",
        "fixed_session_integrity_validation.xlsx",
        "Programme_Timetable_Visuals.xlsx",
        "Tutor_Timetable_Visuals.xlsx",
        "Room_Timetable_Visuals.xlsx",
        "timetable_visualisation_validation.xlsx"
    )
    $ExcelScript = Join-Path $VerificationDir "excel_open_check.ps1"
    @'
param([string]$RunDir, [string]$TargetsText)
$Targets = $TargetsText -split '\|'
$excel = $null
$rows = @()
try {
    try {
        $excel = New-Object -ComObject Excel.Application
    } catch {
        foreach ($target in $Targets) {
            $rows += [pscustomobject]@{
                Workbook = $target
                OpenResult = "FAIL"
                RepairPrompt = "Unknown"
                RemovedRecordsWarning = "Unknown"
                SheetCount = ""
                RelevantRowCount = ""
            }
        }
        $rows | ConvertTo-Csv -NoTypeInformation
        exit 1
    }
    $excel.DisplayAlerts = $false
    foreach ($target in $Targets) {
        $path = Join-Path $RunDir $target
        $status = "PASS"
        $repair = "No"
        $removed = "No"
        $sheetCount = ""
        $rowCount = ""
        try {
            $workbook = $excel.Workbooks.Open((Resolve-Path $path).Path, 0, $true)
            $sheetCount = $workbook.Worksheets.Count
            if ($workbook.Worksheets.Count -ge 1) {
                $rowCount = $workbook.Worksheets.Item(1).UsedRange.Rows.Count
            }
            $workbook.Close($false)
        } catch {
            $status = "FAIL"
            $repair = "Unknown"
            $removed = "Unknown"
        }
        $rows += [pscustomobject]@{
            Workbook = $target
            OpenResult = $status
            RepairPrompt = $repair
            RemovedRecordsWarning = $removed
            SheetCount = $sheetCount
            RelevantRowCount = $rowCount
        }
    }
} finally {
    if ($excel -ne $null) {
        $excel.Quit()
        [System.Runtime.InteropServices.Marshal]::ReleaseComObject($excel) | Out-Null
    }
}
$rows | ConvertTo-Csv -NoTypeInformation
'@ | Set-Content -Path $ExcelScript -Encoding UTF8
    $ExcelTargetsText = $ExcelTargets -join "|"
    powershell -NoProfile -ExecutionPolicy Bypass -File $ExcelScript -RunDir $RunDir -TargetsText $ExcelTargetsText |
        Set-Content -Path $ExcelOutput -Encoding UTF8
    if ($LASTEXITCODE -ne 0) {
        Add-GateFailure "Excel compatibility check process failed with exit code $LASTEXITCODE"
    }
    $ExcelRowCount = (Import-Csv $ExcelOutput).Count
    if ($ExcelRowCount -ne $ExcelTargets.Count) {
        Add-GateFailure "Excel compatibility check covered $ExcelRowCount of $($ExcelTargets.Count) expected workbooks"
    }
    if ((Select-String -Path $ExcelOutput -Pattern '"FAIL"').Count -gt 0) {
        Add-GateFailure "Excel compatibility check reported a FAIL"
    }
} else {
    Add-GateFailure "Excel compatibility skipped because run folder is missing"
}

if ($RunDir) {
    Run-Native "Export final release metrics" {
        & $PythonPath scripts/export_final_metrics.py --run-dir $RunDir --output-dir $VerificationDir --test-output $TestOutput --zip-path $ZipPath --zip-sha-path $ZipHashOutput --remarks-comparison $RemarksPath
    }
}

$GateStatus = if ($GateFailures.Count -eq 0) { "PASS" } else { "FAIL" }
$Summary = @(
    "# Final Verification Summary",
    "",
    "- Branch: $Branch",
    "- Commit: $Commit",
    "- Python: $PythonVersion",
    "- Final run ID: $RunId",
    "- Final run folder: $RunDir",
    "- Remarks attribution status: $RemarksStatus",
    "- Fixed-session integrity: $FixedStatus",
    "- Template 2 readiness: $TemplateStatus",
    "- Visual validation: $VisualStatus",
    "- ZIP filename: $(Split-Path $ZipPath -Leaf)",
    "- ZIP file count: $ZipFileCount",
    "- ZIP size bytes: $ZipSize",
    "- ZIP SHA-256: $ZipHash",
    "- FINAL RELEASE GATE: $GateStatus",
    ""
)
if ($GateFailures.Count -gt 0) {
    $Summary += "## Failures"
    foreach ($failure in $GateFailures) {
        $Summary += "- $failure"
    }
}
$Summary | Set-Content -Path $SummaryPath -Encoding UTF8

if ($GateStatus -eq "PASS") {
    Write-Host "FINAL RELEASE GATE: PASS"
    exit 0
}
Write-Host "FINAL RELEASE GATE: FAIL"
exit 1
