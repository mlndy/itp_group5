# Presentation Evidence

## Visual Timetable Workbooks

The prototype now creates three operational visual workbooks after a successful Engineering run:

- `Programme_Timetable_Visuals.xlsx`
- `Tutor_Timetable_Visuals.xlsx`
- `Room_Timetable_Visuals.xlsx`

Presentation framing:

```text
The timetable is generated once, validated for hard constraints, and then exported into multiple review formats. The visual workbooks make the validated schedule easier to read; they do not change the timetable.
```

## Evidence Slide Points

- Scheduled hard violations remain `0`.
- Quarantined and unscheduled requirements are not hidden as scheduled blocks.
- Fixed and generated sessions are visually distinguishable.
- Physical, online and external sessions are labelled with text cues as well as colour.
- Every visual block keeps a traceable assignment ID.
- `timetable_visualisation_validation.xlsx` reports `PASS`.

## Final Visual Counts

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
```
