# Batch: scope-violations-and-brief

```yaml
task: haiku-4-5 implementer reliability (hang + path mangle)
batch: scope-violations-and-brief
number: 2
cards: 3
verify: PYTHONPATH= uv run --project plugins/mill python plugins/mill/unit_tests/run-all.py --only test-cleanliness.py test-implementer-common.py
depends-on: []
```

## Batch Scope

Adds path-mangle detection and prevention. Detection: new `compute_scope_violations(worktree)` in `_cleanliness.py` that returns untracked files outside `_mill/`; called from `_forward_output` in `_implementer_common.py` so scope violations appear in the JSON report. Prevention: new `## Path format` section in `implementer-brief.md` that explicitly tells the implementer not to flatten path separators.

## Cards

### Card 5: Add compute_scope_violations to _cleanliness.py

- **Context:**
  - `plugins/mill/scripts/_pygit2_util.py`
- **Edits:**
  - `plugins/mill/scripts/_cleanliness.py`
- **Creates:** none
- **Deletes:** none
- **Requirements:**
  Add the following function to `_cleanliness.py` after the existing `compute_new_dirt` function:
  ```python
  def compute_scope_violations(worktree: Path) -> list[str]:
      """Return untracked files outside _mill/ that appeared at batch end.

      Uses _pygit2_util.status_porcelain with include_untracked=True so
      gitignored files are excluded automatically. Returns bare path strings
      (no '?? ' prefix), sorted. Empty list means no violations.
      """
      lines = _pygit2_util.status_porcelain(worktree, include_untracked=True)
      violations = []
      for line in lines:
          if line.startswith("?? "):
              path = line[3:]
              if not path.startswith("_mill/"):
                  violations.append(path)
      return sorted(violations)
  ```
  `_pygit2_util` is already imported at the top of `_cleanliness.py`. `Path` is already imported. The docstring uses ASCII only (no em dashes).
- **Commit:** `feat(_cleanliness): add compute_scope_violations`

### Card 6: Call compute_scope_violations in _forward_output

- **Context:**
  - `plugins/mill/scripts/_cleanliness.py`
  - `plugins/mill/scripts/_implementer_common.py`
- **Edits:**
  - `plugins/mill/scripts/_implementer_common.py`
- **Creates:** none
- **Deletes:** none
- **Requirements:**
  Modify `_forward_output` in `_implementer_common.py` to call `_cleanliness.compute_scope_violations(project_root)` and attach violations to the JSON output. The changes cover three code paths inside `_forward_output`:

  **Path A — explicit JSON from LLM output** (inside the `matches` regex branch, after `parsed = json.loads(last)` succeeds and `commit_sha` is attached):
  Before `print(json.dumps(parsed))`, add:
  ```python
  violations = _cleanliness.compute_scope_violations(project_root)
  if violations:
      parsed["scope_violations"] = violations
  ```

  **Path B — inferred success** (inside the `if result_full.stdout.strip():` else-branch that prints the `success`/`inferred` result):
  The current code prints:
  ```python
  print(json.dumps({"status": "success", "commit_sha": head, "session_id": session_id or "unknown", "inferred": True}))
  return 0
  ```
  Replace with:
  ```python
  violations = _cleanliness.compute_scope_violations(project_root)
  if violations:
      print(json.dumps({"status": "stuck", "stuck_type": "logic", "reason": f"untracked files outside scope: {violations}", "scope_violations": violations, "inferred": True}))
  else:
      print(json.dumps({"status": "success", "commit_sha": head, "session_id": session_id or "unknown", "inferred": True}))
  return 0
  ```

  **Path C — final no-structured-report fallback** (the last `print(json.dumps(...))` in the function):
  The current code prints:
  ```python
  print(json.dumps({"status": "stuck", "stuck_type": "logic", "reason": "no structured report"}))
  ```
  Replace with:
  ```python
  violations = _cleanliness.compute_scope_violations(project_root)
  result = {"status": "stuck", "stuck_type": "logic", "reason": "no structured report"}
  if violations:
      result["scope_violations"] = violations
  print(json.dumps(result))
  ```

  The `_cleanliness` module is already imported at the top of `_implementer_common.py`. All three calls use `project_root` which is already an argument to `_forward_output`. The `reason` string in Path B uses an f-string with a list; confirm the list repr is ASCII (path strings from the filesystem are ASCII-safe in this context).
- **Commit:** `feat(_implementer_common): report scope violations in _forward_output`

### Card 7: Add Path format section to implementer-brief.md

- **Context:**
  - `plugins/mill/templates/implementer-brief.md`
- **Edits:**
  - `plugins/mill/templates/implementer-brief.md`
- **Creates:** none
- **Deletes:** none
- **Requirements:**
  Insert a new `## Path format` section between the `## Tools` section and the `## Cross-worktree isolation` section. The exact text to insert (between the blank line ending `## Tools` and the `## Cross-worktree isolation` heading):
  ```
  ## Path format

  **File paths are POSIX-style relative paths from `<PROJECT_ROOT>`.** Never flatten path separators into underscores. `plugins/mill/scripts/_config.py` is a file at `plugins/mill/scripts/` named `_config.py` -- not a file named `plugins_mill_scripts_config.py` at the worktree root. When in doubt, verify with `Read` before writing.

  ```
  Use `--` (double hyphen + space) not an em dash. The section must appear before `## Cross-worktree isolation` and after `## Tools`. No other changes to the file.
- **Commit:** `docs(brief): add Path format section to prevent underscore-flattening`

## Batch Tests

Verify runs `test-cleanliness.py` (9 existing cases for `compute_new_dirt` + `capture_snapshot`) and `test-implementer-common.py` (6 existing cases for inferred-success paths). The new tests for `compute_scope_violations` and scope-violations-in-`_forward_output` are in batch 3. This verify is a regression check: all existing cases must still pass after the new function is added and `_forward_output` is modified. The existing cases do not call `compute_scope_violations`, so if the existing mock patches are in place they should be unaffected.
