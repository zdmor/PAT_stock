# WTOS-1 Opportunity Eligibility Fail-Closed Review — 2026-09-02

STATUS: `NEEDS_ONE_MORE_BRANCH_FIX`

Independent T-3 review used current WTOS `main=ce9ade14bf5b6c8f1d7a904423c9d4b931dd7adf` and private branch `review/wtos1-decision-architecture-v01-20260902-corrected@ad1dd92b62a04f388aad825965118694643caa53`.

The six findings in `WTOS1_CODEX_FINAL_FAIL_CLOSED_REVIEW_20260902.md` are closed in the branch implementation and tests. One additional merge-blocking fail-closed gap remains in the Active Opportunity Funnel.

## Finding 7 — UNKNOWN candidate eligibility can become zero opportunities

Current `classify_opportunity_funnel()` behavior:

```python
for item in universe:
    if not isinstance(item, dict):
        rejected.append(...)
        continue
    if item.get("eligible") is not True:
        continue
```

Therefore a completed scan such as:

```python
{
  "scan_status": "SCAN_COMPLETE",
  "hard_gate": True,
  "universe": [{"candidate_id": "C1", "eligible": "UNKNOWN"}]
}
```

can finish with no candidates and no rejected records and be returned as `NO_VALID_OPPORTUNITY`.

That violates the branch's own provisional contract:

- every supplied universe record must carry an explicit boolean eligibility classification;
- unclassified universe membership must be `UNRESOLVED`, never zero/NONE/pass;
- `NO_VALID_OPPORTUNITY` is valid only after a completed **valid** scan returns no eligible candidate.

This is also inconsistent with WTOS core semantics `UNKNOWN != 0`.

## Required fix

On the same private branch:

1. Make the opportunity funnel require explicit boolean `eligible` for every supplied universe record participating in the scan.
2. Missing / `None` / `UNKNOWN` / non-boolean eligibility must make the opportunity set `OPPORTUNITY_SET_UNRESOLVED`; do not silently skip the record.
3. A malformed universe item must also fail the opportunity set closed rather than allowing a misleading `NO_VALID_OPPORTUNITY` / `CANDIDATE_NOT_ACTIONABLE` conclusion.
4. Explicit `eligible=False` may be excluded normally.
5. A completed valid scan in which every record has explicit boolean eligibility and all are `False` may legitimately return `NO_VALID_OPPORTUNITY`.
6. Preserve reason ownership and expose a deterministic reason code such as `UNIVERSE_ELIGIBILITY_UNCLASSIFIED` / `CANDIDATE_INPUT_MALFORMED`.

## Required tests

Add regression cases for:

- missing `eligible`;
- `eligible=None`;
- `eligible="UNKNOWN"`;
- `eligible=1`;
- mixed explicit eligible records plus one unclassified record;
- malformed non-dict universe item;
- all records explicitly `eligible=False` -> valid `NO_VALID_OPPORTUNITY`.

Run targeted and full Runtime suites. Commit and push the same private branch and verify remote retrieval. Append `Opportunity Eligibility Fail-Closed Fix Result` to `reviews/WTOS1_CODEX_TASK.md`.

## Boundaries unchanged

`RESEARCH_SHADOW / NOT_LIVE / NOT_AUTHORITY`.

Do not merge to `main`. Do not modify `active/`, real ChatGPT automations, schedules, enabled state, strategy authority, risk ceilings, Broker Write, or Production Cutover.

After the fix, T-3 must independently re-read the remote branch and tests before giving non-live research-shadow merge readiness.