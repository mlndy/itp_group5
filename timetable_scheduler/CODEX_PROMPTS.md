# DSC2204 ITP — Codex Working Guide and Prompt Pack

Project: **Timetabling System for SIT Engineering Cluster**

Use this file with **GitHub Copilot / Codex in VS Code**. The purpose is to keep Codex aligned with the project architecture, constraints, and assessment requirements.

---

## 1. Role split

### ChatGPT role
ChatGPT is the **project architect**:

- Defines system design and data flow
- Protects project scope and requirements
- Reviews whether generated code matches hard/soft constraints
- Helps explain decisions for report and presentation
- Provides debugging strategy and validation logic

### Codex role
Codex is the **implementation assistant**:

- Writes or edits Python files inside VS Code
- Refactors code without changing architecture
- Adds tests
- Fixes tracebacks
- Improves pandas/openpyxl handling
- Helps run and debug the prototype locally

### Student/team role
The student/team remains accountable:

- Reviews every change
- Runs tests
- Checks output Excel files
- Explains the approach during presentation
- Documents AI usage transparently

---

## 2. Non-negotiable architecture

The system must follow this pipeline:

```text
Input Excel / CSV
        ↓
Data Loader
        ↓
Structured Models
Course, Room, TimeSlot, Assignment
        ↓
Constraint Engine
Hard constraints + soft constraints
        ↓
Greedy Feasible Scheduler
Target: 0 hard violations
        ↓
Local Search Optimiser
Reduce soft violations only
        ↓
Exporter
Template 2-style timetable + violation report
        ↓
Demo / Report / Slides
Evidence of operational improvement
```

Do **not** let Codex replace this with a completely different architecture unless ChatGPT approves it first.

---

## 3. Project folder structure

Expected structure:

```text
timetable_scheduler/
├── main.py
├── config.py
├── data/
│   ├── models.py
│   ├── loader.py
│   ├── synthetic.py
│   └── availability_parser.py
├── engine/
│   └── constraint_checker.py
├── generator/
│   └── scheduler.py
├── optimiser/
│   └── local_search.py
├── output/
│   └── exporter.py
├── tests/
│   ├── test_constraints.py
│   ├── test_scheduler.py
│   ├── test_exporter.py
│   └── test_availability_parser.py
├── input/
│   ├── 2510_DSC.xlsx
│   ├── Venue Information(Campus Court).csv
│   ├── Common Modules(Sheet1).csv
│   └── Upload template_System (Template 2).xlsx
└── output_files/
    ├── final_timetable.xlsx
    └── violation_report.xlsx
```

---

## 4. Existing dataclasses

Use these dataclasses. Do **not** redefine them unnecessarily.

```text
Course:
- module_code
- activity
- prog_yr
- class_size
- delivery_mode
- teaching_weeks
- week_pattern
- staff_ids
- duration_hrs
- is_common_module

Room:
- room_id
- capacity
- room_type

TimeSlot:
- day
- start_time
- week

Assignment:
- course
- room
- timeslot
- hard_violations
- soft_violations
- status property
```

If extra information is needed, prefer adding optional fields in a backward-compatible way, or use separate dictionaries/helper dataclasses.

---

## 5. Hard constraints

Hard constraints must never be violated in the final schedule.

```text
Room:
- No two classes in the same room at the same time
- Room capacity must be >= class enrolment

Tutor:
- A tutor cannot teach two classes at the same time

Group:
- A student group cannot attend two classes at the same time

Mode:
- ONLINE classes must use the VIRTUAL room only
- F2F classes must NOT use the VIRTUAL room

Pattern:
- ODD-week courses run on odd weeks only
- EVEN-week courses run on even weeks only

Calendar:
- No classes on public holidays
- No classes during term breaks

Time:
- No classes before 09:00
- No classes after 18:00
- No Wednesday classes from 13:00 onwards
- No Friday classes from 12:00 to 14:00
- Lunch break: each group should have at least 1 free hour between 11:00 and 14:00
- No Saturday classes
- No Friday classes after 17:00
```

---

## 6. Soft constraints

Soft constraints should be reduced where possible, but never at the cost of hard constraints.

```text
Mode:
- Avoid Online↔F2F switch in adjacent slots for the same tutor
- Avoid Online↔F2F switch in adjacent slots for the same group

Gap:
- Avoid tutor idle gaps longer than 2 hours on the same day
- Avoid student group having more than 4 consecutive teaching hours
- Avoid back-to-back classes beyond 3 consecutive hours for groups
- Cluster tutor classes to minimise wasted free slots

Room:
- Prefer room utilisation >= 60% of capacity

Group:
- Avoid scheduling groups in the very first or very last slot of the day

Time:
- Prefer classes to end by 17:00
```

