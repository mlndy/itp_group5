"""Input readiness checks that gate timetable generation before scheduling."""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

import pandas as pd

from data.fixed_sessions import FixedSessionLoaderReport
from data.loader import LoaderReport
from engine.fixed_reconciliation import FixedReconciliationReport

ISSUE_COLUMNS = ["severity", "workbook", "sheet", "row", "field", "entered value", "problem", "how to correct it"]
SUMMARY_COLUMNS = ["Metric", "Value"]


@dataclass(slots=True)
class InputReadinessResult:
    """Readiness result used by CLI and UI before generation."""

    status: str
    critical_errors: list[dict[str, object]] = field(default_factory=list)
    warnings: list[dict[str, object]] = field(default_factory=list)
    info: list[dict[str, object]] = field(default_factory=list)
    fixed_loader_report: FixedSessionLoaderReport | None = None
    reconciliation_report: FixedReconciliationReport | None = None
    fixed_assignment_issues: list[dict[str, object]] = field(default_factory=list)
    loader_report: LoaderReport | None = None

    @property
    def ready(self) -> bool:
        """Return True when no critical errors were found."""
        return not self.critical_errors

    @property
    def message(self) -> str:
        """Return a concise user-facing readiness message."""
        critical_count = len(self.critical_errors)
        warning_count = len(self.warnings)
        if critical_count:
            return f"Input not ready: {critical_count} critical error(s) and {warning_count} warning(s)"
        if warning_count:
            return f"Input ready with {warning_count} warning(s)"
        return "Input ready"


def _normalise_issue(issue: dict[str, object], default_workbook: str = "") -> dict[str, object]:
    """Return an issue with the standard readiness columns."""
    return {
        "severity": issue.get("severity", "info"),
        "workbook": issue.get("workbook", issue.get("source", default_workbook)),
        "sheet": issue.get("sheet", ""),
        "row": issue.get("row", ""),
        "field": issue.get("field", ""),
        "entered value": issue.get("entered value", ""),
        "problem": issue.get("problem", issue.get("manual-review reason", "")),
        "how to correct it": issue.get("how to correct it", issue.get("recommendation", "")),
    }


def build_input_readiness_result(
    *,
    fixed_loader_report: FixedSessionLoaderReport,
    reconciliation_report: FixedReconciliationReport,
    fixed_assignment_issues: list[dict[str, object]],
    loader_report: LoaderReport | None = None,
) -> InputReadinessResult:
    """Build a generation gate from loader, reconciliation and fixed-placement checks."""
    critical: list[dict[str, object]] = []
    warnings: list[dict[str, object]] = []
    info: list[dict[str, object]] = []

    for issue in fixed_loader_report.issues:
        row = _normalise_issue(issue, fixed_loader_report.workbook_path)
        if row["severity"] == "critical":
            critical.append(row)
        elif row["severity"] == "warning":
            warnings.append(row)
        else:
            info.append(row)

    for row in reconciliation_report.ambiguous_matches:
        critical.append(
            _normalise_issue(
                {
                    **row,
                    "severity": "critical",
                    "problem": "Ambiguous fixed/non-fixed reconciliation could duplicate demand.",
                    "how to correct it": row.get("manual-review reason", "Review the matching source rows."),
                }
            )
        )
    for row in reconciliation_report.partial_matches:
        critical.append(
            _normalise_issue(
                {
                    **row,
                    "severity": "critical",
                    "problem": "Partial fixed/non-fixed reconciliation requires a reviewed split to avoid duplicate demand.",
                    "how to correct it": row.get("manual-review reason", "Review and confirm the fixed portion before generation."),
                }
            )
        )
    for row in reconciliation_report.invalid_fixed_rows:
        severity = str(row.get("severity") or "critical")
        target = critical if severity == "critical" else warnings
        target.append(
            _normalise_issue(
                {
                    **row,
                    "severity": severity,
                    "problem": row.get("manual-review reason", "Invalid fixed source row."),
                    "how to correct it": "Correct the fixed-session source workbook or mark the row as non-fixed.",
                }
            )
        )
    for issue in fixed_assignment_issues:
        critical.append(_normalise_issue(issue, fixed_loader_report.workbook_path))

    status = "PASS" if not critical else "FAIL"
    return InputReadinessResult(
        status=status,
        critical_errors=critical,
        warnings=warnings,
        info=info,
        fixed_loader_report=fixed_loader_report,
        reconciliation_report=reconciliation_report,
        fixed_assignment_issues=fixed_assignment_issues,
        loader_report=loader_report,
    )


def _summary_rows(result: InputReadinessResult) -> pd.DataFrame:
    """Return input readiness summary rows."""
    fixed = result.fixed_loader_report
    reconciliation = result.reconciliation_report
    rows = [
        {"Metric": "Readiness status", "Value": result.status},
        {"Metric": "Readiness message", "Value": result.message},
        {"Metric": "Critical errors", "Value": len(result.critical_errors)},
        {"Metric": "Warnings", "Value": len(result.warnings)},
        {"Metric": "Information", "Value": len(result.info)},
        {"Metric": "Fixed source rows", "Value": fixed.source_rows if fixed else 0},
        {"Metric": "Valid fixed source rows", "Value": fixed.fixed_rows_loaded if fixed else 0},
        {"Metric": "Invalid fixed source rows", "Value": len(reconciliation.invalid_fixed_rows) if reconciliation else 0},
        {"Metric": "Ambiguous reconciliation cases", "Value": len(reconciliation.ambiguous_matches) if reconciliation else 0},
        {"Metric": "Fixed-source conflicts", "Value": len(result.fixed_assignment_issues)},
    ]
    return pd.DataFrame(rows, columns=SUMMARY_COLUMNS)


def export_input_readiness_report(result: InputReadinessResult, output_path: Path) -> None:
    """Export input readiness status and blocking issues."""
    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    fixed_issues = []
    if result.fixed_loader_report is not None:
        fixed_issues.extend(_normalise_issue(issue, result.fixed_loader_report.workbook_path) for issue in result.fixed_loader_report.issues)
    fixed_issues.extend(_normalise_issue(issue) for issue in result.fixed_assignment_issues)
    source_files = []
    if result.loader_report is not None:
        source_files = [
            {
                "Workbook": item.file_path,
                "Sheet": item.sheet_name,
                "Status": item.status,
                "Reason": item.reason,
                "Rows Parsed": item.rows_parsed,
                "Rows Skipped": item.rows_skipped,
            }
            for item in result.loader_report.workbooks
        ]
    with pd.ExcelWriter(output_path, engine="openpyxl") as writer:
        _summary_rows(result).to_excel(writer, sheet_name="Summary", index=False)
        pd.DataFrame(result.critical_errors, columns=ISSUE_COLUMNS).to_excel(writer, sheet_name="Critical Errors", index=False)
        pd.DataFrame(result.warnings, columns=ISSUE_COLUMNS).to_excel(writer, sheet_name="Warnings", index=False)
        pd.DataFrame(fixed_issues, columns=ISSUE_COLUMNS).to_excel(writer, sheet_name="Fixed Session Issues", index=False)
        pd.DataFrame(result.reconciliation_report.ambiguous_matches if result.reconciliation_report else []).to_excel(
            writer,
            sheet_name="Reconciliation Issues",
            index=False,
        )
        pd.DataFrame(source_files).to_excel(writer, sheet_name="Source Files", index=False)
