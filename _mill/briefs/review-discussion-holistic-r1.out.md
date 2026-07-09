Verification complete. All the discussion's cited line numbers and current-state claims check out. I found gaps in two Decisions and some inconsistencies. Compiling the review.

MILL_REVIEW_BEGIN
# Review: Fix mill-start instruction gaps, baseline long-path on Windows, and language skill tooling reliability

```yaml
verdict: GAPS_FOUND
reviewer_model: opushigh
reviewed_file: _mill/discussion.md
date: 2026-07-09
```

## Findings

### [GAP] dotnet test pipe masks the test exit code
**Section:** Decisions → 622-fix
**Issue:** `dotnet test ... | grep -E "Passed!|Failed!|Total tests"` returns grep's exit status, not dotnet's — a failing suite whose output still contains a `Failed!` summary line exits 0, so mill-go verify / git-commit lint (the very chokepoints the decision routes through) see success. This silently masks failures, the exact class of defect this task targets.
**Fix:** Decide how the exit code is preserved (e.g. `set -o pipefail`, `${PIPESTATUS[0]}`, or a logger file + separate exit check) and state it in the decision, not just the visible-text filter.

### [GAP] Removal-side longpaths flag: scope and target unresolved
**Section:** Scope (In) + Decisions → 615-620-fix
**Issue:** The decision says apply `-c core.longpaths=true` to the teardown "via `_worktree.remove_safe` if it shells `git worktree remove`" — it does (`_worktree.py:228`), but `_worktree.py` is not in the In-file list, `remove_safe` is a shared helper used by cleanup/merge/spawn (blast radius on all callers), and it already has a long-path `safe_rmtree` fallback (`_worktree.py:238-259`) that makes the flag arguably redundant. The `if`/"for symmetry" hedging leaves the teardown change undecided.
**Fix:** Resolve explicitly: either drop the removal flag (fallback already covers long-path deletion) or add `_worktree.py` to In-scope and decide whether the flag is threaded per-call (not a blanket edit of the shared helper).

### [NOTE] grep pattern drops per-test failure detail
**Section:** Decisions → 622-fix
**Issue:** The rationale claims "the grep keeps `Failed!` lines" preserving "failing test names + assertion messages", but `Passed!|Failed!|Total tests` matches only the VSTest summary line; per-test failures print as `  Failed <TestName>` / `Error Message:` (no `!`) and are dropped.
**Fix:** Widen the pattern (e.g. also match leading-whitespace `Failed`/`error`) or drop the "preserves test names" claim and state detail is fully deferred to re-run.

### [NOTE] Entry reorder does not bind git_root / wiki_path
**Section:** Decisions → 618-fix
**Issue:** After moving config ahead of the slug read, step 2 still calls `slug_from_branch(git_root, wiki_path, cfg)`, but current step 1 resolves the wiki path inline without binding `git_root`/`wiki_path` as named variables (they are assigned later in Path Setup). The decision audits step-number cross-refs but not these bindings.
**Fix:** Note that the reorder must also bind `git_root` and `wiki_path` (or move the relevant Path Setup lines up) so the reordered slug call is literal-execution-safe.

## Verdict
GAPS_FOUND
Two decisions leave silent-failure and shared-helper-scope questions unresolved for the plan writer.
MILL_REVIEW_END