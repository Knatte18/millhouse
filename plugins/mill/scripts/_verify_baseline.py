"""
Transient-worktree computation of the module-wide verify baseline.

The baseline-aware verify gate (`_implementer_common._run_verify_gates`)
needs a one-time, task-scoped answer to "does the parent branch's own
module-wide verify command already fail, independent of anything this
task's batches have done?" This module is the ONLY place that runs
`module_wide_verify_cmd` against the parent branch's own content --
`_run_verify_gates` only ever reads the cached result `compute_baseline`
produces (via `_status.get_module_verify_baseline`/`set_module_verify_baseline`);
it never computes or persists a baseline itself.

The computation checks out the parent branch's current tip into a fresh,
throwaway worktree under `<project_root>/.scratch/` (never the system temp
directory, never the task worktree's own working tree/index), reuses the
task worktree's already-installed gitignored dependency state via
filesystem junctions, and runs `module_wide_verify_cmd` there.

Return contract -- `compute_baseline` returns one of exactly two strings:

    "clean"               -- the parent branch's own module-wide verify
                             passes (directly, or after the retry/control
                             corroboration below rules out flakiness and
                             path/environment mismatch).
    "pre-existing-failures" -- the parent branch's own module-wide verify
                             is genuinely broken, confirmed by two
                             consecutive transient-worktree failures AND a
                             matching failure in the task worktree itself.

A single failing run is never trusted on its own: caching
"pre-existing-failures" on a first failure would silently disable the
regression-catching gate this baseline check feeds (#541) for the rest of
the task, which is the unsafe direction (a false "clean" merely costs one
over-strict gate later; a false "pre-existing-failures" removes the gate
entirely). See the retry-then-control-check sequence in
`compute_baseline`'s docstring for the two corroboration steps.

`compute_baseline` raises on any INFRASTRUCTURE failure (parent-branch
rev-parse failure, `git worktree add` failure, junction creation failure)
-- it does not itself decide the fail-safe policy for those cases. The
caller (`millpy-implement.py`'s `--stage baseline`) is responsible for
catching such exceptions and falling back to "leave the baseline
unset," which makes the next `_run_verify_gates` call run the module-wide
gate strictly (the same fail-safe behavior as an inconclusive read).

Public API:
    compute_baseline(project_root, git_root, parent_branch, module_wide_verify_cmd) -> str
        Returns "clean" or "pre-existing-failures". Raises RuntimeError /
        OSError on infrastructure failure.
    compute_batch_baselines(commands, checkout_path, project_root) -> dict[str, list[str]]
        Per-batch, multi-command companion to compute_baseline: takes an
        ALREADY-CHECKED-OUT checkout_path (no checkout/teardown of its own)
        so many commands can share one transient checkout, and returns a
        union-of-two-runs failure-signature list per command name instead
        of a binary "clean"/"pre-existing-failures" verdict.
"""
from __future__ import annotations

import subprocess
import sys
import uuid
from pathlib import Path

import _junction
import _subprocess_util
import _worktree
from _implementer_common import _extract_failure_signatures, _posix_shell_run_args

# Fixed candidate list of gitignored dependency directories to reuse from the
# task worktree's already-installed state. There is no existing mill-config.yaml
# venv/dependency-dir convention to mirror (confirmed absent from both the hub
# config and the template schema) -- this fixed probe-list IS the mechanism.
_DEPENDENCY_DIR_CANDIDATES = (".venv", "venv", "node_modules", "vendor")


