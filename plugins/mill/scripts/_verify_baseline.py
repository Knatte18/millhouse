"""
No-checkout computation of the module-wide verify baseline.

The baseline-aware verify gate (`_implementer_common._run_verify_gates`) needs a one-time,
task-scoped answer to "does the parent branch's own module-wide verify command already fail,
independent of anything this task's batches have done?"
This module is the ONLY place that runs `module_wide_verify_cmd` (and, via `compute_batch_baselines`,
each batch's own `verify:` command) to answer that question -- `_run_verify_gates` only ever reads
the cached result `compute_baseline` produces (via
`_status.get_module_verify_baseline`/`set_module_verify_baseline`);
it never computes or persists a baseline itself.

The computation runs directly against an already-resolved `cwd` inside the task worktree itself --
never a checkout, never a transient worktree under `.scratch/`.
This is safe because at `--stage baseline` time (before batch 1's implementer is ever dispatched)
the task worktree's source content already equals the merge-base content, per Decision
`capture-site` in `_mill/discussion.md`: there is nothing left for a parent-branch checkout to
re-derive that the task worktree doesn't already hold.

Return contract -- `compute_baseline` returns a `tuple[str, list[str]]`:

    verdict -- one of exactly two strings:
        "clean" -- the module-wide verify passes (directly, or after the flakiness-guard retry
        below rules out a spurious first failure).
        "pre-existing-failures" -- the module-wide verify is genuinely broken, confirmed by two
        consecutive failures at `cwd`.
    signatures -- the deduplicated, order-preserving union of the raw failure-signature lines
        extracted (via `_extract_failure_signatures`) from every run actually performed.

A single failing run is never trusted on its own: caching "pre-existing-failures" on a first failure
would silently disable the regression-catching gate this baseline check feeds (#541) for the rest of
the task, which is the unsafe direction (a false "clean" merely costs one over-strict gate later; a
false "pre-existing-failures" removes the gate entirely).
Two consecutive failures at `cwd` alone is now sufficient -- there is no control-check corroboration
step, since there is no separate checkout whose path/environment could differ from `cwd`.

`compute_baseline` raises only `subprocess.TimeoutExpired` -- the caller treats that as "computation
failed, leave the baseline unset," identically to before.
The caller (`millpy-implement.py`'s `--stage baseline`) is responsible for catching that exception
and falling back to "leave the baseline unset," which makes the next `_run_verify_gates` call run
the module-wide gate strictly (the same fail-safe behavior as an inconclusive read).

Public API:
    compute_baseline(cwd, module_wide_verify_cmd, *, timeout_seconds=None) -> tuple[str, list[str]]
    Returns (verdict, signatures). Raises subprocess.TimeoutExpired on a
    run exceeding timeout_seconds.
    compute_batch_baselines(commands, cwd, *, pair_cache=None, timeout_seconds=None) -> dict[str, list[str]]
    Per-batch, multi-command companion to compute_baseline: takes a
    plain cwd (the default working directory used when a given
    command's own cwd_override is None) so many commands can share one
    verify run, and returns a union-of-runs failure-signature list per
    command name instead of a binary "clean"/"pre-existing-failures"
    verdict.
    Deduplicates work across names sharing one (command, cwd) pair and
    skips the corroboration re-run when run 1 is green. Pass a
    caller-owned `pair_cache` dict to make that dedup span calls.

Both entry points accept `timeout_seconds`, a per-run wall-clock ceiling. `subprocess.TimeoutExpired`
propagates to the caller, which applies the same "leave the baseline unset" fail-safe it applies to
a genuine "pre-existing-failures" verdict -- a hung test runner would otherwise block the whole
pre-flight indefinitely before batch 1 dispatches (#1101).
"""
from __future__ import annotations

import subprocess
from pathlib import Path

import _subprocess_util
from _implementer_common import _extract_failure_signatures, _posix_shell_run_args


def compute_baseline(
    cwd: Path,
    module_wide_verify_cmd: str,
    *,
    timeout_seconds: float | None = None,
) -> tuple[str, list[str]]:
    """
    Compute whether the module-wide verify already fails at `cwd`.

    `cwd` is the caller's already-resolved absolute working directory -- resolved the same way
    `_run_verify_gate` resolves its own effective cwd: an explicit override if present, else
    `git_root`.
    There is no checkout: at `--stage baseline` time (before batch 1's implementer is ever
    dispatched) `cwd`'s content already equals the merge-base content, per Decision `capture-site`
    in `_mill/discussion.md`.

    Delegates the run-then-retry algorithm to `_run_module_wide_verify_algorithm`.

    Args:
        cwd: The already-resolved absolute working directory to run `module_wide_verify_cmd` in.
        module_wide_verify_cmd: The module-wide verify command string to run, verbatim.
        timeout_seconds: Per-run wall-clock ceiling for each verify run, or None for no ceiling.
            Applied to each of the algorithm's up-to-two runs individually, not to their total.

    Returns:
        A `(verdict, signatures)` tuple: `verdict` is `"clean"` or `"pre-existing-failures"`;
        `signatures` is the deduplicated, order-preserving union of the raw failure-signature lines
        extracted from every run actually performed.

    Raises:
        subprocess.TimeoutExpired: A verify run exceeded `timeout_seconds`. The caller applies the
            same "leave the baseline unset" fail-safe it applies to a genuine
            "pre-existing-failures" verdict.
    """
    return _run_module_wide_verify_algorithm(module_wide_verify_cmd, cwd, timeout_seconds)


