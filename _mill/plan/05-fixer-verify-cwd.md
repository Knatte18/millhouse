# Batch: fixer-verify-cwd

```yaml
task: Fix nested-hub-layout path resolution bugs across scope violations and review CLIs
batch: fixer-verify-cwd
number: 5
cards: 4
verify: PYTHONPATH= uv run --project plugins/mill python plugins/mill/unit_tests/run-all.py --only test-millpy-fix.py test-fix-finalize.py
depends-on: [3, 4]
```

## Batch Scope

Fixes #604 for the fixer path: `millpy-fix.py` has four `verify` read sites — two batch-scope (finalize stage `~239`, prepare/full stage `~284`) and two holistic-scope that join every batch's verify string via `_plan_dag.iter_batch_verifies` (finalize stage `~242-244`, prepare/full stage `~357`). All four route through `parse_verify_field` (batch 3) and the new `cwd_override` kwarg (batch 4). Holistic-scope joining introduces a new constraint not present in the implementer path: multiple batches' verify commands are concatenated into a single shell command (`" && ".join(...)`), which cannot be satisfied by more than one subprocess `cwd` — mixed `cwd` values across the joined batches is therefore a plan-authoring error, not something the fixer can silently coerce. Depends on batch 3 (`parse_verify_field`, `iter_batch_verifies`'s 3-tuple shape) and batch 4 (`_run_verify_gate`'s `cwd_override` kwarg lives in the shared `_implementer_common.py` module both `millpy-implement.py` and `millpy-fix.py` call into).

## Cards

### Card 19: Thread parse_verify_field through millpy-fix.py batch-scope verify reads

- **Context:**
  - `plugins/mill/scripts/_plan_dag.py`
  - `plugins/mill/scripts/_implementer_common.py`
- **Edits:**
  - `plugins/mill/scripts/millpy-fix.py`
- **Creates:** none
- **Deletes:** none
- **Moves:** none
- **Requirements:** At the finalize stage, `verify_cmd = None` is pre-initialized (line ~231) before branching on `args.scope`, because the batch-scope read is nested inside `if batch_entry is not None:` and the holistic-scope read inside `if batch_verifies:` — either guard can be false, leaving the pre-initialized value. Add `cwd_override = None` as the same kind of pre-initialization alongside it, **before** the `if args.scope == "batch":` branch. Inside `if batch_entry is not None:`, replace `verify_cmd = batch_frontmatter.get("verify")` with `verify_cmd, cwd_override = _plan_dag.parse_verify_field(batch_frontmatter, project_root, git_root)` — the assignment stays inside the existing guard; when `batch_entry is None`, both `verify_cmd` and `cwd_override` keep their pre-initialized `None` values, exactly matching today's behavior. Thread `cwd_override` onward as the `cwd_override=` keyword argument to the enclosing `finalize_from_output(...)` call (the kwarg added by batch 4's Card 13). At the prepare/full-stage batch-scope read site (`batch_frontmatter = _plan_dag._read_batch_frontmatter(batch_file); verify_cmd = batch_frontmatter.get("verify")` — this one is unconditional, since `batch_entry` was already confirmed non-`None` earlier in that code path), replace with `verify_cmd, cwd_override = _plan_dag.parse_verify_field(batch_frontmatter, project_root, git_root)` directly (no pre-initialization needed here), threading `cwd_override` into the `_forward_output(...)` call at the bottom of the file. Let a `ValueError` from `parse_verify_field` propagate uncaught in all cases, matching batch 4's implementer-path policy.
- **Commit:** `feat(millpy-fix): resolve batch-scope verify cwd via parse_verify_field (#604)`

### Card 20: Thread iter_batch_verifies through millpy-fix.py holistic-scope joining

- **Context:**
  - `plugins/mill/scripts/_plan_dag.py`
  - `plugins/mill/scripts/_implementer_common.py`
- **Edits:**
  - `plugins/mill/scripts/millpy-fix.py`
