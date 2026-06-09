# Discussion: Fix millpy-review-discussion to write briefs to the task worktree

```yaml
task: Fix millpy-review-discussion to write briefs to the task worktree
slug: review-discussion-brief-path
status: discussing
parent: main
```

## Problem

`millpy-review-discussion.py` sets `project_root = hub_dir` (the main millhouse worktree) and then computes `briefs_dir = _paths.resolve_task_path(project_root, "_mill/briefs/")`. As a result, agent-mode discussion briefs land in the hub's `_mill/briefs/`, not the task worktree's `_mill/briefs/`.

The sister scripts `millpy-review-plan.py` and `millpy-review-code.py` both use `project_root = Path.cwd()`, which equals the task worktree when invoked from within it. The discussion CLI was refactored to use `hub_dir` as `project_root` for reviewer-registry and template rendering, but the one-line `briefs_dir` assignment was not updated to match.

## Scope

**In:**
- `plugins/mill/scripts/millpy-review-discussion.py` — change `briefs_dir = _paths.resolve_task_path(project_root, "_mill/briefs/")` to use `git_root` instead of `project_root`.
- `plugins/mill/unit_tests/test-review-cli.py` — add a regression test that calls `main(["--stage", "prepare"])` with `git_root != hub_dir`, asserts `brief_path` is under `git_root` and not under `hub_dir`.

**Out:**
- `_review_discussion.py` — the backend `prepare()` function is not involved; it receives its paths from its callers and does not compute `briefs_dir`.
- `millpy-review-plan.py` and `millpy-review-code.py` — those CLIs already use `Path.cwd()` as `project_root` and are not broken.
- The `--slug` (run-from-hub) usage path — when the script is run from the hub, `git_root == hub_dir`, so no regression for that case.
- No changes to config, templates, wiki, or other scripts.

## Decisions

### Targeted fix: `git_root` not a full init-pattern refactor

- Decision: Replace `project_root` with `git_root` on the single `briefs_dir` line (line 90 of `millpy-review-discussion.py`).
- Rationale: `project_root = hub_dir` is used correctly in other parts of the function (registry loading via `_reviewers.load(project_root)`, task-title lookup via `load_task_title(project_root, ...)`, constraints via `read_constraints_md(project_root)`). A global rename to `Path.cwd()` would silently break those callers. A surgical fix avoids collateral damage.
- Rejected: Align the full init pattern to `Path.cwd()` as in plan/code review — wider change, not justified by the narrow scope of the bug.

### Test in `test-review-cli.py` with mocks

- Decision: Add one test function to the existing `test-review-cli.py` that exercises the `--stage prepare` branch of the discussion CLI with `git_root` and `hub_dir` pointing to distinct temp directories.
- Rationale: `test-review-cli.py` already contains test (d) that loads `millpy-review-discussion.py` as a module, mocks path resolution, and calls `main([])`. The same pattern applies. No new file needed.
- Rejected: Full integration test — not necessary; the mock approach proves the specific path-selection behavior being fixed.

### No special `--slug` handling

- Decision: The fix uses `git_root` as-is; when `--slug` is passed from the hub, `git_root == hub_dir` and behavior is identical to today, consistent with the plan/code review scripts.
- Rationale: No other review CLI resolves the task worktree via the container when `--slug` is used. Introducing that here would be out of scope and inconsistent.
- Rejected: Resolve actual task worktree via `resolve_active_worktree` — over-engineered for this bug.

## Technical context

`millpy-review-discussion.py` (in `plugins/mill/scripts/`):
- Line 64-69: path initialization block. `git_root = resolve_git_root()` correctly captures the cwd's git root (task worktree when invoked normally). `project_root = hub_dir` is used for hub-specific operations.
- Line 87-105: `--stage prepare` branch. Line 90 is the only place `project_root` is wrongly substituted for `git_root` when computing the briefs directory.

`_paths.resolve_task_path(worktree_root, cfg_relative_path)`:
- Simple: returns `worktree_root / cfg_relative_path`, with a `_mill/` → `task/` compat fallback for in-flight worktrees.
- The fix is just passing `git_root` instead of `project_root` as `worktree_root`.

`_agent_dispatch.write_brief(briefs_dir, role, scope, round_n, prompt_text)`:
- Creates parent dirs, writes the file, returns the path. No change needed here.

`test-review-cli.py` (in `plugins/mill/unit_tests/`):
- Test (d) (lines 385–459) is the template: loads the CLI module, creates a tmp dir with a git repo, mocks `resolve_git_root` / `resolve_hub_path` / `resolve_wiki_path`, calls `main([])`. The new test follows the same shape but uses `--stage prepare` and verifies `brief_path` in the JSON envelope.
- The test must mock: `_paths.resolve_git_root` → `task_root`, `_paths.resolve_hub_path` → `hub_root` (different), `_paths.resolve_wiki_path`, `_review_common.load_config` (returns a cfg dict), `_reviewers.load` (returns `{}`), `_reviewers.validate_role_refs`, `_review_common.find_active_slug` (returns `"my-slug"`), `_review_discussion.prepare` (returns a fake prepare dict with `model: "claude-sonnet-4-6"`, `scope: "holistic"`, `round: 1`).
- Assert: `str(task_root) in envelope["brief_path"]` AND `str(hub_root) not in envelope["brief_path"]`.

No wiki interaction, no git commits, no config writes needed for this task.

## Constraints

None from CONSTRAINTS.md (file absent). Existing test suite must continue to pass — the fix is additive (one line change, one new test function).

## Testing

**`test-review-cli.py` — new function `test_discussion_prepare_brief_path_uses_git_root`:**
- Set `task_root` and `hub_root` to distinct paths in a temp dir.
- Mock path resolution so `git_root = task_root`, `hub_dir = hub_root`.
- Mock `_review_discussion.prepare` to avoid real LLM / filesystem setup.
- Call `main(["--stage", "prepare"])` and parse stdout JSON.
- Assert `brief_path` is under `task_root`, not under `hub_root`.
- Failure modes to cover: brief under hub (the regression), non-zero exit, non-JSON stdout.

**Existing tests to keep green:**
- All tests in `test-review-cli.py` — the fix does not change any error paths, so the existing failure-mode tests are unaffected.
- `test-review-discussion-flow.py` — tests the backend `run()`, not the CLI; unaffected.
- `test-agent-mode-dispatch.py` — calls `write_brief` directly with `project_root / "_mill" / "briefs"`; unaffected.

## Q&A log

- **Q:** Fix scope — targeted single-line fix or full init-pattern refactor? **A:** [auto-pick] Targeted fix (option 1). **Why:** `project_root = hub_dir` is correct for registry/template callers; only `briefs_dir` is wrong.
- **Q:** Where does the regression test go? **A:** [auto-pick] `test-review-cli.py` (option 1). **Why:** existing test (d) is the exact same pattern.
- **Q:** What should the test assert? **A:** [auto-pick] `main(["--stage", "prepare"])` with distinct `git_root` and `hub_dir`; verify `brief_path` under `git_root`, not `hub_dir` (option 1). **Why:** unit-test-with-mocks pattern is established and sufficient.
- **Q:** Does `--slug` (run from hub) need special handling? **A:** [auto-pick] No (option 1). **Why:** consistent with plan/code review; no other CLI resolves the worktree from the container for `--slug`.
