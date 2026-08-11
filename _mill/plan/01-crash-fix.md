# Batch: crash-fix

```yaml
task: mill-merge-in --recompute-baseline crashes uncaught on absent status.md
batch: crash-fix
number: 1
cards: 1
verify: PYTHONPATH= uv run --project plugins/mill python plugins/mill/unit_tests/test-millpy-merge-in-subagent.py
depends-on: []
```

## Batch Scope

Fix the last of the three #803 crash sites: `_run_recompute_baseline()` in `millpy-merge-in-subagent.py` calls `_paths.require_status_path(project_root, cfg)` outside any try/except, breaking the function's own documented "never raises" contract when `_mill/status.md` is entirely absent (the closed-PR re-entry path after mill-finalize's cleanup commit removes `_mill/`). This is a single, inseparable production-fix + regression-test change — one card, one commit. No external interface changes; the next batch does not exist (this plan has one batch).

## Cards

### Card 1: wrap require_status_path in _run_recompute_baseline and add regression coverage

- **Context:**
  - `plugins/mill/scripts/_paths.py`
- **Edits:**
  - `plugins/mill/scripts/millpy-merge-in-subagent.py`
  - `plugins/mill/unit_tests/test-millpy-merge-in-subagent.py`
- **Creates:** none
- **Deletes:** none
- **Moves:** none
- **Requirements:**
  In `_run_recompute_baseline` (`millpy-merge-in-subagent.py:224`), replace:
  ```python
  status_path = _paths.require_status_path(project_root, cfg)
  ```
  with:
  ```python
  try:
      status_path = _paths.require_status_path(project_root, cfg)
  except Exception as e:
      print(json.dumps({"status": "success", "baseline": "error", "reason": str(e)}))
      return 0
  ```
  No new import is needed (`_paths` and `json` are already imported at module top level). Do not add a `file=sys.stderr` diagnostic line — this mirrors the `parent_branch = _parent_branch.resolve(...)` sibling block (lines 247-251), not the `compute_baseline` sibling block.

  Also update the function's docstring (`millpy-merge-in-subagent.py` lines 211-214): its "Never raises" paragraph enumerates failure paths as "no module-wide verify configured, parent branch unresolvable, or the computation itself raising" — add "status.md absent" as a fourth enumerated failure path so the docstring stays accurate to the fixed behavior.

  In `TestMillpyMergeInSubagent` (`test-millpy-merge-in-subagent.py`), add one new test method immediately after `test_2x_finalize_conflicts_missing_files_flag` (the class's last existing method, ending at line 846) — still indented inside `TestMillpyMergeInSubagent`'s body, and before the module-level `def _git(args, cwd, check=True):` helper (line 849) and the subsequent `class TestVerifyConflictMarkersGate` (line 864). Do not place it after `_git` or outside the class — that would break indentation/`self` semantics:
  ```python
      def test_20_recompute_baseline_missing_status_md(self):
          """--recompute-baseline with status.md absent -> exit 0, baseline:error JSON, no raise.

          setUp() never creates _mill/ under self.tmp_path, so status.md is already absent by
          default here. load_config's mocked return_value must carry a realistic "paths" section
          (mirroring real mill-config.yaml) so require_status_path raises the genuine TaskHubError
          this bug is about, rather than an unrelated KeyError from a paths-less test fixture.
          """
          self.mock_load_config.return_value = {
              "merge": {"verify_fix_rounds": 3},
              "llm": {"implementer_timeout": 1800},
              "paths": {"status_md": "_mill/status.md", "plan_dir": "_mill/plan/"},
          }
          rc, out = self._run_main(["--recompute-baseline"])
          self.assertEqual(rc, 0)
          data = json.loads(out.strip())
          self.assertEqual(data["status"], "success")
          self.assertEqual(data["baseline"], "error")
          self.assertIn("status.md", data["reason"])
  ```
  This exercises the fixed code path end-to-end through `main(["--recompute-baseline"])`, asserting the function returns 0 and emits the documented fail-safe JSON shape without raising.
- **Commit:** `fix(mill-merge-in): don't crash on absent status.md during --recompute-baseline`

## Batch Tests

`verify:` runs the full `test-millpy-merge-in-subagent.py` file (not a narrower `--only` scope) because the new test lives in the same file as, and shares `setUp` with, every other test in `TestMillpyMergeInSubagent` — a file-scoped run is the natural verify unit here, not an unbounded `run-all.py` across the whole suite. Covers: the new `test_20_recompute_baseline_missing_status_md` regression case, plus the existing `--recompute-baseline`-adjacent tests (`test_9_missing_mode`, `test_10_missing_slug`) to catch any regression in the surrounding dispatch logic.