- **Creates:** none
- **Deletes:** none
- **Moves:** none
- **Requirements:** Introduce a shared helper (module-level function in `millpy-fix.py`, e.g. `_resolve_holistic_verify(batch_verifies)`) that: computes the set of distinct non-`None` `cwd` values across a `(name, command, cwd)` 3-tuple list; raises `ValueError` naming the conflicting batch names and their resolved cwd values when that set has more than one element (mixed-cwd holistic joining cannot be satisfied by a single subprocess `cwd` and is a plan-authoring error that must surface immediately, matching the fail-loud policy established for `parse_verify_field` in batch 3); otherwise returns `(joined_command, cwd_override)` where `joined_command` is `" && ".join(cmd for _, cmd, _ in batch_verifies)` and `cwd_override` is the single distinct `cwd` value (or `None` if every batch's cwd was `None`). At the finalize-stage holistic-scope site (`elif args.scope == "holistic": batch_verifies = _plan_dag.iter_batch_verifies(plan_base); if batch_verifies: verify_cmd = " && ".join(...)`), first update the call to `_plan_dag.iter_batch_verifies(plan_base, project_root, git_root)`. `cwd_override = None` must already be pre-initialized before the `if args.scope == "batch":` branch (per Card 19) — inside `if batch_verifies:`, replace the join line with `verify_cmd, cwd_override = _resolve_holistic_verify(batch_verifies)`; when `batch_verifies` is empty, both `verify_cmd` and `cwd_override` keep their pre-initialized `None` values, matching today's behavior. At the prepare/full-stage holistic-scope site (`batch_verifies = _plan_dag.iter_batch_verifies(plan_base); verify_cmd = (" && ".join(...) if batch_verifies else None)`), update the `iter_batch_verifies` call the same way and replace the ternary with `verify_cmd, cwd_override = _resolve_holistic_verify(batch_verifies) if batch_verifies else (None, None)` (this site has no pre-initialization dependency — the ternary always assigns both names directly). Thread `cwd_override` into the enclosing `finalize_from_output(...)` / `_forward_output(...)` call at each of the two call sites.
- **Commit:** `feat(millpy-fix): enforce uniform verify cwd across batches for holistic joining (#604)`

### Card 21: Add nested-layout and mixed-cwd cases to test-millpy-fix.py

- **Context:**
  - `plugins/mill/scripts/millpy-fix.py`
- **Edits:**
  - `plugins/mill/unit_tests/test-millpy-fix.py`
- **Creates:** none
- **Deletes:** none
- **Moves:** none
- **Requirements:** Add a batch-scope nested-layout case asserting a `verify: {cwd: hub, command: ...}` batch frontmatter resolves and threads `cwd_override` correctly (Card 19). Add a holistic-scope case with all contributing batches resolving to the same `cwd` (`hub`, or all plain-string), asserting the join succeeds and `cwd_override` resolves correctly (Card 20). Add a holistic-scope case with batches resolving to mixed `cwd` values, asserting `ValueError` is raised naming the conflicting batches rather than the fixer silently picking one. Add a finalize-stage regression case for the batch-not-found path (`batch_entry is None`) asserting `cwd_override` stays `None` (not a `NameError`) and behavior is otherwise unchanged from today. Add a finalize-stage regression case for the holistic empty-`batch_verifies` path asserting the same.
- **Commit:** `test(millpy-fix): cover nested-layout and mixed-cwd holistic joining (#604)`

### Card 22: Add cwd_override case to test-fix-finalize.py

- **Context:**
  - `plugins/mill/scripts/millpy-fix.py`
- **Edits:**
  - `plugins/mill/unit_tests/test-fix-finalize.py`
- **Creates:** none
- **Deletes:** none
- **Moves:** none
- **Requirements:** Add a nested-layout case at the finalize-stage batch-scope verify path (Card 19) asserting `cwd_override` is correctly resolved and threaded into the `finalize_from_output` call, distinct from the prepare/full-stage coverage added in Card 21.
- **Commit:** `test(fix-finalize): cover cwd_override threading at the finalize stage (#604)`

## Batch Tests

`verify: PYTHONPATH= uv run --project plugins/mill python plugins/mill/unit_tests/run-all.py --only test-millpy-fix.py test-fix-finalize.py` covers both affected test files: batch-scope and holistic-scope verify cwd resolution (Cards 21) and the finalize-stage-specific case (Card 22).
