# Batch: verify-replay-callers-wiring

```yaml
task: Batch review/verify pipeline doesn't account for cross-batch state changes
batch: verify-replay-callers-wiring
number: 4
cards: 2
verify: PYTHONPATH= uv run --project plugins/mill python plugins/mill/unit_tests/run-all.py --only test-millpy-fix.py
depends-on: [3]
```

## Batch Scope

Wires the `status_path` kwarg from batch `iter-batch-verifies-cross-batch-filter` into both existing `iter_batch_verifies()` callers, and adds the visible, counted skip reporting required by the overview's "visible, counted skips" Shared Decision. Card 5 covers `millpy-fix.py`'s two call sites (holistic finalize and the non-finalize holistic branch); Card 6 covers `mill-merge-in`'s prose-driven Step 4/Step 6. Both cards implement the identical diff-and-reclassify attribution mechanism (recompute the unfiltered raw batch-with-verify set independently, diff it against `iter_batch_verifies()`'s actual return, attribute each missing batch's reason by re-checking approval state first, then target-removal) — this mirroring is intentional per `_mill/discussion.md` Decision 5's note that the mechanism must be the same in both callers, not independently reinvented. This is the final batch in the plan; no further batch depends on it.

## Cards

### Card 5: `millpy-fix.py` — pass `status_path`, add stderr skip attribution

- **Context:**
  - `plugins/mill/scripts/_plan_dag.py`
  - `plugins/mill/scripts/_status.py`
- **Edits:**
  - `plugins/mill/scripts/millpy-fix.py`
  - `plugins/mill/unit_tests/test-millpy-fix.py`
- **Creates:** none
- **Deletes:** none
- **Moves:** none
- **Requirements:** In `plugins/mill/scripts/millpy-fix.py`, both existing calls to `_plan_dag.iter_batch_verifies(plan_base, project_root, git_root)` — the `--stage finalize` holistic branch (around line 332, inside `if args.scope == "holistic":`) and the non-finalize holistic dispatch branch (around line 452, inside the `else:  # args.scope == "holistic"` block) — must pass `status_path=status_path` as an additional keyword argument (`status_path` is already an in-scope local variable at both sites, resolved earlier in `main()` around line 225 via `_paths.require_status_path`). Immediately after each of these two calls, add the diff-and-reclassify skip-attribution logic (a small local helper is fine, e.g. a module-level function `_report_skipped_verifies(plan_base, project_root, git_root, status_path, batch_verifies) -> None` called from both sites to avoid duplicating the logic twice in `main()`): (1) independently compute the raw unfiltered batch-with-verify set by calling `_plan_dag.extract_batch_index()` on the overview text, `_plan_dag.topo_order()` on the result, and for each batch in that order reading its frontmatter via `_plan_dag._read_batch_frontmatter()` and normalizing its `verify:` via `_plan_dag.parse_verify_field()`, collecting the names of every batch whose command is non-`None` — this reproduces exactly what `iter_batch_verifies()` would return with zero filtering; (2) compute `missing = raw_names - {name for name, _cmd, _cwd in batch_verifies}` (`batch_verifies` is the actual, already-filtered return value from the call this diff follows); (3) for each `name` in `missing`, call `_status.read_batches(status_path)` once (reuse the result across all `missing` names, not once per name) to build a `{name: state}` lookup, and attribute the reason: if `states.get(name) != "approved"`, the reason is `"batch not approved"`; otherwise (the batch IS approved but still missing) the reason is `"target removed by later batch"`; (4) print `[millpy-fix] skipped <batch_name>: <reason>` to `sys.stderr` for each attributed `(name, reason)` pair, in the same order as `raw_names`. Wrap the whole helper's `_status.read_batches` call in the same `ValueError`-tolerant handling as `iter_batch_verifies()` itself (Card 4 of the prior batch) — if it raises, skip the attribution/logging entirely for this call (do not crash `millpy-fix.py` over a reporting nicety). `_resolve_holistic_verify(batch_verifies)` (line 67) is unchanged — it already operates on whatever list it's handed and now simply sees a correctly-filtered list.
- **Commit:** `feat(millpy-fix): pass status_path to iter_batch_verifies and log skipped-verify reasons to stderr`

### Card 6: `mill-merge-in/SKILL.md` — pass `status_path`, extend skip counters

- **Context:**
  - `plugins/mill/scripts/_plan_dag.py`
  - `plugins/mill/scripts/millpy-fix.py`
  - `plugins/mill/scripts/_status.py`
