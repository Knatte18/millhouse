# Batch: batch-numbering

```yaml
task: 10 (B) — Plan-template format-forbedringer
batch: batch-numbering
cards: 6
verify: python plugins/mill/unit_tests/test-plan-dag.py && python plugins/mill/unit_tests/test-plan-validate.py
depends-on: []
```

## Batch Scope

This batch adds `number:` as a first-class field on plan batches and switches `depends-on:` from name strings to integers. It adds a public `resolve_deps_as_names()` helper to `_plan_dag.py`, updates `_check_shapes` / `_check_deps` / `_check_acyclic` / `topo_order` to handle both integer and string deps, updates `_plan_validate.py` to use the helper, and updates both templates and SKILL.md to document the new format. Unit tests in `test-plan-dag.py` and `test-plan-validate.py` are updated and extended. No other batch consumes an API introduced here — the new `resolve_deps_as_names` export from `_plan_dag.py` is consumed by `_plan_validate.py` in Card 2.

## Cards

### Card 1: Update `_plan_dag.py` for integer `depends-on` and `number:` field

- **Context:**
  - `plugins/mill/scripts/_plan_dag.py`
- **Edits:**
  - `plugins/mill/scripts/_plan_dag.py`
- **Creates:** none
- **Deletes:** none
- **Requirements:**
  Add a new public function `resolve_deps_as_names(batches: list[dict]) -> dict[str, list[str]]` that maps each batch's `depends-on:` entries to names, translating any integer entry `n` to its corresponding `name` via `{entry["number"]: entry["name"] for entry in batches if "number" in entry}`. String entries pass through unchanged. **Unresolved integer entries (no matching `number:` in any entry) are silently dropped** — `_check_deps` is the authoritative check for dangling deps and emits a clean error there; downstream callers (`_check_acyclic`, `topo_order`, `_compute_transitive_ancestors`) must not crash on data that the validator has already flagged. Place it between `_check_shapes` and `_check_deps`.

  Update `_check_shapes` to:
  1. Track `seen_numbers: set[int] = set()` alongside `seen_names`.
  2. For each entry, after validating `name` and `file`, read `number = entry.get("number")`. If present, assert `isinstance(number, int) and number >= 1`; raise `PlanDAGError(f"Batch {name!r} \`number:\` must be a positive integer, got {number!r}")` if not. Assert uniqueness: `if number in seen_numbers: raise PlanDAGError(f"Duplicate batch number: {number}")`. Add to `seen_numbers`.
  3. For `depends-on:` type check: replace `not all(isinstance(d, str) for d in deps)` with logic that accepts all-int OR all-str, not mixed: `if deps: types = {type(d) for d in deps}; if types - {int, str}: raise ...; if len(types) > 1: raise PlanDAGError(f"Batch {name!r} \`depends-on:\` must not mix int and str entries")`.

  Update `_check_deps` to:
  - Compute `numbers = {entry["number"] for entry in batches if "number" in entry}`.
  - For each `dep` in each batch's `depends-on:`: if `isinstance(dep, int)`, check against `numbers`; raise `PlanDAGError(f"Batch {entry['name']!r} depends on unknown batch number {dep}")` if missing. Self-dep check: `if entry.get("number") == dep: raise PlanDAGError(f"Batch {entry['name']!r} (number {dep}) depends on itself")`. If `isinstance(dep, str)`, keep existing name-based logic unchanged.

  Update `_check_acyclic` to call `resolve_deps_as_names(batches)` and use the returned `deps_by_name` dict instead of directly reading `entry.get("depends-on", [])`. Concretely: replace the two-line loop `for entry in batches: for dep in entry.get("depends-on", []):` with `for name, deps in deps_by_name.items(): for dep in deps:`, and replace `indegree[entry["name"]] += 1` / `adj[dep].append(entry["name"])` with `indegree[name] += 1` / `adj[dep].append(name)`.

  Update `topo_order` similarly: replace the `for entry in batches: for dep in entry.get("depends-on", []):` loop with `deps_by_name = resolve_deps_as_names(batches)` then `for name, deps in deps_by_name.items(): for dep in deps:`. Update `indegree` and `adj` construction accordingly.

  Update module docstring: add `number: NN` as first field in the YAML example block; change `depends-on: [foundation]` to `depends-on: [1]` in the example; add a sentence: "``number:`` (optional positive int) labels the batch for human navigation. ``depends-on:`` accepts a list of integers (referencing ``number:`` values) or strings (referencing ``name:`` values; legacy format). Mixed types in one list are rejected."

