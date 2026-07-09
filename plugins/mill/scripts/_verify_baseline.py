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
"""
from __future__ import annotations

import subprocess
import sys
import uuid
from pathlib import Path

import _junction
import _subprocess_util
import _worktree
from _implementer_common import _posix_shell_run_args

# Fixed candidate list of gitignored dependency directories to reuse from the
# task worktree's already-installed state. There is no existing mill-config.yaml
# venv/dependency-dir convention to mirror (confirmed absent from both the hub
# config and the template schema) -- this fixed probe-list IS the mechanism.
_DEPENDENCY_DIR_CANDIDATES = (".venv", "venv", "node_modules", "vendor")


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
    tmp_path = scratch_dir / f"verify-baseline-{uuid.uuid4().hex}"

    # core.longpaths is scoped to this single invocation (via -c, not a
    # persistent git config write) so deep-path Windows repos don't hit a
    # transient "Filename too long" failure that would silently disable the
    # baseline gate -- see the module docstring and #615/#620.
    worktree_add_result = _subprocess_util.run(
        ["git", "-C", str(git_root), "-c", "core.longpaths=true", "worktree", "add", str(tmp_path), parent_sha],
    )
    if worktree_add_result.returncode != 0:
        raise RuntimeError(
            f"git worktree add failed (target={tmp_path}, sha={parent_sha}): "
            f"{worktree_add_result.stderr.strip()}"
        )

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
        for name in _DEPENDENCY_DIR_CANDIDATES:
            src = project_root / name
            if src.exists():
                _junction.create(
                    src,
                    (tmp_path / cwd_override_relative / name)
                    if cwd_override_relative is not None
                    else (tmp_path / name),
                )

        if _run_verify_in(module_wide_verify_cmd, effective_tmp_path) == 0:
            return "clean"

        # Flakiness-guard retry: a single transient-worktree failure is never
        # trusted on its own.
        if _run_verify_in(module_wide_verify_cmd, effective_tmp_path) == 0:
            return "clean"

        # Second consecutive transient-worktree failure. Corroborate with a
        # control run in the task worktree itself before caching a real
        # pre-existing-failures verdict.
        if _run_verify_in(module_wide_verify_cmd, project_root) != 0:
            return "pre-existing-failures"

        print(
            "[_verify_baseline] warning: module-wide verify failed twice in "
            "transient worktree but passed in task worktree -- treating as "
            "path/environment-induced, caching 'clean'",
            file=sys.stderr,
        )
        return "clean"
    finally:
        _worktree.remove_safe(tmp_path, cwd=git_root, junctions_cfg={})


def _run_verify_in(module_wide_verify_cmd: str, cwd: Path) -> int:
    """Run `module_wide_verify_cmd` with cwd set to `cwd`; return the exit code."""
    run_args, run_kwargs = _posix_shell_run_args(module_wide_verify_cmd)
    result = subprocess.run(
        run_args,
        capture_output=True,
        text=True,
        cwd=cwd,
        **run_kwargs,
    )
    return result.returncode
