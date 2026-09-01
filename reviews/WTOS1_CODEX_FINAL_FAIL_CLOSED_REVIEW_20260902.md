# WTOS-1 Final Fail-Closed Review — 2026-09-02

STATUS: NEEDS_ONE_MORE_BRANCH_FIX

Independent review confirms prior findings 1-5 are closed in private WTOS commit `3ff51d8c37637f9051f0941571657fa6d291dc36`, and the branch is based on actual current GitHub main `bf023c8bd98bd56723bdd6d2ebbb6a4425d3aad6`.

Before merge, close these remaining fail-closed gaps on the same private branch:

1. `calculate_market_state`: require `trading_day is True`. Missing/UNKNOWN/non-bool must return `UNRESOLVED`; do not treat absence as a trading-day PASS.
2. Market universe eligibility: if any stock participating in the supplied decision universe has missing/UNKNOWN/non-bool eligibility state, do not silently drop it from the breadth denominator. Return `UNRESOLVED` unless the input contract proves that the list contains only fully classified records.
3. Mainline constituent status: missing/UNKNOWN `suspended`, `is_st`, or `new_listing` must not be treated as False/safe. Require explicit PIT-safe boolean status (or an explicit fully-qualified eligibility fact) before including a constituent; otherwise Mainline must be `UNRESOLVED`.
4. Mainline market-data identity: require explicit price/benchmark source identity, freshness, as-of/decision-time validity and PIT-safe declaration for sector bars and benchmark bars. Taxonomy/membership identity alone is insufficient for the decision-affecting price/RS layer.
5. Persistence `3-of-5`: make the observation-count semantics explicit. If the rule is truly 3 of the last 5 trading days, require a complete 5-observation PIT history before `CONFIRMED`; otherwise return `UNRESOLVED`. If a shorter history is intentionally allowed, document and test that rule explicitly rather than silently confirming from only three observations.
6. Add malformed-input regression checks so market/mainline functions fail closed instead of raising on non-dict/non-list records or invalid date/source field types.

Required tests: explicit trading_day UNKNOWN/missing; mixed known+unknown universe eligibility; unknown ST/suspension/new-listing status; missing/stale/future sector-price and benchmark identities; 3-vs-5 persistence boundary; malformed market/mainline inputs.

Keep all existing boundaries: research-shadow only; no `main` merge, no `active/`, no automation/schedule/risk/Broker Write/Production Cutover changes.

When complete, commit and push the same private branch, verify remote retrieval, rerun targeted + full Runtime suites, and append `Final Fail-Closed Fix Result` to `reviews/WTOS1_CODEX_TASK.md`.