def _run_module_wide_verify_algorithm(
    module_wide_verify_cmd: str,
    cwd: Path,
    timeout_seconds: float | None = None,
) -> tuple[str, list[str]]:
    """
    Run the 2-run module-wide verify flakiness-guard algorithm.

    Implementation, in order:
        1. Run `module_wide_verify_cmd` with cwd set to `cwd`.
            Exit code 0 -> return ("clean", <signatures from this run>).
        2. On a non-zero exit, re-run the same command at the same `cwd` once more (the
            flakiness-guard retry).
            A pass here means the first failure was a spurious fluke -> return ("clean", <union of
            both runs' signatures>).
        3. If the retry also fails, return ("pre-existing-failures", <union of both runs'
            signatures>) -- two consecutive failures at `cwd` is sufficient corroboration; there is
            no separate control-check cwd to fall back to.

    Args:
        module_wide_verify_cmd: The module-wide verify command string to run, verbatim.
        cwd: The already-resolved working directory to run it in for both runs.
        timeout_seconds: Per-run wall-clock ceiling passed through to `_run_verify_in`, or None for
            no ceiling. Applied to each of the up-to-two runs individually, not to their total.

    Returns:
        A `(verdict, signatures)` tuple: `verdict` is `"clean"` or `"pre-existing-failures"`;
        `signatures` is the deduplicated, order-preserving union of the raw failure-signature lines
        extracted from every run actually performed.

    Raises:
        subprocess.TimeoutExpired: One of the runs exceeded `timeout_seconds`. The caller treats
            this like any other computation failure and leaves the baseline unset.
    """
    signatures: list[str] = []
    seen: set[str] = set()

    def _accumulate(output: str) -> None:
        for line in _extract_failure_signatures(output):
            if line not in seen:
                seen.add(line)
                signatures.append(line)

    rc, output = _run_verify_in(module_wide_verify_cmd, cwd, timeout_seconds)
    _accumulate(output)
    if rc == 0:
        return "clean", signatures

    # Flakiness-guard retry: a single failure is never trusted on its own.
    rc, output = _run_verify_in(module_wide_verify_cmd, cwd, timeout_seconds)
    _accumulate(output)
    if rc == 0:
        return "clean", signatures

    # Second consecutive failure at cwd is sufficient corroboration.
    return "pre-existing-failures", signatures


def _run_verify_in(
    module_wide_verify_cmd: str, cwd: Path, timeout_seconds: float | None = None
) -> tuple[int, str]:
    """
    Run `module_wide_verify_cmd` with cwd set to `cwd`.

    Args:
        module_wide_verify_cmd: The command string to run, verbatim.
        cwd: The working directory to run it in.
        timeout_seconds: Wall-clock ceiling for the run, or None for no ceiling.
            A hung test runner or a build server waiting on a lock in the transient checkout would
            otherwise block the whole `--stage baseline` pre-flight indefinitely, before batch 1 has
            dispatched and with no output (#1101);
            the module's fail-safe design covers a crash but not a hang.

    Returns:
        A tuple of (exit code, combined stdout + stderr).

    Raises:
        subprocess.TimeoutExpired: The command exceeded `timeout_seconds`.
            Deliberately propagated rather than converted to a non-zero exit code: every caller
            already treats an exception as "computation failed, leave the baseline unset," which
            makes the hang degrade exactly the way every other infrastructure failure does, whereas
            a fabricated non-zero exit would feed a truncated output into the signature extractor
            and cache a bogus baseline.
    """
    run_args, run_kwargs = _posix_shell_run_args(module_wide_verify_cmd)
    result = subprocess.run(
        run_args,
        capture_output=True,
        text=True,
        cwd=cwd,
        timeout=timeout_seconds,
        **run_kwargs,
    )
    return result.returncode, result.stdout + result.stderr


