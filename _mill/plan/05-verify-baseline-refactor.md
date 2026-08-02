# Batch: verify-baseline-refactor

```yaml
task: Improve diagnosability of plan-validate errors and finalize verify-replay failures
batch: verify-baseline-refactor
number: 5
cards: 6
verify: PYTHONPATH= uv run --project plugins/mill python plugins/mill/unit_tests/run-all.py --only test-verify-baseline.py
depends-on: [4]
```

## Batch Scope

Splits `compute_baseline`'s checkout/junction-link/algorithm logic into three named, independently-callable helpers so a future orchestrator (batch 6's `_run_baseline_stage`) can share one checkout across the module-wide command and every per-batch command, without `compute_baseline` itself changing its public contract for any existing standalone caller. Adds the new per-batch multi-command computation function using batch 4's `_extract_failure_signatures`/`_normalize_failure_signature` helpers. Depends on batch 4 for those two helpers.

## Cards

### Card 14: Extract `_checkout_parent_branch`

- **Context:** none
- **Edits:**
  - `plugins/mill/scripts/_verify_baseline.py`
- **Creates:** none
- **Deletes:** none
- **Moves:** none
- **Requirements:** Extract the `git rev-parse` + `git worktree add` sequence (`_verify_baseline.py:139-172` — the `.scratch` directory creation, the 12-hex-char `uuid.uuid4().hex[:12]` transient-worktree basename, and the `-c core.longpaths=true` flag) into a new module-level function `_checkout_parent_branch(project_root: Path, git_root: Path, parent_branch: str) -> Path`, returning the created `tmp_path`. No behavior change: raises `RuntimeError` on `rev-parse`/`worktree add` failure exactly as today's inline code does, with the same error messages.
- **Commit:** `refactor(verify-baseline): extract _checkout_parent_branch helper`

### Card 15: Extract `_link_dependency_dirs` with a simplified signature

- **Context:** none
- **Edits:**
  - `plugins/mill/scripts/_verify_baseline.py`
- **Creates:** none
- **Deletes:** none
- **Moves:** none
- **Requirements:** Extract the `_DEPENDENCY_DIR_CANDIDATES` junction-linking loop (`_verify_baseline.py:184-193`) into a new module-level function `_link_dependency_dirs(project_root: Path, target_path: Path) -> None`. Unlike the original inline loop, this function does NOT branch on `cwd_override_relative`/`tmp_path` — it takes one already-resolved `target_path` and, for each name in `_DEPENDENCY_DIR_CANDIDATES` whose `project_root / name` exists, calls `_junction.create(project_root / name, target_path / name)`. The caller is responsible for resolving `cwd_override_relative` into a concrete `target_path` (`tmp_path / cwd_override_relative`, or plain `tmp_path`) before calling this function — the original inline closure-variable branching does not carry over, since those variables no longer exist in this function's scope.
- **Commit:** `refactor(verify-baseline): extract _link_dependency_dirs helper`

### Card 16: Extract `_run_module_wide_verify_algorithm`

- **Context:** none
- **Edits:**
  - `plugins/mill/scripts/_verify_baseline.py`
- **Creates:** none
- **Deletes:** none
- **Moves:** none
- **Requirements:** Extract the 3-run/control-check verification logic (`_verify_baseline.py:195-215`: the first `_run_verify_in` call, the flakiness-guard retry, and the control-run-in-`project_root` corroboration, including the stderr warning print on the path/environment-mismatch case) into a new module-level function `_run_module_wide_verify_algorithm(module_wide_verify_cmd: str, effective_tmp_path: Path, project_root: Path) -> str`, returning `"clean"` or `"pre-existing-failures"` exactly as the inline logic does today. This is a verbatim extraction — only de-closured to take `effective_tmp_path`/`project_root` as explicit parameters instead of closing over `compute_baseline`'s locals. As part of this extraction, change `_run_verify_in` (`_verify_baseline.py:220-230`) to return `tuple[int, str]` (exit code, combined `stdout + stderr`) instead of just the exit code, and update this algorithm's three call sites to unpack `(rc, _output) = _run_verify_in(...)` and use only `rc` for its decisions (this algorithm never needed the output text; card 17's new per-batch function is what needs it).
- **Commit:** `refactor(verify-baseline): extract _run_module_wide_verify_algorithm helper`

### Card 17: Thin `compute_baseline` wrapper; new per-batch multi-command computation

- **Context:**
  - `plugins/mill/scripts/_implementer_common.py`
  - `_mill/discussion.md`
- **Edits:**
  - `plugins/mill/scripts/_verify_baseline.py`
- **Creates:** none
- **Deletes:** none
- **Moves:** none
- **Requirements:**
  1. Rewrite `compute_baseline`'s body (`_verify_baseline.py:139-217`) to: call `tmp_path = _checkout_parent_branch(project_root, git_root, parent_branch)`; resolve `effective_tmp_path` exactly as today (`tmp_path / cwd_override_relative if cwd_override_relative is not None else tmp_path`); inside the existing `try/finally` (teardown via `_worktree.remove_safe` unchanged), call `_link_dependency_dirs(project_root, effective_tmp_path)` then `return _run_module_wide_verify_algorithm(module_wide_verify_cmd, effective_tmp_path, project_root)`. The function's public signature, its docstring's returned-value contract (`"clean"`/`"pre-existing-failures"`, raises on infrastructure failure), and its behavior for any standalone caller are UNCHANGED.
  2. Add a new module-level function `compute_batch_baselines(commands: list[tuple[str, str, Path | None]], checkout_path: Path, project_root: Path) -> dict[str, list[str]]` accepting an ALREADY-CHECKED-OUT `checkout_path` (no checkout or teardown of its own) and a list of `(name, command, cwd_override)` triples — `cwd_override` is `None` (use `checkout_path` directly as the effective cwd) or an already-resolved absolute `Path` (use it directly), mirroring `_run_verify_gate`'s `cwd_override` handling. For each triple, run `command` via `_run_verify_in(command, cwd_override or checkout_path)` TWICE unconditionally (union-of-two-runs corroboration — no third control-run step, unlike the module-wide algorithm; see `_mill/discussion.md`'s `gap2-baseline-corroboration` Decision), and for each run pass its combined `stdout + stderr` output to `_implementer_common._extract_failure_signatures` (import via `from _implementer_common import _extract_failure_signatures` alongside the existing `from _implementer_common import _posix_shell_run_args` import). The returned dict's value for each `name` is the UNION (deduplicated, order-preserving by first occurrence across both runs) of both runs' extracted (unnormalized) signature lists — an empty list (present, not an absent key) when a command has zero failures on both runs.
