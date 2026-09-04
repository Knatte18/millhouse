# Batch: forward-verify-baselines-millpy-fix

```yaml
task: 'millpy-implement/fix.py: stuck-type false positives and session-hygiene gaps'
batch: forward-verify-baselines-millpy-fix
number: 3
cards: 2
verify: PYTHONPATH= uv run --project plugins/mill python plugins/mill/unit_tests/test-fix-finalize.py
depends-on: [1]
```

## Batch Scope

Fixes #916: `millpy-fix.py --stage finalize` never forwards `batch_verify_baseline`/`module_verify_baseline`/`batch_name` to `finalize_from_output`, for either `--scope batch` or `--scope holistic` — unlike `millpy-implement.py`'s finalize branch, which already forwards all three. This means a holistic (or batch-scope) fixer round's live verify replay always runs strict, with no subset-diff waiver for pre-existing/unrelated failures, producing false `stuck_type: verify`/`logic` classifications. This batch adds the missing forwarding to both scopes (the finalize branch is one shared code path for both), plus the `module_wide_verify_cmd`/`module_wide_cwd_override` derivation `millpy-fix.py` never had at all — without it, forwarding `module_verify_baseline` alone is inert, since `_run_verify_gates` short-circuits the module-wide gate whenever `module_wide_verify_cmd is None`. Depends on batch 1 because it edits the same `finalize_from_output(...)` call site batch 1's Card 4 already added `git_name`/`git_email` to.

## Cards

### Card 6: `millpy-fix.py` — forward verify baselines and module-wide verify command for both scopes

- **Context:**
  - `plugins/mill/scripts/_plan_dag.py`
  - `plugins/mill/scripts/_implementer_common.py`
  - `plugins/mill/scripts/_status.py`
- **Edits:**
  - `plugins/mill/scripts/millpy-fix.py`
- **Creates:** none
- **Deletes:** none
- **Moves:** none
- **Requirements:**
  Inside the `if args.stage == "finalize":` block, before the existing `verify_cmd = None` / `cwd_override = None` initialization and the `if args.scope == "batch": ... elif args.scope == "holistic": ...` branch, add the module-wide verify derivation `millpy-implement.py`'s `main()` already performs (mirror it exactly, reading from the already-defined local `overview_path` variable):
  ```python
        overview_frontmatter = _plan_dag._read_batch_frontmatter(overview_path)
        module_wide_verify_cmd, module_wide_cwd_override = _plan_dag.parse_verify_field(
            overview_frontmatter, project_root, git_root
        )
        module_verify_baseline = _status.get_module_verify_baseline(status_path)
  ```
  `_status.get_module_verify_baseline` is the same function `millpy-implement.py`'s `main()` already calls for this exact purpose; `_status` is already imported in `millpy-fix.py`.

  Compute `batch_verify_baseline` and `batch_name_for_finalize` per scope, immediately inside the existing `if args.scope == "batch": ... elif args.scope == "holistic": ...` branch (extend each arm, do not replace the existing `verify_cmd`/`cwd_override` resolution already there):
  - In the `if args.scope == "batch":` arm, after the existing `verify_cmd, cwd_override = _plan_dag.parse_verify_field(...)` call, add: read `batch_status = next((b for b in _status.read_batches(status_path) if b.get("name") == args.batch_name), None)`, then `batch_verify_baseline = batch_status.get("verify_baseline_failures") if batch_status is not None else None`.
  - In the `elif args.scope == "holistic":` arm, the existing `batch_verifies = _plan_dag.iter_batch_verifies(...)` call already produces the same `(batch_name, verify_cmd, cwd)` triples `_status.read_batches` entries are keyed by. After that call (and after the existing `_report_skipped_verifies(...)` call and the existing `if batch_verifies: verify_cmd, cwd_override = _resolve_holistic_verify(batch_verifies)` block), add:
    ```python
        _all_batches_status = _status.read_batches(status_path)
        _union_baseline: set[str] = set()
        for _bv_name, _bv_cmd, _bv_cwd in batch_verifies:
            _bv_status = next((b for b in _all_batches_status if b.get("name") == _bv_name), None)
            if _bv_status is not None and _bv_status.get("verify_baseline_failures"):
                _union_baseline.update(_bv_status["verify_baseline_failures"])
        batch_verify_baseline = sorted(_union_baseline) if _union_baseline else None
    ```
    (`_bv_cmd`/`_bv_cwd` are unused — the loop only needs `_bv_name` to key the status lookup — but `iter_batch_verifies` returns the full triple, so unpack all three per its documented return shape.) Initialize `batch_verify_baseline = None` before this `elif` arm's body (both arms must define the name unconditionally, since it is read below regardless of scope) — or equivalently give it a shared `batch_verify_baseline = None` initializer alongside the existing `verify_cmd = None` / `cwd_override = None` lines above the `if`/`elif`, and only reassign it inside each arm.

  Finally, extend the existing `return finalize_from_output(...)` call (whose last keyword argument, after batch 1's Card 4, is `git_email=git_email,`) with four more keyword arguments: `module_wide_verify_cmd=module_wide_verify_cmd,`, `module_verify_baseline=module_verify_baseline,`, `batch_verify_baseline=batch_verify_baseline,`, and `batch_name=args.batch_name,` (note: `args.batch_name` is `None` for `--scope holistic` per this file's own argparse validation earlier in `main()` — `finalize_from_output`/`_run_verify_gates` already treat a `None` `batch_name` as "self-healing persist disabled," which is the correct behavior for holistic scope: the per-batch corroboration persist Card 1 added only makes sense keyed to a single batch).
- **Commit:** `fix(fix): forward verify baselines and module-wide verify command to finalize for both scopes`

### Card 7: tests — verify-baseline forwarding for both scopes

- **Context:**
  - `plugins/mill/scripts/millpy-fix.py`
  - `plugins/mill/scripts/_plan_dag.py`
- **Edits:**
  - `plugins/mill/unit_tests/test-fix-finalize.py`
- **Creates:** none
- **Deletes:** none
- **Moves:** none
- **Requirements:**
  Add new test cases to `plugins/mill/unit_tests/test-fix-finalize.py`, following its existing pattern of mocking `finalize_from_output` on the `millpy_fix` module object and asserting on `mock_finalize.call_args`/`call_args.kwargs` after invoking `main(argv)` with `--stage finalize`:
  1. `--scope batch`: with a status.md fixture whose batch entry has a non-empty `verify_baseline_failures` list, assert `finalize_from_output` is called with `batch_verify_baseline` equal to that exact list (not `None`).
  2. `--scope holistic`, two contributing batches whose status entries each have a distinct non-empty `verify_baseline_failures` list: assert `finalize_from_output` is called with `batch_verify_baseline` equal to the sorted union of both lists — not just one batch's.
  3. Either scope: assert `finalize_from_output` is called with `module_wide_verify_cmd` and `module_wide_cwd_override` matching the plan fixture's `00-overview.md` frontmatter `verify:` field (parsed the same way `parse_verify_field` would resolve it), proving the derivation this batch added actually runs and is forwarded — not just that `module_verify_baseline` is passed (which alone would be inert per Card 6's Requirements).
- **Commit:** `test(fix): cover verify-baseline and module-wide-verify forwarding for #916`

## Batch Tests

`verify:` runs `plugins/mill/unit_tests/test-fix-finalize.py` directly, covering every case this batch adds plus the file's existing regression suite for `millpy-fix.py`'s `--stage finalize` branch across both scopes.
