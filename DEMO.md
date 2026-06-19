# Timetabling System Demo

## Project Overview

This repository contains a Python prototype for the DSC2204 Integrative Team Project: a timetabling system for the SIT Engineering Cluster.

The system loads Template 1 scheduling requirements, generates hard-feasible assignments, optionally improves soft-constraint quality, and exports a proposed Template 2 timetable plus stakeholder reports. The prototype prioritises feasibility: if a class cannot be scheduled safely, it remains visible for review instead of being forced into an invalid timetable slot.

## Local Setup

Run these commands in Windows PowerShell from the repository root:

```powershell
cd C:\Users\Admin\Documents\GitHub\itp_group5
py -m venv .venv
.\.venv\Scripts\Activate.ps1
cd timetable_scheduler
py -m pip install -r requirements.txt
```

## Test Command

Run tests from inside the `timetable_scheduler` folder:

```powershell
cd C:\Users\Admin\Documents\GitHub\itp_group5\timetable_scheduler
py -m pytest -q
```

## Desktop Demo

Launch the local Windows desktop app:

```powershell
cd C:\Users\Admin\Documents\GitHub\itp_group5\timetable_scheduler
python run_ui.py
```

Demo flow:

1. Select **Consolidated Schedule**.
2. Choose one Template 1 `.xlsx` or `.xlsm` scheduling-requirements workbook.
3. Click **Generate Timetable**.
4. Wait for the loading screen to finish.
5. Review the four headline results:
   - Coverage
   - Scheduled classes
   - Classes needing review
   - Hard conflicts
6. Open the generated files with the plain-language output actions.

The UI uses fixed validated Engineering defaults. Venue information, common-module data, Template 2 and output locations are loaded internally from the bundled `Data/` resources.

## Output Actions

Use these completion-screen buttons:

- **Open Proposed Timetable**: opens the generated Template 2 workbook prepared for submission to the internal system.
- **View Timetable Views**: opens programme, tutor and room timetable views.
- **Review Unscheduled Classes**: opens the workbook containing the Exception Queue sheet for classes needing manual review.
- **View Scheduling Summary**: opens coverage, validation checks and scheduling findings.
- **Open All Files**: opens the output folder containing all generated artefacts.

Technical reports such as the run manifest and release validation remain available inside the generated output folder.

## Workflow

1. Programme scheduling requirements use Template 1.
2. Requirements are consolidated.
3. The consolidated Template 1 workbook is selected in the UI.
4. The system validates and loads the requirements.
5. The generator creates a hard-feasible timetable.
6. The bounded optimiser improves soft-constraint quality.
7. The timetable is exported using Template 2.
8. Timetabling staff review the proposed timetable and unresolved exceptions.

## Advanced Command-Line Fallback

Run the verified Engineering command when a command-line run is needed:

```powershell
cd C:\Users\Admin\Documents\GitHub\itp_group5\timetable_scheduler
python main.py --scope eng --skip-optimisation --max-candidate-patterns 300 --max-retry-assignments 50 --skip-unscheduled-diagnostics --progress-interval 25 --audit-demand-metrics
```

Expected Engineering result:

- Required teaching occurrences: `2777`
- Scheduled teaching occurrences: `2747`
- Unscheduled teaching occurrences: `30`
- Coverage rate: `98.92%`
- Scheduled hard violations: `0`
- Online coverage: `813 / 813`

The remaining unscheduled teaching occurrences are intentionally reported, not hidden.

## Stakeholder Reports

Running the pipeline creates decision-support workbooks in `timetable_scheduler/generated/`.

`preflight_report.xlsx` lists input data issues found before scheduling, such as invalid class sizes, missing teaching weeks, delivery-mode concerns, or room capacity problems. These checks do not block scheduling; they help explain input risks before reviewing the timetable.

`run_summary.xlsx` summarises the completed run with schedule counts, hard and soft violations, unscheduled reasons, room utilisation, programme breakdown and validation checks. This gives stakeholders a compact view of feasibility, unresolved scheduling demand and resource use without changing the Template 2 timetable export.

The unscheduled-analysis sheets keep the scheduler reasons visible so unresolved classes can be reviewed operationally.

## How to Read the Engineering Result

The main feasibility success metric is scheduled hard violations. A value of `0` means every class that received a room and timeslot satisfies the hard constraints.

Unscheduled assignments are not hidden. They remain visible in the summary and exception-review outputs so the project can explain what still needs more search time, better input data, more rooms, or manual review.

All-assignment hard-violation counts may include unscheduled feasibility failures. Do not confuse those with invalid scheduled timetable entries.

The `Validation Checks` sheet is the evidence page for presentation and reporting. It checks total consistency, scheduled hard-constraint safety, cluster data coverage and unscheduled visibility.

## Clean Release ZIP

Build a clean distributable ZIP from the repository root:

```powershell
cd C:\Users\Admin\Documents\GitHub\itp_group5
python scripts/build_clean_release.py
```

The ZIP is written to:

```text
dist/itp_group5_prototype.zip
```

The ZIP excludes `.git`, virtual environments, caches, generated outputs, editor folders and temporary files.

## Troubleshooting

- Activate the virtual environment before running commands:

```powershell
.\.venv\Scripts\Activate.ps1
```

- Run pytest from the `timetable_scheduler` folder:

```powershell
cd C:\Users\Admin\Documents\GitHub\itp_group5\timetable_scheduler
py -m pytest -q
```

- Generated folders should not be committed:

```text
timetable_scheduler/generated/
timetable_scheduler/output_files/
dist/
```
