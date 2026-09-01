# WTOS-1 Codex T-Review Correction — 2026-09-02

STATUS: REMEDIATION_REQUIRED

Independent review found the prior execution used a stale WTOS baseline and did not prove the branch was pushed to the actual private GitHub WTOS repository.

Required remediation:

1. Reconnect the local WTOS checkout to the actual private GitHub repository while preserving any local mirror as a separate remote if needed.
2. Fetch actual GitHub `main` and start again from `SYSTEM_MANIFEST.yaml`.
3. Current GitHub main at review time is `bf023c8bd98bd56723bdd6d2ebbb6a4425d3aad6`; the prior baseline `e7db8ae14fafac2732f7d0669446253af5fa29b9` is 70 commits behind.
4. Re-resolve the real current `runtime/chatgpt/` tree. The previous statement that the ChatGPT runtime tree is missing is invalid for Current.
5. Preserve useful code from local commit `7a0922c...`, but transplant it onto a fresh branch based on actual current GitHub main. Resolve assumptions against Current rather than the stale baseline.
6. Re-run targeted and full Runtime tests. Do not weaken tests.
7. Push the corrected work branch to the actual private GitHub WTOS repository. Do not merge main and do not modify `active/`, real platform automations, schedules, risk ceilings, Broker Write, or Production Cutover.
8. Verify the branch and final commit are actually retrievable from GitHub. If remote CI runs and fails, fix it before returning unless a true external blocker remains.
9. Re-run the WTOS-1 architecture audit against the real current ChatGPT runtime.
10. When complete, append `Corrected Execution Result` below the existing result in `reviews/WTOS1_CODEX_TASK.md`, including actual GitHub main SHA, corrected branch/commit, remote verification, tests, CI, files changed, corrected system verdict, and remaining blockers.

Do not claim completion until the corrected private WTOS branch is independently retrievable from GitHub.
