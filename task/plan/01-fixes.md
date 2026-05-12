# Batch: fixes

```yaml
task: 54 (A) — Bug-fix batch 6 (post-46/50 triage)
batch: fixes
number: 1
cards: 6
verify: "python plugins/mill/unit_tests/run-all.py"
depends-on: []
```

## Batch Scope

Six tightly coupled fixes to production code and their unit tests. Cards 1–4 patch production modules (`_worktree.py`, `_marker.py`, `mill-go/SKILL.md`) and delete three dead reviewer files. Cards 5–6 add unit tests for the two Python changes. All six changes are small and share the same context set; implementing them together lets the test author see the finished production code.

## Cards

### Card 1: `_worktree.remove_safe` — extend rmtree fallback to "is not a working tree"

- **Context:**
  - `plugins/mill/scripts/_subprocess_util.py`
- **Edits:**
  - `plugins/mill/scripts/_worktree.py`
- **Creates:** none
- **Deletes:** none
- **Requirements:**
  - At line 253 in `_worktree.py`, rename `long_path_marker` to `rmtree_fallback` and extend the condition to also include `"is not a working tree" in stderr`: `rmtree_fallback = "Filename too long" in stderr or "filename too long" in stderr or "is not a working tree" in stderr`.
  - Replace every subsequent reference to `long_path_marker` in the function with `rmtree_fallback` (one use at `if not long_path_marker:`).
  - Update the inline print at line 263–267 to read `"[worktree] remove_safe: git failed; falling back to shutil.rmtree (junctions already stripped)"` (drop the "long-path error" phrasing so it covers both triggers).
  - Update the `Raises:` section of the `remove_safe` docstring to read: `WorktreeError: git worktree remove failed for a reason other than long-path or "not a working tree" (e.g., "is in use"), and the fallback was not attempted.`
- **Commit:** `fix(_worktree): extend rmtree fallback to cover "is not a working tree" (#264 #265)`

### Card 2: `_marker.slug_from_branch` — self-healing user-prefix retry

- **Context:** none
- **Edits:**
  - `plugins/mill/scripts/_marker.py`
- **Creates:** none
- **Deletes:** none
- **Requirements:**
  - In `slug_from_branch` (line 59–62 in `_marker.py`), after `task = next((t for t in tasks if t.slug == slug), None)`, insert a self-healing block inside the `if task is None:` branch. The block must:
    1. Check `"/" in branch and not prefix`.
    2. Compute `stripped_slug = branch.split("/", 1)[1]`.
    3. Retry: `task = next((t for t in tasks if t.slug == stripped_slug), None)`.
    4. If found: `return stripped_slug`.
    5. If still not found: `raise MarkerError(f"branch slugs {slug!r} and {stripped_slug!r} not found in Home.md")`.
  - The existing `raise MarkerError(f"branch slug {slug!r} not present in Home.md")` at line 61 is only reached when the branch contains no `/` or a prefix is configured (i.e. the self-healing path did not activate); keep it as-is.
  - No changes to any other function in `_marker.py`.
- **Commit:** `fix(_marker): self-healing slug retry for user-prefix branches with no configured branch_prefix (#261)`

### Card 3: `mill-go/SKILL.md` — CLAUDE_PLUGIN_ROOT fallback preamble

- **Context:** none
- **Edits:**
  - `plugins/mill/skills/mill-go/SKILL.md`
- **Creates:** none
- **Deletes:** none
- **Requirements:**
  - Insert a new "**Step 0: Resolve `PLUGIN_ROOT`.**" paragraph immediately before the current "1." step in `## Entry`. The step must contain a fenced bash code block:
    ```bash
    PLUGIN_ROOT="${CLAUDE_PLUGIN_ROOT}"
    if [ -z "$PLUGIN_ROOT" ]; then
        PLUGIN_ROOT="$(git rev-parse --show-toplevel)/plugins/mill"
        echo "[mill-go] CLAUDE_PLUGIN_ROOT unset; resolved to: $PLUGIN_ROOT"
    fi
    ```
    Followed by a single explanatory sentence: "Use `$PLUGIN_ROOT` in place of `$CLAUDE_PLUGIN_ROOT` for all subsequent `uv run` commands in this skill."
  - Replace every occurrence of `$CLAUDE_PLUGIN_ROOT` inside fenced bash/shell code blocks in the file with `$PLUGIN_ROOT`. There are 25 such occurrences. Do not alter occurrences in prose text (there are none — all 25 are inside code blocks).
- **Commit:** `fix(mill-go): add PLUGIN_ROOT fallback for empty CLAUDE_PLUGIN_ROOT (#262)`

### Card 4: Delete dead opus reviewer files