def _checkout_parent_branch(project_root: Path, git_root: Path, parent_branch: str) -> Path:
    """
    Check out `parent_branch`'s current tip into a fresh transient worktree.

    Resolves the parent branch's current tip SHA via `git rev-parse`, then
    creates a fresh, uniquely-named subdirectory under
    `<project_root>/.scratch/` and runs `git worktree add` (detached HEAD, no
    new branch) at that SHA, with `-c core.longpaths=true` scoped to this
    single invocation (never a persistent git config write) so deep-path
    Windows repos don't hit a transient "Filename too long" failure that
    would silently disable the baseline gate -- see the module docstring and
    #615/#620.

    Args:
        project_root: Absolute path to the task worktree root (where
            `.scratch/` lives).
        git_root: Absolute path to the repo root `git` commands run against.
        parent_branch: Name of the parent branch to snapshot (e.g. "main").

    Returns:
        The absolute path to the newly-created transient worktree.

    Raises:
        RuntimeError: `git rev-parse` or `git worktree add` failed.
    """
    rev_parse_result = _subprocess_util.run(
        ["git", "-C", str(git_root), "rev-parse", parent_branch],
    )
    if rev_parse_result.returncode != 0:
        raise RuntimeError(
            f"git rev-parse {parent_branch!r} failed: {rev_parse_result.stderr.strip()}"
        )
    parent_sha = rev_parse_result.stdout.strip()

    scratch_dir = project_root / ".scratch"
    scratch_dir.mkdir(parents=True, exist_ok=True)
    # 12 hex characters (~2^48 combinations) is effectively collision-free for
    # a short-lived per-invocation scratch directory, and reclaims path
    # budget for Windows MAX_PATH on repos with deep fixture trees (#629).
    # This is a best-effort mitigation, not a guaranteed fix -- the
    # non-blocking fail-safe in `_run_baseline_stage` (which never raises; on
    # any failure it leaves the baseline field unset and the next
    # `_run_verify_gates` call runs the gate strictly) remains the actual
    # safety net regardless of whether this shortening is sufficient for any
    # given repo's fixture depth.
    tmp_path = scratch_dir / f"verify-baseline-{uuid.uuid4().hex[:12]}"

    worktree_add_result = _subprocess_util.run(
        ["git", "-C", str(git_root), "-c", "core.longpaths=true", "worktree", "add", str(tmp_path), parent_sha],
    )
    if worktree_add_result.returncode != 0:
        raise RuntimeError(
            f"git worktree add failed (target={tmp_path}, sha={parent_sha}): "
            f"{worktree_add_result.stderr.strip()}"
        )

    return tmp_path


def _link_dependency_dirs(project_root: Path, target_path: Path) -> None:
    """
    Junction every existing gitignored dependency dir into `target_path`.

    For each name in `_DEPENDENCY_DIR_CANDIDATES` whose `project_root / name`
    exists, junctions it into `target_path / name` via `_junction.create`.

    Unlike the inline loop this was extracted from, this function does not
    branch on `cwd_override_relative` -- the caller is responsible for
    resolving that into a single, already-concrete `target_path` (either
    `tmp_path / cwd_override_relative` or plain `tmp_path`) before calling.

    Args:
        project_root: Absolute path to the task worktree root, where
            gitignored dependency dirs are probed for reuse.
        target_path: The already-resolved effective checkout path to
            junction dependency dirs into.

    Raises:
        OSError: junction creation failed.
        ValueError: link_path already exists (dependency dir collision).
    """
    for name in _DEPENDENCY_DIR_CANDIDATES:
        src = project_root / name
        if src.exists():
            _junction.create(src, target_path / name)