- **Commit:** `feat(plan-dag): add number: field + integer depends-on support with backward compat`

### Card 2: Update `_plan_validate.py` for integer `depends-on`

- **Context:**
  - `plugins/mill/scripts/_plan_validate.py`
  - `plugins/mill/scripts/_plan_dag.py`
- **Edits:**
  - `plugins/mill/scripts/_plan_validate.py`
- **Creates:** none
- **Deletes:** none
- **Requirements:**
  Import `resolve_deps_as_names` from `_plan_dag` by adding it to the existing `from _plan_dag import PlanDAGError, extract_batch_index` line: `from _plan_dag import PlanDAGError, extract_batch_index, resolve_deps_as_names`.

  Update `_compute_transitive_ancestors`: replace the dict-comprehension `deps_map: dict[str, list[str]] = {entry["name"]: list(entry.get("depends-on", [])) for entry in batches}` with `deps_map = resolve_deps_as_names(batches)`. The rest of the BFS is unchanged.

  Update `_check_depends_on_unknown`: after computing `known_names`, also compute `known_numbers = {entry["number"] for entry in batches if "number" in entry}`. In the inner loop, change `for dep_name in entry.get("depends-on", []):` to `for dep in entry.get("depends-on", []):`. Check: if `isinstance(dep, int)`, check against `known_numbers`; error message: `f"depends-on references unknown batch number {dep}"`. If `isinstance(dep, str)`, check against `known_names`; error message unchanged (`f"depends-on references unknown batch '{dep}'"`).
- **Commit:** `feat(plan-validate): handle integer depends-on in transitive-ancestors and unknown-dep checks`

### Card 3: Update `plan-overview.md` and `plan-batch.md` templates

- **Context:**
  - `plugins/mill/templates/plan-overview.md`
  - `plugins/mill/templates/plan-batch.md`
- **Edits:**
  - `plugins/mill/templates/plan-overview.md`
  - `plugins/mill/templates/plan-batch.md`
- **Creates:** none
- **Deletes:** none
- **Requirements:**
  In `plan-overview.md`, update the `batches:` example block to add `number: NN` as the first field in each entry and change `depends-on: []` to `depends-on: []` (unchanged for the root) and change the example with a dep to show `depends-on: [NN]` as an integer reference. The final example in the comment should look like:
  ```yaml
  batches:
    - number: NN
      name: <batch-name>
      file: NN-<batch-slug>.md
      depends-on: []
      verify: <command or null>
  ```
  Update the HTML comment at the top to mention `number:`: "Each batch entry has `number:` (the NN integer prefix, for DAG navigation), `name:`, `file:`, `depends-on:` (list of integers referencing other batch `number:` values), and `verify:`."

  In `plan-batch.md`, add `number: NN` as the third line of the frontmatter block (after `batch: <BATCH_NAME>`, before `cards: 0`). Add a note in the HTML comment: "Replace `NN` in `number: NN` with the integer from the batch filename (e.g., `02-field-rename.md` → `number: 2`)."

- **Commit:** `feat(templates): add number: field to plan-overview and plan-batch templates`

### Card 4: Update `mill-plan/SKILL.md` for batch numbering

- **Context:**
  - `plugins/mill/skills/mill-plan/SKILL.md`
- **Edits:**
  - `plugins/mill/skills/mill-plan/SKILL.md`
- **Creates:** none
- **Deletes:** none
- **Requirements:**
  In Phase: Plan, step 2 ("Fill the Batch Index DAG..."), add: "Set `number:` for each entry to the NN integer from the batch filename. Write `depends-on:` as a list of integers (e.g., `depends-on: [1]` meaning this batch depends on batch number 1). Leave `depends-on: []` for root batches."

  In Phase: Plan, step 3 ("For each batch, render `plan-batch.md`..."), add: "Set `number: NN` in the rendered frontmatter to the batch's integer (same as the filename prefix)."

  In the validator mechanical-fix table, update the `depends-on-unknown` row to cover both formats (since legacy string deps remain valid): "If the unknown dep is an integer, compare it against the `number:` values in the Batch Index — if close to an existing number (likely a typo), correct it. If the unknown dep is a string (legacy format), compare it against the `name:` values — if it is a typo of an existing entry, correct it. If the dependency genuinely needs a new batch, halt — adding a batch is not a mechanical fix."

