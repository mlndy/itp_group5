# Report Structure

## 1. Problem Definition
SIT's academic timetabling problem is a resource allocation and constraint satisfaction problem involving rooms, tutors, student groups, delivery modes, and academic weeks.

## 2. Current Process
The current workflow depends on Excel templates shared between programme leaders, administrators, and the timetabling team. Manual consolidation increases the risk of conflicts and repeated revisions.

## 3. System Design
The prototype is split into five technical stages: data loading, constraint checking, greedy scheduling, local search optimisation, and Excel exporting.

## 4. Data Model
Explain Course, Room, TimeSlot, and Assignment. Show how the requirement workbook and venue CSV are converted into these dataclasses.

## 5. Constraint Engine
Separate hard constraints from soft constraints. Hard constraints define feasibility; soft constraints define timetable quality.

## 6. Schedule Generator
Explain the greedy approach. Courses are sorted by difficulty, and each course is assigned to the first feasible room/day/time pattern that passes all hard constraints.

## 7. Optimisation
Explain local search. The optimiser attempts small moves and accepts them only when hard violations remain zero and the soft score improves.

## 8. Outputs
Show final_timetable.xlsx and violation_report.xlsx. Explain Summary, Timetable, Hard Violations, and Soft Violations sheets.

## 9. Evaluation
Report before/after metrics:

| Metric | Before | After |
|---|---:|---:|
| Hard violations | 0 | 0 |
| Soft violations | X | Y |
| Scheduled assignments | X | X |

## 10. Limitations
- Room suitability is simplified from resource type text.
- Staff availability from free-text remarks is not fully parsed.
- Common module grouping is identified but not fully merged across every Engineering programme in the DSC-only demo.
- The optimiser is heuristic and does not guarantee global optimality.

## 11. AI Usage Documentation

| Tool | Usage | Human validation |
|---|---|---|
| ChatGPT | Architecture, code generation, debugging suggestions | Reviewed code and tested with pytest |
| GitHub Copilot/Codex | Local implementation assistance and refactoring | Accepted only changes that preserve constraints |
| Python tests | Validation | Confirmed hard-constraint behaviour |

## 12. Operational Process Improvement
Suggest a standardised input template, automated validation before timetable submission, centralised conflict dashboard, and version-controlled timetable changes.