def compute_baseline(
    project_root: Path,
    git_root: Path,
    parent_branch: str,
    module_wide_verify_cmd: str,
    *,
    cwd_override_relative: Path | None = None,
) -> str:
    """
    Compute whether the parent branch's own module-wide verify already fails.

    Implementation, in order:
        1. Resolve the parent branch's current tip SHA.
        2. Create a fresh, uniquely-named subdirectory under
           `<project_root>/.scratch/` as the transient worktree target.
        3. `git worktree add <tmp-path> <parent-sha>` (detached HEAD, no new
           branch) at that SHA.
        4. From here on, everything is wrapped in try/finally so the
           transient worktree is torn down via `_worktree.remove_safe`
           unconditionally -- on success, on a verify failure, and on any
           exception raised inside the try block.
        5. Reuse the task worktree's already-installed gitignored dependency
           state: for each name in `_DEPENDENCY_DIR_CANDIDATES` that exists
           at the task worktree's top level, junction it into the transient
           worktree.
        6. Run `module_wide_verify_cmd` with cwd set to the transient
           worktree. Exit code 0 -> return "clean" immediately.
        7. On a non-zero exit, re-run the same command in the same transient
           worktree once more (the flakiness-guard retry). A pass here means
           the first failure was a spurious fluke -> return "clean".
        8. If the retry also fails, run `module_wide_verify_cmd` once more in
           `project_root` itself (the task worktree -- always safe, no
           mutation) as a control check. If the control run also fails,
           return "pre-existing-failures" -- both flakiness and a
           deterministic path/environment mismatch have been ruled out. If
           the control run passes, the two transient-worktree failures are
           path/environment-induced (not a real pre-existing failure): warn
           on stderr and return "clean" instead.

    Args:
        project_root: Absolute path to the task worktree root (where
            `.scratch/` lives and where gitignored dependency dirs are
            probed for reuse).
        git_root: Absolute path to the repo root `git` commands run against
            (passed to `git -C <git_root> ...` for rev-parse and worktree
            add/remove).
        parent_branch: Name of the parent branch to snapshot (e.g. "main").
        module_wide_verify_cmd: The module-wide verify command string to run,
            verbatim, in both the transient worktree and (for the control
            check) the task worktree.
        cwd_override_relative: Hub-relative path fragment (not an absolute cwd)
            resolved by `_plan_dag.parse_verify_field` when the overview's
            `verify:` mapping resolves to `cwd: hub` in a nested-hub-layout
            repo. When set, both the transient-worktree verify subprocess's
            cwd and the dependency-junction targets are re-anchored to
            `tmp_path / cwd_override_relative` -- the temp checkout's
            equivalent of the real worktree's hub sub-directory -- instead of
            `tmp_path` (which mirrors `git_root`, not `hub_root`). When None
            (plain-string `verify:` or a `cwd: git_root` resolution), behavior
            is unchanged: everything runs at `tmp_path` directly.

    Returns:
        The literal string "clean" or "pre-existing-failures".

    Raises:
        RuntimeError: `git rev-parse` or `git worktree add` failed.
        OSError: junction creation failed.
        ValueError: link_path already exists (dependency dir collision).
    """
    tmp_path = _checkout_parent_branch(project_root, git_root, parent_branch)

    # The temp checkout at tmp_path mirrors git_root, not hub_root. When the
    # verify subprocess must run one or more levels below that (cwd: hub in a
    # nested-hub-layout repo), both the subprocess cwd and the dependency
    # junctions need to be re-anchored to the equivalent hub sub-directory
    # inside the temp checkout. Flat-layout behavior (tmp_path directly) is
    # unchanged when cwd_override_relative is None.
    effective_tmp_path = (
        tmp_path / cwd_override_relative if cwd_override_relative is not None else tmp_path
    )

    try:
        _link_dependency_dirs(project_root, effective_tmp_path)

        return _run_module_wide_verify_algorithm(
            module_wide_verify_cmd, effective_tmp_path, project_root
        )
    finally:
        _worktree.remove_safe(tmp_path, cwd=git_root, junctions_cfg={})


def _run_module_wide_verify_algorithm(
    module_wide_verify_cmd: str, effective_tmp_path: Path, project_root: Path
) -> str:
    """
    Run the 3-run/control-check module-wide verify corroboration algorithm.

    Implementation, in order:
        1. Run `module_wide_verify_cmd` with cwd set to `effective_tmp_path`.
           Exit code 0 -> return "clean" immediately.
        2. On a non-zero exit, re-run the same command in the same
           `effective_tmp_path` once more (the flakiness-guard retry). A pass
           here means the first failure was a spurious fluke -> return "clean".
        3. If the retry also fails, run `module_wide_verify_cmd` once more in
           `project_root` itself (the task worktree -- always safe, no
           mutation) as a control check. If the control run also fails,
           return "pre-existing-failures" -- both flakiness and a
           deterministic path/environment mismatch have been ruled out. If
           the control run passes, the two `effective_tmp_path` failures are
           path/environment-induced (not a real pre-existing failure): warn
           on stderr and return "clean" instead.

    Args:
        module_wide_verify_cmd: The module-wide verify command string to run,
            verbatim, in both `effective_tmp_path` and (for the control
            check) `project_root`.
        effective_tmp_path: The transient checkout's effective cwd to run the
            command against for the first two runs.
        project_root: Absolute path to the task worktree root, used as cwd
            for the control-check run.

    Returns:
        The literal string "clean" or "pre-existing-failures".
    """
    rc, _output = _run_verify_in(module_wide_verify_cmd, effective_tmp_path)
    if rc == 0:
        return "clean"

    # Flakiness-guard retry: a single transient-worktree failure is never
    # trusted on its own.
    rc, _output = _run_verify_in(module_wide_verify_cmd, effective_tmp_path)
    if rc == 0:
        return "clean"

    # Second consecutive transient-worktree failure. Corroborate with a
    # control run in the task worktree itself before caching a real
    # pre-existing-failures verdict.
    rc, _output = _run_verify_in(module_wide_verify_cmd, project_root)
    if rc != 0:
        return "pre-existing-failures"

    print(
        "[_verify_baseline] warning: module-wide verify failed twice in "
        "transient worktree but passed in task worktree -- treating as "
        "path/environment-induced, caching 'clean'",
        file=sys.stderr,
    )
    return "clean"


