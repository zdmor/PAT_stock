# WTOS-1 Codex Independent T-Review Findings — 2026-09-02

STATUS: `NEED_FIX_BEFORE_MERGE`

Transport/baseline correction is PASS: corrected private branch is retrievable from GitHub and is based on current `main` `bf023c8bd98bd56723bdd6d2ebbb6a4425d3aad6`. Scope remained branch-only/non-live.

However independent code review found the following defects in `runtime/src/decision_architecture_v01.py` at `e4f2cf15825800a7b33d03b9bd33ea1f5d5df3be`:

1. **Hard-gate UNKNOWN is not fail-closed.** `classify_opportunity_funnel()` only blocks when `hard_gate is False`. Missing/`UNKNOWN` hard-gate values currently proceed as though the gate passed. A completed scan with no candidates can therefore become `NO_VALID_OPPORTUNITY` even though gate state is unresolved. Require `hard_gate is True` to proceed. `False` => `BLOCKED_BY_HARD_GATE`; missing/UNKNOWN/non-bool => `OPPORTUNITY_SET_UNRESOLVED` with an explicit gate-unknown reason.

2. **60D return lookback off-by-one can crash.** `calculate_mainline()` accepts sector/benchmark bars when `_bars_valid(..., 60)` passes, but `_return(..., 60)` requires 61 observations. Exactly 60 bars can yield `None` and then subtraction in `rs60`. Validate 61 bars for 60D return or otherwise define/implement the return convention consistently. Add exact 60/61 boundary tests.

3. **Advance/decline participation misclassifies unchanged stocks as decliners.** Current formula derives decliners as `N - advances`; unchanged names are therefore counted negative. Count `advance`, `decline`, and `unchanged` separately and compute participation from true advancers minus true decliners.

4. **Persistence remains an unverified decision-affecting derived input.** `daily_all_conditions` is trusted as a boolean history without its own source/as-of/PIT identity or deterministic recomputation. Because it can promote `EMERGING -> CONFIRMED`, this hidden derived input must either be recomputed from frozen historical inputs or carry explicit source identity/freshness/PIT semantics and fail to `UNRESOLVED` when not proven. Apply the same discipline to lifecycle history such as `prior_state` where it changes classification.

5. **Run-record UNKNOWN aggregation is incomplete.** `build_run_record()` currently aggregates missing run keys plus market blockers, but omits Mainline blockers and opportunity unresolved/unknown reason codes. `material_unknowns` should preserve all material unresolved dependencies relevant to replay/audit.

Also harden malformed-input handling where practical; `_known()` currently assumes hashable values.

Required action:

- Fix the above on the existing corrected private branch or a direct successor based on the same current main ancestry.
- Add regression tests for every finding.
- Run the same targeted/full local suites.
- Do not change `main`, `active/`, platform automations, schedule/enabled state, risk ceilings, Broker Write, or Production Cutover.
- Push the corrected private branch to actual GitHub and verify remote retrieval.
- Append a new `T-Review Fix Result` to `reviews/WTOS1_CODEX_TASK.md` with final commit, tests, files changed, and disposition for findings 1-5.

Do not claim merge-ready until findings 1-5 are closed or explicitly rebutted with reproducible evidence.