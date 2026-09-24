# Batch: status-core

```yaml
task: 'status.md: rename parent to parent_branch, add parent_thread'
batch: status-core
number: 1
cards: 4
verify: PYTHONPATH= uv run --project plugins/mill python plugins/mill/unit_tests/run-all.py --only test-status.py test-parent-branch.py test-cleanup.py
depends-on: []
```

## Batch Scope

Renames the status.md key `parent:` to `parent_branch:` in the status template and in every Python reader/writer of that key, keeping the legacy `parent:` readable, and teaches `_status.render_initial` to emit the optional `parent_thread:` row.
Delivers the interface batches 2 and 3 consume: `_status.render_initial(..., *, parent_thread=None)` and `_status.set_parent_branch(status_path, value)`.
One batch because all four cards touch the status.md key contract in `_status.py` / `_parent_branch.py` and their two unit-test files.

## Cards

### Card 1: status template renders parent_branch and optional parent_thread

- **Context:**
  - `plugins/mill/scripts/_yaml_writer.py`
- **Edits:**
  - `plugins/mill/templates/status-discussing.md`
  - `plugins/mill/scripts/_status.py`
  - `plugins/mill/unit_tests/test-status.py`
- **Creates:** none
- **Deletes:** none
- **Moves:** none
- **Requirements:**
  - In `status-discussing.md`, change the yaml row `parent: <PARENT_BRANCH>` to `parent_branch: <PARENT_BRANCH>`.
    In its leading HTML comment, add one line stating that `render_initial` inserts an optional `parent_thread:` row immediately after `parent_branch:` when a non-empty `parent_thread` is passed, and that the template has no token for it.
  - In `_status.py`, add a keyword-only parameter `parent_thread: str | None = None` to `render_initial` (after `branch`, behind a bare `*`).
    After the existing token substitution and the unresolved-token `KeyError` check: when `parent_thread` is a `str` and `parent_thread.strip()` is non-empty, find the first line of the rendered body matching `^parent_branch:\s*` and insert `parent_thread: {quote_scalar(parent_thread.strip())}` as the next line.
    If no `parent_branch:` line exists, raise `ValueError` naming the template (template drift).
    When `parent_thread` is `None`, empty, or whitespace-only, the output is unchanged (no `parent_thread` row).
  - Update the `render_initial` docstring `Args:` with `parent_thread` (the spawning session's name, recorded for the follow-up escalation task; row omitted when `None`/empty) and change its `parent_branch` arg text to name the `parent_branch:` key.
  - In the module docstring's `Public API:` list, change the `render_initial` line to `render_initial(task_title, task_description, timestamp, parent_branch, slug, branch, *, parent_thread=None) -> str`.
  - In `test-status.py`: change the assertion `"parent: main" in out` to `"parent_branch: main" in out` and add an assertion that no line of `out` starts with `parent:`; change `assert "parent" in r["yaml"]` to check `"parent_branch"`; change `result["parent"] == "main"` (and its message) to `result["parent_branch"]`.
  - Add new blocks inside `test-status.py`'s `main()`, in the existing `print("PASS: ...")` style: `render_initial(..., parent_thread="mh:orch")` places the `parent_thread:` line immediately after the `parent_branch:` line, and `read()` on the written file returns `"mh:orch"` for `parent_thread`; `parent_thread=None`, `""` and `"   "` each render no line starting with `parent_thread:`.
- **Commit:** `feat(status): render parent_branch and optional parent_thread in status.md`

### Card 2: read_parent_branch fallback and set_parent_branch writer

- **Context:**
  - `plugins/mill/scripts/_yaml_writer.py`
- **Edits:**
  - `plugins/mill/scripts/_status.py`
  - `plugins/mill/unit_tests/test-status.py`
- **Creates:** none
- **Deletes:** none
- **Moves:** none
- **Requirements:**
  - `read_parent_branch`: read `full["yaml"].get("parent_branch")`; when that is not a non-empty `str`, fall back to `full["yaml"].get("parent")`.
    Keep the existing contract: stripped string, or `None` on missing file / parse failure / neither key usable.
    Update the docstring to name `parent_branch:` with the legacy `parent:` fallback and the precedence rule (`parent_branch:` wins).
  - Add `set_parent_branch(status_path: Path | str, value: str) -> None`, placed directly after `update_field`, modelled on `update_field`'s line scan over the `_split_fences(text, _YAML_FENCE)` block:
    if a line matching `^parent_branch:\s*` exists, rewrite it as `parent_branch: {quote_scalar(value)}` keeping its line ending;
    else if a line matching `^parent:\s*` exists, replace that line in place with `parent_branch: {quote_scalar(value)}` keeping its line ending (migrate-on-write, row order preserved);
    else raise `ValueError(f"parent_branch: key missing from yaml block of {status_path}")`.
    Use `_as_path(status_path, "set_parent_branch")`.
    Docstring states the dual-key behaviour and why it exists (skills rebind the parent branch on files carrying either key).
  - Add `set_parent_branch(status_path, value) -> None` to the module docstring's `Public API:` list after `update_field`.
  - In `test-status.py`, import `read_parent_branch` and `set_parent_branch` from `_status` (add to the existing import block if absent) and add blocks in `main()`:
    `read_parent_branch` on a file with only `parent_branch: main`, only legacy `parent: main`, both (`parent_branch: feat` and `parent: main` -> `"feat"`), and neither (-> `None`);
    `set_parent_branch` rewrites an existing `parent_branch:` row;
    on a legacy file it leaves no line starting with `parent:`, puts `parent_branch:` at the old row's index, and keeps every other row in order;
    on a yaml block with neither key it raises `ValueError`.
- **Commit:** `feat(status): add set_parent_branch and legacy parent fallback in read_parent_branch`

### Card 3: baseline rows anchor after parent_thread, parent_branch, or legacy parent

- **Context:**
  - `plugins/mill/scripts/_yaml_writer.py`
- **Edits:**
  - `plugins/mill/scripts/_status.py`
  - `plugins/mill/unit_tests/test-status.py`
- **Creates:** none
- **Deletes:** none
- **Moves:** none
- **Requirements:**
  - Add a private helper `_baseline_anchor_index(lines: list[str], start: int, end: int, status_path: Path) -> int` in `_status.py`, placed just before `set_module_verify_baseline`.
    It returns the index of the first yaml-block line matching `^parent_thread:\s*`; if none, the first matching `^parent_branch:\s*`; if none, the first matching `^parent:\s*`.
    It raises `ValueError(f"parent_branch: key missing from yaml block of {status_path}")` when none of the three exists.
  - In `set_module_verify_baseline` and `set_module_verify_baseline_signatures`, replace the "Absent: insert a new row immediately after parent:." scan (the `parent_idx` loop and its `ValueError`) with a call to `_baseline_anchor_index`, inserting the new row at the returned index plus one.
    The rewrite-in-place branch is unchanged.
  - Update both functions' docstrings: the insertion anchor is `parent_thread:` when present, else `parent_branch:`, else legacy `parent:`; the `Raises:` text names the missing-anchor case accordingly.
  - In `test-status.py` add blocks in `main()` for each of `set_module_verify_baseline` and `set_module_verify_baseline_signatures`: on a hand-written yaml block with `parent_branch:` followed by `parent_thread:`, the new row lands immediately after `parent_thread:`; with `parent_branch:` only, immediately after `parent_branch:`; with legacy `parent:` only, immediately after `parent:`; with none of the three, `ValueError` is raised.
- **Commit:** `feat(status): anchor baseline rows after parent_thread/parent_branch with legacy parent fallback`

### Card 4: _parent_branch reads parent_branch with legacy parent fallback

- **Context:**
  - `plugins/mill/scripts/_subprocess_util.py`
- **Edits:**
  - `plugins/mill/scripts/_parent_branch.py`
  - `plugins/mill/unit_tests/test-parent-branch.py`
- **Creates:** none
- **Deletes:** none
- **Moves:** none
- **Requirements:**
  - Rewrite `_parse_parent_from_yaml_text` to track two values while scanning the first yaml block: `parent_branch_value` from lines whose stripped form starts with `parent_branch:`, and the legacy `parent_value` from lines whose stripped form starts with `parent:`.
    Strip surrounding quotes from both the same way the current code does.
    `parent_thread:` must never feed either value (it does not start with `parent:`; keep it that way).
    The `expected_slug` guard is unchanged.
    Return `parent_branch_value` when non-empty, else `parent_value` when non-empty, else `None`.
  - Update docstrings to name `parent_branch:` with the legacy `parent:` fallback: the module docstring, `_parse_parent_from_yaml_text`, `_read_parent_from_status`, `resolve_dead_parent` (state that archived status.md files carry legacy `parent:` and are read through the fallback), and `resolve`.
  - Change user-facing text in `resolve`: the non-interactive `ParentBranchError` becomes `f"No parent_branch: in {status_path} and non-interactive context; set status.md's parent_branch: row and re-run mill-merge manually."`; the prompt becomes `"[_parent_branch] status.md has no parent_branch: row. Enter parent branch name (e.g. main): "`; the EOF `ParentBranchError` becomes `f"No parent_branch: in {status_path} and stdin not attached"`.
  - In `test-parent-branch.py`: change both `"No parent:" in str(exc)` assertions to `"No parent_branch:"`.
    Add cases: `resolve` on a file with `parent_branch: main` only; both keys (`parent_branch: feat` plus `parent: main` -> `"feat"`); a file with only `parent_thread: 'mh:orch'` raises `ParentBranchError` non-interactively; `expected_slug` mismatch raises `ParentBranchError` for a `parent_branch:` file just as for a legacy one.
    Add `resolve_dead_parent` cases with `_parent_branch._subprocess_util.run` patched via `side_effect` (tag check rc 0, `git show` rc 0 whose `stdout` is an archived status.md yaml block, then `ls-remote` rc 0): one archived block with `parent_branch: main`, one with legacy `parent: main`; both return `{"outcome": "resolved", "branch": "main", "hops": [...]}`.
    Pass `cfg={"spawn": {"branch_prefix": "test/"}, "git": {"base_branch": "main"}}` and a `test/<slug>` dead branch.
- **Commit:** `feat(parent-branch): read parent_branch with legacy parent fallback`

## Batch Tests

`verify:` runs `test-status.py` (cards 1-3), `test-parent-branch.py` (card 4) and `test-cleanup.py`, whose existing `read_parent_branch` cases consume card 2's reader through legacy `parent:` fixtures.
