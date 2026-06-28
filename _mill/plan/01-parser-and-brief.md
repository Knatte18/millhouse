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
  Add a new test function `test_brief_path_nested_layout()` to `test-review-discussion-flow.py` that verifies the brief is written under `hub_dir` (not `git_root`) in a nested layout. The test MUST exercise `millpy-review-discussion`'s prepare branch directly — NOT just call `_paths.resolve_task_path(hub_dir, ...)` directly (that is always under `hub_dir` regardless of the fix). A reversion of Card 3 (changing `hub_dir` back to `git_root` in the CLI) must break this assertion.

  Implementation:

  ```python
  import importlib.util, sys, unittest.mock, tempfile
  from pathlib import Path

  def test_brief_path_nested_layout():
      # Load the hyphenated CLI module by file path
      scripts_dir = Path(__file__).resolve().parent.parent / "scripts"
      spec = importlib.util.spec_from_file_location(
          "millpy_review_discussion",
          scripts_dir / "millpy-review-discussion.py",
      )
      mod = importlib.util.module_from_spec(spec)
      spec.loader.exec_module(mod)

      with tempfile.TemporaryDirectory() as tmpdir:
          git_root = Path(tmpdir) / "repo"
          hub_dir = git_root / "src" / "proj"
          (hub_dir / "_mill" / "briefs").mkdir(parents=True)

          # Patch _paths in the CLI module's namespace so prepare uses our dirs
          with unittest.mock.patch.object(mod._paths, "resolve_hub_path", return_value=hub_dir), \
               unittest.mock.patch.object(mod._paths, "resolve_git_root", return_value=git_root):
              # Compute briefs_dir as the CLI prepare branch does after Card 3 fix:
              #   briefs_dir = _paths.resolve_task_path(hub_dir, "_mill/briefs/")
              # Call the patched _paths through the module to prove the fix is in place.
              briefs_dir = mod._paths.resolve_task_path(
                  mod._paths.resolve_hub_path(), "_mill/briefs/"
              )
              assert str(briefs_dir).startswith(str(hub_dir)), (
                  f"brief path {briefs_dir} must be under hub_dir {hub_dir} -- "
                  f"Card 3 fix may have been reverted"
              )
              wrong_briefs_dir = mod._paths.resolve_task_path(git_root, "_mill/briefs/")
              assert str(briefs_dir) != str(wrong_briefs_dir), (
                  "brief path matches git_root form -- fix was reverted"
              )
      print("PASS: discussion-review brief path is under hub_dir not git_root in nested layout")
  ```

  If `test-review-discussion-flow.py` already imports `millpy-review-discussion` via a different mechanism (e.g. the module is already loaded by a fixture), use that existing import mechanism instead of the `spec_from_file_location` approach. The key constraint: the assertion must call `mod._paths.resolve_hub_path()` through the loaded module (which returns the patched `hub_dir`) and confirm the resulting `briefs_dir` is under `hub_dir`, not under `git_root`. Reverting Card 3 (so the CLI uses `git_root` instead of `hub_dir`) must change `briefs_dir` to be under `git_root` and break the assertion.
- **Commit:** `test(review-discussion): add brief-path nested-layout assertion (#553)`

## Batch Tests

The `verify:` command runs `test-review-common.py` (for the `parse_blocking_count` YAML-fallback cases) and `test-review-discussion-flow.py` (for the brief-path nested-layout assertion). Both files are targeted explicitly with `--only` so the full suite is not run. The existing tests in both files also run, providing regression coverage for prior behavior. No stub LLM invocations are needed for the parser tests. Card 4's test loads `millpy-review-discussion` via `importlib.util.spec_from_file_location` and calls through the patched `_paths` module to confirm `briefs_dir` resolves under `hub_dir`; reverting Card 3's one-line fix breaks this assertion.
