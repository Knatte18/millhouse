# Batch: preflight-attribute-guard

```yaml
task: 'mill-go-base/mill-merge: documented step behavior diverges from underlying script capability'
batch: preflight-attribute-guard
number: 2
cards: 4
verify: PYTHONPATH= uv run --project plugins/mill python plugins/mill/unit_tests/run-all.py --only test-preflight.py
depends-on: []
```

## Batch Scope

Implements #856: `_preflight.missing_helpers`/`check_helpers` gains an optional attribute-level
check (a `"module:attr"` entry form, alongside the existing bare `"module"` form), and
`mill-merge/SKILL.md` Step 4 plus `mill-merge-in/SKILL.md`'s own liveness-check call site each gain
a `_preflight.check_helpers(['_parent_branch:check_liveness'])` guard before their
`_parent_branch.check_liveness(...)` call. One batch because the helper extension (card 1), its
test coverage (card 2), and its two doc call sites (cards 3-4) are one small, self-contained
feature touching files disjoint from both other batches in this plan — no dependency on batch 1 or
batch 3.

External interface this batch establishes: `_preflight.missing_helpers`/`check_helpers` accepting
`"module:attr"` entries. Consumed within this same batch (cards 3-4); no other batch in this plan
uses it.

Batch-local decision (not in Shared Decisions since it's specific to this batch's own helper
extension): per `_mill/discussion.md`'s `#856-attribute-level-guard` Decision, if importing the
named module raises for any reason (not just a missing attribute — e.g. a syntax error in a very
stale cached file), the exception is caught and that module is reported missing too, consistent
with the guard's existing actionable-message intent rather than letting an unrelated import error
surface as an unhandled traceback at the guard call site — see card 1.

## Cards

### Card 6: extend `_preflight.missing_helpers`/`check_helpers` with attribute-level checking

- **Context:** none
- **Edits:**
  - `plugins/mill/scripts/_preflight.py`
- **Creates:** none
- **Deletes:** none
- **Moves:** none
- **Requirements:** In `missing_helpers` (`plugins/mill/scripts/_preflight.py`, currently lines
  25-40), change the per-`name` loop body: split each `name` on the first `:` (via
  `name.split(":", 1)`) into `module_name` and an optional `attr_name` (empty string when no `:` is
  present, meaning "no attribute check" — the existing bare-module-name behavior). First check
  `(scripts_dir / f"{module_name}.py").exists()` exactly as today; if missing, append the original
  `name` (not just `module_name`) to the `missing` list and `continue` to the next entry — unchanged
  behavior for this half. If the file exists and `attr_name` is non-empty, additionally attempt to
  import the module directly from the file path in `scripts_dir` — do NOT use
  `importlib.import_module(module_name)`, since that resolves against `sys.path` and `scripts_dir`
  is a plain function argument that is not guaranteed to be on `sys.path` (it is only the real
  `CLAUDE_PLUGIN_ROOT/scripts` path for `check_helpers`'s own call sites; `missing_helpers` is also
  called directly with arbitrary `scripts_dir` values, e.g. in tests). Instead use
  `importlib.util.spec_from_file_location(module_name, scripts_dir / f"{module_name}.py")`, then
  `importlib.util.module_from_spec(spec)` and `spec.loader.exec_module(module)` (add `import
  importlib.util` to the file's existing `import os` / `import sys` block at the top) — this loads
  the module straight from its file path regardless of `sys.path` contents. Wrap the whole
  spec-load-exec sequence in a `try/except Exception`. If it raises for any reason, append
  `name` to `missing` (per this batch's Batch Scope decision — an import failure is reported as
  "missing" too, not left to propagate). If the import succeeds, check `hasattr(module, attr_name)`;
  if `False`, append `name` to `missing`. Update the function's docstring (currently lines 26-34) to
  document the new `"module:attr"` form alongside the existing `"module"` form, and update
  `check_helpers`'s docstring (currently lines 44-57) with the same clarification since it delegates
  to `missing_helpers`. Add a one-line docstring caveat on `missing_helpers` noting that the
  `"module:attr"` form fully imports (executes the top level of) the target module to check the
  attribute, not just a presence check — a cost worth flagging for any future caller passing a
  heavier module, even though it is harmless for this task's own two call sites (`_parent_branch.py`
  imports only `_subprocess_util` at its top level). Do not change the bare-`"module"`-form code
  path's behavior — a bare module
  name must produce byte-identical results to today (no import, file-existence check only).
- **Commit:** `feat(preflight): support module:attr entries for attribute-level presence checks (#856)`

### Card 7: test the `"module:attr"` form

- **Context:**
  - `plugins/mill/scripts/_preflight.py`
