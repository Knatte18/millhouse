MILL_REVIEW_BEGIN
# Review: Merge-in conflict handling: silent marker-verification gaps, mill-config.yaml chicken-and-egg crash, and undocumented dirty-worktree squash failure — holistic

```yaml
verdict: REQUEST_CHANGES
reviewer_model: sonnetmax
reviewed_file: plan/
date: 2026-07-28
```

## Findings

### [BLOCKING] Batch 4's new integration-test scenarios are never auto-run
**Location:** Batch 4 (dirty-parent-worktree-preflight), Card 16 + batch/overview `verify:` fields
**Issue:** Card 16 adds three new dirty-parent-worktree scenarios to `test-merge.py`, but batch 4's `verify: null` (and the overview's) never invokes that file, so the new assertions only ever run if a human remembers the manual step. The Shared Decision's rationale ("`test-merge.py` ... not via the `run-all.py` unit-test harness this project's `verify:` convention targets") is contradicted within this same plan: batches 1 and 2 wire `verify:` directly to `test-config.py`/`test-millpy-merge-in-subagent.py`, both invoked the same non-run-all.py way, proving direct script invocation is already an accepted `verify:` shape here.
**Fix:** Set batch 4's `verify:` (04-...md frontmatter) and the overview's batch-index entry for batch 4 to `PYTHONPATH= uv run --project plugins/mill python plugins/mill/integration_tests/test-merge.py`, mirroring the precedent batches 1-2 already set.

### [NIT] Card 16's new `_setup_trio()` calls risk shadowing the primary scenario's locals
**Location:** Batch 4, Card 16
**Issue:** The card calls `_setup_trio(container)` three more times inside the same flat-hub `main()` scenario (independent-edit case, mid-retry case, untracked-noise case) but never says to bind the returned `(hub, wiki_path, worktree, slug)` tuples to new names. Reusing the existing `hub`/`worktree`/`wiki_path` identifiers already in scope at that point in `main()` would silently repoint every assertion from line ~614 onward (squash, archive tag, Home.md flip) at the wrong trio.
**Fix:** Add a line directing distinct names for the three new tuples (e.g. `dirty_hub`, `retry_hub`, `untracked_hub`), matching the file's own convention for `nested_hub`/`verify_hub_root`.

### [NIT] Card 12 doesn't call for renumbering the brief's subsequent steps
**Location:** Batch 3, Card 12
**Issue:** Inserting a new numbered instruction directly after existing step 3 (before step 4, "Run git add") leaves the old steps 4/5/6 literally mis-numbered relative to their new position unless separately renumbered; the card never says to do this.
**Fix:** Add a line directing the implementer to renumber the old steps 4-6 to 5-7 after inserting the new instruction.

## Verdict

REQUEST_CHANGES
Batch 4's new integration-test coverage is never wired into an automated verify: command.
MILL_REVIEW_END
