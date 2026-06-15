The only em dash in a runtime `print(...)` is line 1241 (inside the `_warn_if_prose_diverges` print, which spans lines 1238-1243). All other em dashes are in docstrings/comments. The card correctly scopes to "not docstrings or comments." Card 1 is accurate. There is also a `→` at line 1367 but that's inside a docstring (aggregate_verdict). Good — no other runtime-output non-ASCII.

I now have enough to produce the review.

MILL_REVIEW_BEGIN
# Review: Fix wiki push upstream, cleanliness gate, mojibake, container config, and stacked-branch finalize — holistic

```yaml
verdict: REQUEST_CHANGES
reviewer_model: opushigh
reviewed_file: plan/
date: 2026-06-15
```

## Findings

### [BLOCKING] Card 3 omits resolve_main_worktree_root from Context
**Location:** Batch 2 / Card 3
**Issue:** Card 2 adds candidate #2 `_paths.resolve_main_worktree_root(worktree_root)` which invokes pygit2 on a real repo, but Card 3's container-layout test must construct a real git worktree whose main-root is the clone, and its `Context:` lists only `_config.py`/`_paths.py` without specifying how `worktree_root` is built so `resolve_main_worktree_root` returns `<hub>/wts/<repo>/`. Existing `test-config.py` tests stub `resolve_wiki_path` and pass non-git `wt_root`; the new candidate breaks that pattern.
**Fix:** In Card 3 Requirements, name how `worktree_root` is set up (a real `_git_init`'d clone at `<hub>/wts/<repo>/`) so `resolve_main_worktree_root(worktree_root)` resolves to the clone, and state whether `resolve_wiki_path` is stubbed.

### [BLOCKING] Card 8 test-mocking contract is underspecified
**Location:** Batch 4 / Card 8 + Card 10
**Issue:** Card 8 computes the parent-diff via `git diff --name-only <parent_branch>...HEAD` (real git via `_subprocess_util.run`), but Card 10 says to "mock the parent-diff lookup" without naming the exact symbol to patch. `test-cleanliness.py` only ever patches `_cleanliness._pygit2_util.status_porcelain`; there is no established mock point for a `_subprocess_util.run` git-diff call, so the test is not implementable as written without cold-start exploration.
**Fix:** In Card 8, name the discrete function used for the parent-diff (e.g. a small `_parent_diff_names(worktree, parent_branch)` helper) and in Card 10 state the exact patch target (`_cleanliness._subprocess_util.run` or the named helper).

### [NIT] Real-git test added to run-all default set, unlike test-wiki-sync
**Location:** Batch 5 / Card 14
**Issue:** `test-finalize-cleanup.py` uses a real tempfile git repo (per Card 14) but is not added to `run-all.py`'s SKIP set; `test-wiki-sync.py` (the cited precedent) IS skipped precisely because it needs real git, hence Batch 3 runs it directly. The new file will run under every full `run-all.py`, diverging from the precedent and from CLAUDE.md's "unit_tests: no real git."
**Fix:** Either add `test-finalize-cleanup.py` to `run-all.py`'s SKIP and run it directly in the batch verify, or note the deliberate choice to keep it in the default set.

### [NIT] Card 4 push refspec — clarify branch resolution failure path
**Location:** Batch 3 / Card 4
**Issue:** The card resolves the branch via `rev-parse --abbrev-ref HEAD` then pushes `HEAD:{branch}`, but does not state behaviour when HEAD is detached (abbrev-ref returns `HEAD`), which would push `HEAD:HEAD`.
**Fix:** Add a one-line requirement to raise `WikiPushError` (or fall through) when the resolved branch is empty/`HEAD`.

## Verdict

REQUEST_CHANGES
Two Context/test-mocking gaps make Cards 3 and 8/10 non-implementable as written.
MILL_REVIEW_END