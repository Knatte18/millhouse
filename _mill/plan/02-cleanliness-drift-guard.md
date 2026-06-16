# Batch: cleanliness-drift-guard

```yaml
task: "Fix nested mill layout paths, whole-repo formatter drift, and stacked-branch PR cleanup"
batch: cleanliness-drift-guard
number: 2
cards: 4
verify: PYTHONPATH= uv run --project plugins/mill python plugins/mill/unit_tests/test-cleanliness.py
depends-on: []
```

## Batch Scope

Deliver the out-of-scope formatter-drift guard and the formatter-scoping
conventions. Adds one new helper to `_cleanliness.py`
(`revert_out_of_scope_drift`) with unit coverage, and scopes the writing
formatters in the three `{lang}-build` templates plus aligns the `git-commit`
lint wording. The new helper is the **external interface** batch 3 consumes: its
mill-go cleanliness-gate wiring (batch 3, card 10) calls
`_cleanliness.revert_out_of_scope_drift`, which is why batch 3 depends on this
batch. This batch touches no orchestrator SKILL and no review CLI, so it runs in
parallel with batch 1.

Batch-local decision: "out-of-scope tracked modification" = a porcelain status
line whose path is NOT under `task_dir` AND NOT in the task's parent-diff owned
set, with a modified status code (` M`, `M `, `MM`). Untracked files are out of
scope for this helper — they remain the responsibility of the existing
`compute_scope_violations` gate and must NOT be reverted here.

## Cards

### Card 4: Add revert_out_of_scope_drift helper to _cleanliness.py

- **Context:**
  - `plugins/mill/scripts/_pygit2_util.py`
  - `plugins/mill/scripts/_subprocess_util.py`
- **Edits:**
  - `plugins/mill/scripts/_cleanliness.py`
- **Creates:** none
- **Deletes:** none
- **Requirements:** Add `revert_out_of_scope_drift(worktree: Path, task_dir: Path,
  parent_branch: str) -> tuple[list[str], list[str]]`. It computes the owned set by
  calling the existing `_parent_diff_names(worktree, parent_branch)`, reads current
  dirt via `_pygit2_util.status_porcelain(worktree, include_untracked=False)`,
  partitions each line into in-scope vs out-of-scope using the same predicate as
  `_filter_to_task_scope` (path under `task_dir` worktree-relative OR in the owned
  set), and for each out-of-scope line with a modified status code (` M`, `M `,
  `MM`) reverts the file via `git checkout HEAD -- <path>` (run through
  `_subprocess_util.run`). Normalize `task_dir` to worktree-relative exactly as
  `compute_terminal_dirt` does (`task_dir.relative_to(worktree)` when absolute).
  Return `(reverted_paths, remaining_in_scope_lines)` both sorted: `reverted_paths`
  are the out-of-scope files reset, `remaining_in_scope_lines` are the in-scope
  porcelain lines still dirty after the revert. Do NOT revert untracked (`??`) or
  added (`A `) entries. ASCII-only log output.
- **Commit:** `feat(cleanliness): revert out-of-scope formatter drift instead of blocking`

### Card 5: Unit tests for revert_out_of_scope_drift

- **Context:**
  - `plugins/mill/scripts/_cleanliness.py`
  - `plugins/mill/scripts/_pygit2_util.py`
- **Edits:**
  - `plugins/mill/unit_tests/test-cleanliness.py`
- **Creates:** none
- **Deletes:** none
- **Requirements:** Add tests using the existing tempfile + real-`git` fixture
  style in `test-cleanliness.py`. Cover: (a) out-of-scope tracked modification only
  → reverted, `remaining_in_scope_lines` empty; (b) mixed in-scope + out-of-scope
  modifications → out-of-scope reverted, in-scope line returned in `remaining`;
  (c) an untracked out-of-scope file is NOT reverted and NOT returned in
  `remaining`; (d) a file in the parent-diff owned set but outside `task_dir` is
  treated as in-scope (not reverted). Build the parent-diff via a real commit on a
  parent branch so `_parent_diff_names` returns the owned set.
- **Commit:** `test(cleanliness): cover out-of-scope drift revert helper`

### Card 6: Scope writing formatters in {lang}-build templates

- **Context:**
  - `plugins/mill/skills/git-commit/SKILL.md`
- **Edits:**
  - `plugins/golang/skills/golang-build/SKILL.md`
  - `plugins/python/skills/python-build/SKILL.md`
  - `plugins/csharp/skills/csharp-build/SKILL.md`
- **Creates:** none
- **Deletes:** none
- **Requirements:** In `golang-build/SKILL.md`, change the writing formatter
  `goimports -w .` to operate on changed `.go` files only, and add a convention
  note that a whole-project formatter must never run in write mode during a batch.
  Keep `go vet ./...`, `go build ./...`, `go test ./...`, `golangci-lint run`
  whole-project. In `python-build/SKILL.md`, add the same convention note; since it
  ships only `ruff check .` (read-only) and `pytest` today with no write-mode
  formatter, state the note is precautionary so any future `ruff format`/`ruff
  check --fix` is scoped to changed files. In `csharp-build/SKILL.md`, add the
  convention note only (it ships no formatter). Do not alter build/test invocations.
- **Commit:** `docs(build): scope writing formatters to changed files`

### Card 7: Align git-commit lint wording with scoped formatters

- **Context:**
  - `plugins/golang/skills/golang-build/SKILL.md`
  - `plugins/python/skills/python-build/SKILL.md`
- **Edits:**
  - `plugins/mill/skills/git-commit/SKILL.md`
- **Creates:** none
- **Deletes:** none
- **Requirements:** Update the "Lint (language-specific)" step wording so it is
  explicit that the lint/format step runs on **changed files only**, never the
  whole solution/project, matching the now-scoped `{lang}-build` writing
  formatters. Keep the existing "skip if no source files changed or no language
  detected" behavior.
- **Commit:** `docs(git-commit): clarify lint runs on changed files only`

## Batch Tests

`verify:` runs `test-cleanliness.py`, which now covers the new
`revert_out_of_scope_drift` helper (cards 4–5) alongside the existing snapshot/dirt
functions. The `{lang}-build` and `git-commit` SKILL edits (cards 6–7) are
documentation with no runnable surface; they are verified by review, not by a test
runner. Scope is a single test file — no cross-cutting helper is touched, so
`run-all.py` is not warranted.
