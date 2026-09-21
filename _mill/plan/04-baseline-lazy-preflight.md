# Batch: baseline-lazy-preflight

```yaml
task: "Misc infra/wiki/PR/self-hosting reliability bugs"
batch: baseline-lazy-preflight
number: 4
cards: 5
verify: PYTHONPATH= uv run --project plugins/mill python plugins/mill/unit_tests/run-all.py --only test-status.py test-verify-baseline.py test-implementer-common.py test-millpy-implement.py
depends-on: []
```

## Batch Scope

Implements #1102's "lazy" fallback (per `_mill/discussion.md`'s `baseline-preflight-lazy-not-eager`
Decision — the "halt on red parent" primary proposal is explicitly out of scope for this task).
Stops eagerly computing every batch's `verify_baseline_failures` before batch 1 dispatches; instead
pins the parent branch's tip SHA once (cheaply — a `git rev-parse`, not a checkout) and computes a
batch's baseline on demand, only when that batch's own verify gate actually fails and no baseline is
cached yet. The module-wide (single-command, dependency-manifest) baseline computation is untouched.
External interface: `_run_verify_gates` (`_implementer_common.py`) gains no new parameters — it reads
the pinned SHA from `status_path`, which every existing caller already passes.

## Cards

### Card 8: `baseline_parent_sha` status.md accessors

- **Context:**
  - `plugins/mill/scripts/_yaml_writer.py`
- **Edits:**
  - `plugins/mill/scripts/_status.py`
  - `plugins/mill/unit_tests/test-status.py`
- **Creates:** none
- **Deletes:** none
- **Moves:** none
- **Requirements:**
  Add `get_baseline_parent_sha(status_path: Path) -> str | None` and
  `set_baseline_parent_sha(status_path: Path, value: str) -> None` to `_status.py`, placed adjacent
  to the existing `get_module_verify_baseline`/`set_module_verify_baseline`/`clear_module_verify_baseline`
  trio and mirroring their exact mechanics: `get_baseline_parent_sha` calls `_require_path` then
  `read(status_path).get("baseline_parent_sha")`; `set_baseline_parent_sha` validates `value` is a
  non-empty string (raise `ValueError` otherwise — unlike `set_module_verify_baseline` there is no
  fixed enum to check against, just non-emptiness), then rewrites an existing `baseline_parent_sha:`
  row in place or inserts a new one immediately after `parent:` (identical insert-after-`parent:`
  mechanics to `set_module_verify_baseline`, including `quote_scalar` for the written value). No
  `clear_baseline_parent_sha` is needed — the value is pinned once per task and never cleared within
  a task's lifetime (a new task gets a fresh `status.md`). Add both functions to this module's
  top-of-file `Public API` docstring listing, alongside the existing `module_verify_baseline` trio.
- **Commit:** `feat(status): add baseline_parent_sha accessors (#1102)`

### Card 9: on-demand single-batch baseline computation

- **Context:**
  - `plugins/mill/scripts/_worktree.py`
  - `plugins/mill/scripts/_implementer_common.py`
- **Edits:**
  - `plugins/mill/scripts/_verify_baseline.py`
  - `plugins/mill/unit_tests/test-verify-baseline.py`
