# Batch: implement-baseline-stage

```yaml
task: 'compute_baseline: use the task worktree''s own pre-edit state, not a parent-branch checkout'
batch: implement-baseline-stage
number: 3
cards: 9
verify: PYTHONPATH= uv run --project plugins/mill python plugins/mill/unit_tests/run-all.py --only test-millpy-implement.py
depends-on: [1, 2]
```

## Batch Scope

This batch is the heart of the task: it turns `--stage baseline` from "module-wide capture plus a cheap `baseline_parent_sha` pin" into "module-wide capture plus an eager, in-worktree, per-batch capture," per Decision `two-half-stage-ownership`/`eager-not-lazy`/`capture-set-equals-gate-set`/`per-batch-capture-driver`/`module-wide-verdict-source`/`preflight-precondition-guard`/`preflight-dirt-warning`. It depends on batch 1 (the new `_status.get/set_module_verify_baseline_signatures` accessors it persists through) and batch 2 (the new `compute_baseline(cwd, cmd, ...)` / `compute_batch_baselines(commands, cwd, ...)` signatures it calls). This batch also removes the `pipeline.baseline_prepare_cmd` config key from both the hub config and the template, in the same batch that deletes the key's last reader — see the overview's `mid-flight-config-key-removal-is-safe` Shared Decision.

## Cards

### Card 11: Add the preflight-precondition-guard helper

- **Context:**
  - `plugins/mill/scripts/_parent_branch.py`
  - `plugins/mill/scripts/_subprocess_util.py`
- **Edits:**
  - `plugins/mill/scripts/millpy-implement.py`
- **Creates:** none
- **Deletes:** none
- **Moves:** none
- **Requirements:** Add a new module-level function, e.g. `_baseline_preflight_skip_reason(project_root: Path, git_root: Path, status_path: Path) -> str | None`, implementing Decision `preflight-precondition-guard`'s gating condition. Resolve `<parent>` via `_parent_branch.resolve(status_path, interactive=False)`; on any exception, return a skip reason string describing the unresolvable parent (do not raise). Run `git -C <git_root> merge-base HEAD <parent>`; a non-zero exit returns a skip reason describing the failed merge-base. Run `git -C <git_root> diff --name-only <merge_base_sha> HEAD` to get the set of changed paths since the merge-base. Compute the exclusion set `{"_mill/", ".millhouse/"}` re-anchored to the hub fragment: `project_root.relative_to(git_root)` (empty string in a flat layout) prepended to each prefix, per Decision `preflight-precondition-guard`'s coordinate-space note. If any changed path falls outside both exclusion prefixes, return a skip reason string ("worktree is not pre-edit"); otherwise return `None` (precondition holds, capture may proceed). This function performs no capture itself and mutates nothing — it is a pure gate, called once per `--stage baseline` invocation, before either half attempts anything. Do NOT check `git status --porcelain` here — a dirty tracked file outside `_mill/`/`.millhouse/` is the ADVISORY case Card 12 covers separately; this gate's only load-bearing check is the merge-base-vs-HEAD diff (whether implementation work has been *committed* to this branch), per the "Why a dirty tree only warns" rationale in `_mill/discussion.md`'s `preflight-precondition-guard` Decision.
- **Commit:** `feat(millpy-implement): add baseline preflight precondition guard`

### Card 12: Add the preflight-dirt-warning helper

- **Context:**
  - `plugins/mill/scripts/_subprocess_util.py`
- **Edits:**
  - `plugins/mill/scripts/millpy-implement.py`
- **Creates:** none
- **Deletes:** none
- **Moves:** none
- **Requirements:** Add two small helpers implementing Decision `preflight-dirt-warning`: one to take a `git -C <git_root> status --porcelain` snapshot (returning the raw modified-tracked-path list, e.g. `_porcelain_snapshot(git_root: Path) -> set[str]`), and one to compare a before/after pair and print an ASCII-only stderr warning naming any path that is newly dirty and falls outside the same hub-fragment-anchored `_mill/`/`.millhouse/` exclusion set Card 11's guard uses (e.g. `_warn_new_dirt(before: set[str], after: set[str], exclusions: tuple[str, str]) -> None`). This warning never blocks, never reverts, and never fails the stage — it is advisory only, reused verbatim by both halves (the module-wide half wraps its own before/after snapshot around its 1-2 verify runs; the per-batch half wraps its own before/after snapshot around the whole per-batch capture loop, per the discussion's "reuses `preflight-precondition-guard`'s exclusion set verbatim... so the two checks cannot drift apart" requirement).
- **Commit:** `feat(millpy-implement): add preflight dirt-warning helper`

