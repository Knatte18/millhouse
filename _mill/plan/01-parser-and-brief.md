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
  Add a new test function `test_brief_path_nested_layout()` to `test-review-discussion-flow.py`. The test MUST invoke `millpy-review-discussion.py`'s prepare branch and spy on the `_paths.resolve_task_path` call to confirm the first argument is `hub_dir` (not `git_root`). A reversion of Card 3 changes the first argument back to `git_root`, breaking the assertion.

  **Critical constraint on patching:** `millpy-review-discussion.py` imports `_paths`, `_review_discussion`, `_review_common`, `_agent_dispatch`, `_reviewers`, and `_review_cli` INSIDE `main()` at lines 61-67 (indented, not module-level). After `spec.loader.exec_module(mod)`, `mod._paths` does NOT exist. Patching `mod._paths` or calling `mod._paths.anything` raises `AttributeError`. The only correct approach is to insert mock objects into `sys.modules` BEFORE loading the module, so that when `main()` runs `import _paths`, Python uses the mock from `sys.modules`.

  **Test design:**

  1. Create a temp layout: `git_root = tmpdir / "repo"`, `hub_dir = git_root / "src" / "proj"` (nested; `hub_dir` is a subdir of `git_root`).

  2. Build mock objects for every mill-script import that `main()` uses. Insert them into `sys.modules` before loading the module. Required mocks:
     - `sys.modules['_paths']`: a `MagicMock()` where:
       - `resolve_hub_path()` → `hub_dir`
       - `resolve_git_root()` → `git_root`
       - `resolve_wiki_path(git_root)` → `git_root / "wiki"`
       - `resolve_task_path` has `side_effect=lambda root, path: Path(str(root)) / path.lstrip('/')` (so calls are recorded and the return value is a real Path)
     - `sys.modules['_review_common']`: `load_config()` returns a minimal config dict with `paths.discussion_file`, `paths.reviews_dir`, and `roles.discussion-review.holistic.rounds = 1`. `discover_round()` returns 1. `find_active_slug()` returns `"test-slug"`.
     - `sys.modules['_review_discussion']`: `prepare` is a `MagicMock()`.
     - `sys.modules['_agent_dispatch']`, `sys.modules['_reviewers']`, `sys.modules['_review_cli']`: `MagicMock()`.
     Clean up `sys.modules` after the test (use `try/finally` or `unittest.mock.patch.dict(sys.modules, {...})`).

  3. Load the CLI module via `importlib.util.spec_from_file_location("millpy_review_discussion", scripts_dir / "millpy-review-discussion.py")` and call `spec.loader.exec_module(mod)`.

  4. Patch `sys.argv = ['prog', '--stage', 'prepare']`. Call `mod.main()` inside a `try/except (TypeError, SystemExit, Exception): pass` block — the prepare branch calls `json.dumps(envelope)` after `resolve_task_path`, and a bare-MagicMock return value will cause a `TypeError` at that point. The `resolve_task_path` call is recorded before the crash, so the assertion below still works.

  5. Assert: inspect `sys.modules['_paths'].resolve_task_path.call_args_list`. Find the call whose second argument starts with `"_mill/briefs/"`. Assert its first argument equals `hub_dir`.

  6. Assert the first argument is NOT equal to `git_root` (to confirm the check is meaningful, not vacuous).

  7. Print: `"PASS: discussion-review brief path is under hub_dir not git_root in nested layout"`.

  **Reversion guard:** reverting Card 3 (changing `_paths.resolve_task_path(hub_dir, ...)` back to `_paths.resolve_task_path(git_root, ...)` in the CLI prepare branch) causes assertion 5 to fail, because `resolve_task_path` is called with `git_root` instead of `hub_dir`.
- **Commit:** `test(review-discussion): add brief-path nested-layout assertion (#553)`

## Batch Tests

The `verify:` command runs `test-review-common.py` (for the `parse_blocking_count` YAML-fallback cases) and `test-review-discussion-flow.py` (for the brief-path nested-layout assertion). Both files are targeted explicitly with `--only` so the full suite is not run. The existing tests in both files also run, providing regression coverage for prior behavior. No stub LLM invocations are needed for the parser tests. Card 4's test loads `millpy-review-discussion` via `importlib.util.spec_from_file_location` and calls through the patched `_paths` module to confirm `briefs_dir` resolves under `hub_dir`; reverting Card 3's one-line fix breaks this assertion.
