# Batch: baseline-stage-wiring

```yaml
task: Improve diagnosability of plan-validate errors and finalize verify-replay failures
batch: baseline-stage-wiring
number: 6
cards: 5
verify: PYTHONPATH= uv run --project plugins/mill python plugins/mill/unit_tests/run-all.py --only test-millpy-implement.py
depends-on: [3, 4, 5]
```

## Batch Scope

Wires everything the prior three batches built into `millpy-implement.py`'s actual CLI flow: `_run_baseline_stage` restructures into two independent sub-steps (module-wide unchanged, per-batch new) so per-batch baselines are computed eagerly before batch 1, and both the `--stage finalize` and `--stage full` code paths read each batch's stored baseline from `status.md` and thread it into the verify gate. Also updates `mill-go/SKILL.md`'s baseline pre-flight documentation for the new two-JSON-line output contract. Depends on batch 3 (the `status.md` field), batch 4 (the threading parameter and helpers), and batch 5 (the per-batch computation function and shared-checkout helpers).

## Cards

### Card 20: Restructure `_run_baseline_stage` with an independent per-batch sub-step

- **Context:**
  - `plugins/mill/scripts/_status.py`
  - `plugins/mill/scripts/_verify_baseline.py`
  - `plugins/mill/scripts/_plan_dag.py`
  - `_mill/discussion.md`
- **Edits:**
  - `plugins/mill/scripts/millpy-implement.py`
