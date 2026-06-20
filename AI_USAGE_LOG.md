# AI Usage Log

This project used AI assistance transparently. The user was the project architect and final decision-maker. ChatGPT and OpenAI Codex were used as support tools for implementation, debugging, testing, documentation and release preparation.

AI did not independently design the project. AI-generated suggestions were reviewed, corrected and validated before being retained.

| Stage | User Architectural Direction | AI Assistance | User Review Or Correction | Validation Evidence |
| --- | --- | --- | --- | --- |
| Problem framing and Engineering scope | Defined the project as an Engineering Cluster timetabling problem, with DSC included in Engineering. | Helped organise requirements into implementation phases. | Rejected DSC-only framing as the final deliverable. | Engineering run and Programme Breakdown confirm DSC inclusion. |
| Data modelling | Required explicit Course, Room, TimeSlot and Assignment objects. | Suggested dataclass usage and helper structure. | Preserved existing model boundaries and prevented duplicate dataclass definitions. | Model tests and downstream scheduler/exporter tests. |
| Hard and soft constraints | Defined hard constraints as non-negotiable and soft constraints as quality preferences. | Helped implement and test constraint checks. | Required scheduled assignments with hard violations to remain unacceptable. | Constraint tests and scheduled hard violation count of 0. |
| Schedule generator | Required a safe heuristic generator that leaves unsafe demand unscheduled. | Helped implement ordering, candidate filtering and retry controls. | Rejected changes that increased coverage by weakening constraints or changing demand. | Engineering baseline: 2747/2777 scheduled, 0 scheduled hard violations. |
| Engineering scaling and bottleneck reporting | Required Engineering to be the primary deliverable. | Helped add reports, diagnostics and evidence sheets. | Required unscheduled demand to remain visible. | Run summary, stakeholder views and residual analysis. |
| Shared online-room policy correction | Clarified that fully online teaching does not require physical room allocation. | Helped audit virtual-room semantics. | Corrected earlier treatment of `ONLINE_ROOM` as a scarce physical room. | Online baseline coverage: 813/813 scheduled. |
| Demand-metric integrity | Required stable comparison metrics. | Helped separate raw assignment counts from teaching-occurrence demand. | Rejected comparisons where the total assignment pool changed. | Required teaching occurrences remain 2777. |
| Resource and residual analysis | Required clear explanation of remaining unscheduled demand. | Helped classify room and F2F bottlenecks. | Required operational exceptions to be reported, not hidden. | Residual F2F analysis and exception queue. |
| Optimiser safety | Required optimisation to improve quality without harming feasibility. | Helped add optimiser acceptance checks and summaries. | Required optimiser output to preserve demand and hard safety. | Soft violations 3030 to 3019, hard safety preserved. |
| Stakeholder Excel outputs | Required evidence workbooks for decision-making. | Helped implement preflight, run summary, stakeholder views and manifest outputs. | Required output clarity without changing the proposed timetable structure. | Release validator checks required workbooks and sheets. |
| Minimal desktop UI | Required a local dark desktop UI, not a web app. | Helped implement Tkinter UI and controller tests. | Required a single Consolidated Schedule input and plain-language output buttons. | UI/controller tests and demo flow. |
| Workbook-role detection | Clarified operational workbook roles. | Helped implement structure-based validation. | Corrected prior confusion over workbook names and required structure-based detection rather than filename-based acceptance. | Workbook-role tests reject generated timetable as input. |
| Repository cleanup and release packaging | Required a clean final repository and distributable ZIP. | Helped create packaging script, exclusions and release checklist. | Required generated files, virtual environments and caches to stay out of Git. | Clean release builder tests and ZIP inspection. |
| Remarks interpretation innovation | Required deterministic, explainable handling of free-text scheduling remarks. | Helped implement supported patterns such as multiple rooms, hybrid delivery and preferences. | Required unsupported or unclear remarks to remain visible rather than guessed. | Remarks interpreter, scheduling and report tests. |
| Remarks refinement | Required ambiguous remarks to remain non-blocking unless explicit and supported. | Helped refine enforcement levels and review classifications. | Rejected over-broad hard interpretation of low-confidence remarks. | Special Requests Review and remarks handling counts. |
| Baseline restoration and deterministic comparison | Required a comparable baseline against the same 2777 teaching occurrences. | Helped restore neutral disabled-remarks behaviour and comparison reports. | Required zero unexplained enhanced-only differences. | Baseline 2747/30, enhanced 2715/62, attribution reconciles. |
| Final release preparation | Required final documentation, validation and GitHub release readiness. | Helped update docs, AI disclosure and packaging checks. | Required honest AI disclosure and final validation before release. | Tests, compile check, deterministic runs, release validation and clean ZIP build. |

## Meaningful User Corrections

The user corrected or clarified several important project decisions:

- The final deliverable is Engineering scope, not DSC-only.
- DSC is part of Engineering and should not be presented as a separate inclusion feature.
- Workbook roles must be detected from structure and headers, not filenames.
- The final UI should be a minimal dark desktop app with one **Consolidated Schedule** input.
- Internal template-number terminology should not appear in the UI.
- Remarks such as multiple rooms and hybrid delivery matter for the final innovation.
- Ambiguous remarks must remain non-blocking and visible for staff review.
- The comparison denominator must be teaching occurrences, not raw assignment-object counts.
- Deterministic baseline restoration is required before claiming remarks-aware effects.
- Tests, full Engineering runs, generated evidence and release validation are required before release.

## Verification Summary

Final evidence expected for release:

- Tests: `220 passed`
- Core baseline: `2777` required, `2747` scheduled, `30` unscheduled, `98.92%` coverage
- Remarks-aware run: `2777` required, `2715` scheduled, `62` unscheduled, `97.77%` coverage
- Scheduled hard violations: `0`
- Online baseline coverage: `813 / 813`
- Remarks attribution: `13` direct explicit effects, `19` indirect displacements, `30` unchanged unscheduled, `0` unexplained
- Release validator: `PASS`

## Limitations Of AI Assistance

AI assistance can produce useful code and explanations, but it can also make incorrect assumptions about metrics, repository state, stakeholder policy or domain semantics. The user reviewed AI-generated work, corrected inaccurate assumptions and accepted only changes supported by tests and generated evidence.

The final submission remains the user's responsibility.
