# Release Checklist

Use this checklist before final v1.1 submission and GitHub release.

## Repository

- [ ] Final changes are on `codex/final-v1.1-integration`.
- [ ] Final changes are merged to `main` only after validation passes.
- [ ] `main` is clean after validation.
- [ ] `main` has been pushed.
- [ ] No generated files are tracked.
- [ ] No virtual environments are tracked.
- [ ] No Python caches or pytest caches are tracked.
- [ ] No obsolete ZIP archives are tracked.
- [ ] Required operational data remains present under `Data/`.
- [ ] Required source, tests and scripts remain present.
- [ ] No branches or tags are deleted during this release.

## Documentation

- [ ] `README.md` uses the final v1.1 metrics.
- [ ] `DEMO.md` uses the final Engineering command with `--audit-demand-metrics`.
- [ ] `DEMO_SCRIPT.md` explains schedulable coverage versus total-recorded-demand coverage.
- [ ] `FINAL_RESULTS.md` labels the old `2777 / 2747 / 30 / 98.92%` result as earlier pre-fixed-session v1.0 validation.
- [ ] `REPORT_EVIDENCE.md` and `PRESENTATION_EVIDENCE.md` use the final v1.1 figures.
- [ ] `ADDITIONAL_REQUIREMENTS_COMPLIANCE.md` cites implementation files and generated evidence.
- [ ] `AI_USAGE_LOG.md` and `AI_ASSISTANCE_STATEMENT.md` present the project as team-owned and AI-assisted.
- [ ] All six team members and Prof. Tsoi Mun Heng are listed in AI transparency documentation.

## Prototype

- [ ] Desktop application launches.
- [ ] **Consolidated Schedule** input is accepted when structurally valid.
- [ ] A generated timetable workbook is rejected as input.
- [ ] Engineering data loads successfully.
- [ ] DSC is included as part of Engineering.
- [ ] UI remains responsive and uses final plain-language labels.
- [ ] UI does not display internal template-number terminology.
- [ ] Fixed sessions remain anchored.
- [ ] Non-fixed sessions are scheduled around fixed reservations.
- [ ] Quarantined records are excluded from scheduled output.
- [ ] Programme visual timetable workbook is generated.
- [ ] Tutor visual timetable workbook is generated.
- [ ] Room visual timetable workbook is generated.
- [ ] Visual timetable workbooks use scheduled assignments only and do not alter Template 2.
- [ ] Unscheduled and quarantined cases remain visible.
- [ ] Scheduled hard violations remain zero.
- [ ] Proposed timetable output structure is unchanged.

## Validation

- [ ] Full test suite passes from the repository root:

```powershell
.\.venv\Scripts\python.exe -m pytest -q
```

- [ ] Test result is at least:

```text
259 passed
```

- [ ] The guarded Engineering run completes twice with unchanged metrics:

```text
Total teaching occurrences: 3562
Schedulable occurrences: 3160
Quarantined input occurrences: 402
Scheduled occurrences: 3070
Scheduler search failures: 90
Scheduled hard-constraint violations: 0
```

- [ ] Template 2 validation matches:

```text
Proposed timetable rows: 2868
Submission-ready Template 2 rows: 1183
Template 2 invalid rows: 0
Template 2 complete programme-years: 30
Submission-ready programme-years: 23
Template 2 readiness: PASS
```

- [ ] Visual timetable validation matches:

```text
Programme visual sheets: 81
Tutor visual sheets: 225
Room visual sheets: 43
Programme visual entries: 3454
Tutor visual entries: 4255
Room visual entries: 2367
Missing visual entries: 0
Unexpected visual entries: 0
Invalid overlaps: 0
Visual export status: PASS
```

- [ ] `.\.venv\Scripts\python.exe validate_release.py` reports `FINAL RELEASE VALIDATION: PASS`.
- [ ] Generated workbook SHA-256 values and logical fingerprints are recorded.

## Packages

- [ ] Clean source ZIP builds as `dist/itp_group5_prototype_v1.1.0.zip`.
- [ ] Clean source ZIP excludes `.git`, `.venv`, caches, generated outputs, old ZIP files, temporary files and private approval workbooks.
- [ ] Extracted source ZIP can import the application.
- [ ] Extracted source ZIP smoke tests pass.
- [ ] Assessment evidence ZIP builds as `dist/DSC2204_Group5_Assessment_Evidence.zip`.
- [ ] Assessment evidence ZIP includes `EVIDENCE_README.md`.
- [ ] Assessment evidence ZIP includes final generated output and validation workbooks.
- [ ] Visual sample PNGs are prepared under `dist/presentation_assets/`.

## GitHub

- [ ] Integration branch is pushed.
- [ ] Integration branch is merged into `main`.
- [ ] Tests and release validation pass again on `main`.
- [ ] `main` is pushed after merge.
- [ ] Release tag `v1.1.0` is created and pushed only if it does not already exist.
- [ ] No existing tag is overwritten.
- [ ] No local or remote branches are deleted.
