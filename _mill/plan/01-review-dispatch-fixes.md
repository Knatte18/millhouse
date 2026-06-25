# Batch: review-dispatch-fixes

```yaml
task: "Fix pre-existing unit-test failures, CRLF cleanliness false-positive, and review false-BLOCKING on Go"
batch: review-dispatch-fixes
number: 1
cards: 3
verify: "PYTHONPATH= uv run --project plugins/mill python plugins/mill/unit_tests/run-all.py --only test-review-cli.py test-review-guard.py"
depends-on: []
```

## Batch Scope

Two production bugs in the review subsystem: (1) the review brief is written under the shared **hub** root instead of the **task worktree**, and (2) `worktree_snapshot_guard` raises `ReviewerOverstepError` on any HEAD change, even a clean fast-forward where the reviewer legitimately committed its own output. Both are exercised by existing red tests (`test-review-cli.py` brief-path assertions, `test-review-guard.py` cases B/F/I). This batch is one unit because both touch the review-dispatch/guard surface and share no files with other batches. No external interface is produced for later batches. Batch-local decision: the brief base path is `resolve_git_root()` (the task worktree), never `resolve_hub_path()`.

## Cards

### Card 1: Write review briefs under the task worktree, not the hub root

- **Context:**
  - `plugins/mill/scripts/_paths.py`
  - `plugins/mill/scripts/_agent_dispatch.py`
- **Edits:**
  - `plugins/mill/scripts/millpy-review-discussion.py`
  - `plugins/mill/scripts/millpy-review-plan.py`
  - `plugins/mill/scripts/millpy-review-code.py`
- **Creates:** none
- **Deletes:** none
- **Requirements:** In all three CLIs the `prepare` stage computes `briefs_dir = _paths.resolve_task_path(project_root, "_mill/briefs/")` where `project_root` is `resolve_hub_path()` (the hub). Change the first argument from the hub root to the task worktree `git_root` (already computed as `git_root = _paths.resolve_git_root()` / `resolve_git_root()` in each file's top try-block): i.e. `briefs_dir = _paths.resolve_task_path(git_root, "_mill/briefs/")`. In `millpy-review-discussion.py` the brief line uses `project_root` (== `hub_dir`); switch it to `git_root` there too (do not change the unrelated `project_root` uses for config/reviewer/slug loading). Do not alter `_agent_dispatch.write_brief` or `resolve_task_path` themselves.
- **Commit:** `fix(review): write agent brief under task worktree, not hub root`

### Card 2: Cover plan & code brief paths in test-review-cli

- **Context:**
  - `plugins/mill/scripts/millpy-review-plan.py`
  - `plugins/mill/scripts/millpy-review-code.py`
  - `plugins/mill/scripts/millpy-review-discussion.py`
- **Edits:**
  - `plugins/mill/unit_tests/test-review-cli.py`
- **Creates:** none
- **Deletes:** none
- **Requirements:** The file already has `test_discussion_prepare_brief_path_uses_git_root` (patches `resolve_git_root -> task_root`, `resolve_hub_path -> hub_root`, asserts the brief is under `task_root` and NOT under `hub_root`). Add two parallel tests — one for `millpy-review-plan.py` `--stage prepare` and one for `millpy-review-code.py` `--stage prepare` — asserting each writes its brief under the task `git_root`, not the hub root. Register the new test functions in the file's `main()` aggregator following the existing pass/fail-counting style. Mirror the existing discussion test's mocking/setup; do not weaken the existing assertion. Note: `millpy-review-plan.py --stage prepare` runs `_plan_validate.run` BEFORE `prepare`, so the plan test must bypass the validator — pass `--skip-validate` in the argv it invokes, or mock `_plan_validate.run` to return no errors — otherwise the CLI exits 1 before writing the brief. The `millpy-review-code.py` prepare path has no validator and needs no such bypass.
- **Commit:** `test(review): assert plan and code brief paths use task worktree`

### Card 3: Tolerate clean fast-forward in worktree_snapshot_guard

- **Context:**
  - `plugins/mill/scripts/_pygit2_util.py`
  - `plugins/mill/unit_tests/test-review-guard.py`
- **Edits:**
  - `plugins/mill/scripts/_review_common.py`
- **Creates:** none
- **Deletes:** none
- **Requirements:** In `worktree_snapshot_guard` (`_review_common.py`), the current raise condition is `should_raise = bool(added) or head_changed or bool(removed)` (HEAD change alone always raises). Add a fast-forward check using the existing helper `_pygit2_util.is_ancestor(project_root, before_sha, after_sha)` (returns True when `after_sha` is a descendant of, or equal to, `before_sha`): compute `ff = head_changed and _pygit2_util.is_ancestor(project_root, before_sha, after_sha)`; if the helper raises `_pygit2_util.GitOpsError`, treat `ff` as `False` (a non-verifiable ancestry is not a safe fast-forward). Redefine the raise condition to `should_raise = bool(added) or (head_changed and not ff) or (bool(removed) and not ff)` so a clean fast-forward (descendant HEAD, no NEW working-tree dirt) is tolerated while non-fast-forward HEAD changes and newly-added dirt still raise. When `ff` is True and the guard does not raise, emit a one-line warning to stderr containing the token `fast-forward` and both short SHAs (e.g. `print(f"[worktree_snapshot_guard] fast-forward: HEAD {before_sha[:8]} -> {after_sha[:8]}", file=sys.stderr)`); ensure `sys` is imported in the module. Update the function docstring line "Any change to HEAD during the review window is considered an overstep." to describe the fast-forward tolerance. This must satisfy test-review-guard cases B, F, I (warn, no raise) while keeping C, D, J, K raising.
- **Commit:** `fix(review): tolerate clean fast-forward in reviewer overstep guard`

## Batch Tests

`verify:` runs `test-review-cli.py` (brief-path contract for all three CLIs, including the two new plan/code tests from card 2) and `test-review-guard.py` (overstep guard cases A-K; cards 3 turns B/F/I green and must keep C/D/J/K raising). Both files are scoped via `run-all.py --only`. No new test file is created; `test-review-guard.py` already encodes the intended fast-forward contract and is the verify target for card 3.
