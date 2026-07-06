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

Fixes #604 for the fixer path: `millpy-fix.py` has two batch-scope `verify` read sites (finalize stage `~239`, prepare/full stage `~284`) and two holistic-scope sites that join every batch's verify string via `_plan_dag.iter_batch_verifies` (finalize stage `~357`, prepare/full stage `~357` — wait, both branches share the same holistic block at line `~357`; the finalize-stage holistic join is at `~242-244`). All four route through `parse_verify_field` (batch 3) and the new `cwd_override` kwarg (batch 4). Holistic-scope joining introduces a new constraint not present in the implementer path: multiple batches' verify commands are concatenated into a single shell command (`" && ".join(...)`), which cannot be satisfied by more than one subprocess `cwd` — mixed `cwd` values across the joined batches is therefore a plan-authoring error, not something the fixer can silently coerce. Depends on batch 3 (`parse_verify_field`, `iter_batch_verifies`'s 3-tuple shape) and batch 4 (`_run_verify_gate`'s `cwd_override` kwarg lives in the shared `_implementer_common.py` module both `millpy-implement.py` and `millpy-fix.py` call into).

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
- **Requirements:** At the finalize-stage batch-scope read site (`if args.scope == "batch": ... verify_cmd = batch_frontmatter.get("verify")`), replace with `verify_cmd, cwd_override = _plan_dag.parse_verify_field(batch_frontmatter, project_root, git_root)`, and thread `cwd_override` onward as the `cwd_override=` keyword argument to the enclosing `finalize_from_output(...)` call (the kwarg added by batch 4's Card 13). At the prepare/full-stage batch-scope read site (`batch_frontmatter = _plan_dag._read_batch_frontmatter(batch_file); verify_cmd = batch_frontmatter.get("verify")`), apply the identical replacement, threading `cwd_override` into the `_forward_output(...)` call at the bottom of the file. Let a `ValueError` from `parse_verify_field` propagate uncaught in both cases, matching batch 4's implementer-path policy.
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
- **Requirements:** At both holistic-scope call sites (finalize stage: `batch_verifies = _plan_dag.iter_batch_verifies(plan_base)` followed by `verify_cmd = " && ".join(verify for _, verify in batch_verifies)`; prepare/full stage: the identical pattern), update the call to `_plan_dag.iter_batch_verifies(plan_base, project_root, git_root)` (now returning `(name, command, cwd)` 3-tuples per batch 3). Compute the set of distinct non-`None` `cwd` values across `batch_verifies`. If that set has more than one element, raise `ValueError` with a message naming the conflicting batch names and their resolved cwd values — mixed-cwd holistic joining cannot be satisfied by a single subprocess `cwd` and is a plan-authoring error that must surface immediately (matches the fail-loud policy established for `parse_verify_field` in batch 3). Otherwise, resolve `cwd_override` to that single distinct `cwd` value (or `None` if every batch's cwd was `None`, i.e. every batch used the plain-string form or had no cwd override). Join the command strings unchanged (`" && ".join(cmd for _, cmd, _ in batch_verifies)`). Thread `cwd_override` into the enclosing `finalize_from_output(...)` / `_forward_output(...)` call at each of the two call sites.
- **Commit:** `feat(millpy-fix): enforce uniform verify cwd across batches for holistic joining (#604)`

### Card 21: Add nested-layout and mixed-cwd cases to test-millpy-fix.py

- **Context:**
  - `plugins/mill/scripts/millpy-fix.py`
- **Edits:**
  - `plugins/mill/unit_tests/test-millpy-fix.py`
- **Creates:** none
- **Deletes:** none
- **Moves:** none
- **Requirements:** Add a batch-scope nested-layout case asserting a `verify: {cwd: hub, command: ...}` batch frontmatter resolves and threads `cwd_override` correctly (Card 19). Add a holistic-scope case with all contributing batches resolving to the same `cwd` (`hub`, or all plain-string), asserting the join succeeds and `cwd_override` resolves correctly (Card 20). Add a holistic-scope case with batches resolving to mixed `cwd` values, asserting `ValueError` is raised naming the conflicting batches rather than the fixer silently picking one.
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
