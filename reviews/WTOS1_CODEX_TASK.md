# WTOS-1 Decision Architecture v0.1 — Local Codex Long-Run Task

> PUBLIC TASK CARRIER ONLY. This file is NOT WTOS Current, Runtime Current, Infrastructure Current, or Live Authority.
>
> TARGET REPOSITORY: private local clone of `zdmor/WTOS`.
>
> Execute this task in the local WTOS working tree. Review, modify, test, commit and push the WTOS branch directly. Do NOT implement changes in this public task repository.

## Authorization

`LONG_RUN_BRANCH_ONLY_IMPLEMENTATION_AND_REVIEW`

Work continuously. Do not stop for ordinary confirmations. Do not ask “should I continue?”. If one lane is blocked, record the blocker and continue every other safe lane. Return only after all safely executable work is exhausted.

## 0. Startup — Formal Current

In the local private `WTOS` repository:

1. Fetch latest remote `main` and record `BASELINE_MAIN_SHA`.
2. First read `SYSTEM_MANIFEST.yaml`.
3. Follow only the relevant resolver and exact files it requires.
4. For current ChatGPT WTOS review/improvement, resolve at minimum:

`SYSTEM_MANIFEST.yaml -> project/MANIFEST.yaml -> project/07_CHATGPT_REVIEW_RUNTIME_CONTRACT.md -> runtime/MANIFEST.yaml -> runtime/chatgpt/MANIFEST.yaml -> runtime/chatgpt/CURRENT_OPERATING_MODEL.md -> runtime/chatgpt/AUTOMATION_SNAPSHOT.md -> runtime/chatgpt/INPUT_SOURCES.md -> runtime/chatgpt/OUTPUT_CONTRACT.md -> runtime/chatgpt/GAPS_AND_ITERATION.md -> active/ACTIVE_RULE_INDEX.yaml -> exact referenced authority artifacts as needed`

Historical/frozen WTOS may be read only for explicit reuse analysis.

Never infer Current from chat history, email, handoff, Issue, latest filenames, latest commit semantics, old Canonical packs, or frozen material.

Preserve:

- `PROJECT != RUNTIME != INFRASTRUCTURE != LIVE_AUTHORITY`
- `CURRENT_CHATGPT_RUNTIME != FUTURE_LOCAL_RUNTIME`
- `FROZEN != CURRENT != AUTHORITY`
- `RESEARCH != LIVE_AUTHORITY`
- `UNKNOWN != 0`
- `Signal != Trade`
- `CANDIDATE != AUTHORIZED_PLAN != POSITION`
- `PROPOSED_RESULT != BROKER_ORDER != BROKER_FILL`

## 1. GitHub authentication / secret handling

Use the machine's already-configured GitHub authentication for the private WTOS repo.

Prefer:

1. existing Git credential / Git Credential Manager;
2. existing authenticated `gh` session;
3. only if required, an existing local PAT-backed credential already present on this machine.

If a PAT-backed local file is required, use it only locally for authentication. Never print, echo, display, summarize, log, transmit, copy, commit, or expose the token or any part of it. Do not place it in repository files, `.env`, tests, reports, Issues, email, or final output.

Final report may state only:

- `GITHUB_AUTH=PASS/FAIL`
- `FETCH=PASS/FAIL`
- `PUSH=PASS/FAIL`

Secrets are never WTOS evidence.

## 2. Working branch and commit rule

Create a fresh branch from remote `main` in the private WTOS repo.

Preferred branch:

`review/wtos1-decision-architecture-v01-20260901`

If it already exists, use a clear equivalent.

Do not work on `main`. Do not merge to `main`.

You ARE authorized to modify the relevant WTOS files on this branch, run tests, make durable commits, and push the branch. Commit the actual reviewed/modified WTOS files directly in the private WTOS branch. Do not return only a design memo.

## 3. Mission

This is not a prompt-shortening exercise. Repair the decision architecture of the CURRENT ChatGPT WTOS-1 so the system becomes logically complete, evidence-grounded, and actually capable of finding opportunities rather than merely blocking risk.

Target causal chain:

`SOURCE/TRUTH -> MARKET STATE -> MARKET PERMISSION -> MAINLINE/SECTOR LEADERSHIP -> ACTIVE UNIVERSE SCAN -> OPPORTUNITY -> CANDIDATE STATE -> SETUP/LOCATION -> ENTRY/MAX BUY -> INVALIDATION -> PAYOFF/EXIT MODEL -> ACCOUNT/PORTFOLIO -> RISK -> POSITION SIZE -> AUTHORIZATION -> USER ACTION`

