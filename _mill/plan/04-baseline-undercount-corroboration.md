# Batch: baseline-undercount-corroboration

```yaml
task: 'millpy-implement/bg: Windows baseline-worktree teardown (WinError 145) and stale liveness reporting'
batch: baseline-undercount-corroboration
number: 4
cards: 3
verify: PYTHONPATH= uv run --project plugins/mill python plugins/mill/unit_tests/run-all.py --only test-implementer-common.py test-millpy-implement.py
depends-on: []
```

## Batch Scope

`_run_verify_gates`'s subset-diff waiver (in `_implementer_common.py`) only waives a batch-level
verify failure when the live replay's failure signatures are already a subset of the cached
per-batch `verify_baseline_failures` (itself computed once, before the task started, by
`_verify_baseline.compute_batch_baselines` against a transient parent-branch checkout). GitHub issue
#917 shows that transient-checkout computation can undercount vs. a live worktree, causing a real
pre-existing failure to be missing from the cached baseline — which then makes an unrelated,
genuinely pre-existing failure block the batch with a false `stuck_type: verify`.

This batch adds a corroboration step: when the subset check fails (mismatch), re-run the exact
failing command once more in a **fresh transient checkout of the batch's own `start_sha`** (the
commit the live replay's own worktree started from, before this batch's implementer made any
commits — never `project_root` itself, since by the time this gate runs `project_root` already
contains the batch's own commits and so cannot discriminate a genuine regression from a true
pre-existing failure). If the control run reproduces the same failure, treat it as corroborated:
waive the batch and persist the expanded signature set back into `status.md` so later batches in the
same task don't re-pay the same false block (self-healing). If it does not reproduce, block exactly
as today.