- **Context:** none
- **Edits:** none
- **Creates:** none
- **Deletes:**
  - `plugins/mill/scripts/_reviewer_opushigh.py`
  - `plugins/mill/scripts/_reviewer_opusmax.py`
  - `plugins/mill/scripts/_reviewer_opusmid.py`
- **Requirements:**
  - Before deleting, grep `plugins/mill/scripts/` for `_reviewer_opushigh`, `_reviewer_opusmax`, and `_reviewer_opusmid` to confirm zero import sites (discussion already confirmed this; the grep is a pre-delete guard).
  - Delete all three files. Do not modify any other file.
- **Commit:** `chore(scripts): delete dead opus reviewer modules (#267)`

### Card 5: `test-worktree.py` — "is not a working tree" test cases

- **Context:**
  - `plugins/mill/scripts/_worktree.py`
- **Edits:**
  - `plugins/mill/unit_tests/test-worktree.py`
- **Creates:** none
- **Deletes:** none
- **Requirements:**
  - Add three new test blocks inside the `try:` body of `main()`, immediately after the existing `"PASS: remove_safe raises WorktreeLockedError on Invalid argument"` block (the last existing `remove_safe` test).
  - **Test A** — path exists, rmtree succeeds: mock `_subprocess_util.run` to return `returncode=1, stderr="fatal: 'path' is not a working tree"`. Create `path` with `mkdir`. Do NOT patch `shutil.rmtree`. Call `remove_safe(path, cwd=cwd, junctions_cfg={})` and assert no exception is raised. Assert `not path.exists()` (real rmtree ran). Print `"PASS: remove_safe exits cleanly via rmtree fallback on 'is not a working tree' (path exists)"`.
  - **Test B** — path exists, rmtree raises PermissionError: same mock for git; additionally patch `shutil.rmtree` with `side_effect=PermissionError("locked")`. Assert `WorktreeLockedError` is raised. Print `"PASS: remove_safe raises WorktreeLockedError when rmtree raises PermissionError on 'is not a working tree'"`.
  - **Test C** — path absent: mock git same way but do NOT call `path.mkdir()` (path does not exist). Assert no exception is raised (rmtree is skipped; prune runs but its mock result returning `returncode=1` only prints a warning). Print `"PASS: remove_safe exits cleanly when path absent and 'is not a working tree'"`.
  - Update the `"All _worktree unit tests passed."` final print to remain accurate (it is already generic — no change needed to the text).
- **Commit:** `test(_worktree): add remove_safe 'is not a working tree' cases (#264 #265)`

### Card 6: `test-marker.py` — user-prefix retry test cases

- **Context:**
  - `plugins/mill/scripts/_marker.py`
  - `plugins/mill/unit_tests/_test_helpers.py`
- **Edits:**
  - `plugins/mill/unit_tests/test-marker.py`
- **Creates:** none
- **Deletes:** none
- **Requirements:**
  - Add two new test functions after `test_slug_from_branch_prefix_mismatch` and before `test_task_data_happy_path`.
  - **`test_slug_from_branch_user_prefix_no_config_prefix`**: use `_test_helpers._make_task_worktree(tmp, "foo", "Foo Title", branch_prefix="hanf/", phase="active")` to create a worktree on branch `hanf/foo` with Home.md containing `[[foo]] [active]`. Pass `cfg = {}` (no `spawn.branch_prefix`). Call `_marker.slug_from_branch(worktree_path, wiki_path, cfg)` and assert it returns `"foo"`. Print `"PASS: test_slug_from_branch_user_prefix_no_config_prefix"`.
  - **`test_slug_from_branch_user_prefix_slug_not_found`**: same helper call creating branch `hanf/bar`. Then overwrite `wiki_path / "Home.md"` to contain only `[[foo]] [active]` (not `bar`). Pass `cfg = {}`. Assert `_marker.MarkerError` is raised. Print `"PASS: test_slug_from_branch_user_prefix_slug_not_found"`.
  - Register both new functions in the `tests` list inside `main()`, after `test_slug_from_branch_prefix_mismatch` and before `test_task_data_happy_path`. Update the `"All {len(tests)} _marker unit tests passed."` counter is derived from `len(tests)` dynamically — no manual update needed.
- **Commit:** `test(_marker): add user-prefix self-healing retry cases (#261)`

## Batch Tests

The batch verify command is `python plugins/mill/unit_tests/run-all.py`. It discovers and runs every `test-*.py` in `plugins/mill/unit_tests/`, including `test-worktree.py` and `test-marker.py`. After cards 5 and 6, the three new `remove_safe` cases and two new `slug_from_branch` cases must all report `PASS`. Existing test cases must continue to pass (regression coverage).