- **Creates:** none
- **Deletes:** none
- **Moves:** none
- **Requirements:** Restructure `_run_baseline_stage` (`millpy-implement.py:78-162`) into two independent sub-steps that both run on every invocation, regardless of each other's outcome:
  1. **Module-wide sub-step:** the EXISTING logic (lines 114-161) UNCHANGED, including both its early returns (`module_wide_verify_cmd is None` at line 114; already-cached at line 126). Its printed JSON line gains a `"substage": "module_wide"` key alongside its existing `"stage"`/`"result"`/`"value"`/`"reason"` keys — identical shape otherwise to today's single-line contract.
  2. **Per-batch sub-step:** add a new `plan_base: Path` parameter to `_run_baseline_stage`'s signature (threaded from `main()`, which already resolves `plan_base = _paths.resolve_task_path(project_root, plan_dir)` at line 346, before the `--stage baseline` branch at line 369). Enumerate batches by calling `_plan_dag._read_batch_frontmatter(batch_path)` + `_plan_dag.parse_verify_field(frontmatter, project_root, git_root)` directly over `sorted(plan_base.glob("??-*.md"))`, excluding `00-overview.md` — NOT `_plan_dag.iter_batch_verifies` (see `_mill/discussion.md`'s `gap2-enumerate-batches-directly-not-via-iter-batch-verifies` Decision). Skip any batch whose resolved verify command is `None`. Read `_status.read_batches(status_path)` and skip any batch whose entry already has `verify_baseline_failures` set (the ONLY idempotency gate on this sub-step — never gated by the module-wide command's presence or cache state, per `_mill/discussion.md`'s `gap2-baseline-stage-independent-of-module-wide-early-returns` Decision). For the remaining batches needing computation: wrap the ONE-TIME shared setup — `_verify_baseline._checkout_parent_branch(project_root, git_root, parent_branch)` once, then `_verify_baseline._link_dependency_dirs` once per distinct resolved cwd fragment actually present among the module-wide command (if configured) and all enumerated batches needing computation (at most two: the checkout path itself for a `cwd: git_root`/plain-string command, and `checkout_path / project_root.relative_to(git_root)` for a `cwd: hub` command) — in ONE try/except around the whole per-batch sub-step: on failure, record EVERY batch needing computation in the per-batch JSON line's `"errored"` dict with the same reason string (e.g. `f"checkout failed: {e}"`), compute no baselines this invocation, and leave the module-wide sub-step (which performs its own independent checkout via `compute_baseline` when it runs) unaffected. When the shared setup succeeds, call `_verify_baseline.compute_batch_baselines` for the `(name, command, cwd)` triples needing computation, wrapping EACH batch's own entry in its own try/except (mirroring the module-wide sub-step's existing try/except pattern at lines 147-158): on a per-batch exception, record `{name: reason}` in `"errored"`, leave that batch's `verify_baseline_failures` UNSET on `status.md` (fail-safe to strict per-batch verify behavior), and continue to the next batch. On success, persist each computed batch's signature list via `_status.set_batch_field(status_path, name, "verify_baseline_failures", failures)`. Resolve `parent_branch` for this sub-step the same way the module-wide sub-step already does (`_parent_branch.resolve(status_path, interactive=False)`, wrapped in its own try/except with the same error-JSON-and-return-0 fallback). Print a second JSON line: `{"stage": "baseline", "substage": "per_batch", "computed": [...], "cached": [...], "errored": {...}}` where `"computed"` lists batch names successfully computed THIS call, `"cached"` lists batch names skipped because a baseline was already stored, and `"errored"` maps batch name to reason string for any failure (including every batch listed under a shared-setup failure). `_run_baseline_stage` must never raise, matching its existing contract. Update the call site in `main()` (`millpy-implement.py:369-372`) to pass `plan_base` as the new argument.
- **Commit:** `feat(millpy-implement): restructure baseline stage with independent per-batch sub-step`

### Card 21: Thread per-batch baseline into `--stage finalize`

- **Context:** none
- **Edits:**
  - `plugins/mill/scripts/millpy-implement.py`
- **Creates:** none
- **Deletes:** none
- **Moves:** none
- **Requirements:** In the `--stage finalize` branch (`millpy-implement.py:415-455`), after `batch_status` is resolved (lines 419-425), read `batch_verify_baseline = batch_status.get("verify_baseline_failures")` and pass it to the `finalize_from_output(...)` call (lines 439-455) as a new `batch_verify_baseline=batch_verify_baseline` keyword argument.
- **Commit:** `feat(millpy-implement): thread per-batch baseline into finalize stage`

### Card 22: Thread per-batch baseline into `--stage full`

- **Context:** none
- **Edits:**
  - `plugins/mill/scripts/millpy-implement.py`
- **Creates:** none
- **Deletes:** none
- **Moves:** none
- **Requirements:** In the `--stage full` (default) branch, immediately before the `_forward_output(...)` call (`millpy-implement.py:706-722`), read `_status.read_batches(status_path)`, find the entry whose `"name"` matches `args.batch_name` (mirroring the existing lookup pattern already used in the `resume_incomplete` branch at lines 492-495), and extract `batch_verify_baseline = <entry>.get("verify_baseline_failures")` when found, else `None`. Pass it to the `_forward_output(...)` call as a new `batch_verify_baseline=batch_verify_baseline` keyword argument.
- **Commit:** `feat(millpy-implement): thread per-batch baseline into full stage`

### Card 23: Document the two-JSON-line baseline-stage output in mill-go/SKILL.md

- **Context:**
  - `plugins/mill/scripts/millpy-implement.py`
- **Edits:**
  - `plugins/mill/skills/mill-go/SKILL.md`
- **Creates:** none
- **Deletes:** none
- **Moves:** none
- **Requirements:** In "### 0.5. Baseline pre-flight" (`plugins/mill/skills/mill-go/SKILL.md:396-406`), update the step to reflect that `--stage baseline` now prints TWO JSON lines instead of one: the first with `"substage": "module_wide"` (identical shape to today's single-line contract, just tagged — parse and log exactly as today), the second with `"substage": "per_batch"` (carrying `"computed"`/`"cached"`/`"errored"` keys). Change the sentence "Parse the JSON line the CLI prints." to "Parse the two JSON lines the CLI prints — one per substage." and add a short paragraph after the existing "On `{"result": "error", ...}`..." sentence: for the `per_batch` line, log a one-line summary of the `"computed"`/`"cached"`/`"errored"` counts and continue to batch 1 regardless of any `"errored"` entries — this step never blocks the task for either substage, matching the module-wide substage's existing never-block behavior.
- **Commit:** `docs(mill-go): document two-JSON-line baseline stage output`

### Card 24: Tests for the restructured baseline stage

- **Context:**
  - `plugins/mill/scripts/millpy-implement.py`
  - `plugins/mill/scripts/_status.py`
  - `plugins/mill/scripts/_plan_dag.py`
- **Edits:**
  - `plugins/mill/unit_tests/test-millpy-implement.py`
- **Creates:** none
- **Deletes:** none
- **Moves:** none
- **Requirements:** Following this file's existing class-based test style and `_run_baseline_stage` mocking convention (see `test_baseline_stage_cwd_hub_derives_relative_fragment_for_compute_baseline` and its siblings around `test-millpy-implement.py:1148-1267`), add tests covering: (a) exactly two JSON lines are printed per invocation, `substage: "module_wide"` first then `substage: "per_batch"`, and the module-wide line's shape is unchanged from today's single-line contract aside from the added `substage` key; (b) idempotency — a fixture plan with batch A already having `verify_baseline_failures` set in `status.md` and batch B not: confirm batch A's verify command is not re-run (its stored value is unchanged) while batch B's is computed and appears in `"computed"`, not `"cached"`, and batch A appears in `"cached"`; (c) per-batch failure isolation — mock one batch's computation to raise: confirm sibling batches still get computed and persisted, the module-wide sub-step is unaffected, the failing batch appears in `"errored"`, and its `verify_baseline_failures` stays unset; (d) shared-checkout failure isolation — mock `_verify_baseline._checkout_parent_branch` to raise: confirm ALL batches needing computation appear in `"errored"` (none partially succeed) and the module-wide sub-step's own independent checkout (via `compute_baseline`) is unaffected; (e) direct-frontmatter enumeration — a fixture plan where a later batch's `Deletes:` references a path an earlier batch's own `verify:` command names: confirm the earlier batch STILL gets a baseline computed (unlike what `_plan_dag.iter_batch_verifies` would return for DAG-wide replay, which would suppress it).
- **Commit:** `test(millpy-implement): cover per-batch baseline stage restructure`

## Batch Tests

`verify:` runs `run-all.py --only test-millpy-implement.py`, the sole test file covering `millpy-implement.py`'s `_run_baseline_stage` and its finalize/full stage call sites this batch modifies.