def compute_batch_baselines(
    commands: list[tuple[str, str, Path | None]],
    cwd: Path,
    *,
    pair_cache: dict[tuple[str, Path], list[str]] | None = None,
    timeout_seconds: float | None = None,
) -> dict[str, list[str]]:
    """
    Compute per-batch verify-command failure-signature baselines.

    `cwd` is simply the default working directory used when a given command's own `cwd_override` is
    `None` -- this function performs no checkout of its own.
    This lets a caller batch many verify commands against one shared `cwd` in a single call.

    Work is keyed on the `(command, effective_cwd)` pair, NOT on the batch `name` (`cwd_override` if
    not None, else `cwd` directly -- mirroring `_run_verify_gate`'s `cwd_override`
    handling).
    Plans whose last batch verifies the union of the earlier batches' commands are a common and
    reasonable shape, and re-running an identical command string in an identical cwd cannot
    corroborate anything the first evaluation of that pair did not already establish (#1098);
    each distinct pair is therefore evaluated once and its signature list fanned out (as an
    independent copy) to every batch name that maps to it.

    That dedup only spans ONE call unless the caller supplies `pair_cache`.
    The production call site drives a batch at a time so a failing batch never aborts a sibling
    (`millpy-implement.py`'s per-batch try/except), which means a call-local cache is re-created
    empty per batch and can never fire (#1101);
    a caller-owned `pair_cache` dict threaded across those calls restores the dedup without giving
    up that per-batch isolation.

    Each pair is run via `_run_verify_in` up to TWICE.
    Each run's combined stdout+stderr is passed through `_extract_failure_signatures`;
    the returned signature list for that pair is the union (deduplicated, order-preserving by
    first occurrence across both runs) of both runs' extracted (unnormalized) signatures.
    Run 2 is SKIPPED when run 1 exits 0 with zero extracted signatures: there is nothing to
    corroborate, and a green parent branch is the normal state rather than the exception, so paying
    the retry cost there doubles every task's baseline pre-flight for no baseline content (#1098).
    This mirrors `compute_baseline`'s module-wide algorithm, which likewise returns "clean"
    immediately on a zero exit and only re-runs after a non-zero one.

    This is a union-of-two-runs corroboration, not the module-wide algorithm's binary verdict with a
    third task-worktree control run: a flaky pre-existing failure that reproduces on only one of the
    two runs still needs to be in the baseline (so it doesn't spuriously block a later batch), and
    finalize's own verify-replay run against the real, in-progress worktree is the natural
    downstream corroboration point for the module-wide path's control-run role.
    See `_mill/discussion.md`'s `gap2-baseline-corroboration` Decision.

    Args:
        commands: A list of `(name, command, cwd_override)` triples. `cwd_override` is `None` (use
            `cwd` directly) or an already-resolved absolute `Path` to run `command` in instead.
        cwd: The default working directory used when a given command's own `cwd_override` is
            `None`.
        pair_cache: Optional caller-owned `{(command, effective_cwd): signatures}` dict, mutated in
            place, that makes the dedup span every call sharing it -- pass one dict across a whole
            shared-checkout pre-flight.
            `None` (the default) falls back to a call-local cache, i.e. dedup within this call only.
            Only ever share a cache across calls whose commands resolve to the SAME `cwd`: the key
            carries no cwd identity beyond what is already part of it.
        timeout_seconds: Per-run wall-clock ceiling passed through to `_run_verify_in`, or None for
            no ceiling. Applied to each run individually, not to a pair's two runs together.

    Raises:
        subprocess.TimeoutExpired: A run exceeded `timeout_seconds`. Nothing is written to
            `pair_cache` for a pair whose evaluation raised, so a later call may retry it.

    Returns:
        A dict keyed by `name`, each value the union (deduplicated, order-preserving) of the runs'
        extracted raw failure-signature lines for that command's `(command, effective_cwd)` pair.
        A command with zero failures maps to `[]` (present, not an absent key).
        Each value is an independent list object, never aliased across names -- including across
        names that share one `(command, effective_cwd)` pair.
    """
    by_pair = pair_cache if pair_cache is not None else {}
    results: dict[str, list[str]] = {}
    for name, command, cwd_override in commands:
        effective_cwd = cwd_override if cwd_override is not None else cwd
        pair = (command, effective_cwd)
        if pair not in by_pair:
            by_pair[pair] = _signatures_for_pair(command, effective_cwd, timeout_seconds)
        # Copy per name: callers treat each value as their own mutable list.
        results[name] = list(by_pair[pair])
    return results


def _signatures_for_pair(
    command: str, effective_cwd: Path, timeout_seconds: float | None = None
) -> list[str]:
    """
    Run one `(command, effective_cwd)` pair and return its union-of-runs failure signatures.

    Runs `command` in `effective_cwd` once;
    re-runs it once more -- unioning both runs' signatures, deduplicated and order-preserving by
    first occurrence -- unless run 1 exited 0 with zero extracted signatures, in which case there is
    nothing for a second run to corroborate.

    Args:
        command: The verify command string to run, verbatim.
        effective_cwd: The already-resolved working directory to run it in.
        timeout_seconds: Per-run wall-clock ceiling, or None for no ceiling.

    Returns:
        The extracted raw failure-signature lines, `[]` when the command produced none.

    Raises:
        subprocess.TimeoutExpired: A run exceeded `timeout_seconds`.
    """
    signatures: list[str] = []
    seen: set[str] = set()
    for run_index in range(2):
        rc, output = _run_verify_in(command, effective_cwd, timeout_seconds)
        for line in _extract_failure_signatures(output):
            if line not in seen:
                seen.add(line)
                signatures.append(line)
        if run_index == 0 and rc == 0 and not signatures:
            break
    return signatures