WTOS-1 must not degrade into:

`DATA BLOCKED -> ACCOUNT BLOCKED -> NO BUY`

Risk is a boundary, not the purpose of WTOS.

`ZERO_VALID_OPPORTUNITIES` is acceptable.

`ZERO_ACTUAL_SCAN` is not acceptable.

## 4. Field / capability existence audit

Audit every decision-affecting WTOS-1 field/capability and classify it as one or more of:

`DEFINED / PARTIALLY_DEFINED / UNDEFINED / DISCRETIONARY_LLM_ONLY / SOURCE_MISSING / ALGORITHM_MISSING / RUNTIME_NOT_CONNECTED / OUTPUT_ONLY / REDUNDANT / RESEARCH_ONLY / LIVE_AUTHORITY`

At minimum audit:

Authority, Trading Day, Data/Freshness, Account, Market State, Market Permission, Market Breadth, Market Participation, Market Trend, Sector/Mainline, Relative Strength, Leader, Universe, Active Scan, Opportunity, Candidate lifecycle, Thesis, Setup, Entry, MaxBuy, Invalidation, Payoff, Risk per unit, Risk budget, Position size, Execution conditions, Cancel conditions, Authorization, WHY_NOT_BUY, WTOS1->WTOS3 handoff, run identity, plan identity.

A capability exists only when semantics, source, computation/decision rule, UNKNOWN behavior, and downstream consumer are sufficiently defined.

Produce a compact Field Existence Matrix.

## 5. Market State v0.1

Design and implement deterministic `PROVISIONAL_MEASUREMENT_V0.1` for A-share Market State.

This is not automatically Live Authority.

Separate `MARKET_STATE` from `MARKET_PERMISSION`.

Do not restore old undefined Market Score 80/60 thresholds.

Evaluate a minimal robust formulation using, where supportable:

- structural/long trend, e.g. broad market vs MA200 or equivalent long-horizon rule;
- intermediate trend, candidate baseline: `UP if Close > MA20 > MA60`, `DOWN if Close < MA20 < MA60`, else `MIXED`;
- breadth: `% eligible stocks > MA20`, `% > MA60`, advance/decline participation;
- participation/liquidity: e.g. `5D average turnover / 20D average turnover`;
- cross-index confirmation across suitable A-share indices.

Candidate state vocabulary may be `RISK_ON / MIXED / RISK_OFF / UNRESOLVED` or a better deterministic vocabulary if justified.

Define exact source, as_of, lookback, formulas, transition logic, missing-data behavior, source-conflict behavior, and UNKNOWN behavior.

Do not invent probabilities.

## 6. Mainline v0.1

Design and implement deterministic `PROVISIONAL_MEASUREMENT_V0.1` for Mainline / Sector Leadership.

Initial hypothesis to evaluate:

- Trend: sector `Close > MA20 > MA60` and MA20 recent slope > 0.
- Relative Strength: 20D and 60D sector excess return vs broad benchmark > 0.
- Breadth: >50% of eligible sector constituents above MA20.
- Participation: sector 5D average turnover >= sector 20D average turnover.
- Persistence: major conditions persist at least 3 of previous 5 trading days.

Lifecycle candidates:

`EMERGING / CONFIRMED / WEAKENING / LOST / UNRESOLVED`

Do not blindly accept these exact parameters. Research reasonable alternatives, but do not optimize using future holdout results and do not call parameters “best” without evidence.

Define exact machine semantics for:

