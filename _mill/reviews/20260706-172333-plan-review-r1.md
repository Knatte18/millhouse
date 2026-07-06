I have verified all plan claims against the source files. Let me confirm the finding details are grounded before writing the review.

All plan claims check out: the 17 public `status_path` functions in `_status.py` match Card 5's list exactly (excluding `render_initial` and `_write_batches`); `run-all.py` supports `--only <basename>`; the `_worktree.py` line references and `-AsArray` string are accurate; `_setup_trio` line references and the no-op check block at line 446 (which uses the trio fixture via `main()` line 420) are correct; the MERGE_REF fallback logic degrades gracefully when origin is absent.

MILL_REVIEW_BEGIN
# Review: Fix mill-merge-in stale ref check, PowerShell 5.1 ConvertTo-Json, and _status str-path crash — holistic

```yaml
verdict: APPROVE
reviewer_model: opushigh
reviewed_file: plan/
date: 2026-07-06
```

## Findings

### [NIT] Card 2 step-2 instruction is self-contradictory
**Location:** Batch 1 / Card 2, Requirements item 2
**Issue:** The bullet says to "push the worktree's view of `main`'s current tip to the new origin" then immediately says "no push needed here" — the net instruction is a no-op but the phrasing risks confusing the implementer into adding a redundant push.
**Fix:** Collapse item 2 to a single sentence stating no additional push is required because `main` has not advanced past the step-1 push.

### [NIT] "touches nothing" first sentence now slightly overstated
**Location:** Batch 1 / Card 1, "## No-op guarantee" edit
**Issue:** Retaining the first sentence verbatim keeps the literal claim "touches nothing," yet the added `git fetch` updates `refs/remotes/origin/<parent>` on disk; the appended caveat sentence mitigates this but the two sentences sit in mild tension.
**Fix:** Acceptable as specified (enumerated items — checkpoint/verify/codeguide/output — remain untouched, and the caveat is explicit); optionally reword the first clause to "touches no task state."

## Verdict

APPROVE
Specific, well-sequenced, three independent root batches; claims verified against source, only cosmetic NITs.
MILL_REVIEW_END
