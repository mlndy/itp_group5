# AI Usage Log

This project used AI assistance transparently. Group 5 defined the problem, requirements, architecture, validation criteria and final decisions. ChatGPT and OpenAI Codex were used as support tools for implementation, debugging, automated testing, documentation refinement and code review.

AI did not independently design or own the project. AI-generated suggestions were reviewed, corrected and validated by the team before acceptance.

## Team And Supervisor

- Ivin Chew Jian Wei - 2503347
- Chua Kai Zhong - 2500249
- Chang Wen Lin Sarah - 2501932
- Addison Kang Jun Loong - 2501053
- Lim Ting Yong - 2501044
- Amal Nadiy Bin Mohamed Faizal - 2500282
- Academic supervisor: Prof. Tsoi Mun Heng

Preliminary project-plan roles should be read as initial workstream allocations, not proof of exclusive ownership by any single student.

## Usage Summary

| Stage | Group 5 Direction | AI Assistance | Team Review Or Correction | Validation Evidence |
| --- | --- | --- | --- | --- |
| Problem framing and Engineering scope | Defined the deliverable as Engineering Cluster timetabling, with DSC included. | Helped organise requirements into implementation phases. | Rejected DSC-only framing as the final deliverable. | Engineering evidence confirms DSC inclusion. |
| Data modelling | Required explicit Course, Room, TimeSlot and Assignment objects. | Suggested helper structure and type-hinted code. | Preserved existing model boundaries and prevented duplicate dataclass definitions. | Model, loader and downstream tests. |
| Hard and soft constraints | Defined hard constraints as non-negotiable and soft constraints as quality preferences. | Helped implement and test constraint checks. | Required scheduled hard violations to remain unacceptable. | Final scheduled hard-constraint violations: 0. |
| Engineering scaling | Required the Engineering cluster as the final scope. | Helped add reports, diagnostics and evidence sheets. | Required unresolved demand to remain visible. | `run_summary.xlsx`, `guarded_generation_report.xlsx`. |
| Fixed-session compliance | Required official fixed sessions to remain anchored. | Helped implement fixed/non-fixed reconciliation and guarded generation. | Required fixed sessions not to be moved or guessed. | Fixed-session tests and generated fixed-session evidence. |
| Template 2 readiness | Required official output structure and upload-critical validation. | Helped implement validation and source-to-output reconciliation. | Required invalid or incomplete rows to be excluded from submission-ready output. | `template2_submission_validation.xlsx`, Template 2 readiness currently FAIL under the stricter completeness gate. |
| Remarks interpretation | Required deterministic, explainable handling of supported free-text requests. | Helped implement supported patterns and review classifications. | Required unsupported or unclear remarks to remain visible rather than guessed. | Remarks tests and Special Requests Review. |
| Visual timetable exports | Required stakeholder-friendly views without changing the schedule. | Helped implement programme, tutor and room visual workbooks. | Required visual exports to use scheduled assignments only. | Visual export status PASS, 0 missing entries, 0 invalid overlaps. |
| Release validation | Required final metrics to be defensible and reproducible. | Helped update validators, documentation and packaging scripts. | Required current completeness-gate metrics to replace old historical figures until release readiness passes. | Tests, guarded runs, `validate_release.py`. |

## Current Completeness-Gate Evidence

```text
Total teaching occurrences: 3562
Schedulable occurrences: 3160
Quarantined input occurrences: 402
Scheduled occurrences: 3046
Scheduler search failures: 114
Scheduled hard-constraint violations: 0
Coverage of schedulable demand: 96.39%
Coverage of total recorded demand: 85.51%
```

The `85.51%` total-recorded-demand figure includes quarantined source records. The primary scheduling-performance measure is `96.39%` coverage of schedulable demand.

Template 2 evidence:

```text
Proposed timetable rows: 2838
All-valid scheduled Template 2 rows: 2817
Submission-ready Template 2 rows: 111
Template 2 invalid rows: 0
Qualifying submission-ready programme-years: 17
Minimum required programme-year schedules: 20
Template 2 readiness: FAIL
```

Visual timetable evidence:

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

## Meaningful Human Corrections

The team corrected or clarified several important project decisions:

- The final deliverable is Engineering scope, not DSC-only.
- DSC is part of Engineering and should not be presented as a separate inclusion feature.
- Workbook roles must be detected from structure and headers, not filenames.
- Hard constraints must not be weakened to increase coverage.
- Quarantined input demand and scheduler search failures must be reported separately.
- The final UI should use plain-language terms such as **Consolidated Schedule** and **Proposed Timetable**.
- Ambiguous remarks must remain non-blocking and visible for staff review.
- Current completeness-gate metrics supersede earlier pre-fixed-session v1.0 metrics until release readiness passes.

## Limitations Of AI Assistance

AI assistance can produce useful code and explanations, but it can also make incorrect assumptions about metrics, repository state, stakeholder policy or domain semantics. The team reviewed AI-generated work, corrected inaccurate assumptions and accepted only changes supported by tests and generated evidence.

The final submission remains the responsibility of Group 5.
