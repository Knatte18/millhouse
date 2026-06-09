# Batch: fix-and-test

```yaml
task: Fix millpy-review-discussion to write briefs to the task worktree
batch: fix-and-test
number: 1
cards: 2
verify: PYTHONPATH= uv run --project plugins/mill python plugins/mill/unit_tests/test-review-cli.py
depends-on: []
```

## Batch Scope

This batch delivers the complete fix for the briefs-path bug in `millpy-review-discussion.py` and the regression test that pins the correct behavior. Card 1 makes the one-line change in the CLI script. Card 2 adds a test function to `test-review-cli.py` that exercises `--stage prepare` with `git_root != hub_dir` and verifies the brief lands under `git_root`. Both changes are independent on disk; no ordering constraint between the two cards.

## Cards

### Card 1: Fix briefs_dir to use git_root

- **Context:**
  - `plugins/mill/scripts/_paths.py`
  - `plugins/mill/scripts/_agent_dispatch.py`
- **Edits:**
  - `plugins/mill/scripts/millpy-review-discussion.py`
- **Creates:** none
- **Deletes:** none
- **Requirements:** In `main()`, within the `if args.stage == "prepare":` branch, change the single line `briefs_dir = _paths.resolve_task_path(project_root, "_mill/briefs/")` to `briefs_dir = _paths.resolve_task_path(git_root, "_mill/briefs/")`. No other changes to the file. The variable `project_root` continues to equal `hub_dir` everywhere else in `main()`.
- **Commit:** `fix(review-discussion): write briefs to task worktree (git_root not hub)`

### Card 2: Add regression test for brief path location

- **Context:**
  - `plugins/mill/scripts/millpy-review-discussion.py`
  - `plugins/mill/scripts/_agent_dispatch.py`
  - `plugins/mill/scripts/_review_discussion.py`
  - `plugins/mill/scripts/_review_common.py`
  - `plugins/mill/scripts/_reviewers.py`
  - `plugins/mill/unit_tests/_test_helpers.py`
- **Edits:**
  - `plugins/mill/unit_tests/test-review-cli.py`
- **Creates:** none
- **Deletes:** none
- **Requirements:**
  1. Define `test_discussion_prepare_brief_path_uses_git_root() -> int` immediately before the existing `main()` function in `test-review-cli.py`.
  2. Body of the function:
     - Declare `failures = 0` at the top.
     - Import `importlib.util as _ilu`, `unittest.mock as _mock`, `os as _os` locally inside the function.
     - Load the CLI module: `_cli_path = HUB / "plugins" / "mill" / "scripts" / "millpy-review-discussion.py"`. Create spec with name `"millpy_review_discussion_brief_path"` via `_ilu.spec_from_file_location`. Create module via `_ilu.module_from_spec`. Execute via `_spec.loader.exec_module(_mod)`.
     - Use `_test_helpers.safe_temp_dir()` as context manager. Inside: `task_root = tmp / "wts" / "my-slug"`, `hub_root = tmp / "wts" / "millhouse"`, `wiki_root = tmp / "wiki"`. Create all three with `.mkdir(parents=True)`.
     - Build `cfg_dict = {"paths": {"discussion_file": "_mill/discussion.md", "plan_dir": "_mill/plan/", "reviews_dir": "_mill/reviews/"}, "roles": {"discussion-review": {"holistic": {"rounds": 1, "reviewer": "sonnetmax"}}}, "spawn": {"branch_prefix": "hanf/"}}`.
     - Build `fake_prepare = {"prompt_text": "# test prompt", "model": "claude-sonnet-4-6", "round": 1, "reviews_dir": task_root / "_mill" / "reviews", "scope": "holistic"}`.
     - Capture stdout: `stdout_buf = io.StringIO()`. Save cwd: `_orig_cwd = _os.getcwd()`. Change to task_root: `_os.chdir(task_root)`.
     - Wrap in try/finally to restore cwd.
     - Inside try, use nested `with` blocks to apply mocks (order: `_paths.resolve_git_root` → `task_root`, `_paths.resolve_hub_path` → `hub_root`, `_paths.resolve_wiki_path` → `wiki_root`, `_review_common.load_config` → `cfg_dict`, `_reviewers.load` → `{}`, `_reviewers.validate_role_refs`, `_review_common.find_active_slug` → `"my-slug"`, `_review_discussion.prepare` → `fake_prepare`).
     - Inside the innermost `with` block, apply `contextlib.redirect_stdout(stdout_buf)` and call `_rc = _mod.main(["--stage", "prepare"])`.
     - Check `_rc != 0`: if so, print `f"FAIL brief_path (exit): expected 0, got {_rc}"` to stderr and increment `failures`; return early.
     - Parse stdout: `envelope = json.loads(stdout_buf.getvalue().strip())`. On `json.JSONDecodeError`: print `f"FAIL brief_path (JSON): ..."` to stderr, increment `failures`, return early.
     - `brief_path_str = envelope.get("brief_path", "")`.
     - If `str(task_root) not in brief_path_str`: print `f"FAIL brief_path: expected path under task_root {task_root!r}, got {brief_path_str!r}"` to stderr, increment `failures`.
     - If `str(hub_root) in brief_path_str`: print `f"FAIL brief_path: brief went to hub_root (regression): {brief_path_str!r}"` to stderr, increment `failures`.
     - If `failures == 0`: print `"PASS brief_path: discussion prepare stage writes brief to git_root (task worktree)"`.
     - Return `failures`.
  3. In `main()`: after the line `failures += test_review_cli_emits_envelope_on_slug_failure()`, add `failures += test_discussion_prepare_brief_path_uses_git_root()`.
- **Commit:** `test(review-cli): brief_path must be under git_root not hub_dir`

## Batch Tests

`verify: PYTHONPATH= uv run --project plugins/mill python plugins/mill/unit_tests/test-review-cli.py`

This runs the entire `test-review-cli.py` suite, which includes the new `test_discussion_prepare_brief_path_uses_git_root` function. Running the full file (rather than `--only`) is appropriate here because `test-review-cli.py` is a focused single file that tests the three review CLIs — not the unbounded `run-all.py` suite. The new test is the primary verification for Card 2; the existing tests confirm Card 1 hasn't regressed any error paths.