---

## 7. Common module rule

Common modules are listed in `Common Modules(Sheet1).csv` or equivalent.

Rule:

```text
If a module is taken by multiple cohorts, all those cohorts should be scheduled at the same time, unless there is a special request.
The scheduler should treat it as one combined class using the total enrolment across the cohorts.
The assigned room must have enough capacity for the combined enrolment.
```

Implementation expectation:

```text
Group single-cohort modules normally.
Group common modules by module_code + activity.
Combine class_size.
Combine prog_yr/group identifiers.
Preserve all staff_ids.
Schedule once.
Export once or export linked rows consistently, depending on output needs.
```

---

## 8. Output file requirements

The final timetable must be exported in a Template 2-style format.

Most important rule:

```text
Column Room1 must contain the assigned room ID generated by the algorithm.
```

Expected key columns:

```text
Module
Class Type
Template
Group
Day
Start
End
Class Size
Room1
Staff1
Staff2
Tri Week
Activity Type
Duration
Remark
Location Hostkey
```

Recommended exporter behaviour:

```python
"Room1": assignment.room.room_id if assignment.room else None
"Location Hostkey": assignment.room.room_id if assignment.room else None
```

The violation report should separate:

```text
Hard Violations
Soft Violations
Unscheduled Classes
Summary Metrics
```

---

## 9. Validation commands

Run these after every meaningful Codex edit:

```bash
python main.py
pytest
```

Optional checks:

```bash
python main.py --scope dsc
python main.py --scope eng --skip-optimisation
python -m pytest tests/test_constraints.py
python -m pytest tests/test_scheduler.py
python -m pytest tests/test_exporter.py
```

Expected demo-quality result:

```text
Hard violations after optimisation: 0
Scheduled assignments: all or nearly all required assignments
Soft violations after optimisation: lower than before optimisation
final_timetable.xlsx generated
violation_report.xlsx generated
Room1 populated with assigned room IDs
```

---

# 10. Master Codex prompt

Paste this first when opening a new Codex thread.

```text
You are assisting with a Python 3.11 university timetabling prototype for DSC2204 ITP.

Project title: Timetabling System for SIT Engineering Cluster.

Act as an implementation assistant, not the architect. Follow the existing architecture and do not redesign the whole project unless asked.

Architecture:
Input Excel/CSV -> loader -> dataclasses -> constraint checker -> greedy scheduler -> local search optimiser -> Excel exporter.

Use the existing dataclasses in data/models.py. Do not redefine them unless strictly necessary.

Hard constraints must never be violated. Soft constraints should be reduced only when hard violations remain zero.

Use config.py constants. Do not hardcode time/day rules in multiple files.

Keep code simple, readable, and explainable for a Year 1 Digital Supply Chain student. Use type hints and short docstrings.

After editing, ensure:
- python main.py runs
- pytest passes
- output_files/final_timetable.xlsx is generated
- output_files/violation_report.xlsx is generated
- Room1 column contains the assigned room ID
- hard violations after optimisation are zero

Do not make unnecessary dependencies beyond pandas, openpyxl, pytest, and standard library.
```

---

# 11. Optional AGENTS.md content

If using Codex CLI/Web/App, create an `AGENTS.md` file at the repository root and paste this:

```text
# AGENTS.md

## Project
DSC2204 ITP — Timetabling System for SIT Engineering Cluster.

## Role
You are an implementation assistant. ChatGPT is the project architect. Follow the existing architecture and avoid unnecessary redesign.

## Tech stack
Python 3.11, pandas, openpyxl, pytest.

## Architecture
Input Excel/CSV -> loader -> dataclasses -> constraint checker -> greedy scheduler -> local search optimiser -> Excel exporter.

## Coding rules
- Use existing dataclasses in data/models.py.
- Use config.py for constants.
- Keep functions small and single-purpose.
- Add type hints.
- Add short docstrings.
- Avoid adding new dependencies.
- Preserve clear separation between hard and soft constraints.

## Scheduling rule
Hard constraints define feasibility. Soft constraints define quality. Optimisation must never introduce hard violations.

## Output rule
Room1 in final_timetable.xlsx must contain the assigned room ID from the algorithm.

## Validation
Run:
python main.py
pytest

Success means:
- Hard violations = 0
- Output Excel files generated
- Room1 populated
- Tests pass
```

