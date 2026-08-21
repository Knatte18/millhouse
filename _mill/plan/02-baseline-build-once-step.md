# Batch: baseline-build-once-step

```yaml
task: "mill-go: baseline-stage timeout/cold-build cost and finalize dirty-tree false positive"
batch: baseline-build-once-step
number: 2
cards: 3
verify: PYTHONPATH= uv run --project plugins/mill python plugins/mill/unit_tests/test-millpy-implement.py
depends-on: []
```

## Batch Scope

Fixes the cold-build-cost half of Bug A (issue #894): `_run_baseline_stage`'s Case B (shared-checkout) path in `plugins/mill/scripts/millpy-implement.py` replays every batch's `verify:` command twice plus the module-wide command up to three times against one shared transient checkout, with no build run up front — a `.NET` (or any compiled-ecosystem) checkout starts stone cold, so the compile cost lands inside the first of several doubled verify commands instead of being paid once. This batch adds an optional, config-driven build-once step (`pipeline.baseline_prepare_cmd`) that runs once per distinct cwd fragment, immediately after the shared checkout's dependency-dir linking and before any verify command executes, reusing the existing `_verify_baseline._run_verify_in` helper directly (no new function). Failure of the prepare command is logged and non-fatal — the stage still completes normally.

## Cards

### Card 3: run `baseline_prepare_cmd` once per cwd fragment before the baseline verify replay

- **Context:**
  - `plugins/mill/scripts/_verify_baseline.py`
- **Edits:**
  - `plugins/mill/scripts/millpy-implement.py`
- **Creates:** none
- **Deletes:** none
- **Moves:** none
- **Requirements:**
  **3a. Signature change.** In `_run_baseline_stage`'s signature (`plugins/mill/scripts/millpy-implement.py:216-223`), add a new parameter after `plan_base: Path,`:

  ```python
      plan_base: Path,
      baseline_prepare_cmd: str | None,
  ) -> int:
  ```

  **3b. Docstring update.** In the same function's docstring `Args:` section (currently ending `plan_base: Directory containing ... per-batch verify commands directly off disk.` immediately before the blank line and `Returns:`), add one new entry after `plan_base`:

  ```
          baseline_prepare_cmd: Optional build-once command (e.g. "dotnet build") to run against the
              shared transient checkout, once per distinct cwd fragment, before any verify command
              executes -- read by the caller from `pipeline.baseline_prepare_cmd` in mill-config.yaml.
              `None` (the default when the key is absent) disables this step entirely, matching
              today's behavior exactly.
  ```

  **3c. Insertion point.** In the same function, locate the one-time shared setup `try`/`except` block (`plugins/mill/scripts/millpy-implement.py:357-389` in the pre-edit file) that checks out the parent branch and links dependency dirs, ending with the `return 0` inside its `except Exception as e:` clause, followed by a blank line and then the second `try:` block that begins `# (a) Module-wide command, if it needs computing this round...`. Insert the following new code in the blank line between those two blocks (after the first `try`/`except` statement ends, before the second `try:` starts):

  ```python
      # Build-once step: run baseline_prepare_cmd (if configured) once per distinct cwd fragment,
      # against the shared checkout, before any verify command executes -- eliminates the cold-build
      # cost otherwise paid inside the first of several doubled verify commands below (#894).
      # Failure here is deliberately non-fatal: it is logged and the verify commands still run,
      # since a real build break will also surface naturally as a verify-command failure signature,
      # which is correct baseline data rather than something to suppress by aborting early.
      if baseline_prepare_cmd:
          for fragment in cwd_fragments:
              target = tmp_path / fragment if fragment is not None else tmp_path
              try:
                  prepare_rc, prepare_output = _verify_baseline._run_verify_in(baseline_prepare_cmd, target)
                  if prepare_rc != 0:
                      print(
                          f"[millpy-implement] baseline_prepare_cmd failed (cwd={target}, exit={prepare_rc}): {prepare_output.strip()}",
                          file=sys.stderr,
                      )
              except Exception as e:
                  print(f"[millpy-implement] baseline_prepare_cmd raised (cwd={target}): {e}", file=sys.stderr)

  ```

  This reuses `_verify_baseline._run_verify_in(command, cwd) -> tuple[int, str]` directly (already imported as `_verify_baseline` in this file) — do not add a new function to `_verify_baseline.py` (see the overview's "reuse `_verify_baseline._run_verify_in` directly, no new function" Shared Decision). `cwd_fragments` and `tmp_path` are both already in scope at this point in the function (computed earlier in Case B).

  **3d. Call site threading.** At the `--stage baseline` call site (`plugins/mill/scripts/millpy-implement.py:644-647`), which currently reads:

  ```python
    if args.stage == "baseline":
        return _run_baseline_stage(
            project_root, git_root, status_path, module_wide_verify_cmd, module_wide_cwd_override, plan_base
        )
  ```

  replace it with:

  ```python
      if args.stage == "baseline":
          baseline_prepare_cmd = (cfg.get("pipeline") or {}).get("baseline_prepare_cmd")
          return _run_baseline_stage(
              project_root, git_root, status_path, module_wide_verify_cmd, module_wide_cwd_override, plan_base, baseline_prepare_cmd
          )
  ```

  `cfg` at this point in `main()` is already the corrected, reloaded config (`cfg = _review_common.load_config(project_root, mill_dir)` at line 569, which runs before this call site) — do not re-load config or add a new `_review_common.load_config` call.
- **Commit:** `feat(implementer): run baseline_prepare_cmd once per cwd fragment before baseline verify replay (#894)`

### Card 4: document `pipeline.baseline_prepare_cmd` in the config template and hub config

- **Context:** none
- **Edits:**
  - `plugins/mill/templates/mill-config.yaml`
  - `mill-config.yaml`
- **Creates:** none
- **Deletes:** none
- **Moves:** none
- **Requirements:**
  This is a `mill-config.yaml` key ADDITION, not a removal/rename or a plan file edit — the `wiki-config-mutation` validator check fires on any batch that edits `mill-config.yaml`. This card is the bootstrap justification the check's fix-table row requires: the new key is read only via `(cfg.get("pipeline") or {}).get("baseline_prepare_cmd")` (Card 3), which returns `None` for any hub whose config does not declare the key — byte-identical to the value read before this key existed. No existing code enumerates `pipeline`'s keys exhaustively or rejects unrecognized keys, so this addition changes behavior for nobody who doesn't explicitly opt in by setting a non-null value. Safe mid-flight.

  In `plugins/mill/templates/mill-config.yaml`, in the `pipeline:` block, add a new line immediately after the existing `done_gate_baseline_preflight: false  # ...` line (currently line 123) and before `max_cards_per_batch: 10  # ...` (currently line 124):

  ```yaml
    baseline_prepare_cmd: null  # Optional build-once command run once per distinct cwd fragment against --stage baseline's shared transient checkout, before any module-wide/per-batch verify command; null = disabled. e.g. "dotnet build" for a .NET solution whose verify: commands otherwise pay a cold-compile cost inside the first of several doubled baseline runs. (#894)
  ```

  In this hub's own `mill-config.yaml`, in its own `pipeline:` block, add the same key with the same comment, immediately after `done_gate_baseline_preflight: false  # ...` — this hub's own `pipeline:` block orders its keys differently from the template (`max_cards_per_batch: 10` precedes `done_gate_baseline_preflight: false` here, the reverse of the template's order), so anchor only on `done_gate_baseline_preflight`, not on position relative to `max_cards_per_batch`; key order within the block has no functional effect. This still matches the CLAUDE.md "`mill-config.yaml` hub file and plugin template must stay in sync" convention (both files gain the key with the same value and comment):

  ```yaml
    baseline_prepare_cmd: null  # Optional build-once command run once per distinct cwd fragment against --stage baseline's shared transient checkout, before any module-wide/per-batch verify command; null = disabled. e.g. "dotnet build" for a .NET solution whose verify: commands otherwise pay a cold-compile cost inside the first of several doubled baseline runs. (#894)
  ```

  Do not change the value of any other existing key in either file.
- **Commit:** `docs(config): document pipeline.baseline_prepare_cmd in template and hub config (#894)`

### Card 5: cover the `baseline_prepare_cmd` build-once step with unit tests

- **Context:**
  - `plugins/mill/scripts/millpy-implement.py`
  - `plugins/mill/scripts/_verify_baseline.py`
- **Edits:**
  - `plugins/mill/unit_tests/test-millpy-implement.py`
- **Creates:** none
- **Deletes:** none
- **Moves:** none
- **Requirements:**
  Add three new test methods to `TestMillpyImplement` in `plugins/mill/unit_tests/test-millpy-implement.py`, inserted immediately after `test_baseline_stage_checkout_failure_teardown_failure_never_raises` ends (its last statement is `self.assertIn("batch-b", per_batch["errored"])`) and before `test_baseline_stage_enumerates_batch_own_verify_despite_later_deletes` begins. Follow this file's existing `unittest.mock.patch.object(...)` context-manager style (see the three tests immediately preceding the insertion point) and its `self._write_two_batch_fixture()` / `self._run_main(["--stage", "baseline"])` helpers exactly as those tests use them.

  **Test `test_baseline_stage_prepare_cmd_runs_once_per_cwd_fragment_before_verify`:**
  1. Call `self._write_two_batch_fixture()` (both batches use plain-string `verify:`, so `cwd_fragments` resolves to the single fragment `{None}`).
  2. Override `self.mock_load_config.return_value = {**self.mock_load_config.return_value, "pipeline": {"baseline_prepare_cmd": "dotnet build"}}`.
  3. Bind `checkout_path = self.tmp_path / "checkout"` and a local `call_order = []` list.
  4. Define `_run_verify_in_side_effect(command, cwd)` that appends `("prepare_cmd", command, cwd)` to `call_order` and returns `(0, "")`.
  5. Define `_compute_batch_baselines_side_effect(commands, checkout_path_arg, project_root)` that appends `("verify", commands[0][0])` to `call_order` and returns `{commands[0][0]: []}`.
  6. Patch, inside one `with (...)` block: `millpy_implement._parent_branch.resolve` (`return_value="main"`); `millpy_implement._verify_baseline._checkout_parent_branch` (`return_value=checkout_path`); `millpy_implement._verify_baseline._link_dependency_dirs` (bare patch); `millpy_implement._worktree.remove_safe` (bare patch); `millpy_implement._verify_baseline._run_verify_in` with `side_effect=_run_verify_in_side_effect`, captured as `mock_run_verify_in`; `millpy_implement._verify_baseline.compute_batch_baselines` with `side_effect=_compute_batch_baselines_side_effect`.
  7. Call `rc, out = self._run_main(["--stage", "baseline"])`.
  8. Assert `rc == 0`.
  9. Assert `mock_run_verify_in.assert_called_once_with("dotnet build", checkout_path)`.
  10. Assert `call_order[0][0] == "prepare_cmd"` (the prepare command ran before either batch's verify).
  11. Assert `("verify", "batch-a") in call_order[1:]` and `("verify", "batch-b") in call_order[1:]`.

  **Test `test_baseline_stage_prepare_cmd_unset_no_prepare_call`:**
  1. Call `self._write_two_batch_fixture()`.
  2. Do NOT override `self.mock_load_config.return_value` — the default fixture config has no `"pipeline"` key at all, matching every real hub before this key is opted into.
  3. Patch (same `with (...)` shape as the test above, omitting the `pipeline` override): `millpy_implement._parent_branch.resolve` (`return_value="main"`); `millpy_implement._verify_baseline._checkout_parent_branch` (`return_value=self.tmp_path / "checkout"`); `millpy_implement._verify_baseline._link_dependency_dirs` (bare patch); `millpy_implement._worktree.remove_safe` (bare patch); `millpy_implement._verify_baseline._run_verify_in` (bare patch, captured as `mock_run_verify_in`); `millpy_implement._verify_baseline.compute_batch_baselines` with `side_effect=lambda commands, checkout_path, project_root: {commands[0][0]: []}`.
  4. Call `rc, out = self._run_main(["--stage", "baseline"])`.
  5. Assert `rc == 0`.
  6. Assert `mock_run_verify_in.assert_not_called()` — this is the behavior-unchanged regression case proving every existing hub without the key is unaffected.

  **Test `test_baseline_stage_prepare_cmd_failure_is_non_fatal`:**
  1. Call `self._write_two_batch_fixture()`.
  2. Override `self.mock_load_config.return_value = {**self.mock_load_config.return_value, "pipeline": {"baseline_prepare_cmd": "dotnet build"}}`.
  3. Patch: `millpy_implement._parent_branch.resolve` (`return_value="main"`); `millpy_implement._verify_baseline._checkout_parent_branch` (`return_value=self.tmp_path / "checkout"`); `millpy_implement._verify_baseline._link_dependency_dirs` (bare patch); `millpy_implement._worktree.remove_safe` (bare patch); `millpy_implement._verify_baseline._run_verify_in` with `return_value=(1, "build failed: missing csproj")`; `millpy_implement._verify_baseline.compute_batch_baselines` with `side_effect=lambda commands, checkout_path, project_root: {commands[0][0]: []}`.
  4. Call `rc, out = self._run_main(["--stage", "baseline"])`.
  5. Assert `rc == 0`.
  6. Parse both JSON lines from `out` (`lines = out.strip().splitlines()`, `self.assertEqual(len(lines), 2)`).
  7. Assert `sorted(json.loads(lines[1])["computed"]) == ["batch-a", "batch-b"]` and `json.loads(lines[1])["errored"] == {}` — the stage completes and persists both batches' baselines normally despite the prepare command's non-zero exit.
- **Commit:** `test(implementer): cover baseline_prepare_cmd build-once step (#894)`

## Batch Tests

`verify:` runs `plugins/mill/unit_tests/test-millpy-implement.py` (`unittest`-based) directly. Card 5's three new tests are the direct TDD-relevant coverage for Card 3's change (once-per-fragment invocation order, unset-key no-op regression, non-fatal failure handling); the file's existing `test_baseline_stage_*` tests (module-wide/per-batch computation, idempotency, failure isolation, teardown-failure safety) serve as the regression guard proving Card 3's insertion does not alter any pre-existing baseline-stage behavior.
