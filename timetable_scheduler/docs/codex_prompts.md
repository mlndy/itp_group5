# Codex / GitHub Copilot Prompts for VS Code

Use these prompts in VS Code after pasting the project files.

## 1. Validate loader against the real DSC workbook

```text
You are helping with a Python timetabling project. Check data/loader.py against input/2510_DSC.xlsx. The goal is to correctly parse the Module sheet into Course dataclasses. Keep the existing dataclasses and function signatures. Fix only parsing bugs, missing columns, NaN handling, and week parsing. Do not change the scheduling algorithm.
```

## 2. Improve constraint checker tests

```text
Add pytest tests for engine/constraint_checker.py. Cover room clash, staff clash, group clash, online/F2F room compatibility, blocked Wednesday afternoon, blocked Friday lunch, class ending after 18:00, odd/even week mismatch, and flexible lunch break. Use the existing Course, Room, TimeSlot, Assignment dataclasses. Keep tests small.
```

## 3. Debug scheduler when assignments are unscheduled

```text
Review generator/scheduler.py. Some courses are unscheduled. Improve candidate ordering without weakening hard constraints. Keep greedy scheduling explainable. Add debug print or helper summary showing module, activity, class size, delivery mode, and why no candidate was found.
```

## 4. Improve local search optimiser

```text
Review optimiser/local_search.py. Improve soft-constraint reduction while guaranteeing zero hard violations. Keep the algorithm understandable for a Year 1 supply chain project. Only accept moves if hard violations remain zero and the score improves.
```

## 5. Improve Excel output formatting

```text
Improve output/exporter.py. Keep the current sheets: Summary, Timetable, Hard Violations, Soft Violations. Add readable column widths, freeze panes, filters, wrapped text, and stakeholder-friendly ordering. Do not break Template 2-compatible columns.
```

## 6. Add demo-friendly terminal output

```text
Improve main.py terminal output for a university project demo. Show courses loaded, rooms loaded, scheduled assignments, hard violations, soft violations before and after optimisation, and exported file paths. Keep code simple and typed.
```

## Common Module and Room1 Verification Prompt

Use this when checking the latest prototype in VS Code:

```text
Review the timetabling prototype for two requirements:
1. In output/exporter.py, confirm the Template 2 column Room1 contains the assigned room ID from assignment.room.room_id, and Location Hostkey matches the same assigned room ID.
2. In generator/scheduler.py, confirm common modules are merged by module code and activity, use combined enrolment, preserve all cohort group IDs, and are scheduled once so all cohorts attend at the same time in one sufficiently large room.
Do not change the hard constraint rules. If improving the optimiser, only accept moves that keep hard violations at zero.
```