---

# 12. Prompt: inspect current codebase

```text
Inspect the current repository for the timetabling project.

Tasks:
1. Summarise the current data flow from input files to final Excel output.
2. Identify whether hard and soft constraints are clearly separated.
3. Check whether Room1 in the exporter is populated using assignment.room.room_id.
4. Check whether common modules are handled by combined enrolment and shared scheduling.
5. List missing tests.

Do not edit files yet. Return a concise audit report with file paths and recommended next edits.
```

---

# 13. Prompt: fix exporter Room1

```text
Open output/exporter.py.

Goal:
Ensure the final timetable export writes the algorithm-assigned room ID into the Room1 column.

Requirements:
- Room1 must equal assignment.room.room_id if a room exists.
- Location Hostkey should also use the same room ID where possible.
- Do not use room description, room type, or capacity in Room1.
- Preserve existing Template 2-style columns.
- Add or update a test in tests/test_exporter.py to verify Room1 is populated correctly.

After editing, run pytest and explain what changed.
```

---

# 14. Prompt: strengthen hard constraints

```text
Open engine/constraint_checker.py and config.py.

Goal:
Ensure all hard constraints are implemented and tested.

Hard constraints:
- No two classes in the same room at the same time
- Tutor cannot teach two classes at the same time
- Student group cannot attend two classes at the same time
- Room capacity must be >= class enrolment
- ONLINE classes use VIRTUAL room only
- F2F classes must not use VIRTUAL room
- ODD-week courses only on odd weeks
- EVEN-week courses only on even weeks
- No classes on public holidays
- No classes during term breaks if configured
- No classes before 09:00
- No classes after 18:00
- No Wednesday classes from 13:00 onwards
- No Friday classes from 12:00 to 14:00
- No Saturday classes
- No Friday classes after 17:00
- Lunch rule: each group must have at least 1 free hour between 11:00 and 14:00

Requirements:
- Keep each check in a small function.
- Return readable violation messages.
- Use config.py constants where possible.
- Add or update pytest tests for each hard constraint.
- Do not change scheduler logic unless needed.
```

---

# 15. Prompt: strengthen soft constraints

```text
Open engine/constraint_checker.py and optimiser/local_search.py.

Goal:
Improve soft constraint scoring while keeping the logic explainable.

Soft constraints:
- Avoid Online↔F2F switch in adjacent slots for the same tutor
- Avoid Online↔F2F switch in adjacent slots for the same group
- Avoid tutor idle gaps longer than 2 hours on the same day
- Avoid student group having more than 4 consecutive teaching hours
- Avoid back-to-back classes beyond 3 consecutive hours for groups
- Cluster tutor classes to minimise wasted free slots
- Prefer room utilisation >= 60% of capacity
- Avoid groups in very first/last slot of day
- Prefer classes to end by 17:00

Requirements:
- Create a score where lower is better.
- Hard violations must not be part of the soft score.
- The optimiser must only accept a move if hard violations remain zero and the soft score improves.
- Add tests that prove the optimiser never accepts a move that introduces hard violations.
```

---

# 16. Prompt: implement common modules

```text
Open data/loader.py, data/models.py if needed, generator/scheduler.py, and tests.

Goal:
Implement common module handling.

Common module rule:
If a module is taken by multiple cohorts, all cohorts must be scheduled at the same time, using one room large enough for the combined enrolment, unless a special request exists.

Implementation requirements:
- Read Common Modules(Sheet1).csv.
- Identify common modules by module code.
- Group common-module Course objects by module_code + activity.
- Combine class_size across cohorts.
- Preserve all cohort/group identifiers so group clash and lunch checks still work.
- Preserve staff_ids without duplicates.
- Schedule the grouped common module once.
- Export the grouped cohort information clearly in the Group column.

Add tests:
- Combined enrolment is calculated correctly.
- Common module uses one shared timeslot.
- Room capacity check uses combined enrolment.
- Group clash checks still catch conflicts with any linked cohort.
```

---

# 17. Prompt: improve greedy scheduler

