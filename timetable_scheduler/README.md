# DSC2204 ITP Timetabling System

Prototype timetabling system for the SIT Engineering Cluster. It reads Excel/CSV input, generates a feasible timetable using hard constraints, optimises soft constraints with local search, and exports stakeholder-friendly Excel reports.

## Run

```bash
pip install -r requirements.txt
python main.py
```

Generated files:

```text
output_files/final_timetable.xlsx
output_files/violation_report.xlsx
```

## Test

```bash
pytest
```

## Build stages

1. Data models + loader
2. Constraint checker
3. Greedy schedule generator
4. Local search optimiser
5. Excel exporter + full pipeline

## Scoring logic

Hard constraints are treated as feasibility rules. The optimiser only accepts a timetable move if hard violations remain zero and the soft-constraint score improves.

## Main hard constraints implemented

- No room double-booking
- No staff double-booking
- No student group double-booking
- Room capacity >= class size
- Online classes use virtual room
- F2F classes do not use virtual room
- Week pattern compliance
- No classes outside 09:00-18:00
- No Wednesday afternoon classes from 13:00
- No Friday 12:00-14:00 classes
- No Friday classes after 17:00
- Flexible lunch break for student groups

## Main soft constraints implemented

- Low room utilisation penalty
- First/last slot penalty
- Online/F2F adjacent switch penalty
- Tutor idle gap penalty
- Student group consecutive-hour penalty