- **Edits:**
  - `plugins/mill/unit_tests/test-preflight.py`
- **Creates:** none
- **Deletes:** none
- **Moves:** none
- **Requirements:** Add tests for the new `"module:attr"` entry form in
  `plugins/mill/unit_tests/test-preflight.py`, placed after the existing
  `test_missing_helpers_all_missing` test (currently lines 55-68), following this file's established
  fixture pattern (`tempfile` scratch dir with hand-written `.py` files — see
  `test_missing_helpers_all_present`/`test_missing_helpers_some_missing` for the exact setup shape).
  Cover: (1) `"module:attr"` where the module file exists and defines `attr` — `missing_helpers`
  returns an empty list for that entry; (2) `"module:attr"` where the module file exists but does
  NOT define `attr` — the entry appears in the returned `missing` list, using the full `"module:attr"`
  string (not just `"module"`); (3) `"module:attr"` where the module file itself raises on import
  (e.g. a syntax error, or any other uncaught exception during import) — the entry appears in
  `missing` rather than the exception propagating out of `missing_helpers`; (4) a bare `"module"`
  entry (no `:`) continues to use file-existence-only checking, unaffected by the new code path —
  reuse/adapt the existing `test_missing_helpers_all_present` fixture to confirm no regression. This
  file currently defines seven pre-existing `test_*` functions, plus whichever new ones this card
  adds per the coverage above, but has **no
  test-invocation entrypoint at all**: no `main()`, no `if __name__ == "__main__"` block, so
  `run-all.py` (which runs each `test-*.py` as a subprocess) currently executes this file as a
  no-op that silently exits 0 without running any test. Add a `main() -> int` function and an `if
  __name__ == "__main__": sys.exit(main())` block at the end of the file, mirroring
  `test-marker.py`'s `main()` (its exact structure: a hard-coded `tests = [...]` list of every
  `test_*` function in this file — all seven pre-existing plus every new one this card adds — a loop
  calling each and catching `AssertionError`/`Exception` into a `failures` list, and a final
  pass/fail summary print with `return 1` on any failure or `return 0` when all pass).
- **Commit:** `test(preflight): cover module:attr entries and import-failure handling (#856)`

### Card 8: guard mill-merge Step 4's liveness check

- **Context:**
  - `plugins/mill/scripts/_preflight.py`
- **Edits:**
  - `plugins/mill/skills/mill-merge/SKILL.md`
- **Creates:** none
- **Deletes:** none
- **Moves:** none
- **Requirements:** In `mill-merge/SKILL.md` Step 4 "Liveness check (#817)" (currently lines
  81-111), immediately before the `_parent_branch.check_liveness('<parent_branch>', git_root)` call
  (currently line 88), add a preflight guard line mirroring Step 5.5's existing precedent (currently
  lines 415-416: `` import _preflight; exit(_preflight.check_helpers(['_archive_tag'])) ``) but
  targeting the attribute this step actually depends on:
  `` import _preflight; exit(_preflight.check_helpers(['_parent_branch:check_liveness'])) ``. Do not
  modify the `check_liveness` call itself or any of the step's subsequent liveness-handling logic —
  this card only adds the guard line immediately before the existing call.
- **Commit:** `docs(mill-merge): add preflight guard before liveness check, mirroring Step 5.5 (#856)`

### Card 9: guard mill-merge-in's liveness check

- **Context:**
  - `plugins/mill/scripts/_preflight.py`
- **Edits:**
  - `plugins/mill/skills/mill-merge-in/SKILL.md`
- **Creates:** none
- **Deletes:** none
- **Moves:** none
- **Requirements:** In `mill-merge-in/SKILL.md` (currently line 21, the `_parent_branch.check_liveness(parent_branch,
  git_root)` call inside its own liveness-check paragraph — not line 23, which is the
  `resolve_dead_parent` call in the dead-parent branch), add the identical preflight guard line used
  in card 8, immediately before this call: `` import _preflight;
  exit(_preflight.check_helpers(['_parent_branch:check_liveness'])) ``. Do not modify the
  `check_liveness` call itself or the surrounding dead-parent-handling logic.
- **Commit:** `docs(mill-merge-in): add preflight guard before liveness check, mirroring mill-merge Step 4 (#856)`

## Batch Tests

`verify:` runs `test-preflight.py` via `run-all.py --only` — the only test file this batch's code
change (card 6) affects. Cards 8-9 edit SKILL.md prose with no automated test harness (mill's
prose-driven orchestration steps are not executable code) — verified manually per each card's
`Requirements:` (guard line placed immediately before the existing `check_liveness` call, matching
Step 5.5's exact placement-before-import pattern).