`start_sha` is already captured per-batch and stored in `status.md` before the implementer's first
commit (`millpy-implement.py`'s existing `start_sha` capture/resume machinery) — this batch reuses
it, adding no new state. The corroboration checkout reuses
`_verify_baseline._checkout_parent_branch`/`_link_dependency_dirs`/`_worktree.remove_safe` directly
(that first function's `parent_branch` parameter is just a ref/SHA string passed straight to `git
rev-parse` — passing a raw commit SHA works identically to a branch name, so no signature change is
needed there). `_verify_baseline.py` already does `from _implementer_common import
_extract_failure_signatures, _posix_shell_run_args` at module level, so `_implementer_common.py`
must import `_verify_baseline`/`_worktree` **as function-local imports inside the new corroboration
function only** (never at `_implementer_common.py` module level) to avoid a circular import.

This corroboration path only ever fires for `millpy-implement.py`'s own finalize/full-stage calls —
`millpy-fix.py` never passes `batch_verify_baseline` to `finalize_from_output`/`_forward_output` at
all today, so the existing subset-diff waiver (and this batch's extension of it) is already scoped
to the implementer's own verify gate, not the fixer's; this batch does not change that scope.

## Cards

### Card 7: Corroboration helper + parameter threading in `_implementer_common.py`

- **Context:**
  - `plugins/mill/scripts/_verify_baseline.py`
- **Edits:**
  - `plugins/mill/scripts/_implementer_common.py`
- **Creates:** none
- **Deletes:** none
- **Moves:** none
- **Requirements:**
  Add a new function `_corroborate_batch_failure(project_root: Path, git_root: Path | None,
  start_sha: str | None, verify_cmd: str | None, cwd_override: Path | None) -> dict | None`, placed
  immediately before `_run_verify_gates` in `_implementer_common.py`. Behavior:
  - If `start_sha` is `None` or `verify_cmd` is `None`, return `None` immediately (cannot
    corroborate — this is the fail-safe-toward-"not corroborated" default that keeps every existing
    call site that never passes `start_sha` fully backward-compatible, since `_run_verify_gates`
    itself defaults the new `start_sha` parameter to `None`, see below).
  - Add `import _verify_baseline` and `import _worktree` as the first two statements inside this
    function's body (function-local, not module-level — see Batch Scope for why).
  - Compute `effective_git_root = git_root or project_root`.
  - Wrap the whole body from here on in `try: ... except Exception: return None` (any infrastructure
    failure here — a failed `git worktree add`, a junction error — degrades to "not corroborated",
    never propagates; matches this module's existing `None`-means-fail-safe-strict convention).
  - Call `tmp_path = _verify_baseline._checkout_parent_branch(project_root, effective_git_root,
    start_sha)` (passing `start_sha` positionally as that function's `parent_branch` argument — it
    is generic: it resolves whatever ref/SHA string it is given via `git rev-parse` and checks that
    out, so a raw commit SHA works identically to a branch name).
  - Inside a `try`/`finally`, with the `finally` clause calling `_worktree.remove_safe(tmp_path,
    cwd=effective_git_root, junctions_cfg={})` (swallow any exception raised by this teardown call
    itself — best-effort cleanup, must never mask the control run's own result):
    - Compute `effective_tmp_path = tmp_path`. If `cwd_override` is not `None`: attempt
      `rel = cwd_override.relative_to(effective_git_root)` inside its own `try: ... except
      ValueError: rel = None`; when `rel` is not `None`, set `effective_tmp_path = tmp_path / rel`
      (mirrors `_verify_baseline.compute_baseline`'s own `effective_tmp_path = tmp_path /
      cwd_override_relative if cwd_override_relative is not None else tmp_path` pattern, adapted
      since this call site receives an already-absolute `cwd_override` rather than a pre-resolved
      relative fragment).
    - Call `_verify_baseline._link_dependency_dirs(project_root, effective_tmp_path)`.
    - `return _run_verify_gate(effective_tmp_path, verify_cmd, git_root=None, cwd_override=None)` —
      reuses `_run_verify_gate` (singular, already defined earlier in this same file) directly,
      passing the temp checkout path AS its `project_root` argument so the verify subprocess runs
      there; this gets `_run_verify_gate`'s existing Windows dotnet-lock retry and failure-signature
      extraction for free, with zero new subprocess-invocation code.
  - Give the function a docstring stating its purpose (corroborate a subset-diff mismatch against a
    pre-batch-changes checkout) and return contract (the control run's own stuck dict with a
    `"signatures"` field on failure, or `None` on a clean pass / when corroboration could not be
    attempted).

  Add three new keyword-only parameters to `_run_verify_gates`'s signature, after the existing
  `batch_verify_baseline: list[str] | None = None` parameter: `start_sha: str | None = None`,
  `status_path: Path | None = None`, `batch_name: str | None = None`. Document each in the
  docstring's `Args:` section (mirroring the existing `batch_verify_baseline` entry's style): all
  three default to `None`, preserving today's exact behavior (no corroboration attempted) for every
  existing caller that does not pass them.

  Inside `_run_verify_gates`, in the subset-diff waiver block (the `if batch_verify_baseline and
  replay_signatures:` block), the current shape is:
  ```python
        if batch_verify_baseline and replay_signatures:
            normalized_replay = {
                _normalize_failure_signature(line) for line in replay_signatures
            }
            normalized_baseline = {
                _normalize_failure_signature(line) for line in batch_verify_baseline
            }
            if normalized_replay.issubset(normalized_baseline):
                # Waived: fall through to the module-wide gate below exactly as the batch_result is None path already does.
                batch_result = None
  ```
  Extend the `if normalized_replay.issubset(normalized_baseline):` block with an
  `elif start_sha is None: pass` and a final `else:` (both at the same indentation level as that
  `if`, per the code block below), so the mismatch case now attempts corroboration before falling
  through to the unchanged `if batch_result is not None: return batch_result` below it. Guard the
  corroboration attempt on `start_sha is not None` at this call site itself — do not rely solely on
  `_corroborate_batch_failure`'s own internal `None` check (Card 9's test 72h patches
  `_corroborate_batch_failure` itself to assert it is never called when `start_sha` is omitted; a
  mocked replacement bypasses that function's own internal guard entirely, so the call site must not
  invoke it at all in that case):
  ```python
          elif start_sha is None:
              pass
          else:
              control_result = _corroborate_batch_failure(
                  project_root, git_root, start_sha, verify_cmd, cwd_override
              )
              if control_result is not None:
                  normalized_control = {
                      _normalize_failure_signature(line)
                      for line in (control_result.get("signatures") or [])
                  }
                  if normalized_replay.issubset(normalized_control):
                      # Corroborated: this exact failure set also reproduces in a checkout that
                      # predates this batch's own changes -- treat as pre-existing, waive, and
                      # persist the expanded signature set so later batches in this task don't
                      # re-pay the same false block.
                      expanded = sorted(set(batch_verify_baseline) | set(replay_signatures))
                      if status_path is not None and batch_name is not None:
                          try:
                              _status.set_batch_field(
                                  status_path,
                                  batch_name,
                                  "verify_baseline_failures",
                                  expanded,
                              )
                          except Exception:
                              pass
                      batch_result = None
  ```
  (`_status` is already imported at module level in `_implementer_common.py`.) Do not otherwise
  change the subset-diff block, the batch-level gate call above it, or the module-wide gate logic
  below it.

  Add the same three new keyword-only parameters (`start_sha: str | None = None`, `status_path: Path
  | None = None`, `batch_name: str | None = None`) to `_forward_output`'s own signature — but note
  `_forward_output` already has a `start_sha` parameter and a `status_path` parameter; only
  `batch_name: str | None = None` is new there. At all 4 occurrences within `_forward_output` of the
  exact call shape:
  ```python
            gate_result = _run_verify_gates(
                project_root,
                verify_cmd,
                module_wide_verify_cmd,
                git_root=git_root,
                module_verify_baseline=module_verify_baseline,
                cwd_override=cwd_override,
                module_wide_cwd_override=module_wide_cwd_override,
                batch_verify_baseline=batch_verify_baseline,
            )
  ```
  (indentation varies by call site — two are nested deeper inside `if`/`for` blocks than the other
  two; match each occurrence's own existing indentation), add three more keyword arguments
  immediately after `batch_verify_baseline=batch_verify_baseline,`, at the same indentation:
  `start_sha=start_sha,`, `status_path=status_path,`, `batch_name=batch_name,`.

  Add the same new `batch_name: str | None = None` keyword-only parameter to
  `finalize_from_output`'s signature (it already has `start_sha` and `status_path`), and thread
  `batch_name=batch_name,` into its own `return _forward_output(...)` call (alongside the existing
  `start_sha=start_sha,`/`status_path=status_path,` lines already forwarded there). Document the new
  parameter in both functions' docstrings, mirroring the style of the adjacent existing parameter
  docs.
- **Commit:** `fix(implementer): corroborate a baseline subset-diff mismatch against a start_sha checkout`

### Card 8: Thread `batch_name` and `status_path` from `millpy-implement.py`'s two call sites

- **Context:**
  - `plugins/mill/scripts/_implementer_common.py`
- **Edits:**
  - `plugins/mill/scripts/millpy-implement.py`
- **Creates:** none
- **Deletes:** none
- **Moves:** none
- **Requirements:**
  In `millpy-implement.py`'s `--stage finalize` branch, the existing call
  `return finalize_from_output(Path(args.agent_output), project_root, start_sha=start_sha, ...)`
  (the finalize-stage call already passing `batch_verify_baseline=batch_verify_baseline,` and
  `task_dir=status_path.parent,`, but **not** `status_path=status_path,` itself) — add two new
  keyword arguments to this call, placed immediately after the existing
  `batch_verify_baseline=batch_verify_baseline,` line: `batch_name=args.batch_name,` and
  `status_path=status_path,`. Both are critical — `_run_verify_gates`'s new self-healing persist
  (Card 7) only fires when both are non-`None`; passing `batch_name` alone without `status_path`
  would silently disable the corroboration self-healing this batch exists to add, even though the
  corroboration waiver itself would still work. `args.batch_name` is already read and validated
  earlier in this same `if args.stage == "finalize":` branch (used to look up `batch_status` from
  `_status.read_batches(status_path)`); `status_path` is already a local variable in scope throughout
  `main()`. Neither is a new variable.

  In the `--stage full` branch's `return _forward_output(output, project_root, start_sha=start_sha,
  ...)` call (the one immediately following the `batch_verify_baseline = (...)` computation that
  reads `_full_stage_batch_entry` — this call also already has `task_dir=status_path.parent,` but not
  `status_path=status_path,`), add the same two keyword arguments, placed immediately after the
  existing `batch_verify_baseline=batch_verify_baseline,` line in that call:
  `batch_name=args.batch_name,` and `status_path=status_path,`.

  Do not modify any other call in this file (the `--resume-incomplete` handling, or any other stage,
  are unaffected — only these two calls pass `batch_verify_baseline` today, per this batch's Batch
  Scope note that `millpy-fix.py` never does).
- **Commit:** `fix(implement): pass batch_name and status_path through to the verify-gate corroboration path`

### Card 9: Unit tests for the corroboration path

- **Context:**
  - `plugins/mill/scripts/_verify_baseline.py`
  - `plugins/mill/scripts/millpy-implement.py`
  - `plugins/mill/scripts/_status.py`
  - `plugins/mill/scripts/_implementer_common.py`
- **Edits:**
  - `plugins/mill/unit_tests/test-implementer-common.py`
- **Creates:** none
- **Deletes:** none
- **Moves:** none
- **Requirements:**
  Add new test cases to `test-implementer-common.py`, placed immediately after the existing "Case 72
  -- _run_verify_gates batch_verify_baseline subset-diff matrix" cases — this matrix actually has
  five existing sub-cases today, 72a through 72e (72e: "a stuck dict with no 'signatures' key must
  never be waived"), not four; insert the new cases after 72e and before the following, unrelated
  "Case 73" (a dirty-tree regression test), using the same `_setup_fixture(project_root)` real-git-repo
  helper already defined in this file, which inits a repo with a seed base commit and returns that
  commit's SHA.

  New case "72f — corroboration succeeds: a start_sha checkout reproduces the same mismatch ->
  waived + baseline persisted". Setup: call `base_sha = _setup_fixture(project_root)`. Use a
  `verify_cmd` whose failure is content-independent (reproduces identically regardless of repo
  content, e.g. `"echo '--- FAIL: TestNew (0.00s)' && exit 1"`, matching case 72b's own
  content-independent command). Build a real `status.md` fixture using the established
  `_status.render_initial(...)` + `_status.init_batches(status_path, [...])` pattern (used
  identically in `test-millpy-fix.py`/`test-status.py`): write
  `_status.render_initial("Test Task", "test", "2026-01-01T00:00:00Z", "main", "test-slug",
  "test-branch")`'s return value to a `status_path` under `project_root` (e.g. `project_root /
  "_mill" / "status.md"`, creating the parent `_mill/` dir first), then call
  `_status.init_batches(status_path, ["01-test-batch"])` to seed one batch entry at `state: pending`
  with no `verify_baseline_failures` field yet. Call `_run_verify_gates(project_root,
  verify_cmd, None, batch_verify_baseline=["--- FAIL: TestOld (1.11s)"], start_sha=base_sha,
  status_path=<the fixture status.md path>, batch_name="01-test-batch")`. Assert the result is `None`
  (waived). Assert (via `_status.read_batches(status_path)`) that the `"01-test-batch"` entry's
  `verify_baseline_failures` now includes both the original `"--- FAIL: TestOld (1.11s)"` entry and
  the new `"--- FAIL: TestNew (0.00s)"` signature (self-healing persisted).

  New case "72g — corroboration fails to reproduce: still blocks". Setup: call `base_sha =
  _setup_fixture(project_root)`, then create and commit a new file in `project_root` (e.g.
  `(project_root / "marker.txt").write_text("x")` + `git add` + `git commit`) so `project_root`'s
  current `HEAD` differs from `base_sha` — this simulates "the batch's own commit". Use a
  `verify_cmd` whose result depends on that file's presence, e.g.
  `"test -f marker.txt && echo '--- FAIL: TestNew (0.00s)' && exit 1 || exit 0"` (fails at `HEAD`
  where `marker.txt` exists, passes at `base_sha` where it does not exist yet). Call
  `_run_verify_gates(project_root, verify_cmd, None, batch_verify_baseline=["--- FAIL: TestOld
  (1.11s)"], start_sha=base_sha, status_path=<a fresh status.md fixture built via the same
  `_status.render_initial`/`_status.init_batches` pattern as case 72f>, batch_name="01-test-batch")`. Assert the
  result is not `None` and `result["stuck_type"] == "verify"` (still blocks — the control run at
  `base_sha` passed, so the mismatch was not corroborated as pre-existing).

  New case "72h — backward compatibility: omitting start_sha never attempts corroboration". Re-run
  case 72b's exact scenario (a replay signature absent from baseline, `verify_cmd = "echo '--- FAIL:
  TestNew (0.00s)' && exit 1"`, `baseline = ["--- FAIL: TestFoo (9.99s)"]`) but this time patch
  `_implementer_common._corroborate_batch_failure` (via `unittest.mock.patch`) to raise
  `AssertionError("should not be called")` if invoked, then call `_run_verify_gates(project_root,
  verify_cmd, None, batch_verify_baseline=baseline)` with no `start_sha`/`status_path`/`batch_name`
  kwargs at all (matching every pre-existing call site in this codebase before this task). Assert the
  result is not `None` and the patched mock was never called — confirming `start_sha=None`
  (the default) short-circuits `_corroborate_batch_failure` before it does any git/filesystem work,
  so every pre-existing caller's behavior is provably unchanged.
- **Commit:** `test(implementer-common): cover the start_sha corroboration path and its backward compatibility`

## Batch Tests

`verify:` runs `test-implementer-common.py` (this batch's primary edited module, and the location of
all new corroboration tests) and `test-millpy-implement.py` (regression coverage for the two
`batch_name=args.batch_name` call-site edits in Card 8 — no new test cases are required there since
`args.batch_name` was already read and used by both call sites before this batch; existing
`test-millpy-implement.py` coverage of those two stages already exercises the modified call sites
and would fail on a `TypeError` if the new keyword argument were misspelled or misplaced).
