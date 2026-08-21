# Batch: detached-head-branch-detection

```yaml
task: 'mill-go-base/mill-merge: documented step behavior diverges from underlying script capability'
batch: detached-head-branch-detection
number: 1
cards: 5
verify: PYTHONPATH= uv run --project plugins/mill python plugins/mill/unit_tests/run-all.py --only test-marker.py test-pygit2-util.py
depends-on: []
```

## Batch Scope

Implements #850: `_marker.slug_from_branch`'s detached-HEAD `MarkerError` is enriched to name any
local branch whose tip matches the detached commit, and `mill-go-base/SKILL.md`'s Entry Step 1
halt handler surfaces the enriched message verbatim instead of a fixed blanket string. This is one
batch because the branch-enumeration helper (card 1), its consumer in `_marker.py` (card 3), and
the halt-handler doc update (card 4) form one coherent, small feature with no natural sub-split —
the next batch (`preflight-attribute-guard`) touches entirely disjoint files, and the batch after
that (`entry-gate-discussion-phases`) depends on this one only because it separately edits
`mill-go-base/SKILL.md` in an unrelated section (the Entry-gate-wait table, not Entry Step 1) and
needs a stable base to avoid two batches concurrently drafting the same file.

External interface this batch establishes for later use: `_pygit2_util.local_branches_at_sha(path,
sha) -> list[str]` (card 1) — no other batch in this plan consumes it, but it follows the same
`open_repo`/error-wrapping shape as `current_branch`/`head_sha` so any future caller can rely on
that consistency.

Batch-local decision (not in Shared Decisions since it's specific to this batch's own new helper):
on any `pygit2.GitError`/`_pygit2_util.GitOpsError` raised while looking up the detached commit's
SHA or matching branches, `_marker.slug_from_branch` falls back to the original unchanged generic
message (`"detached HEAD or non-branch state"`) rather than letting the lookup failure surface as
an unrelated, undocumented exception type from a function whose docstring promises `MarkerError`
only — see card 3.

## Cards

### Card 1: add `local_branches_at_sha` to `_pygit2_util.py`

- **Context:** none
- **Edits:**
  - `plugins/mill/scripts/_pygit2_util.py`
- **Creates:** none
- **Deletes:** none
- **Moves:** none
- **Requirements:** Add a new function `local_branches_at_sha(path: Path, sha: str) -> list[str]`
  in `plugins/mill/scripts/_pygit2_util.py`, placed immediately after `head_sha` (currently lines
  83-100) and before `current_branch` (currently lines 103-124) — grouping it with the two
  functions it's designed to be used alongside. Follow the exact `open_repo`/error-wrapping pattern
  those two functions use: open the repo via `open_repo(path)`, iterate `repo.branches.local` (this
  iteration yields branch shorthand names as strings, e.g. `"hanf/foo"`), for each name look up
  `repo.branches.local[name]` to get the `Branch` object and compare its `.target` (converted to
  `str`) against the `sha` argument, collecting the names of every matching branch into a list,
  sorted alphabetically for deterministic output. Wrap the body in the
  same `try/except (pygit2.GitError, GitOpsError) as e` shape as `current_branch`/`head_sha`, ASCII
  a re-encode of `str(e)` the same way, and raise `GitOpsError(f"could not enumerate local branches
  at {sha} in {path}: {error_msg}") from e` on failure. Add a docstring matching the file's existing
  docstring shape (Args/Returns/Raises) — see `head_sha`'s docstring as the closest template (single
  SHA input, list-of-branch-names output difference noted). Return an empty list (not an error) when
  no local branch matches — that is the normal, expected outcome for most detached-HEAD cases.
- **Commit:** `feat(pygit2-util): add local_branches_at_sha helper for #850`

### Card 2: test `local_branches_at_sha`

- **Context:**
  - `plugins/mill/scripts/_pygit2_util.py`
- **Edits:**
  - `plugins/mill/unit_tests/test-pygit2-util.py`
- **Creates:** none
- **Deletes:** none
- **Moves:** none
- **Requirements:** Add tests for `_pygit2_util.local_branches_at_sha`, placed after the existing
  `test_current_branch_detached` test (currently lines 134-154), following this file's established
  pattern (real git repo via `subprocess` calls in a `tempfile` dir — see `test_current_branch_named`
  and `test_current_branch_detached` for the exact setup shape). Cover: (1) a commit that is the tip
  of exactly one local branch — assert the returned list is `[<that branch's shorthand name>]`; (2)
  a commit that is the tip of two local branches simultaneously (create a second branch ref pointing
  at the same commit via `git branch <name2> <sha>`) — assert the returned list contains both names,
  sorted; (3) a commit that is not any local branch's tip (e.g. an intermediate commit with a later
  commit on top) — assert the returned list is empty (`[]`), not an error.
- **Commit:** `test(pygit2-util): cover local_branches_at_sha (#850)`

### Card 3: enrich `MarkerError` message in `_marker.slug_from_branch`

- **Context:**
  - `plugins/mill/scripts/_pygit2_util.py`
