# Batch: merge-in-verify-field-fix

```yaml
task: "Misc infra/wiki/PR/self-hosting reliability bugs"
batch: merge-in-verify-field-fix
number: 3
cards: 1
verify: PYTHONPATH= uv run --project plugins/mill python plugins/mill/unit_tests/test-millpy-merge-in-subagent.py
depends-on: []
```

## Batch Scope

Fixes #1106: `millpy-merge-in-subagent.py --recompute-baseline` raises `TypeError: expected str,
bytes or os.PathLike object, not dict` when a plan's module-wide `verify:` field is the
`{cwd: hub|git_root, command: ...}` mapping form, because `_run_recompute_baseline` reads
`overview_frontmatter.get("verify")` directly instead of routing it through
`_plan_dag.parse_verify_field` — the single normalizer every other read site (implementer, fixer,
plan-validate, and the eager baseline pre-flight in `millpy-implement.py`) already uses. One batch,
one card: the fix is a single function's internals, self-contained.

## Cards

### Card 7: route `_run_recompute_baseline` through `parse_verify_field`

- **Context:**
  - `plugins/mill/scripts/_plan_dag.py`
  - `plugins/mill/scripts/_verify_baseline.py`
- **Edits:**
  - `plugins/mill/scripts/millpy-merge-in-subagent.py`
  - `plugins/mill/unit_tests/test-millpy-merge-in-subagent.py`
- **Creates:** none
- **Deletes:** none
- **Moves:** none
- **Requirements:**
  In `millpy-merge-in-subagent.py`'s `_run_recompute_baseline`, this line:
  ```python
  module_wide_verify_cmd = overview_frontmatter.get("verify") or None
  ```
  reads the raw frontmatter value directly, which can be a `{cwd: hub|git_root, command: ...}`
  mapping, not just a plain string. Replace it with:
  ```python
  module_wide_verify_cmd, cwd_override = _plan_dag.parse_verify_field(
      overview_frontmatter, project_root, git_root
  )
  ```
  (mirrors `millpy-implement.py`'s own module-wide baseline call: `module_wide_verify_cmd,
  module_wide_cwd_override = _plan_dag.parse_verify_field(overview_frontmatter, project_root,
  git_root)`). `_plan_dag` must be imported at module scope in `millpy-merge-in-subagent.py` if it
  is not already. `parse_verify_field` can raise `ValueError` on a malformed mapping (missing
  `command:`, or an unrecognized `cwd:` value) — wrap this call in the same
  `try/except Exception as e: print(json.dumps({"status": "success", "baseline": "error", "reason":
  str(e)})); return 0` pattern this function already uses around the adjacent `_parent_branch.resolve`
  and `_verify_baseline.compute_baseline` calls, so the function's documented "never raises, always
  emits a JSON status line" contract holds for this new failure mode too.
  Thread `cwd_override` into the existing `_verify_baseline.compute_baseline(...)` call as its
  `cwd_override_relative=cwd_override` keyword argument (the parameter already exists on
  `compute_baseline` for exactly this purpose — see its docstring's `cwd_override_relative` entry).
  The `module_wide_verify_cmd is None` early-return branch immediately below (today's "no
  module-wide verify configured" skip) is unaffected — `parse_verify_field` already returns `(None,
  None)` for an absent/null `verify:` field, so that branch's existing `if module_wide_verify_cmd is
  None:` check keeps working unchanged.
- **Commit:** `fix(merge-in): normalize mapping-form verify field before baseline recompute (#1106)`

## Batch Tests

Extend `plugins/mill/unit_tests/test-millpy-merge-in-subagent.py`'s existing
`test_20_recompute_baseline_missing_status_md`-adjacent test group (same `TestMillpyMergeInSubagent`
class, same `self._run_main(["--recompute-baseline"])` / `self.mock_load_config` fixture pattern)
with two new cases:
- `test_21_recompute_baseline_mapping_verify_field`: overview frontmatter's `verify:` is a
  `{cwd: "hub", command: "..."}` mapping (write a real `00-overview.md` fixture with that fenced-yaml
  shape under a temp plan dir, mirroring how the existing tests set up `status.md`). Mock
  `_verify_baseline.compute_baseline` to capture its call arguments instead of actually running a
  verify command. Assert no `TypeError` is raised, `compute_baseline` was called with a plain string
  `module_wide_verify_cmd` (not a dict), and `cwd_override_relative` was passed as the resolved hub
  path.
- `test_22_recompute_baseline_malformed_verify_field`: overview frontmatter's `verify:` mapping is
  missing `command:`. Assert `rc == 0` and the JSON output is `{"status": "success", "baseline":
  "error", "reason": ...}` (containing the `parse_verify_field` `ValueError` message) rather than an
  unhandled exception propagating.