- **Edits:**
  - `plugins/mill/skills/mill-merge-in/SKILL.md`
- **Creates:** none
- **Deletes:** none
- **Moves:** none
- **Requirements:** In `plugins/mill/skills/mill-merge-in/SKILL.md`'s `### 4. Verify` section: change the `_plan_dag.iter_batch_verifies(plan_dir, hub_root, git_root)` invocation to additionally pass `status_path` — resolve it the same way `status_path` is already resolved elsewhere in this skill (`_paths.resolve_task_path(hub_root, "_mill/status.md")`) and pass it as `_plan_dag.iter_batch_verifies(plan_dir, hub_root, git_root, status_path=status_path)`. Immediately after that call and before the existing `Initialise counters ran = 0 and skipped = 0` sentence, add two more counters, `skipped_not_approved = 0` and `skipped_target_removed = 0`, and describe the same diff-and-reclassify attribution mechanism as `millpy-fix.py`'s Card 5 (this SKILL.md has no Python CLI of its own for Step 4 — describe the mechanism in prose at the same level of procedural detail this section already uses for the allowlist pre-check and cwd resolution): recompute the raw unfiltered batch-with-verify set via `_plan_dag.extract_batch_index()` + `_plan_dag.topo_order()` + `_plan_dag._read_batch_frontmatter()` + `_plan_dag.parse_verify_field()` per batch, diff it against the names actually returned by the `iter_batch_verifies(...)` call, and for each missing batch attribute the reason via one `_status.read_batches(status_path)` lookup (cached, called once) — `states.get(name) != "approved"` increments `skipped_not_approved`, otherwise increments `skipped_target_removed`. Then in `### 6. Report`: change the conditional report-line rule from its current two-way form (`skipped == 0` vs `skipped >= 1`) to a form that independently includes each of the three skip categories only when its count is nonzero, in this fixed order — allowlisted, not-approved, target-removed — e.g. `Verify: <ran> batch tests ran.` (all three zero); `Verify: <ran> batch tests ran, <skipped> skipped (allowlisted as known-broken).` (only the pre-existing allowlist count nonzero, preserving today's exact wording for that one case); and when any of `skipped_not_approved`/`skipped_target_removed` is also nonzero, append their clauses in the stated order: `, <skipped_not_approved> skipped (batch not approved)` and/or `, <skipped_target_removed> skipped (target removed by later batch)`, each only when its own count is nonzero, terminated with a single trailing period. Keep the existing allowlist pre-check loop (the `for entry p in skip_list` block) and its `skipped` counter entirely unchanged — this card only adds the two new counters and the attribution mechanism alongside it, it does not touch the allowlist mechanism.
- **Commit:** `docs(mill-merge-in): pass status_path to iter_batch_verifies and report skip reasons in Step 4/6`

## Batch Tests

`verify:` runs `test-millpy-fix.py` via `run-all.py --only` (targeted — this batch's code change is entirely inside `millpy-fix.py`). Add test coverage for Card 5: assert both `iter_batch_verifies` call sites now pass `status_path` (e.g. via a fixture where a batch is deliberately left `pending` and confirming the corresponding `verify:` command is absent from what the fixer session dispatches, mirroring this file's existing `status_path`/`read_batches` fixture patterns around lines 200-332); assert a skipped batch (construct one fixture for each reason — a `pending` batch, and a batch whose target a later `approved` batch's `Deletes:` removes) produces the corresponding `[millpy-fix] skipped <batch_name>: <reason>` line on stderr (capture via the same stdout/stderr-capture mechanism this file already uses elsewhere). Card 6 (`mill-merge-in/SKILL.md`) has no Python CLI of its own for Step 4's prose orchestration, so it is not covered by this batch's automated `verify:` — per `_mill/discussion.md`'s Testing section, its `status_path` wiring and extended report-line format are covered by batch `iter-batch-verifies-cross-batch-filter`'s `iter_batch_verifies()` unit tests (the function both callers share) plus a manual verification pass during/after implementation: run `mill-merge-in` against a fixture task once pre-`mill-go` (confirms the "batch not approved" clause and count) and once mid-`mill-go` with a revert-style batch (confirms the "target removed by later batch" clause and count), and visually confirm the report line matches the format specified in Card 6's Requirements. `test-merge-in-subagent.py` covers the conflict/verify-fix sub-agent dispatch paths, which this batch does not touch, and needs no changes.