- **Creates:** none
- **Deletes:** none
- **Moves:** none
- **Requirements:**
  Add `compute_batch_baseline_on_demand(project_root: Path, git_root: Path, parent_sha: str,
  verify_cmd: str, *, cwd_override: Path | None = None, timeout_seconds: float | None = None) ->
  list[str]` to `_verify_baseline.py`, placed after `compute_batch_baselines`. Mirror
  `compute_baseline`'s own checkout/teardown structure exactly: call `_checkout_parent_branch
  (project_root, git_root, parent_sha)` (this function already resolves its `parent_branch` argument
  via `git rev-parse`, so passing an already-resolved 40-character SHA works unchanged — `git
  rev-parse <sha>` on a full SHA returns that same SHA), compute `effective_tmp_path = tmp_path /
  cwd_override if cwd_override is not None else tmp_path` (same pattern `compute_baseline` uses),
  call `_link_dependency_dirs(project_root, effective_tmp_path)`, then call
  `compute_batch_baselines([("_ondemand", verify_cmd, None)], effective_tmp_path, project_root,
  timeout_seconds=timeout_seconds)` and return `result["_ondemand"]`. Wrap the checkout-through-run
  sequence in `try`/`finally` with `_worktree.remove_safe(tmp_path, cwd=git_root, junctions_cfg={})`
  in the `finally` block, identical to `compute_baseline`'s own teardown. Let any exception from
  `_checkout_parent_branch`/`_link_dependency_dirs`/`compute_batch_baselines` propagate to the
  caller — this function has no fail-safe swallowing of its own; the caller (Card 10, inside
  `_run_verify_gates`) is responsible for treating a raised exception as "on-demand computation
  failed, gate strictly" per this codebase's existing None-means-fail-strict convention.
- **Commit:** `feat(verify-baseline): add on-demand single-batch baseline computation (#1102)`

### Card 10: on-demand computation hook in `_run_verify_gates`

- **Context:**
  - `plugins/mill/scripts/_verify_baseline.py`
  - `plugins/mill/scripts/_status.py`
  - `plugins/mill/scripts/_subprocess_util.py`
  - `plugins/mill/scripts/_paths.py`
- **Edits:**
  - `plugins/mill/scripts/_implementer_common.py`
  - `plugins/mill/unit_tests/test-implementer-common.py`
- **Creates:** none
- **Deletes:** none
- **Moves:** none
- **Requirements:**
  In `_implementer_common.py`'s `_run_verify_gates`, the batch-level subset-diff waiver currently
  begins:
  ```python
  replay_signatures = batch_result.get("signatures")
  if batch_verify_baseline and replay_signatures:
      ...
  ```
  Before this `if`, add an on-demand-compute prelude that fires only when there is NO eager baseline
  yet (the normal case now that Card 11 removes eager per-batch precomputation): when
  `not batch_verify_baseline` (`None` or empty) AND `replay_signatures` is truthy AND `status_path is
  not None` AND `verify_cmd is not None`: read `baseline_parent_sha =
  _status.get_baseline_parent_sha(status_path)`; if it is not `None`, call
  `_verify_baseline.compute_batch_baseline_on_demand(project_root, git_root or project_root,
  baseline_parent_sha, verify_cmd, cwd_override=cwd_override)` inside a `try`/`except Exception:` that
  binds the result to `None` on any failure (infrastructure failure degrades to "gate strictly," the
  same fail-safe direction the module-wide mechanism already uses). When the call succeeds and
  returns a non-empty list, rebind the local `batch_verify_baseline` to that list (a plain reassignment
  is sufficient — this is a local variable, not the caller's own) so the existing subset-diff `if
  batch_verify_baseline and replay_signatures:` check below runs against it unmodified, and persist it
  for future batches: call `_status.set_batch_field(status_path, batch_name, "verify_baseline_failures",
  computed)` (when `batch_name is not None`) inside its own `try`/`except Exception: pass`, then, when
  that succeeds and `git_name is not None and git_email is not None`, commit it immediately using the
  exact same pattern the existing corroboration-expansion persist a few lines below already uses:
  `_subprocess_util.run(["git", "add", status_path.relative_to(project_root).as_posix()],
  cwd=project_root)` then `_subprocess_util.git_commit(project_root, f"mill-go: persist on-demand
  verify baseline for {batch_name}", name=git_name, email=git_email)`, both wrapped in
  `try`/`except Exception: pass` (a commit failure here must never crash finalize, matching this
  codebase's existing convention at that call site). This persist-and-commit happens once, at
  on-demand-compute time, regardless of whether the freshly-computed baseline actually waives this
  particular failure below — a computed baseline is valuable for a later batch's failure even when it
  doesn't waive this one.
  Update the function's docstring: extend the `batch_verify_baseline` argument's description to state
  that when this parameter arrives empty/`None` and a batch failure occurs, the function now attempts
  an on-demand computation via `status_path`'s `baseline_parent_sha` before falling back to strict
  blocking (previously: strict blocking was the only behavior when no baseline was cached).
- **Commit:** `feat(implementer-common): compute batch verify baseline on demand when uncached (#1102)`

### Card 11: simplify `_run_baseline_stage` to module-wide-only, add cheap SHA pin

- **Context:**
  - `plugins/mill/scripts/_parent_branch.py`
  - `plugins/mill/scripts/_subprocess_util.py`
  - `plugins/mill/scripts/_implementer_common.py`
  - `plugins/mill/scripts/_status.py`
- **Edits:**
  - `plugins/mill/scripts/millpy-implement.py`
  - `plugins/mill/unit_tests/test-millpy-implement.py`
- **Creates:** none
- **Deletes:** none
- **Moves:** none
- **Requirements:**
  In `millpy-implement.py`'s `_run_baseline_stage`: this function's per-batch computation path
  (`_enumerate_batch_verify_triples`, `batches_needing_computation`, `cached_batches`, and the
  "Case B: at least one batch needs computing" shared-checkout branch that follows) is now dead —
  Card 10 moved per-batch baseline computation to an on-demand call inside `_run_verify_gates`
  instead. Simplify `_run_baseline_stage` so it always takes today's `module_wide_only=True` path
  (today's "Case A": call `_run_module_wide_standalone` and print exactly one JSON line, `{"stage":
  "baseline", "substage": "module_wide", ...}`) — delete the per-batch enumeration, the Case A/Case B
  branch, the shared-checkout logic, and the `substage: "per_batch"` JSON line entirely (including
  its own `print(json.dumps({...}))` call). Remove the now-unconditional `module_wide_only: bool =
  False` parameter from the function signature (every call site becomes parameterless with respect to
  this concern) and update the docstring to describe the simplified single-purpose behavior. Any
  helper this function alone called for the removed path (e.g. `_enumerate_batch_verify_triples`, if
  it has no other caller in this file) may be deleted too — grep this file for other callers first;
  leave it in place if anything else still uses it.

  Add the cheap SHA-pinning step to the same function (runs unconditionally, before or after the
  module-wide computation — order does not matter, since they are independent): if
  `_status.get_baseline_parent_sha(status_path) is None` (idempotent — a resumed/restarted mill-go
  run must not re-pin), resolve `parent_branch = _parent_branch.resolve(status_path,
  interactive=False)` (already imported in this file) inside a `try`/`except Exception:` that,
  on failure, logs to stderr and continues (never raises — matches this function's own "never raises"
  contract); on success, run `_subprocess_util.run(["git", "-C", str(git_root), "rev-parse",
  parent_branch])`, and on a zero return code call `_status.set_baseline_parent_sha(status_path,
  result.stdout.strip())`; on a non-zero return code, log the stderr to stderr and continue without
  pinning (Card 10's on-demand path already treats an absent `baseline_parent_sha` as "gate
  strictly," so a failed pin degrades safely).

  Remove the `--module-wide-only` CLI flag from `main`'s `argparse` setup and its threading into the
  `_run_baseline_stage(..., module_wide_only=args.module_wide_only)` call — the parameter no longer
  exists on the function.
- **Commit:** `refactor(implement): drop eager per-batch baseline pre-flight, pin parent SHA cheaply (#1102)`

### Card 12: mill-go-base/SKILL.md — remove eager per-batch pre-flight and recapture sections

- **Context:**
  - `plugins/mill/scripts/millpy-implement.py`
  - `plugins/mill/scripts/_implementer_common.py`
- **Edits:**
  - `plugins/mill/skills/mill-go-base/SKILL.md`
- **Creates:** none
- **Deletes:** none
- **Moves:** none
- **Requirements:**
  1. In `### 0.5. Baseline pre-flight` (and its companion "speculative early launch" text under the
     "Entry-gate wait for upstream mill-plan" section, which launches `--stage baseline
     --module-wide-only`): update every description of `--stage baseline`'s output to "one JSON
     line" (today's `{"stage": "baseline", "substage": "module_wide", ...}` line) — remove every
     mention of a second `per_batch` JSON line, of parsing "the two JSON lines", and of the
     `--module-wide-only` flag (Card 11 removed it; plain `--stage baseline` is now the only form
     and always behaves the way `--module-wide-only` used to). Specifically, in the "First check: a
     speculative early launch" bullet's `"exit"` handling, delete the entire "then proceed to run a
     SECOND, ordinary (no `--module-wide-only`) `--stage baseline` invocation for the per-batch
     substage only" clause and its accompanying "safe now, since... is not double work" sentence —
     this second call has nothing left to do once the per-batch substage no longer exists; the
     speculative early launch's single module-wide result now IS the complete baseline computation
     for that batch, with nothing further to run. Update the `"running"` sub-bullet's cross-reference
     to that removed second-call handling accordingly (it should simply stop once the module-wide
     result is extracted). `### 0.55. Done-gate baseline pre-flight` is a distinct, unaffected
     mechanism (calls `_done_gate.run_preflight`, not `_verify_baseline`) — do not touch it.
  2. Delete `### 0.6. Per-batch baseline recapture (self-hosting only)` in its entirety. This section
     existed only to backfill a still-missing per-batch `verify_baseline_failures` baseline for a
     self-hosting task's own in-progress plan — that eager per-batch baseline no longer exists to
     backfill (Cards 10/11 replaced it with an on-demand computation inside `_run_verify_gates`
     itself, which already runs the task worktree's own current code when mill-go dispatches an
     implementer/fixer session, so no separate self-hosting recapture step is needed). Grep the rest
     of this file for `baseline_recapture` and `baseline_recapture_attempted` (the Builder variable
     this section introduces) to confirm no other section reads them before deleting; remove any
     remaining reference found.
  3. Search the rest of this file for any other prose that describes `verify_baseline_failures` as
     computed eagerly for every batch before batch 1 (as opposed to consumed at the gate, which is
     unaffected) and correct it to describe the on-demand computation instead.
- **Commit:** `docs(mill-go-base): remove eager per-batch baseline pre-flight and recapture sections (#1102)`

## Batch Tests

- Card 8: extend `plugins/mill/unit_tests/test-status.py` with a `baseline_parent_sha` test group
  mirroring the existing `module_verify_baseline` group's five cases (fresh-file returns `None`,
  set-then-get round-trips, a second `set()` rewrites in place with no duplicate row, an empty-string
  value raises `ValueError`, and — unlike `module_verify_baseline` — no `clear_` case since none is
  added).
- Card 9: extend `plugins/mill/unit_tests/test-verify-baseline.py` (see its existing `compute_baseline`
  tests for the exact `_subprocess_util.run`/`_worktree.remove_safe` mocking pattern) with a test
  asserting `compute_batch_baseline_on_demand` calls `_checkout_parent_branch` with the passed
  `parent_sha` verbatim, calls `compute_batch_baselines` with a single `("_ondemand", verify_cmd,
  None)` triple, returns that entry's signature list, and tears down the transient worktree via
  `_worktree.remove_safe` even when `compute_batch_baselines` raises.
- Card 10: extend `plugins/mill/unit_tests/test-implementer-common.py`'s `_run_verify_gates` test
  group with: (a) a case where `batch_verify_baseline` is `None`, the batch replay fails, and
  `status_path` has a pinned `baseline_parent_sha` — mock `_verify_baseline.compute_batch_baseline_on_demand`
  to return a signature list matching the replay failure, and assert the gate is waived
  (`_run_verify_gates` returns `None` or falls through to the module-wide gate) and that
  `_status.set_batch_field` was called with the computed list; (b) a case with no pinned
  `baseline_parent_sha` — assert the gate blocks exactly as it did before this batch (unwaived,
  no on-demand call attempted); (c) a case where the on-demand computation itself raises — assert the
  gate blocks (fail-safe-strict) rather than propagating the exception.
- Card 11: extend `plugins/mill/unit_tests/test-millpy-implement.py`'s `_run_baseline_stage` tests to
  assert: the function now always prints exactly one JSON line (no `per_batch` line, ever); the
  `module_wide_only` parameter no longer exists (a `TypeError` on the old kwarg is the expected
  regression-proof, or simply drop the old kwarg from every existing call in this test file); a fresh
  `status.md` with no `baseline_parent_sha` gets one set to the mocked `git rev-parse` output after
  one call; a second call does not re-invoke `git rev-parse` for the pin (idempotent).
- Card 12 is documentation-only — verified by re-reading the edited sections for internal consistency
  (no leftover reference to `--module-wide-only`, `per_batch`, or `baseline_recapture`) rather than an
  automated test.
