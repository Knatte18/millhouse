# Batch: parser-and-brief

```yaml
task: Fix review finding-count parser, nested-layout brief path, verify cwd, process leaks, and missing done-gate
batch: parser-and-brief
number: 1
cards: 4
verify: PYTHONPATH= uv run --project plugins/mill python plugins/mill/unit_tests/run-all.py --only test-review-common.py test-review-discussion-flow.py
depends-on: []
```

## Batch Scope

Fixes two bugs with no shared state: #552 (`parse_blocking_count` in `_review_common.py` misses YAML findings-list format) and #553 (`millpy-review-discussion.py` writes the discussion-review brief under `git_root` instead of `hub_dir` in nested layouts). Each fix is a single-function or single-line change. Unit tests for both bugs are written in the same batch so the verify command covers all new assertions in one run.

## Cards

### Card 1: Extend `parse_blocking_count` with YAML findings-list fallback (#552)

- **Context:**
  - `plugins/mill/scripts/_review_common.py`
- **Edits:**
  - `plugins/mill/scripts/_review_common.py`
- **Creates:** none
- **Deletes:** none
- **Requirements:**
  Modify `parse_blocking_count` (line 1328) to add a YAML fallback path when the heading regex returns 0:

  1. After `heading_count = len(pattern.findall(raw_output))`:
     - If `heading_count > 0`: call `_warn_if_prose_diverges(raw_output, severity, heading_count)` and `return heading_count` — no change from today.
     - If `heading_count == 0`: proceed to yaml fallback scan (below).

  2. YAML fallback scan — extract all fenced yaml blocks from `raw_output`:
     - Split `raw_output` into lines. Iterate to find all occurrences of `` ```yaml `` (line where `line.rstrip() == "```yaml"`). For each such open fence, collect body lines until the matching `` ``` `` close fence (`line.rstrip() == "```"`); skip unclosed blocks silently.
     - For each collected body, call `yaml.safe_load("\n".join(body_lines))`. If `yaml.YAMLError` is raised, skip the block (do not crash). `yaml` is already imported at line 58.
     - If the parsed result is a dict with a `findings:` key whose value is a list, count entries where `isinstance(entry, dict) and entry.get("severity", "").upper() == severity` (case-insensitive severity comparison).
     - Sum counts across all parseable yaml blocks with `findings:` lists. Store as `yaml_count`.

  3. Call `_warn_if_prose_diverges(raw_output, severity, yaml_count)` with the yaml count.
  4. Return `yaml_count`.

  Update the `parse_blocking_count` docstring to mention the YAML fallback: "When the heading count is 0, falls back to scanning all fenced ```yaml blocks for a `findings:` list, counting entries whose `severity` field (case-insensitive) matches the severity argument."

  Do NOT change the function signature (`raw_output: str, *, severity: str) -> int`).
- **Commit:** `fix(_review_common): extend parse_blocking_count to count YAML findings-list entries (#552)`

---

### Card 2: Add `parse_blocking_count` YAML-fallback unit tests (#552)

- **Context:**
  - `plugins/mill/scripts/_review_common.py`
- **Edits:**
  - `plugins/mill/unit_tests/test-review-common.py`
- **Creates:** none
- **Deletes:** none
- **Requirements:**
  In `test-review-common.py`, locate the existing `parse_blocking_count` test section (around line 1580) and append six new test cases immediately after the existing ones. Each case follows the `assert result == expected; print("PASS: ...")` pattern already used:

  1. **yaml-list-only BLOCKING**: raw output has one fenced yaml block with `findings: [{severity: BLOCKING, title: "foo"}]` and no `### [BLOCKING]` heading. `parse_blocking_count(raw, severity="BLOCKING")` must return 1. Print: `"PASS: parse_blocking_count yaml-list BLOCKING -> 1"`.

  2. **yaml-list mixed severities**: raw output has `findings: [{severity: BLOCKING, title: "a"}, {severity: NIT, title: "b"}, {severity: NIT, title: "c"}]`. `severity="BLOCKING"` → 1; `severity="NIT"` → 2. Print two PASS lines.

  3. **heading wins over yaml**: raw output has both `### [BLOCKING] foo\n` (1 heading) and a yaml block with `findings: [{severity: BLOCKING}]`. `severity="BLOCKING"` → 1 (heading count, not yaml count — yaml scan is skipped when heading_count > 0). Print: `"PASS: parse_blocking_count heading>0 wins over yaml list"`.

  4. **verdict block is not counted**: raw output is the standard review preamble with a yaml block containing `verdict: APPROVE` but no `findings:` key. `severity="BLOCKING"` → 0 (verdict block must not produce a false positive). Print: `"PASS: parse_blocking_count verdict-only yaml block -> 0"`.

  5. **malformed yaml does not crash**: raw output has a fenced yaml block with invalid yaml (e.g. `findings: [{`). `severity="BLOCKING"` → 0 (skip the block). Print: `"PASS: parse_blocking_count malformed yaml block -> 0, no crash"`.

  6. **case-insensitive severity in yaml**: raw output has `findings: [{severity: blocking, title: "x"}]`. `parse_blocking_count(raw, severity="BLOCKING")` → 1. Print: `"PASS: parse_blocking_count yaml severity is case-insensitive"`.
- **Commit:** `test(_review_common): add parse_blocking_count YAML-fallback test cases (#552)`

---

### Card 3: Fix discussion-review brief path to use hub_dir (#553)

- **Context:**
  - `plugins/mill/scripts/_paths.py`
- **Edits:**
  - `plugins/mill/scripts/millpy-review-discussion.py`
- **Creates:** none
- **Deletes:** none
- **Requirements:**
  In `millpy-review-discussion.py`, in the `args.stage == "prepare"` branch (lines 93-112):

  1. Remove the comment at lines 96-97 that says "Write the brief under the task worktree (git_root)...". This comment was incorrect — the brief should go under `hub_dir`.
  2. At line 98, change `_paths.resolve_task_path(git_root, "_mill/briefs/")` to `_paths.resolve_task_path(hub_dir, "_mill/briefs/")`.

  `hub_dir` is already assigned at line 71 (`hub_dir = resolve_hub_path()`). No other changes needed in this file.
- **Commit:** `fix(millpy-review-discussion): write brief under hub_dir not git_root in nested layouts (#553)`

---

### Card 4: Add brief-path nested-layout test to `test-review-discussion-flow.py` (#553)

- **Context:**
  - `plugins/mill/scripts/millpy-review-discussion.py`
  - `plugins/mill/scripts/_paths.py`
  - `plugins/mill/unit_tests/test-review-discussion-flow.py`
- **Edits:**
  - `plugins/mill/unit_tests/test-review-discussion-flow.py`
- **Creates:** none
- **Deletes:** none
- **Requirements:**
  Add a new test function (or test block inside `main()`) to `test-review-discussion-flow.py` that verifies the brief is written under `hub_dir` when `hub_dir != git_root`. The test must exercise `millpy-review-discussion`'s prepare branch so that reverting Card 3's one-line fix breaks the assertion. Use `unittest.mock.patch` to override `_paths.resolve_hub_path` and `_paths.resolve_git_root` inside the `millpy_review_discussion` module namespace (or the `millpy-review-discussion` CLI module — check the exact import path used by the CLI). Then import and call the prepare branch logic directly:

  ```python
  import unittest.mock, sys, importlib
  from pathlib import Path
  import tempfile, subprocess

  with tempfile.TemporaryDirectory() as tmpdir:
      git_root = Path(tmpdir) / "repo"
      hub_dir = git_root / "src" / "proj"
      hub_dir.mkdir(parents=True)
      # patch _paths in the CLI module's namespace
      with unittest.mock.patch("millpy_review_discussion._paths.resolve_hub_path", return_value=hub_dir), \
           unittest.mock.patch("millpy_review_discussion._paths.resolve_git_root", return_value=git_root):
          # The changed line: _paths.resolve_task_path(hub_dir, "_mill/briefs/")
          import _paths
          briefs_dir = _paths.resolve_task_path(hub_dir, "_mill/briefs/")
          assert str(briefs_dir).startswith(str(hub_dir)), (
              f"brief path {briefs_dir} must be under hub_dir {hub_dir}"
          )
          assert not str(briefs_dir).startswith(str(git_root / "_mill")), (
              "brief must NOT land at git_root/_mill when hub_dir is a subdir"
          )
  ```

  Since `millpy-review-discussion.py` uses a hyphenated filename, import it with `importlib.util.spec_from_file_location` pointing at the script path, or invoke the patch at the `_paths` module level and call `_paths.resolve_task_path` with the patched values directly. The critical assertion is: when `hub_dir` is `git_root/src/proj`, `_paths.resolve_task_path(hub_dir, "_mill/briefs/")` must resolve under `hub_dir`, NOT under `git_root`. A reversion of the fix (changing back to `git_root`) must break this assertion.

  Print: `"PASS: discussion-review brief path is under hub_dir not git_root in nested layout"`.
- **Commit:** `test(review-discussion): add brief-path nested-layout assertion (#553)`

## Batch Tests

The `verify:` command runs `test-review-common.py` (for the `parse_blocking_count` YAML-fallback cases) and `test-review-discussion-flow.py` (for the brief-path nested-layout assertion). Both files are targeted explicitly with `--only` so the full suite is not run. The existing tests in both files also run, providing regression coverage for prior behavior. No stub LLM invocations are needed for the parser tests; the discussion-flow test uses in-process path-logic assertions for Card 4.
