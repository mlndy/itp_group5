# Controlled Demo Runbook

## Command

Run from the repository root:

```powershell
.\scripts\run_demo.ps1
```

## Expected Output

The script should print:

```text
CONTROLLED DEMO: PASS
valid_requirement_accepted: PASS
invalid_input_quarantined: PASS
room_clash_rejected: PASS
tutor_clash_rejected: PASS
student_group_clash_rejected: PASS
fixed_session_anchored_exactly: PASS
non_fixed_scheduled_around_fixed: PASS
template2_output_generated: PASS
exception_report_generated: PASS
visual_output_generated: PASS
```

## Presenter Explanation

- A valid requirement is accepted only when it satisfies hard constraints.
- Missing or invalid input is quarantined instead of being forced into the timetable.
- Room, tutor and student-group clashes are rejected by the hard-constraint checker.
- An official fixed session remains anchored at its supplied day, time, room and staff.
- Non-fixed demand is scheduled around that fixed session.
- The demo produces a proposed timetable, exception report and visual timetable evidence from controlled fixture data.

## Evidence To Open

Generated under:

```text
final_verification/controlled_demo/
```

Open:

- `Demo_Proposed_Timetable.xlsx`
- `Demo_Exception_Report.xlsx`
- `Demo_Programme_Timetable_Visuals.xlsx`
- `Demo_Tutor_Timetable_Visuals.xlsx`
- `Demo_Room_Timetable_Visuals.xlsx`
- `Demo_Timetable_Visualisation_Validation.xlsx`
- `demo_summary.md`

## Fallback Evidence

If a live run is not possible, use the generated workbooks in `final_verification/controlled_demo/` from the last successful demo run. These are fixture-based demonstration files and do not alter the official Engineering dataset.
