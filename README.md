# Engineering Timetable Scheduler

## Overview

This repository contains a local Python prototype for generating a proposed SIT Engineering Cluster timetable, including DSC.

The system:

- reads one consolidated scheduling-requirements workbook;
- validates the selected workbook structure;
- loads Engineering teaching requirements, venue data, common modules and institutional constraints;
- generates a timetable that accepts only hard-feasible scheduled assignments;
- applies bounded soft-constraint optimisation when requested;
- interprets supported free-text scheduling remarks in a deterministic and explainable way;
- exports a proposed timetable, stakeholder views, exception reports and run evidence.

The prototype is intentionally transparent. If a class cannot be placed safely, it remains visible for review instead of being forced into an invalid timetable.

## User Workflow

1. Open the desktop application.
2. Select the **Consolidated Schedule**.
3. Click **Generate Timetable**.
4. Wait for processing to complete.
5. Review the **Proposed Timetable**.
6. Review unscheduled classes and special requests.
7. Approve or manually resolve exceptions.

## Installation

Run from Windows PowerShell at the repository root:

```powershell
cd C:\Users\Admin\Documents\GitHub\itp_group5
py -m venv .venv
.\.venv\Scripts\python.exe -m pip install --upgrade pip
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
```

## Run The Desktop Application

```powershell
cd C:\Users\Admin\Documents\GitHub\itp_group5\timetable_scheduler
..\.venv\Scripts\python.exe run_ui.py
```

## Outputs

The desktop application opens or creates these main outputs:

- **Proposed Timetable**: generated timetable workbook for review.
- **Timetable Views**: programme, tutor and room views.
- **Unscheduled Classes**: exception queue for unresolved demand.
- **Special Requests Review**: how supported free-text remarks were interpreted and handled.
- **Scheduling Summary**: coverage, validation checks, resource audit, residual analysis and optimisation summary.
- **Run Manifest**: traceability and release-validation evidence.

Generated outputs are written under `timetable_scheduler/generated/` and `timetable_scheduler/output_files/`. These folders are intentionally ignored by Git.

## Command-Line Use

The desktop UI is recommended for demonstrations. The full Engineering command remains available for technical validation:

```powershell
cd C:\Users\Admin\Documents\GitHub\itp_group5\timetable_scheduler
..\.venv\Scripts\python.exe main.py --scope eng --skip-optimisation --max-candidate-patterns 300 --max-retry-assignments 50 --skip-unscheduled-diagnostics --progress-interval 25 --audit-demand-metrics
```

For a restored structured-data baseline without remarks enforcement, add:

```powershell
--disable-remark-interpretation
```

## Final Verified Results

### Core Baseline

The core baseline uses the same Engineering input data with remarks interpretation disabled. It proves the restored structured scheduling behaviour.

```text
Required occurrences: 2777
Scheduled occurrences: 2747
Unscheduled occurrences: 30
Coverage: 98.92%
Scheduled hard violations: 0
Online scheduled: 813 / 813
```

### Remarks-Aware Enhanced Run

The remarks-aware enhanced run enables deterministic interpretation of supported free-text scheduling requests.

```text
Required occurrences: 2777
Scheduled occurrences: 2715
Unscheduled occurrences: 62
Coverage: 97.77%
Scheduled hard violations: 0
```

Enhanced-run attribution:

```text
30 unchanged baseline exceptions
13 direct explicit remark effects
19 indirect displacements
0 unexplained occurrences
```

The two runs use the same teaching-demand denominator. The enhanced run schedules fewer occurrences because it enforces additional explicit requirements from supported remarks rather than weakening constraints.

## Implementation Notes

Technical workbook-role detection is structure-based. The requirements input is validated from its worksheet structure and headers, while the final proposed timetable preserves the required output workbook structure.

The Engineering dataset is stored under `Data/`, including Engineering requirement workbooks, common-module data, venue data, timetable constraints, university-wide modules and the output workbook template.

## Limitations

- The heuristic generator does not prove global optimality.
- The optimiser improves soft-constraint quality but the verified improvement is modest.
- Recording capability is used as the available proxy for hybrid-room support.
- Ambiguous or unsupported remarks require staff review.
- Upload to any internal university system is outside this prototype.
- Remaining unscheduled demand requires operational decisions such as venue review, delivery-mode approval, splitting very large sessions, or manual exception handling.

## Testing

Run from inside `timetable_scheduler`:

```powershell
cd C:\Users\Admin\Documents\GitHub\itp_group5\timetable_scheduler
..\.venv\Scripts\python.exe -m pytest -q
```

Current expected release result:

```text
220 passed
```

## Release ZIP

Build a clean distributable ZIP from the repository root:

```powershell
cd C:\Users\Admin\Documents\GitHub\itp_group5
.\.venv\Scripts\python.exe scripts\build_clean_release.py
```

The ZIP is written to `dist/itp_group5_prototype.zip` and excludes Git metadata, virtual environments, caches, generated outputs, editor folders, temporary files and old ZIP archives.

## AI Collaboration

AI-assisted development is documented transparently in [AI_USAGE_LOG.md](AI_USAGE_LOG.md) and [AI_ASSISTANCE_STATEMENT.md](AI_ASSISTANCE_STATEMENT.md). The user remained the project architect and final decision-maker; ChatGPT and Codex were used as support tools for implementation, debugging, testing and documentation.
