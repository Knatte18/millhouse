I have verified all the discussion's claims against source. Key findings below.

The claims about `-AsArray` (line 368), the Python normalization (375-376), the 17 `_status.py` public functions, `_write_batches` being private (606), and the test seam locations all check out. However, I found a genuine mismatch between the Testing instruction and the actual integration-test fixture.

MILL_REVIEW_BEGIN
# Review: Fix mill-merge-in stale ref check, PowerShell 5.1 ConvertTo-Json, and _status str-path crash

```yaml
verdict: GAPS_FOUND
reviewer_model: opushigh
reviewed_file: _mill/discussion.md
date: 2026-07-06
```

## Findings

### [GAP] test-merge fixture has no origin remote for the code repo
**Section:** Testing (Step 1 replica) / Technical context
**Issue:** `_setup_trio` creates the hub via `git init` with NO `origin` remote (only the wiki has a bare remote); the worktree shares the hub git dir and `main` is purely local. The instruction to update the replica (lines 446-453) to `git fetch origin <parent>` then diff against `origin/<parent>` cannot run as written — `git fetch origin main` fails and `origin/main` does not exist, so only the fetch-failure fallback path is reachable.
**Fix:** Decide explicitly: either extend `_setup_trio` to add a real `origin` remote (bare clone of hub) so the fetch-and-compare-origin path is genuinely exercised, or change the replica to assert the local-ref fallback behavior — and reconcile this with the "diff against origin/<parent>" wording.

### [NOTE] No-op guarantee still promises "no output side effects"
**Section:** Decisions #600 (No-op guarantee impact) / SKILL.md line 134
**Issue:** On fetch failure the skill prints a one-line note before the no-op determination, so an output side effect now occurs even on the no-op path; the wording-update note addresses network cost and local-mutation but not the existing "no output side effects" clause.
**Fix:** Include the "no output side effects" phrasing in the section rewrite (fetch-failure note may print even when the result is a no-op).

### [NOTE] Ref choice must thread from Step 1 to Step 3
**Section:** Decisions #600 / Scope
**Issue:** Steps 1 and 3 are separate inline-bash blocks; the decision to merge `origin/<parent>` vs. local `<parent>` is made in Step 1 but consumed in Step 3, with no stated mechanism to carry that choice across the two blocks.
**Fix:** State how the resolved merge ref propagates (e.g. a documented shell variable set in Step 1 and reused in Step 3) so the no-op check and the actual merge provably use the same ref.

## Verdict

GAPS_FOUND
Testing instruction is infeasible against the origin-less merge fixture; resolve before plan writing.
MILL_REVIEW_END