def _run_verify_in(module_wide_verify_cmd: str, cwd: Path) -> tuple[int, str]:
    """
    Run `module_wide_verify_cmd` with cwd set to `cwd`.

    Returns:
        A tuple of (exit code, combined stdout + stderr).
    """
    run_args, run_kwargs = _posix_shell_run_args(module_wide_verify_cmd)
    result = subprocess.run(
        run_args,
        capture_output=True,
        text=True,
        cwd=cwd,
        **run_kwargs,
    )
    return result.returncode, result.stdout + result.stderr


def compute_batch_baselines(
    commands: list[tuple[str, str, Path | None]],
    checkout_path: Path,
    project_root: Path,
) -> dict[str, list[str]]:
    """
    Compute per-batch verify-command failure-signature baselines.

    Unlike `compute_baseline`, this function performs NO checkout and NO
    teardown of its own -- `checkout_path` must already be a live, fully
    linked transient worktree (e.g. produced by `_checkout_parent_branch` +
    `_link_dependency_dirs`, shared across the module-wide command and every
    per-batch command by the caller). This lets a caller batch many verify
    commands against one shared checkout instead of checking out once per
    command.

    For each `(name, command, cwd_override)` triple, runs `command` via
    `_run_verify_in` TWICE unconditionally against its own effective cwd
    (`cwd_override` if not None, else `checkout_path` directly -- mirroring
    `_run_verify_gate`'s `cwd_override` handling). Each run's combined
    stdout+stderr is passed through `_extract_failure_signatures`; the
    returned signature list for that command is the union (deduplicated,
    order-preserving by first occurrence across both runs) of both runs'
    extracted (unnormalized) signatures.

    This is a union-of-two-runs corroboration, not the module-wide
    algorithm's binary verdict with a third task-worktree control run: a
    flaky pre-existing failure that reproduces on only one of the two runs
    still needs to be in the baseline (so it doesn't spuriously block a
    later batch), and finalize's own verify-replay run against the real,
    in-progress worktree is the natural downstream corroboration point for
    the module-wide path's control-run role. See
    `_mill/discussion.md`'s `gap2-baseline-corroboration` Decision.

    Args:
        commands: A list of `(name, command, cwd_override)` triples.
            `cwd_override` is `None` (use `checkout_path` directly) or an
            already-resolved absolute `Path` to run `command` in instead.
        checkout_path: An already-checked-out, already-linked transient
            worktree path. Never checked out or torn down by this function.
        project_root: Absolute path to the task worktree root. Unused by
            this function's own logic today, but accepted for parity with
            `compute_baseline`'s signature and to keep the caller's call
            sites uniform; kept for forward compatibility.

    Returns:
        A dict keyed by `name`, each value the union (deduplicated,
        order-preserving) of both runs' extracted raw failure-signature
        lines for that command's `command`. A command with zero failures on
        both runs maps to `[]` (present, not an absent key). Each value is
        an independent list object, never aliased across names.
    """
    del project_root  # unused today; kept for signature parity/forward compat.
    results: dict[str, list[str]] = {}
    for name, command, cwd_override in commands:
        effective_cwd = cwd_override if cwd_override is not None else checkout_path
        signatures: list[str] = []
        seen: set[str] = set()
        for _run_index in range(2):
            _rc, output = _run_verify_in(command, effective_cwd)
            for line in _extract_failure_signatures(output):
                if line not in seen:
                    seen.add(line)
                    signatures.append(line)
        results[name] = signatures
    return results
