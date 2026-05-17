# Batch: validator-depends-on-cross-check

```yaml
task: 59 (A) -- Small infra fixes batch 8
batch: validator-depends-on-cross-check
number: 2
cards: 1
verify: "C:/Code/millhouse/wts/millhouse/plugins/mill/.venv/Scripts/python.exe plugins/mill/unit_tests/test-plan-validate.py"
depends-on: []
```

## Batch Scope

Adds a new structural check to `_plan_validate`: `depends-on-batch-mismatch`. Verifies that each per-batch file's YAML-frontmatter `depends-on:` matches the overview Batch Index's `depends-on:` for the same batch (#303). Emits a BLOCKING-shape finding when the two sides disagree. Mirrors the per-check structural pattern of the existing `_check_depends_on_unknown` and `_check_parallel_modifies_overlap` functions. Test extension goes in `test-plan-validate.py` and follows the existing fixture pattern.

## Cards

### Card 3: Add `_check_depends_on_batch_mismatch` to `_plan_validate.py`

- **Context:**
  - `plugins/mill/scripts/_plan_dag.py`
- **Edits:**
  - `plugins/mill/scripts/_plan_validate.py`
  - `plugins/mill/unit_tests/test-plan-validate.py`
- **Creates:** none
- **Deletes:** none
- **Requirements:** In `plugins/mill/scripts/_plan_validate.py`, add a new private helper `_check_depends_on_batch_mismatch(batch_files: list[Path], overview_text: str) -> list[dict]` placed below `_check_parallel_modifies_overlap` (current line ~440) and above `# Check 6 -- reads-not-backtick-path` (current line ~501). Behaviour:
  1. Call `extract_batch_index(overview_text)` (already imported at line 35). On `PlanDAGError`, return `[]` -- `_check_depends_on_unknown` already records the parse error; do not double-report.
  2. Build `number_to_name = {entry["number"]: entry["name"] for entry in batches if "number" in entry}` (mirrors `_plan_dag.py:158`).
  3. Build a `batch_name_to_path` dict by matching each `entry["file"]`'s stem against `batch_files` (same shape as the helper at `_check_parallel_modifies_overlap` lines 453-459).
  4. For each entry `b` with a corresponding batch file path, read the batch file via `read_text(encoding="utf-8")`, locate its top fenced-YAML block by reading the substring between the first ``` ```yaml ``` ``` and the next ``` ``` ```, and `yaml.safe_load` it. From the parsed dict, extract `depends-on:` (default to `[]` when absent). Translate ints to names via `number_to_name` lookup; pass strings through unchanged; silently drop unresolved ints (matches `resolve_deps_as_names` behaviour at `_plan_dag.py:170-173`).
  5. Build the overview-side normalisation by calling `resolve_deps_as_names(batches)` (import from `_plan_dag`) -- returns `{batch_name: list[str]}`.
  6. For each batch name present in both `batch_name_to_path` and the overview-resolved map: compare the two `set()`-coerced lists. On mismatch, emit one finding dict: `{"check": "depends-on-batch-mismatch", "batch": b["name"], "card": None, "path": None, "message": f"per-batch file depends-on={sorted(batch_side)} disagrees with overview Batch Index depends-on={sorted(overview_side)}"}`.
  7. Return the list (may be empty).
  `resolve_deps_as_names` is already imported (line 35: `from _plan_dag import PlanDAGError, extract_batch_index, resolve_deps_as_names`); reuse the existing import. Register the new check in `run()` (current line 715) by inserting `errors.extend(_check_depends_on_batch_mismatch(batch_files, overview_text))` between the existing `_check_depends_on_unknown` and `_check_parallel_modifies_overlap` lines (current lines 758-759). Add the new check-key to the module's top-level docstring `Checks performed (check keys):` section (line 13) with a one-line description: `    depends-on-batch-mismatch  -- per-batch file's depends-on disagrees with overview Batch Index depends-on for the same batch`. Add an entry for the new check to the fix-table in the mill-plan SKILL.md... no, mill-plan SKILL.md edits live in Batch 5. Skip that here.
  In `plugins/mill/unit_tests/test-plan-validate.py`, add a new test function `test_depends_on_batch_mismatch_emits_finding()`. Inside a `tempfile.TemporaryDirectory`, write a `00-overview.md` whose Batch Index declares two batches with `number: 1, depends-on: []` and `number: 2, depends-on: [1]`, plus a `01-foo.md` with frontmatter `depends-on: []` and `02-bar.md` with frontmatter `depends-on: []` (mismatch: batch 2's overview says `[1]` but its file says `[]`). Call `_plan_validate.run(plan_dir, project_root=plan_dir)` and assert exactly one finding with `check == "depends-on-batch-mismatch"` and `batch == "bar"`. Add a paired negative-case test `test_depends_on_batch_mismatch_no_finding_on_match()` where both sides agree (`[1]` on both); assert zero `depends-on-batch-mismatch` findings. Wire both into the existing test runner.
- **Commit:** `feat(_plan_validate): cross-check per-batch depends-on against overview (#303)`

## Batch Tests

`verify` runs `test-plan-validate.py`. The two new tests must pass; existing tests must continue to pass without modification.