- **Commit:** `refactor(verify-baseline): thin compute_baseline wrapper; add per-batch baseline computation`

### Card 18: Tests — refactor safety and basic multi-command computation

- **Context:**
  - `plugins/mill/scripts/_verify_baseline.py`
  - `plugins/mill/scripts/_implementer_common.py`
- **Edits:**
  - `plugins/mill/unit_tests/test-verify-baseline.py`
- **Creates:** none
- **Deletes:** none
- **Moves:** none
- **Requirements:** Following this file's existing monkeypatch/in-memory fixture style (patching `_verify_baseline._subprocess_util.run`, `_verify_baseline._run_verify_in`, `_verify_baseline._junction.create`, `_verify_baseline._worktree.remove_safe` — no real git), verify: (a) this file's two existing cases (Case 1: `core.longpaths=true` argv shape; Case 2: 12-hex-char transient-worktree basename) still pass unchanged after the `_checkout_parent_branch`/`_link_dependency_dirs`/`_run_module_wide_verify_algorithm` extraction — a pure refactor, so keep both existing assertions exactly as-is and confirm they still exercise `compute_baseline`'s public contract identically; update their mocked `_run_verify_in` return value from a bare `0` to `(0, "")` to match card 16's new `tuple[int, str]` return shape. Add: (b) a new case calling `compute_batch_baselines` directly against a mocked `checkout_path` with at least two distinct `(name, command, cwd)` triples, confirming it returns that many independent entries keyed by name, each holding its own command's signature list (not a shared/aliased list object); (c) a case where one command's mocked output has zero recognized FAIL-marker lines on both runs, confirming its returned value is `[]` (present, not an absent dict key).
- **Commit:** `test(verify-baseline): cover refactor safety and basic multi-command computation`

### Card 19: Tests — union-of-two-runs corroboration and mixed-cwd dependency linking

- **Context:**
  - `plugins/mill/scripts/_verify_baseline.py`
- **Edits:**
  - `plugins/mill/unit_tests/test-verify-baseline.py`
- **Creates:** none
- **Deletes:** none
- **Moves:** none
- **Requirements:** Add: (d) a case where a mocked command's first run's output contains failure-marker line A and its second run's output contains a different failure-marker line B (neither run contains both), confirming `compute_batch_baselines`'s returned signature list for that command is the UNION `[A, B]` (both present) rather than one run's set overwriting the other; (e) a case exercising shared-checkout orchestration at the `_verify_baseline` module level: call `_link_dependency_dirs` at TWO distinct resolved target paths (mirroring how batch 6's `_run_baseline_stage` will call it — once at the checkout root for a `cwd: git_root`/plain-string command, once at a hub-relative sub-path for a `cwd: hub` command) against one shared mocked `checkout_path`, then call `compute_batch_baselines` with commands resolving to each of those two paths via their `cwd_override` entries, confirming each command runs successfully at its own cwd within the one shared checkout and dependency dirs are linked at both resolved paths.
- **Commit:** `test(verify-baseline): cover union corroboration and mixed-cwd dependency linking`

## Batch Tests

`verify:` runs `run-all.py --only test-verify-baseline.py` (the unit test), the sole unit test file covering `_verify_baseline.py`. The existing real-git `integration_tests/test-verify-baseline.py` (unmodified by this batch) exercises `compute_baseline`'s end-to-end behavior across six cases and must continue to pass unchanged after this refactor — run it manually once during implementation to confirm (it is not part of this batch's fast `verify:` gate per the real-git/slow integration-test convention).