```text
Open generator/scheduler.py.

Goal:
Improve the greedy scheduler while keeping it simple and explainable.

Scheduling logic:
1. Generate valid candidate timeslots from config.py.
2. Sort courses by difficulty:
   - common modules first
   - larger class size first
   - longer duration first
   - fewer compatible rooms first
3. For each course and teaching week, try candidate timeslots and rooms.
4. Accept the first assignment with zero hard violations.
5. If no feasible slot exists, mark the class as unscheduled with a clear hard violation message.

Requirements:
- Do not brute force all full timetable combinations.
- Keep helper functions small.
- Use check_hard_constraints from the constraint engine.
- Do not allow the scheduler to knowingly place an assignment with hard violations.
- Add tests for unscheduled assignment behaviour.
```

---

# 18. Prompt: improve local search optimiser

```text
Open optimiser/local_search.py.

Goal:
Improve timetable quality using local search without breaking hard constraints.

Rules:
- Lower soft score is better.
- A move may change a class timeslot and/or room.
- A move is accepted only if:
  1. hard violations remain zero
  2. soft score improves
- Keep the method explainable for a project presentation.
- Avoid complex black-box algorithms.

Suggested approach:
- Iterate through assignments.
- Generate nearby candidate slots first, then other valid slots.
- Try suitable rooms.
- Evaluate candidate schedule.
- Keep the best improving move.
- Stop after max_iterations or no improvement.

Add summary logging:
- soft score before optimisation
- soft score after optimisation
- number of accepted moves
- hard violations after optimisation
```

---

# 19. Prompt: build availability parser

```text
Create data/availability_parser.py and update loader/checker if needed.

Goal:
Parse simple free-text staff/course remarks into scheduling restrictions.

Supported examples:
- Only Mon AM
- Only Monday morning
- Not Friday
- No Wed PM
- After 2pm
- Before 5pm
- Start at 7pm
- Unavailable Wednesday afternoon

Requirements:
- Keep parser rule-based and explainable.
- Do not use NLP libraries.
- Return a small dataclass or dictionary with:
  - allowed_days
  - blocked_days
  - earliest_start
  - latest_end
  - allowed_periods
  - blocked_periods
  - start_at_7pm flag
- Integrate parsed restrictions into hard constraint checks only when the wording is clear.
- Ambiguous remarks should be preserved as notes, not forced into constraints.
- Add tests for each supported phrase.
```

---

# 20. Prompt: fix loader errors

```text
The loader is failing on the real Excel/CSV files.

Traceback:
[paste traceback]

Relevant file:
[paste loader.py or error function]

Input file column names:
[paste df.columns output]

Goal:
Fix the loader so it robustly reads the uploaded SIT requirement/template files.

Requirements:
- Normalise column names safely.
- Handle missing optional columns.
- Keep required columns validated with clear error messages.
- Do not silently drop important rows.
- Add a small helper function for column lookup by possible names.
```

---

# 21. Prompt: fix hard violations after run

```text
python main.py produced hard violations.

Terminal output:
[paste output]

Violation report sample:
[paste first 10 hard violations]

Goal:
Identify whether the issue is in loader, scheduler, or constraint checker.

Tasks:
1. Trace how the violated assignment was created.
2. Check whether scheduler called check_hard_constraints before accepting it.
3. Check whether timeslot duration caused overlap detection to miss conflicts.
4. Patch the smallest necessary file.
5. Add a regression test for this exact violation.

Do not weaken the hard constraint.
```

---

# 22. Prompt: fix soft score not improving

```text
The optimiser is not reducing soft violations.

Current result:
Soft before optimisation: [paste]
Soft after optimisation: [paste]
Hard after optimisation: [paste]

Goal:
Improve the local search without making it complex.

Tasks:
1. Inspect score_schedule and optimise_schedule.
2. Confirm candidate moves are actually being generated.
3. Confirm hard-feasible improving moves are accepted.
4. Add logging for accepted moves.
5. Keep hard violations at zero.
6. Add a test using synthetic data where one move clearly improves soft score.
```

---

# 23. Prompt: add Excel formatting

```text
Open output/exporter.py.

Goal:
Improve Excel output readability for stakeholders.

Requirements:
- Keep Template 2-style column names.
- Freeze header row.
- Apply autofilter.
- Autosize columns.
- Highlight hard violations separately from soft violations.
- Add a Summary sheet with:
  - total assignments
  - scheduled assignments
  - unscheduled assignments
  - hard violation count
  - soft violation count
  - feasibility rate
- Do not break Room1 assignment logic.
- Add or update tests if possible.
```

---

# 24. Prompt: create demo mode

