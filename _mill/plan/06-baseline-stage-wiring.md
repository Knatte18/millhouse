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
- **Requirements:** Restructure `_run_baseline_stage` (`millpy-implement.py:78-162`) so the module-wide and per-batch computations share exactly one transient checkout whenever BOTH need computing in the same invocation (per the overview's "one shared parent-branch checkout for module-wide and every per-batch verify command" Shared Decision, and `_mill/discussion.md`'s `gap2-checkout-teardown-extraction` Decision, which states the orchestrator "does NOT call `compute_baseline` (that would re-checkout) — it calls `_checkout_parent_branch` ONCE ... then `_run_module_wide_verify_algorithm` directly").
  1. Add a new `plan_base: Path` parameter to `_run_baseline_stage`'s signature (threaded from `main()`, which already resolves `plan_base = _paths.resolve_task_path(project_root, plan_dir)` at line 346, before the `--stage baseline` branch at line 369). Enumerate batches by calling `_plan_dag._read_batch_frontmatter(batch_path)` + `_plan_dag.parse_verify_field(frontmatter, project_root, git_root)` directly over `sorted(plan_base.glob("??-*.md"))`, excluding `00-overview.md` — NOT `_plan_dag.iter_batch_verifies` (see `_mill/discussion.md`'s `gap2-enumerate-batches-directly-not-via-iter-batch-verifies` Decision). Skip any batch whose resolved verify command is `None`. Read `_status.read_batches(status_path)` and build `batches_needing_computation`: every remaining batch whose entry does NOT already have `verify_baseline_failures` set (the ONLY per-batch idempotency gate — never gated by the module-wide command's presence or cache state, per `_mill/discussion.md`'s `gap2-baseline-stage-independent-of-module-wide-early-returns` Decision). Compute `module_wide_needs_computation = module_wide_verify_cmd is not None and _status.get_module_verify_baseline(status_path) is None`.
  2. **Case A — `batches_needing_computation` is empty:** run the module-wide sub-step exactly as the EXISTING logic does today (lines 114-161 UNCHANGED, including both its early returns and its own standalone `compute_baseline` call when it needs to compute) — no shared checkout is created, since there is nothing to share it with. Print its existing JSON line with a `"substage": "module_wide"` key added (identical shape otherwise). Print the per-batch JSON line as `{"stage": "baseline", "substage": "per_batch", "computed": [], "cached": [<every enumerated batch that already had a baseline>], "errored": {}}`.
  3. **Case B — `batches_needing_computation` is non-empty (regardless of whether module-wide also needs computing):** resolve `parent_branch` via `_parent_branch.resolve(status_path, interactive=False)` in its own try/except (on failure, print an error JSON line for EACH substage using the same reason string and return 0 — no checkout is attempted). On success, wrap the ONE-TIME shared setup — `_verify_baseline._checkout_parent_branch(project_root, git_root, parent_branch)` once, then `_verify_baseline._link_dependency_dirs` once per distinct resolved cwd fragment actually present among `batches_needing_computation` PLUS the module-wide command's cwd when `module_wide_needs_computation` is also true (at most two fragments: the checkout path itself for a `cwd: git_root`/plain-string command, and `checkout_path / project_root.relative_to(git_root)` for a `cwd: hub` command) — in ONE try/except around this shared setup: on failure, print `"result": "error"` for the module-wide line (if `module_wide_needs_computation`, else print its normal not-configured/cached line as today) and record EVERY batch in `batches_needing_computation` under the per-batch JSON line's `"errored"` dict with the same reason string (e.g. `f"checkout failed: {e}"`); persist nothing this invocation; return 0. When the shared setup succeeds, wrap the remainder in `try/finally` with `_worktree.remove_safe` teardown of the shared checkout in the `finally` block, then: (a) if `module_wide_needs_computation`, call `_run_module_wide_verify_algorithm(module_wide_verify_cmd, effective_tmp_path, project_root)` directly (bypassing `compute_baseline` entirely — its own try/except, mirroring today's lines 147-158, so a module-wide-specific failure does not abort the per-batch computation below), persist via `_status.set_module_verify_baseline` on success, and print its JSON line (`"substage": "module_wide"`, `"result": "computed"` or `"error"`); if `module_wide_needs_computation` is false, print the module-wide line using the existing not-configured/cached values exactly as today (this batch's checkout still exists for the per-batch work below, but the module-wide line's content is unaffected by it); (b) call `_verify_baseline.compute_batch_baselines` for the `(name, command, cwd)` triples in `batches_needing_computation` against the shared checkout, wrapping EACH batch's own entry in its own try/except (mirroring the module-wide sub-step's existing try/except pattern): on a per-batch exception, record `{name: reason}` in `"errored"`, leave that batch's `verify_baseline_failures` UNSET on `status.md` (fail-safe to strict per-batch verify behavior), and continue to the next batch; on success, persist each computed batch's signature list via `_status.set_batch_field(status_path, name, "verify_baseline_failures", failures)`. Print the per-batch JSON line: `{"stage": "baseline", "substage": "per_batch", "computed": [...], "cached": [<batches that already had a baseline, if any>], "errored": {...}}`.
  4. `_run_baseline_stage` must never raise, matching its existing contract. Update the call site in `main()` (`millpy-implement.py:369-372`) to pass `plan_base` as the new argument.
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
- **Requirements:** Following this file's existing class-based test style and `_run_baseline_stage` mocking convention (see `test_baseline_stage_cwd_hub_derives_relative_fragment_for_compute_baseline` and its siblings around `test-millpy-implement.py:1148-1267`), add tests covering: (a) exactly two JSON lines are printed per invocation, `substage: "module_wide"` first then `substage: "per_batch"`, and the module-wide line's shape is unchanged from today's single-line contract aside from the added `substage` key; (b) idempotency — a fixture plan with batch A already having `verify_baseline_failures` set in `status.md` and batch B not: confirm batch A's verify command is not re-run (its stored value is unchanged) while batch B's is computed and appears in `"computed"`, not `"cached"`, and batch A appears in `"cached"`; (c) per-batch failure isolation — mock one batch's computation to raise: confirm sibling batches still get computed and persisted, the module-wide sub-step is unaffected, the failing batch appears in `"errored"`, and its `verify_baseline_failures` stays unset; (d) shared-checkout failure isolation, two sub-cases: (d1) a fixture with per-batch work needed but NO module-wide computation needed this round (module-wide already cached, or not configured) — mock `_verify_baseline._checkout_parent_branch` to raise: confirm ALL batches needing computation appear in `"errored"` (none partially succeed) and the module-wide JSON line reports its unaffected cached/not-configured value exactly as it would without the failure; (d2) a fixture with BOTH module-wide and per-batch work needed this round — mock the same failure: confirm the module-wide JSON line ALSO reports `"result": "error"` this round (since it was going to share the same now-failed checkout), consistent with the rewritten Card 20 design where module-wide is only unaffected by a shared-checkout failure when it did not need computing in the first place; (e) direct-frontmatter enumeration — a fixture plan where a later batch's `Deletes:` references a path an earlier batch's own `verify:` command names: confirm the earlier batch STILL gets a baseline computed (unlike what `_plan_dag.iter_batch_verifies` would return for DAG-wide replay, which would suppress it).
- **Commit:** `test(millpy-implement): cover per-batch baseline stage restructure`

## Batch Tests

`verify:` runs `run-all.py --only test-millpy-implement.py`, the sole test file covering `millpy-implement.py`'s `_run_baseline_stage` and its finalize/full stage call sites this batch modifies.
