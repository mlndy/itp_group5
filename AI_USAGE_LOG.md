# AI Usage Log

## Cross-Check Note

This checkout does not contain `FINAL_RESULTS.md` or `RELEASE_CHECKLIST.md`, although the report task asks for cross-checks against them. The figures below follow the verified values supplied in the report-phase task prompt.

## AI Tools Used

The project used AI support from:

- ChatGPT
- Codex

AI was used as an assistant, not as an independent decision-maker.

## Types of Assistance

AI assistance supported:

- Planning project stages.
- Drafting targeted implementation prompts.
- Code generation.
- Test generation.
- Debugging.
- Metric interpretation.
- Documentation.

## Human Validation Performed

Human validation included:

- Reviewing code changes.
- Running `pytest`.
- Running the Engineering pipeline.
- Inspecting generated Excel workbooks.
- Rejecting changes that altered the comparison denominator.
- Reverting unsupported candidate-budget changes.
- Validating virtual-room semantics against supplied requirements.
- Preserving all hard constraints.

The final validated figures were:

- Input course records: `507`
- Consolidated scheduling requirements: `465`
- Required teaching occurrences: `2777`
- Scheduled teaching occurrences: `2747`
- Unscheduled teaching occurrences: `30`
- Coverage rate: `98.92%`
- Scheduled hard violations: `0`
- Online required occurrences: `813`
- Online scheduled occurrences: `813`
- Online unscheduled occurrences: `0`
- Tests: `112 passed`
- Release validator: `PASS`

## Important Examples of Critical Review

Raw `Assignment` counts were found to use inconsistent units. A scheduled assignment represents one scheduled week occurrence, while an unscheduled placeholder can represent several missing weeks. This led to the use of invariant teaching-occurrence metrics for final reporting.

The single `ONLINE_ROOM` was identified as a synthetic shared delivery placeholder rather than an exclusive physical venue. This interpretation was validated against supplied requirements before being used in the final evidence.

An artificial virtual-room expansion was not retained. The final approach did not invent additional virtual rooms.

Optimiser output was rejected unless feasibility and coverage were preserved. The verified optimiser run reduced soft violations from `3030` to `3019`, an improvement of `11`, while preserving coverage and hard safety.

Remaining `ENG1001` demand was reported as an operational exception rather than forced into invalid rooms or times.

## Limitations of AI Assistance

AI assistance can suggest code, tests, explanations, and documentation, but it can also make incorrect assumptions about project state, metrics, or policy interpretation.

Known limitations:

- AI can over-trust raw output counts unless metric definitions are checked.
- AI can suggest changes that appear helpful but alter the comparison denominator.
- AI can miss domain-specific policy details unless source requirements are reviewed.
- AI cannot independently verify stakeholder acceptance.
- AI-generated documentation still requires human checking against actual project artefacts.

## Student Accountability and Understanding

Final decisions remained with the student team. The team was responsible for:

- Understanding the timetabling problem.
- Reviewing AI-generated code and documentation.
- Running tests and validation commands.
- Checking generated Excel reports.
- Deciding which changes were valid.
- Preserving hard constraints.
- Explaining remaining operational exceptions.

AI was used as a productivity and review tool. It did not independently make final design, validation, or submission decisions.