- **Edits:**
  - `plugins/mill/scripts/_marker.py`
- **Creates:** none
- **Deletes:** none
- **Moves:** none
- **Requirements:** In `slug_from_branch` (`plugins/mill/scripts/_marker.py`, currently lines
  56-98), change the `if branch is None:` block (currently line 74-75, which unconditionally raises
  `MarkerError("detached HEAD or non-branch state")`) to: call `_pygit2_util.head_sha(git_root)` to
  get the detached commit's SHA, then `_pygit2_util.local_branches_at_sha(git_root, sha)` (both
  wrapped in one `try/except _pygit2_util.GitOpsError`) to look up matching local branches. Per this
  batch's own Batch Scope decision, if either call raises `GitOpsError`, fall through to the
  original unchanged `raise MarkerError("detached HEAD or non-branch state")`. If the lookup
  succeeds and returns a non-empty list, raise `MarkerError` with a message naming the matches,
  comma-joined, in this exact shape: `f"HEAD is detached at a commit matching branch(es)
  {', '.join(matches)} -- run 'git checkout <name>', or use /mill-resume if this worktree was
  copied from another machine."` If the lookup succeeds but returns an empty list, raise
  `MarkerError("detached HEAD or non-branch state")` — the unchanged fallback text, identical to
  today's only behavior. Update the function's `Raises:` docstring line (currently line 68) if its
  wording no longer accurately describes the enriched message (it currently just says "On detached
  HEAD, prefix mismatch, or missing slug" — a category description, not the exact text — so it very
  likely does not need changing; only touch it if it does).
- **Commit:** `fix(marker): enrich detached-HEAD MarkerError with matching branch names (#850)`

### Card 4: surface `str(e)` in mill-go-base's Entry Step 1 halt

- **Context:** none
- **Edits:**
  - `plugins/mill/skills/mill-go-base/SKILL.md`
- **Creates:** none
- **Deletes:** none
- **Moves:** none
- **Requirements:** Change the Entry Step 1 halt-handler line in `mill-go-base/SKILL.md` (currently
  line 52: `` On `MarkerError` → halt with "this worktree was not created by mill-spawn". `` ) to
  surface the exception's own message instead of the fixed string — reword to: `` On `MarkerError`
  → halt with `str(e)` (the exception's own message). `` Keep the trailing `` `signature:
  _marker.slug_from_branch(...)` `` annotation on the same line unchanged. Do not touch any other
  `MarkerError` halt text elsewhere in this file or in any other skill's SKILL.md — per this
  batch's Batch Scope / the overview's "no change to other skills' MarkerError halt wording" Shared
  Decision, only this one call site is in scope.
- **Commit:** `docs(mill-go-base): surface MarkerError's actual message on Entry Step 1 halt (#850)`

### Card 5: extend `test-marker.py` for the enriched message

- **Context:**
  - `plugins/mill/scripts/_marker.py`
  - `plugins/mill/scripts/_pygit2_util.py`
  - `plugins/mill/unit_tests/_test_helpers.py`
- **Edits:**
  - `plugins/mill/unit_tests/test-marker.py`
- **Creates:** none
- **Deletes:** none
- **Moves:** none
- **Requirements:** In `test_slug_from_branch_detached_head` (currently lines 45-68), change the
  bare `except _marker.MarkerError: pass` (line 64-65) to capture the exception (`except
  _marker.MarkerError as e:`) and assert `"hanf/foo" in str(e)` — per `_mill/discussion.md`'s
  `#850-test-coverage` Decision, the fixture's branch is `hanf/foo` (from
  `_make_task_worktree(tmp, "foo", ..., branch_prefix="hanf/", ...)`, which checks out
  `f"{branch_prefix}{slug}"`), not bare `foo`. Add a new test function
  `test_slug_from_branch_detached_head_no_matching_branch`, placed immediately after the modified
  `test_slug_from_branch_detached_head`, following the same fixture-setup shape (`_make_task_worktree`
  + `subprocess` checkout) but checking out a commit that is not any local branch's tip: after the
  existing worktree/branch setup, create one additional empty commit on the current branch via `git
  commit --allow-empty -m "extra"`, then check out that new commit's own parent SHA (the original
  branch-tip commit now has a child, so it is no longer the branch tip) — assert the raised
  `MarkerError`'s message is exactly `"detached HEAD or non-branch state"` (`str(e) ==
  "detached HEAD or non-branch state"`), confirming the no-match fallback path.
- **Commit:** `test(marker): cover detached-HEAD branch-name enrichment, positive and negative (#850)`

## Batch Tests

`verify:` runs `test-marker.py` and `test-pygit2-util.py` via `run-all.py --only` — these are the
two files this batch edits directly (cards 2 and 5) and the two files whose behavior this batch's
non-test cards (1, 3, 4) change. No other test file imports `_marker.local_branches_at_sha`-adjacent
code or the changed `MarkerError` message text (confirmed via repo-wide grep during planning), so
this scope is complete without widening to `run-all.py`'s full suite.