### Card 13: Rewrite _run_module_wide_standalone for the new compute_baseline signature

- **Context:**
  - `plugins/mill/scripts/_verify_baseline.py`
  - `plugins/mill/scripts/_status.py`
- **Edits:**
  - `plugins/mill/scripts/millpy-implement.py`
- **Creates:** none
- **Deletes:** none
- **Moves:** none
- **Requirements:** Delete `_relative_cwd_fragment` (its only caller is rewritten below to resolve the absolute cwd directly instead) and `_pin_baseline_parent_sha` (its only caller is removed in Card 15) in full.
  Rewrite `_run_module_wide_standalone`: keep the existing `_module_wide_skip_or_cached_payload` short-circuit unchanged (no module-wide verify configured, or already cached). Otherwise, call Card 11's `_baseline_preflight_skip_reason(project_root, git_root, status_path)`; if it returns a reason, print `{"stage": "baseline", "substage": "module_wide", "result": "skipped", "reason": <reason>}` and return (this half's own tagged skip line, per Decision `preflight-precondition-guard`). Otherwise resolve `effective_cwd = module_wide_cwd_override if module_wide_cwd_override is not None else git_root` (mirroring `_run_verify_gate`'s own resolution exactly, per the "`git_root` vs `project_root`" gotcha in `_mill/discussion.md`). Take a before-porcelain snapshot (Card 12), call `_verify_baseline.compute_baseline(effective_cwd, module_wide_verify_cmd, timeout_seconds=verify_timeout_seconds)`, take an after-porcelain snapshot and warn on new dirt (Card 12). Unpack `(result, signatures)`; persist both via `_status.set_module_verify_baseline(status_path, result)` and `_status.set_module_verify_baseline_signatures(status_path, signatures)`; print `{"stage": "baseline", "substage": "module_wide", "result": "computed", "value": result}` (unchanged shape — `signatures` is persisted to status.md, not added to this printed line). Keep the existing `except Exception` -> `{"result": "error", "reason": str(e)}` fallback around the `compute_baseline` call, but drop the now-obsolete `parent_branch = _parent_branch.resolve(...)` block above it — the preflight guard already resolved (and validated) the parent internally; this function no longer needs its own separate resolution.
- **Commit:** `refactor(millpy-implement): module-wide baseline capture uses new compute_baseline signature and preflight guard`

### Card 14: Add the eager per-batch capture function

- **Context:**
  - `plugins/mill/scripts/_plan_dag.py`
  - `plugins/mill/scripts/_verify_baseline.py`
  - `plugins/mill/scripts/_status.py`
- **Edits:**
  - `plugins/mill/scripts/millpy-implement.py`
- **Creates:** none
- **Deletes:** none
- **Moves:** none
- **Requirements:** Add a new function, e.g. `_run_per_batch_baseline_standalone(project_root: Path, git_root: Path, status_path: Path, plan_base: Path, timeout_seconds: float | None, module_wide_pair_seed: tuple[str, Path, list[str]] | None) -> None`, implementing the per-batch half of Decision `two-half-stage-ownership` plus `capture-set-equals-gate-set`, `per-batch-capture-driver`, `module-wide-verdict-source`'s seeding, and the key-presence idempotence rule. `module_wide_pair_seed`, when not `None`, is `(module_wide_verify_cmd, effective_cwd, signatures)` from a module-wide half that computed a fresh result *this same invocation* (used to seed `pair_cache` below); `None` when the module-wide half was skipped, errored, or already cached.
  Step 1 (deferred detection): call `_status.read_batches(status_path)`; if the list is empty (`## Batches` section absent or empty), print `{"stage": "baseline", "substage": "per_batch", "result": "deferred", "reason": "## Batches not yet seeded"}` and return — do not call Card 11's preflight guard at all in this branch (there is nothing to gate yet).
  Step 2 (preflight): call Card 11's `_baseline_preflight_skip_reason`; if it returns a reason, print `{"stage": "baseline", "substage": "per_batch", "result": "skipped", "reason": <reason>}` and return.
  Step 3 (raw enumeration, per Decision `capture-set-equals-gate-set`): read `00-overview.md`'s text from `plan_base / "00-overview.md"`; call `_plan_dag.extract_batch_index(overview_text)` inside a `try`/`except _plan_dag.PlanDAGError`, degrading to an empty batch list (never raising) on a malformed-but-present overview — the speculative early launch may fire against a plan that has not been validated yet. For each batch entry, resolve `plan_base / entry["file"]`, call `_plan_dag._read_batch_frontmatter(batch_path)`, then `_plan_dag.parse_verify_field(frontmatter, project_root, git_root)` inside its own per-batch `try`/`except ValueError`, skipping that one batch (not the whole enumeration) on a malformed `verify:` mapping. Skip a batch whose resolved command is `None` (no runnable verify). Do NOT use `_plan_dag.iter_batch_verifies` — it applies a later-batch-deletion suppression filter that is meaningless at pre-flight time and would silently produce a capture set smaller than the gate set.
  Step 4 (idempotence by key presence): read `_status.read_batches(status_path)` fresh; build the set of batch names whose entry already has the `verify_baseline_failures` **key present** (regardless of truthiness — an empty list `[]` counts as already-captured, since a green batch's own baseline is legitimately `[]`). Drop those batch names from the enumeration in step 3; if nothing remains, print `{"stage": "baseline", "substage": "per_batch", "result": "cached", "value": None}` and return.
  Step 5 (seeding, per Decision `module-wide-verdict-source`): build a `pair_cache: dict[tuple[str, Path], list[str]] = {}`; when `module_wide_pair_seed` is not `None`, seed `pair_cache[(module_wide_verify_cmd, effective_cwd)] = signatures` before driving any batch, so a batch whose own `(command, cwd)` matches the module-wide pair string-for-string reuses that result instead of re-running the suite.
  Step 6 (per-batch driver, per Decision `per-batch-capture-driver`): drive `_verify_baseline.compute_batch_baselines` **one batch per call** (not the whole remaining list in one call), each inside its own `try`/`except`, threading the same `pair_cache` across every call. On success, persist immediately via `_status.set_batch_field(status_path, name, "verify_baseline_failures", result)`. On any exception (including `subprocess.TimeoutExpired`), leave that one batch's field unset and continue to the next batch — do not let one hung/failing batch abort the rest.
  Wrap the whole per-batch driver loop (step 6) in Card 12's before/after porcelain dirt-warning snapshot.
  Report the outcome: `{"stage": "baseline", "substage": "per_batch", "result": "computed", "value": <count captured this invocation>}` when at least one batch was captured, `{"result": "cached", ...}` when step 4 found nothing left to do, `{"result": "skipped", ...}` from step 2, `{"result": "deferred", ...}` from step 1. Never `{"result": "error", ...}` at this function's own top level — an individual batch's own failure is swallowed per step 6, not surfaced as a whole-half error (an enumeration-level `PlanDAGError`/missing-overview is degraded to an empty list in step 3, never raised past this function).
- **Commit:** `feat(millpy-implement): add eager per-batch baseline capture`

### Card 15: Rewrite _run_baseline_stage to drive both halves

- **Context:** none
- **Edits:**
  - `plugins/mill/scripts/millpy-implement.py`
- **Creates:** none
- **Deletes:** none
- **Moves:** none
- **Requirements:** Rewrite `_run_baseline_stage`: delete the `baseline_prepare_cmd: str | None` parameter entirely (its only use today is `del plan_base, baseline_prepare_cmd  # unused`). `plan_base: Path` remains a parameter but becomes genuinely used: pass it through to Card 14's `_run_per_batch_baseline_standalone`. Call `_run_module_wide_standalone(...)` (Card 13) first; capture whatever it would need to pass as Card 14's `module_wide_pair_seed` — since `_run_module_wide_standalone` prints its own JSON line rather than returning a value, either (a) have `_run_module_wide_standalone` return the `(module_wide_verify_cmd, effective_cwd, signatures)` seed tuple (or `None`) in addition to printing its line, and thread that return value into `_run_baseline_stage` here, or (b) recompute the same `effective_cwd` resolution redundantly in `_run_baseline_stage` and read the just-persisted `module_verify_baseline_signatures` back from status.md only when `_run_module_wide_standalone` actually computed (not cached/skipped/errored) this invocation. Prefer (a) — a direct return value is simpler and avoids a redundant status.md read. Then call `_run_per_batch_baseline_standalone(project_root, git_root, status_path, plan_base, verify_timeout_seconds, <seed from above>)` (Card 14). Keep the function's "never raises, always returns 0" contract and its module-level docstring's description of the two independent sub-steps, rewritten to describe the module-wide and per-batch halves instead of the module-wide-plus-`baseline_parent_sha`-pin pair it describes today.
- **Commit:** `refactor(millpy-implement): _run_baseline_stage drives module-wide and per-batch halves`

### Card 16: Update main()'s --stage baseline branch

- **Context:** none
- **Edits:**
  - `plugins/mill/scripts/millpy-implement.py`
- **Creates:** none
- **Deletes:** none
- **Moves:** none
- **Requirements:** In `main()`'s `if args.stage == "baseline":` branch, delete the `baseline_prepare_cmd = pipeline_cfg.get("baseline_prepare_cmd")` line and drop the corresponding positional argument from the `_run_baseline_stage(...)` call (the signature no longer accepts it, per Card 15).
- **Commit:** `refactor(millpy-implement): drop baseline_prepare_cmd from --stage baseline call site`

### Card 17: Remove pipeline.baseline_prepare_cmd from the hub config

- **Context:** none
- **Edits:**
  - `mill-config.yaml`
- **Creates:** none
- **Deletes:** none
- **Moves:** none
- **Requirements:** Delete the `pipeline.baseline_prepare_cmd: null  # ...` key entirely from the hub `mill-config.yaml`. Rewrite `pipeline.baseline_verify_timeout_minutes`'s trailing comment, which currently enumerates the commands it ceilings as "(module-wide, per-batch, `baseline_prepare_cmd`)" — drop the `baseline_prepare_cmd` mention (e.g. "(module-wide, per-batch)"). This key's last reader (`millpy-implement.py`'s `main()` and `_run_baseline_stage`) was removed earlier in this same batch (Cards 15-16), satisfying the `wiki-config-mutation` validator's bootstrap-card condition — see the overview's `mid-flight-config-key-removal-is-safe` Shared Decision.
- **Commit:** `chore(mill-config): drop baseline_prepare_cmd (checkout mechanism removed)`

### Card 18: Remove pipeline.baseline_prepare_cmd from the config template

- **Context:** none
- **Edits:**
  - `plugins/mill/templates/mill-config.yaml`
- **Creates:** none
- **Deletes:** none
- **Moves:** none
- **Requirements:** Apply the identical two edits as Card 17 (delete the `pipeline.baseline_prepare_cmd` key; rewrite the `pipeline.baseline_verify_timeout_minutes` trailing comment to drop the `baseline_prepare_cmd` mention) to `plugins/mill/templates/mill-config.yaml`, keeping the hub config and the template in sync per CLAUDE.md's `## Conventions` "`mill-config.yaml` hub file and plugin template must stay in sync" rule.
- **Commit:** `chore(mill-config template): drop baseline_prepare_cmd (checkout mechanism removed)`

### Card 19: Rewrite test-millpy-implement.py for the eager two-half baseline stage

- **Context:**
  - `plugins/mill/scripts/millpy-implement.py`
  - `plugins/mill/scripts/_verify_baseline.py`
- **Edits:**
  - `plugins/mill/unit_tests/test-millpy-implement.py`
- **Creates:** none
- **Deletes:** none
- **Moves:** none
- **Requirements:** Delete the pin-related tests: `test_baseline_stage_pins_baseline_parent_sha_on_fresh_status`, `test_baseline_stage_pin_is_idempotent_across_calls`, `test_baseline_stage_pin_failed_rev_parse_leaves_field_unset` (exercise the deleted `_pin_baseline_parent_sha`). Delete the `cwd_override_relative`-shape tests: `test_baseline_stage_cwd_hub_derives_relative_fragment_for_compute_baseline`, `test_baseline_stage_cwd_git_root_passes_none_relative_fragment`, `test_baseline_stage_plain_string_verify_passes_none_relative_fragment` (exercise the deleted `_relative_cwd_fragment`) — replace with equivalent coverage asserting `compute_baseline` is called with the correctly-resolved absolute `cwd` (hub root, git root, or the flat-layout default) directly, no fragment kwarg.
  Update every `compute_baseline` mock in this file from `return_value="clean"` (bare string) to `return_value=("clean", [])` (tuple), and update call-argument assertions to the new `(cwd, module_wide_verify_cmd)` positional shape (no more `project_root`, `git_root`, `parent_branch`, `cwd_override_relative`).
  Rewrite `test_baseline_stage_prints_exactly_one_json_line` (using the existing `_write_two_batch_fixture` helper) to assert TWO tagged JSON lines are printed — one `{"substage": "module_wide", ...}` and one `{"substage": "per_batch", ...}` — selecting each by its `substage` key rather than by line position.
  Delete `test_baseline_stage_module_wide_only_kwarg_no_longer_exists` and `test_baseline_stage_module_wide_only_cli_flag_no_longer_exists` only if they now fail against the rewritten `_run_baseline_stage`/CLI surface; otherwise leave them (they guard an already-removed, unrelated `module_wide_only` kwarg/flag and are not touched by this batch).
  Add new tests: (a) two-half-stage-ownership — with no `## Batches` section in `status.md`, `--stage baseline` still captures the module-wide baseline, runs zero batch verify commands, raises nothing, and reports the per-batch half as `"deferred"`; a second invocation after `_status.init_batches` reports module-wide `"cached"` and captures every batch for real. (b) per-batch-capture-driver — with three batches where the second's resolved command raises `subprocess.TimeoutExpired` (via a fake `_run_verify_in`), batches one and three are captured and persisted and only the second is left unset. (c) capture-set-equals-gate-set — a plan where batch A's `verify:` references a path batch B declares it deletes must still capture a baseline for A (the regression guard against reintroducing `iter_batch_verifies`'s suppression filter here). (d) key-presence-vs-truthiness idempotence — a batch whose captured baseline is `[]` is not re-run on a second invocation. (e) module-wide-verdict-source seeding — a batch whose `verify:` string and cwd match the module-wide command runs once, not twice, and receives the module-wide run's signature set, asserted across two separate `--stage baseline` invocations (module-wide captured in the first, batch captured in the second), since that split (not a same-invocation in-process cache) is the default path once the speculative early launch is in play. (f) `preflight-precondition-guard` — four cases: a source file differing between `merge-base` and `HEAD` skips both halves with a `result: "skipped"` line per half; an unresolvable parent branch or non-zero `merge-base` does the same; a dirty *tracked* source file with a clean `merge-base`-vs-`HEAD` diff still captures normally and emits Card 12's warning; a tree where only `_mill/`/`.millhouse/` differ captures normally with no warning. Also assert a skip leaves an already-cached `module_verify_baseline` value intact rather than clearing it. (g) `preflight-dirt-warning` — a verify command that touches a tracked file produces the warning naming that path and still returns the correct result; one that touches only `_mill/` produces no warning.
  Assert `baseline_parent_sha` is never written (via `_status.get_baseline_parent_sha` — note: this accessor is deleted in batch 1, so express this assertion via a direct read of `status.md`'s top yaml block instead, e.g. `"baseline_parent_sha" not in yaml.safe_load(...)`).
- **Commit:** `test(millpy-implement): rewrite baseline stage coverage for eager two-half capture`

## Batch Tests

`verify:` runs `test-millpy-implement.py` alone via `run-all.py --only` — it is the sole test file this batch's cards edit, and it directly exercises every function this batch adds, rewrites, or deletes in `millpy-implement.py`. The two config-file edits (Cards 17-18) have no runnable test surface of their own; their correctness is verified structurally by Card 16 removing the config key's last reader in the same batch.