```text
Open main.py.

Goal:
Make the prototype easy to demo.

Requirements:
- Add clear terminal output.
- Show courses loaded and rooms loaded.
- Show initial schedule hard/soft violations.
- Show optimised schedule hard/soft violations.
- Show feasibility rate.
- Show generated output file paths.
- Support arguments:
  --scope dsc
  --scope eng
  --skip-optimisation
- Default should run DSC demo safely.

Keep the CLI simple and beginner-friendly.
```

---

# 25. Prompt: create tests for assessment confidence

```text
Create or update tests so the prototype has assessment-friendly evidence.

Required test areas:
- Room capacity violation
- Room clash violation
- Tutor clash violation
- Group clash violation
- Online class must use virtual room
- F2F class must not use virtual room
- Odd/even week validation
- Wednesday afternoon blocked
- Friday 12:00-14:00 blocked
- No Saturday classes
- Room1 exporter output
- Common module combined enrolment
- Optimiser does not introduce hard violations

Use synthetic Course, Room, TimeSlot, Assignment objects.
Do not depend on private real Excel files for unit tests.
```

---

# 26. Prompt: final repository audit

```text
Perform a final audit of the repository for DSC2204 ITP submission readiness.

Check:
1. python main.py runs successfully.
2. pytest passes.
3. final_timetable.xlsx is generated.
4. violation_report.xlsx is generated.
5. Room1 contains assigned room IDs.
6. Hard violations after optimisation are zero.
7. Common modules are grouped and scheduled using combined enrolment.
8. README explains how to run the project.
9. AI usage documentation exists.
10. Code is understandable and uses type hints.

Return:
- Pass/fail checklist
- Files changed
- Remaining risks
- Suggested wording for limitations section
```

---

# 27. Prompt: README update

```text
Update README.md for the final ITP prototype.

Include:
- Project title
- Problem statement
- System architecture
- Folder structure
- How to install dependencies
- How to run the DSC demo
- How to run Engineering cluster mode
- How to run tests
- Explanation of hard vs soft constraints
- Explanation of common module handling
- Output file descriptions
- Known limitations
- AI usage note

Keep it professional and concise.
```

---

# 28. Prompt: AI usage log update

```text
Update docs/ai_usage_log.md.

Create a transparent AI usage record with columns:
- Date
- Tool
- Task
- Prompt summary
- Output used
- Human validation performed
- Final decision

Include usage of:
- ChatGPT for architecture, constraint design, report/slides guidance, debugging strategy
- GitHub Copilot/Codex for local implementation support, refactoring, tests, and traceback fixes

Tone: honest, accountable, suitable for university submission.
```

---

# 29. Prompt: explain code for presentation

```text
Prepare a short explanation of the codebase for a non-technical presentation.

Explain:
1. How input data is loaded.
2. How courses, rooms, timeslots, and assignments are represented.
3. How hard constraints are checked.
4. How the greedy scheduler chooses a feasible slot.
5. How the optimiser improves soft constraints.
6. How the Excel output helps stakeholders.
7. Why the approach is suitable for an operations/resource allocation problem.

Keep it concise and presentation-friendly.
```

---

# 30. Manual review checklist before submission

Before submitting, manually check:

```text
[ ] python main.py runs without crashing
[ ] pytest passes
[ ] final_timetable.xlsx opens correctly
[ ] Room1 contains assigned room IDs
[ ] Day/Start/End are populated
[ ] Online classes use virtual room
[ ] F2F classes use physical rooms
[ ] Hard violation count is zero
[ ] Violation report separates hard and soft constraints
[ ] Common modules are scheduled once with combined enrolment
[ ] Report explains methodology, not just code
[ ] Slides show before/after optimisation result
[ ] AI usage is documented honestly
[ ] Limitations are stated clearly
```

---

## 31. Suggested limitation wording

Use this if needed in the report or slides:

```text
The prototype prioritises feasibility and explainability over advanced optimisation. It uses a greedy scheduler followed by a local search optimiser, which is suitable for demonstrating operational decision support but may not always produce a globally optimal timetable. Free-text staff availability remarks are handled only when they follow clear patterns; ambiguous remarks are preserved for manual review. Future work could include a richer availability interface, stronger optimisation methods, and integration with the actual institutional scheduling system.
```

---

## 32. Submission-quality success statement

Use this wording in the report/presentation if the run results support it:

```text
The prototype successfully converts programme requirement data and room information into structured scheduling objects, generates a feasible timetable with zero hard-constraint violations, improves timetable quality using soft-constraint optimisation, and exports stakeholder-readable Excel outputs. This demonstrates how a manual Excel-based scheduling workflow can be converted into a more transparent, automated, and auditable decision-support process.
```