- **Commit:** `docs(mill-plan): add batch number: field and integer depends-on authoring instructions`

### Card 5: Update `test-plan-dag.py` with number-based tests

- **Context:**
  - `plugins/mill/unit_tests/test-plan-dag.py`
  - `plugins/mill/scripts/_plan_dag.py`
- **Edits:**
  - `plugins/mill/unit_tests/test-plan-dag.py`
- **Creates:** none
- **Deletes:** none
- **Requirements:**
  Update `test_good_plan_accepted`: add `number:` fields (1, 2, 3, 4) to the four batch entries and change `depends-on: [a]` / `depends-on: [b, c]` etc. to integer deps (`depends-on: [1]`, `depends-on: [1]`, `depends-on: [2, 3]`) to make it a canonical good-plan-with-numbers test. Update the `validate(batches, [...])` call to still pass.

  Add `test_good_plan_with_numbers_accepted`: two batches, batch 2 depends on batch 1 (integer dep). Assert `validate` passes and `topo_order` returns `["a", "b"]`.

  Add `test_number_dep_unknown_rejected`: one batch with `number: 1`, `depends-on: [99]`. Assert `PlanDAGError` with "unknown batch number 99".

  Add `test_number_dep_duplicate_rejected`: two batches both with `number: 1`. Assert `PlanDAGError` with "Duplicate batch number".

  Add `test_mixed_dep_type_rejected`: one batch with `depends-on: [1, "other"]`. Assert `PlanDAGError` with "mix".

  Add `test_old_name_deps_still_valid`: two batches without `number:` field, `depends-on: [a]`. Assert `validate` passes (backward compat).

  Update `main()` to call all new test functions. Add each to the try block.

- **Commit:** `test(plan-dag): add number-field and integer-depends-on tests`

### Card 6: Update `test-plan-validate.py` for integer depends-on

- **Context:**
  - `plugins/mill/unit_tests/test-plan-validate.py`
  - `plugins/mill/scripts/_plan_validate.py`
- **Edits:**
  - `plugins/mill/unit_tests/test-plan-validate.py`
- **Creates:** none
- **Deletes:** none
- **Requirements:**
  Update `_make_overview` helper (lines ~39-65 in the file): add an optional `number:` key to each batch dict parameter. When a `number` key is present in the dict, emit `    number: {number}\n` as the first field under each batch entry in the YAML block. The helper signature stays unchanged — it already accepts dicts with arbitrary keys; just emit `number:` when present.

  Update `deps_yaml` construction (currently line 45: `deps_yaml = "[" + ", ".join(f'"{d}"' for d in deps) + "]"`) so integer deps emit unquoted: `deps_yaml = "[" + ", ".join(str(d) if isinstance(d, int) else f'"{d}"' for d in deps) + "]"`. This is required so the YAML parses integer deps as integers (`[99]`), not strings (`["99"]`); without it, the integer-dep code path in `_check_depends_on_unknown` is never exercised by tests.

  Update `test_check_depends_on_unknown_dirty`: switch the batch dict to `{"name": "alpha", "file": "01-alpha.md", "number": 1, "depends-on": [99]}` (integer dep 99). Verify the error message contains "99" and `check == "depends-on-unknown"`.

  Add `test_check_depends_on_unknown_dirty_legacy_string`: confirms the old string-dep path still works — provide a batch with `depends-on: ["non-existent-batch"]` (no `number:` field) and assert the error mentions `"non-existent-batch"`. (Name reflects body — body tests legacy string deps, not integer deps.)

  Update `main()` to include all new test functions.

- **Commit:** `test(plan-validate): update depends-on-unknown tests for integer deps`

## Batch Tests

Cards 5 and 6 update and extend the unit test suites directly. The `verify:` command runs both test files: `python plugins/mill/unit_tests/test-plan-dag.py && python plugins/mill/unit_tests/test-plan-validate.py`. All existing tests must pass (backward compat) and all new tests must pass (new format).