- sector taxonomy/classification source;
- PIT constituent membership;
- sector aggregate/index construction;
- breadth denominator;
- suspensions;
- ST/*ST;
- new listings;
- delisted securities;
- turnover;
- relative-strength benchmark;
- leader concentration/dominance;
- persistence;
- WEAKENING;
- LOST;
- re-confirmation;
- `DAILY_THEME` vs `MAINLINE`;
- parent-sector / child-theme behavior.

A one-day surge must not automatically become `CONFIRMED`.

Insufficient data => `MAINLINE=UNRESOLVED`, not NONE.

## 7. Active Opportunity Funnel

Restore the useful historical capability `ACTIVE_CANDIDATE_GENERATION` without restoring the old 11-engine runtime.

Review historical WTOS only as research/design evidence, including `historical/wtos-v1.2-live-baseline` and current migration evidence.

Implement a minimal lifecycle similar to:

`UNIVERSE -> DISCOVERED -> RESEARCH -> PRIORITY_WATCH -> BUY_READY -> PLAN_CANDIDATE -> AUTHORIZED`

with explicit rejected/blocked states.

Preserve four distinct no-buy outcomes:

- `NO_VALID_OPPORTUNITY`
- `CANDIDATE_NOT_ACTIONABLE`
- `BLOCKED_BY_HARD_GATE`
- `OPPORTUNITY_SET_UNRESOLVED`

Do not collapse these into generic NO BUY.

Restore strong `WHY_NOT_BUY` semantics with reason ownership such as:

`MARKET / MAINLINE / STRATEGY / SETUP / ENTRY / INVALIDATION / PAYOFF / ACCOUNT / PORTFOLIO / RISK / DATA / AUTHORITY / EXECUTION / UNKNOWN`

## 8. Setup / Entry / Invalidation / Payoff contract

Audit whether current WTOS really has reproducible generation semantics for:

`SETUP / ENTRY / MAX_BUY_PRICE / INVALIDATION / PAYOFF / EXIT_MODEL`

Do not hide missing algorithms behind output fields.

Where incomplete, design and implement a `PROVISIONAL / RESEARCH_SHADOW` contract that is explicit and testable.

Preserve:

`Entry -> Invalidation -> Risk Per Unit -> Risk Budget -> Position Size`

Never reverse-engineer a stop from desired size.

`PAYOFF_UNKNOWN` must remain UNKNOWN.

Do not invent a universal RR minimum without evidence.

## 9. Source architecture

Map exact source requirements for Market State, Mainline, Universe, sector constituents, OHLCV, turnover, historical ST/*ST, suspension, corporate actions, adjustment factors, index data, benchmark data.

Review current/candidate sources where relevant:

- Formal OSS MarketDataBridge
- Tushare
- local TDX
- `HiThink-Tech/Financial-API`
- public/current market sources

Treat HiThink as a candidate market-data source, not broker-account authority unless actual API evidence proves otherwise.

For each source distinguish:

`SOURCE / FACT / AS_OF / FRESHNESS / PIT_SAFETY / REPLAYABILITY / ACCESS / MISSING_FIELDS / FAILURE_MODE`

Public research must not silently replace formal decision-critical data.

## 10. Historical reuse discipline

Selectively reuse capabilities such as:

- Active Candidate Generation
- Candidate lifecycle
- WHY_NOT_BUY
- Opportunity Cost Review
- Market / Theme / Leader / Scanner concepts
- decision-time integrity
- Process != Outcome
- Candidate != Plan != Position

Do not restore:

- historical 11-engine runtime as Current architecture;
- old undefined Market Score thresholds;
- old strategies as Live Authority;
- frozen state as Current.

Historical evidence = research/design evidence only.

## 11. External research

If local web access is available, research mature systems and academic evidence where useful, including LEAN/QuantConnect, NautilusTrader, vn.py, Freqtrade, Backtrader, Qlib, PIT data practices, trend/time-series momentum, sector momentum/relative strength, breadth/participation.

Use external evidence to improve design, not to create Live Authority.

Record references compactly.

## 12. Implementation requirement

Do not stop at design documents.

Implement a branch-level prototype in the private WTOS repo sufficient to prove the architecture can be computed.

Prefer reuse. Avoid unnecessary new frameworks.

Implement the minimum useful deterministic functions/modules for:

- market state calculation;
- mainline calculation;
- opportunity-state classification;
- deterministic reason codes;
- UNKNOWN propagation;
- candidate lifecycle;
- machine-readable output.

Separate:

`FACT INPUT / DERIVED STATE / RESEARCH / HARD GATE / AUTHORIZATION`

Narrative must not silently become machine fact.

## 13. Tests / regression

Add comprehensive tests. At minimum cover:

- authority unreadable;
- non-trading day;
- stale/partial/conflicting market data;
- insufficient lookback;
- Market State unresolved/strong/weak;
- sector trend/RS/breadth/participation pass/fail;
- Mainline emerging/confirmed/weakening/lost/unresolved;
- one-day hotspot not Mainline;
- parent-sector/child-theme behavior;
- PIT membership;
- suspension;
- historical ST;
- corporate action / adjustment PIT;
- active scan returns zero valid candidates;
- scan not performed;
- candidate not actionable;
- hard-gate blocked;
- opportunity unresolved;
- Candidate != Authorized;
- payoff unknown;
- entry missing;
- invalidation missing;
- account unknown;
- risk blocked;
- `UNKNOWN != 0`;
- `Signal != Trade`;
- lookahead prevention;
- decision-time integrity;
- double-counting prevention;
- WTOS1->WTOS3 identity if touched.

Freeze regression semantics now. Run relevant full tests. Fix branch-caused failures. Do not weaken tests merely to obtain green CI.

## 14. User-facing WTOS-1

Do not begin by compressing the existing 12 sections.

First complete semantics.

Only after implementation, propose a simplified user presentation conceptually around:

1. `STATUS / ACTION NOW`
2. `ACTIONABLE OPPORTUNITIES`
3. `BLOCKERS / WHAT CHANGES THE DECISION`
4. `CURRENT HOLDINGS` only when materially relevant pre-open
5. `MARKET CONTEXT / NEXT CHECK`

Presentation is downstream of semantics.

## 15. Prompt proposal

Create a PROPOSED WTOS-1 automation prompt reflecting the completed architecture.

Do not modify the real ChatGPT automation. Do not call platform automation APIs. Do not change schedule or enabled state.

The proposal must separate:

`CURRENT FACTS / DERIVED STATE / RESEARCH / HARD GATES / OPPORTUNITIES / AUTHORIZATION / USER ACTION`

## 16. Minimal run / plan identity

Design the smallest useful identity model, evaluating at minimum:

`run_id / trade_date / decision_time / authority_identity / material_source_ids / material_unknowns / market_state / mainline_states / opportunity_scan_status / candidate_ids / plan_id / gate_results / final_action / WTOS1->WTOS3 inheritance identity`

Do not build a second giant state system.

## 17. Hard boundaries

You are NOT authorized to:

- modify real ChatGPT WTOS-1 or WTOS-3 platform automations;
- change automation schedules or enabled state;
- merge to `main`;
- change `active/` Live Authority;
- change Broker Write permissions;
- enable Broker Write or place orders;
- change current CNY risk ceilings;
- silently activate provisional Market/Mainline thresholds as Live trading rules;
- claim empirical probability before measurement;
- run or consume any explicitly untouched strategy holdout without separate authorization;
- perform Production Cutover;
- describe Local WTOS as current primary production runtime.

`BRANCH IMPLEMENTATION != CURRENT ACTIVATION`

`RESEARCH != LIVE AUTHORITY`

## 18. Work style

This is a LONG-RUN task.

Continue autonomously.

Do not send intermediate progress questions or ask for ordinary engineering confirmations.

For defects:

`DEFECT -> ROOT_CAUSE -> REMEDIATION -> TEST -> RESULT`

When blocked:

`RECORD_BLOCKER -> CONTINUE_NEXT_LANE`

Commit durable checkpoints in the private WTOS branch and push them.

If CI fails:

`READ_LOGS -> FIX -> RERUN -> CONTINUE`

Do not stop merely because one source/API/credential is unavailable.

## 19. Final deliverable

Return only after all safely executable work is complete.

Final report must include:

- `BASELINE_MAIN_SHA`
- `WORK_BRANCH`
- `FINAL_BRANCH_SHA`
- `GITHUB_AUTH`
- `FETCH`
- `PUSH`
- `SYSTEM_VERDICT`
- `WTOS1_CURRENT_ARCHITECTURE_GAPS`
- `MARKET_STATE_V0_1` exact formula/state transitions/source/UNKNOWN semantics
- `MAINLINE_V0_1` exact formula/lifecycle/parent-child/source/UNKNOWN semantics
- `ACTIVE_OPPORTUNITY_FUNNEL` states/transitions/four NO-BUY outcomes/reason taxonomy
- `SETUP_ENTRY_INVALIDATION_PAYOFF_STATUS`
- `SOURCE_QUALIFICATION`
- `HISTORICAL_REUSE` with `REUSED / REJECTED / WHY`
- `CODE_CHANGED`
- `TESTS_ADDED`
- `TEST_RESULTS`
- `CI_STATUS`
- `PROMPT_PROPOSAL_PATH`
- `RUN_RECORD_PROPOSAL`
- `FILES_CHANGED`
- `COMMITS`
- `UNRESOLVED_BLOCKERS` classified USER / T-SESSION / EXTERNAL
- `WHAT_REQUIRES_T_REVIEW_BEFORE_MAIN`
- `WHAT_MUST_NOT_BE_ACTIVATED_YET`
- `ROLLBACK_ANCHOR`
- `FINAL_RECOMMENDATION`

Do not report secrets. Do not claim Current changed. Do not claim Live Authority changed. Do not claim Production Cutover.

Push all private WTOS branch work before final return.
