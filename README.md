# Engineering Timetable Scheduler

Local prototype for generating a proposed SIT Engineering Cluster timetable from a consolidated Template 1 scheduling-requirements workbook.

The desktop application is the recommended route for non-technical users. It asks for one input workbook, runs the validated Engineering pipeline with fixed settings, and opens the generated timetable and supporting Excel reports.

## 1. Install Requirements

Run from Windows PowerShell:

```powershell
cd C:\Users\Admin\Documents\GitHub\itp_group5
py -m venv .venv
.\.venv\Scripts\Activate.ps1
cd timetable_scheduler
py -m pip install -r requirements.txt
```

## 2. Run the Desktop Application

```powershell
cd C:\Users\Admin\Documents\GitHub\itp_group5\timetable_scheduler
python run_ui.py
```

## 3. Generate a Timetable

1. Select **Consolidated Schedule**.
2. Choose one Template 1 `.xlsx` or `.xlsm` scheduling-requirements workbook.
3. Click **Generate Timetable**.
4. Wait for the loading screen to complete.
5. Use **Open Proposed Timetable** for the Template 2 workbook.
6. Use the supporting output buttons for timetable views, unscheduled-class review, and scheduling summary.

The UI does not expose scheduler settings. Venue information, common-module data, Template 2 and output locations are loaded from the bundled `Data/` resources.

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

Run tests:

```powershell
cd C:\Users\Admin\Documents\GitHub\itp_group5\timetable_scheduler
py -m pytest -q
```

Run the verified Engineering command:

```powershell
cd C:\Users\Admin\Documents\GitHub\itp_group5\timetable_scheduler
python main.py --scope eng --skip-optimisation --max-candidate-patterns 300 --max-retry-assignments 50 --skip-unscheduled-diagnostics --progress-interval 25 --audit-demand-metrics
```

The final validated Engineering evidence is:

- Required teaching occurrences: `2777`
- Scheduled teaching occurrences: `2747`
- Unscheduled teaching occurrences: `30`
- Coverage rate: `98.92%`
- Scheduled hard violations: `0`
- Online coverage: `813 / 813`

## Release ZIP

Build a clean distributable ZIP from the repository root:

```powershell
python scripts/build_clean_release.py
```

The ZIP is written to `dist/itp_group5_prototype.zip` and excludes `.git`, virtual environments, caches, generated outputs, editor folders and temporary files.

## Dataset

The bundled Engineering dataset is stored under `Data/`. Full Engineering runs use `Data/Requirements_ENG`, and the desktop UI uses the configured `Data/Upload template_System (Template 2).xlsx` only as the internal output template.
