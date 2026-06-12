# Demo Script

1. Show the input files in `input/`.
2. Run:

```bash
python main.py
```

3. Explain terminal output:
   - Courses loaded
   - Rooms loaded
   - Scheduled assignments
   - Hard violations before/after optimisation
   - Soft violations before/after optimisation

4. Open `output_files/final_timetable.xlsx`.
5. Show `Summary` sheet first.
6. Show `Timetable` sheet and explain Template 2-compatible columns.
7. Show `Hard Violations` sheet. Target is zero.
8. Show `Soft Violations` sheet. Explain these are quality trade-offs, not infeasible schedules.
9. Explain local search optimisation:
   - tries moving classes
   - rejects moves that create hard violations
   - accepts moves that reduce soft violations
10. End with limitations and future improvements.
