# Additional Requirements Compliance

This audit maps the June 26 requirements to implemented repository evidence and generated validation workbooks. Generated workbooks are local artefacts and are not committed to Git.

## 1. Input Interface - Error Prevention

The prototype detects input issues before timetable generation through workbook-role detection, loader diagnostics, preflight checks and fixed-session readiness validation.

Evidence:

- Structural workbook-role checks are implemented in `timetable_scheduler/data/loader.py` and tested in `timetable_scheduler/tests/test_loader.py` and `timetable_scheduler/tests/test_pipeline_workbook_roles.py`.
- Row-level loader diagnostics are exported through `timetable_scheduler/generated/loader_report.xlsx`.
- Preflight course and room checks are implemented in `timetable_scheduler/engine/preflight_validator.py` and exported to `timetable_scheduler/generated/preflight_report.xlsx`.
- Guarded generation separates global blocking issues from quarantinable record-level issues in `timetable_scheduler/engine/guarded_generation.py`.
- Input readiness messages are built in `timetable_scheduler/engine/input_readiness.py` and exported to `timetable_scheduler/generated/input_readiness_report.xlsx`.
- Quarantined and invalid records are excluded from scheduled output and reported in `timetable_scheduler/generated/guarded_generation_report.xlsx`.

Current completeness-gate evidence:

```text
Total teaching occurrences: 3562
Schedulable occurrences: 3160
Quarantined input occurrences: 402
```

The quarantined occurrences are deliberately excluded from valid scheduled rows and remain visible for staff review.

## 2. Fixed Versus Non-Fixed Scheduling

The prototype ingests official fixed-session data, reconciles it with non-fixed teaching demand, anchors valid fixed assignments, and schedules remaining non-fixed sessions around those fixed reservations.

Evidence:

- Fixed-session loading is implemented in `timetable_scheduler/data/fixed_sessions.py`.
- Fixed/non-fixed reconciliation and duplicate-demand prevention are implemented in `timetable_scheduler/engine/fixed_reconciliation.py`.
- Guarded fixed assignment creation is implemented in `timetable_scheduler/generator/fixed_scheduler.py`.
- External venue and W3 location handling are supported through `timetable_scheduler/engine/location_mapping.py`.
- Fixed-session audit and reconciliation evidence are exported to:
  - `timetable_scheduler/generated/fixed_sessions_audit.xlsx`
  - `timetable_scheduler/generated/fixed_nonfixed_reconciliation.xlsx`
  - `timetable_scheduler/generated/fixed_issue_root_cause_analysis.xlsx`
  - `timetable_scheduler/generated/location_mapping_evidence.xlsx`
- The optimiser protects fixed assignments in `timetable_scheduler/optimiser/local_search.py`.
- Tests for fixed-session compliance are in `timetable_scheduler/tests/test_fixed_session_compliance.py`.

Final evidence shows valid fixed assignments are anchored and unresolved fixed-source issues are reported rather than moved or guessed.

## 3. Output Accuracy To Template 2

The official Template 2 workbook structure is preserved for proposed-timetable and submission-ready exports.

Evidence:

- Template 2 export mapping is implemented in `timetable_scheduler/output/exporter.py`.
- Submission-ready filtering and validation are implemented in `timetable_scheduler/output/submission_validator.py`.
- Template 2 mapping tests are in `timetable_scheduler/tests/test_exporter_template2.py`.
- Submission validation evidence is exported to `timetable_scheduler/generated/template2_submission_validation.xlsx`.
- The official proposed timetable is `timetable_scheduler/output_files/final_timetable_engineering_cluster.xlsx`.
- The submission-ready workbook is `timetable_scheduler/output_files/Template2_Submission_Ready.xlsx`.

Current completeness-gate output evidence:

```text
Proposed timetable rows: 2838
All-valid scheduled Template 2 rows: 2817
Submission-ready Template 2 rows: 111
Template 2 invalid rows: 0
Qualifying submission-ready programme-years: 17
Minimum required programme-year schedules: 20
Template 2 readiness: FAIL
```

Invalid, incomplete or unresolved rows do not appear in the submission-ready Template 2 workbook. They remain in exception and validation reports. The current branch is blocked for release because the strict qualifying count is below the required `20`.

## 4. Process Improvement

The final system improves timetable preparation by combining guarded partial generation, deterministic validation, stakeholder-specific reports and visual timetables.

Evidence:

- Guarded partial generation is implemented in `timetable_scheduler/engine/guarded_generation.py`.
- Soft-constraint optimisation is implemented in `timetable_scheduler/optimiser/local_search.py`.
- Run summary and stakeholder review workbooks are implemented in `timetable_scheduler/output/report_exporter.py`.
- Explainable remarks interpretation is implemented in `timetable_scheduler/engine/remarks_interpreter.py`.
- Visual programme, tutor and room timetables are implemented in `timetable_scheduler/output/timetable_visualizer.py`.
- Release validation is implemented in `timetable_scheduler/validate_release.py` with a repository-root wrapper at `validate_release.py`.

Current completeness-gate visual evidence:

```text
Programme visual sheets: 80
Tutor visual sheets: 221
Room visual sheets: 43
Programme visual entries: 608
Tutor visual entries: 554
Room visual entries: 471
Missing visual entries: 0
Unexpected visual entries: 0
Invalid overlaps: 0
Visual export status: PASS
```

Operationally, the prototype reduces repetitive placement, checking, formatting and reporting work while preserving human control over exceptions and final approval.
