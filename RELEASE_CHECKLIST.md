# Release Checklist

Use this checklist before final submission and GitHub release.

## Repository

- [ ] Final changes are merged to `main`.
- [ ] `main` is clean after validation.
- [ ] `main` has been pushed.
- [ ] No generated files are tracked.
- [ ] No virtual environments are tracked.
- [ ] No Python caches or pytest caches are tracked.
- [ ] No obsolete ZIP archives are tracked.
- [ ] No editor settings or temporary lock files are tracked.
- [ ] All final documentation is current: `README.md`, `DEMO.md`, `FINAL_RESULTS.md`, `RELEASE_CHECKLIST.md`, `REPORT_EVIDENCE.md`, `PRESENTATION_EVIDENCE.md`, `AI_USAGE_LOG.md`, `AI_ASSISTANCE_STATEMENT.md`.
- [ ] Required operational data remains present under `Data/`.
- [ ] Required source, tests and scripts remain present.

## Prototype

- [ ] Desktop application launches.
- [ ] **Consolidated Schedule** input is accepted when structurally valid.
- [ ] A generated timetable workbook is rejected as input.
- [ ] Engineering data loads successfully.
- [ ] DSC is included as part of Engineering.
- [ ] UI remains responsive and uses final plain-language labels.
- [ ] UI does not display internal template-number terminology.
- [ ] Remarks interpretation is enabled for the final product run.
- [ ] Multiple-room handling works.
- [ ] Hybrid handling uses the available recording-capability proxy.
- [ ] Special Requests Review is generated.
- [ ] Unscheduled classes remain visible.
- [ ] Scheduled hard violations remain zero.
- [ ] Proposed timetable output structure is unchanged.

## Validation

- [ ] Full test suite passes.
- [ ] Deterministic baseline run with remarks disabled is reproduced twice.
- [ ] Deterministic baseline metrics match:

```text
2777 required
2747 scheduled
30 unscheduled
98.92% coverage
0 scheduled hard violations
813 / 813 online scheduled
```

- [ ] Deterministic remarks-aware run is reproduced twice.
- [ ] Remarks-aware metrics match:

```text
2777 required
2715 scheduled
62 unscheduled
97.77% coverage
0 scheduled hard violations
```

- [ ] Remarks attribution reconciles:

```text
13 direct explicit effects
19 indirect displacements
30 unchanged unscheduled
0 unexplained
```

- [ ] Final product run is remarks-aware and executed last before release validation.
- [ ] `validate_release.py` reports `FINAL RELEASE VALIDATION: PASS`.
- [ ] Clean release ZIP builds.
- [ ] Clean release ZIP inspection passes.
- [ ] ZIP excludes `.git`, virtual environments, caches, generated outputs, editor settings, temporary files and old ZIP archives.
- [ ] Extracted ZIP can import the pipeline and UI launcher safely.

## GitHub

- [ ] Finalisation branch is pushed.
- [ ] Finalisation branch is merged into `main`.
- [ ] `main` is pushed after merge.
- [ ] Release tag `v1.0.0` is created unless it already exists.
- [ ] Release tag is pushed.
- [ ] Clean ZIP is attached to the GitHub release where possible.
- [ ] Old merged `codex/*` branches are identified.
- [ ] Only fully merged old branches are deleted.
- [ ] Unmerged or uncertain branches are preserved and reported.
