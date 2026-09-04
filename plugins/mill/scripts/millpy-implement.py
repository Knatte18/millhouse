"""millpy-implement.py — per-batch implementer dispatch CLI.

Dispatches a per-batch implementer Sonnet session.
Encapsulates the full 10-step dispatch sequence (status update, commit, push, render, spawn) in a
single call.

Flags:
    batch_name (positional, required) batch name from the plan overview's Batch Index
    --resume-incomplete when set, the prepare/full stage reads the existing start_sha and
        implementer_session from status.md rather than re-capturing HEAD and generating a new UUID.
        Skips capture_snapshot and the housekeeping commit so the original batch-start baseline is
            preserved for finalize's completeness recount.

Exit codes:
    0 — implementer ran;
        JSON report on stdout (success or stuck)
    1 — pre-launch error (bad config, missing slug, git failure, missing file);
        message on stderr, no JSON on stdout
"""

from __future__ import annotations

import argparse
import json
import re
import _subprocess_util
import sys
import uuid
from pathlib import Path

import _agent_dispatch
import _cleanliness
import _implementer_claude
import _llm_claude
import _marker
import _parent_branch
import _paths
import _plan_dag
import _render
import _review_common
import _reviewers
import _status
import _verify_baseline
import _worktree
from _implementer_common import _forward_output, emit_prepare, finalize_from_output
from wiki import WikiStartupError


def classify_stuck_type(reason: str) -> str:
    """Classify an LLMError reason into stuck_type: verify or transient.

    Args:
        reason: Error message from LLMError.

    Returns:
        "verify" if the error indicates a missing binary / command not found;
        "transient" otherwise (timeout, dead session, rate limit, etc.).
    """
    reason_lower = reason.lower()
    # Command-not-found / missing-binary indicators
    missing_binary_signals = [
        "command not found",
        "no such file",
        "not found",
        "cannot find",
        "[errno 2]",  # ENOENT on POSIX
        "winerror 2",  # Windows equivalent
        "cannot run program",
    ]
    for signal in missing_binary_signals:
        if signal in reason_lower:
            return "verify"
    # If none of the missing-binary signals are found, treat as transient
    return "transient"


def _relative_cwd_fragment(cwd_override: Path | None, project_root: Path, git_root: Path) -> Path | None:
    """
    Collapse a `parse_verify_field`-resolved verify cwd into a hub-relative fragment.

    `cwd_override` can only ever be `project_root` (hub), `git_root`, or `None` (plain-string
    `verify:` or absent) per `parse_verify_field`'s contract.
    A `git_root`-resolved cwd already matches the transient checkout's own root,
    and `None` has no opinion, so both collapse to `None` -- "run at the checkout root directly."
    Only the `project_root` (hub) case needs an actual relative fragment, since the checkout mirrors
    `git_root`, not `project_root`.

    Returns:
        `project_root.relative_to(git_root)` when `cwd_override == project_root`;
        `None` otherwise.
    """
    return project_root.relative_to(git_root) if cwd_override == project_root else None


def _module_wide_skip_or_cached_payload(
    module_wide_verify_cmd: str | None, status_path: Path
) -> dict | None:
    """
    Return the module-wide JSON payload for the two "nothing to compute" states.

    Covers exactly the two cases where the module-wide sub-step needs no computation this
    invocation: no module-wide verify is configured at all,
    or a baseline is already cached from a prior invocation.
    Shared between the standalone Case-A path (`_run_module_wide_standalone`) and Case B's
    "module-wide is unaffected by the shared checkout" print, since both need to report the exact
    same not-computing payload shape.

    Returns:
        The ready-to-print payload dict,
        or `None` when the module-wide sub-step DOES need computation this invocation (caller must
        compute).
    """
    if module_wide_verify_cmd is None:
        return {
            "stage": "baseline",
            "substage": "module_wide",
            "result": "skipped",
            "reason": "no module-wide verify configured",
        }
    cached = _status.get_module_verify_baseline(status_path)
    if cached is not None:
        return {"stage": "baseline", "substage": "module_wide", "result": "cached", "value": cached}
    return None


def _run_module_wide_standalone(
    project_root: Path,
    git_root: Path,
    status_path: Path,
    module_wide_verify_cmd: str | None,
    module_wide_cwd_override: Path | None,
) -> None:
    """
    Run the module-wide baseline sub-step standalone, via its own `compute_baseline` checkout.

    Used only in Case A (no per-batch command needs computing this invocation), where there is
    nothing to share a checkout with -- this is the existing module-wide logic, byte-for-byte, just
    tagged with a `"substage": "module_wide"` key on the printed JSON line.

    Never raises -- every failure path prints a JSON line describing the outcome without persisting
    a baseline verdict, matching the "leave the field unset -> next `_run_verify_gates` call runs
    the gate strictly" fail-safe policy.
    """
    payload = _module_wide_skip_or_cached_payload(module_wide_verify_cmd, status_path)
    if payload is not None:
        print(json.dumps(payload))
        return

    try:
        parent_branch = _parent_branch.resolve(status_path, interactive=False)
    except Exception as e:
        print(f"[millpy-implement] baseline parent-branch resolution failed: {e}", file=sys.stderr)
        print(json.dumps({"stage": "baseline", "substage": "module_wide", "result": "error", "reason": str(e)}))
        return

    cwd_override_relative = _relative_cwd_fragment(module_wide_cwd_override, project_root, git_root)

    try:
        result = _verify_baseline.compute_baseline(
            project_root,
            git_root,
            parent_branch,
            module_wide_verify_cmd,
            cwd_override_relative=cwd_override_relative,
        )
    except Exception as e:
        print(f"[millpy-implement] baseline computation failed: {e}", file=sys.stderr)
        print(json.dumps({"stage": "baseline", "substage": "module_wide", "result": "error", "reason": str(e)}))
        return

    _status.set_module_verify_baseline(status_path, result)
    print(json.dumps({"stage": "baseline", "substage": "module_wide", "result": "computed", "value": result}))


def _enumerate_batch_verify_triples(
    plan_base: Path, project_root: Path, git_root: Path
) -> list[tuple[str, str, Path | None]]:
    """
    Return `(batch_name, verify_cmd, cwd)` triples read directly off each batch file's own
    frontmatter.

    Deliberately NOT `_plan_dag.iter_batch_verifies` -- that function suppresses a batch's verify
    command when a strictly-later batch's `Deletes:`/`Moves:` bullets reference a path it names,
    which is correct for DAG-wide verify replay but wrong here: a batch's own `--stage finalize`
    always runs its OWN verify command regardless of what a later batch will eventually delete, so
    its baseline must always be computed too.
    See `_mill/discussion.md`'s `gap2-enumerate-batches-directly-not-via-iter-batch-verifies`
    Decision.

    Args:
        plan_base: Directory containing `00-overview.md` and every batch file.
        project_root: Absolute path to the task worktree root, passed through to
        `parse_verify_field` for `cwd: hub` resolution.
        git_root: Absolute path to the repo root, passed through to `parse_verify_field` for `cwd:
        git_root` resolution.

    Returns:
        One `(name, command, cwd)` triple per batch file whose own `verify:` frontmatter field
        resolves to a non-`None` command. `00-overview.md` is always excluded. `cwd` is `None` for
        the plain-string form or the caller's existing default;
        the resolved `Path` for the mapping form.
    """
    triples: list[tuple[str, str, Path | None]] = []
    for batch_path in sorted(plan_base.glob("??-*.md")):
        if batch_path.name == "00-overview.md":
            continue
        frontmatter = _plan_dag._read_batch_frontmatter(batch_path)
        name = frontmatter.get("batch")
        command, cwd = _plan_dag.parse_verify_field(frontmatter, project_root, git_root)
        if command is None:
            continue
        triples.append((name, command, cwd))
    return triples


def _run_baseline_stage(
    project_root: Path,
    git_root: Path,
    status_path: Path,
    module_wide_verify_cmd: str | None,
    module_wide_cwd_override: Path | None,
    plan_base: Path,
    baseline_prepare_cmd: str | None,
) -> int:
    """
    Compute (idempotent, no-op-if-already-cached) both baseline sub-steps and persist them.

    Restructured into two INDEPENDENT sub-steps that both run on every invocation, in either order:
    (1) the module-wide `module_verify_baseline` scalar (unchanged existing mechanism), and (2) a
    new per-batch `verify_baseline_failures` list per batch, computed eagerly for every batch before
    batch 1 ever dispatches.
    Per-batch computation is gated ONLY by that batch's own idempotency check (does it already have
    a stored baseline?) -- never by whether a module-wide verify is configured,
    or by the module-wide baseline's own cache state.
    See `_mill/discussion.md`'s `gap2-baseline-stage-independent-of-module-wide-early-returns`
    Decision.

    Implementation, in order:
        1. Enumerate every batch's own verify command directly off its frontmatter
            (`_enumerate_batch_verify_triples`), then split into `batches_needing_computation` (no
            stored baseline yet) and `cached_batches` (already computed by a prior invocation).
        2. Case A -- nothing per-batch needs computing: run the module-wide sub-step exactly as it
            always has, standalone (its own `compute_baseline` checkout, if it needs one) -- there
            is nothing to share a checkout with.
            Print both JSON lines and return.
        3. Case B -- at least one batch needs computing: resolve the parent
        branch once, then perform ONE shared checkout (`compute_baseline`
        is deliberately bypassed here -- it would re-checkout) covering
        the module-wide command (if it also needs computing) and every
        per-batch command, linking dependency dirs at every distinct
        effective cwd fragment actually in play.
            A shared-setup failure
        (checkout or linking) marks every batch needing computation as
        errored and marks the module-wide sub-step as errored too, but
        ONLY when it was also going to share this now-failed checkout;
        if module-wide had nothing to compute this round, its line is
        unaffected.
            On success, the module-wide command (if needed) and
        each batch's command (each independently try/excepted, so one
        batch's failure never aborts a sibling) run against the shared
        checkout, persisting on success;
            the checkout is torn down via
        `_worktree.remove_safe` in a `finally` block regardless of
        outcome.

    Never raises -- every failure path prints a JSON line describing the outcome and returns 0.
    Both `_worktree.remove_safe` teardown call sites are themselves wrapped in `try`/`except
    Exception` so a teardown failure (e.g. a still-locked dotnet build-server file) is logged to
    stderr and never propagates past this function.
    A per-batch computation failure leaves that batch's `verify_baseline_failures` UNSET, which is the
    same fail-safe direction as the module-wide mechanism's `None` default: the next
    `_run_verify_gates` call for that batch runs the gate strictly.

    Args:
        project_root: Absolute path to the task worktree root.
        git_root: Absolute path to the repo root `git` commands run against.
        status_path: Absolute path to the task's status.md file.
        module_wide_verify_cmd: The overview's module-wide verify command,
            or None when no module-wide verify is configured for this task.
        module_wide_cwd_override: The overview's module-wide verify cwd resolved by
            parse_verify_field -- one of project_root (hub_root), git_root, or None (plain-string
            verify: or absent).
        plan_base: Directory containing `00-overview.md` and every batch file, used to enumerate
            per-batch verify commands directly off disk.
        baseline_prepare_cmd: Optional build-once command (e.g. "dotnet build") to run against the
            shared transient checkout, once per distinct cwd fragment, before any verify command
            executes -- read by the caller from `pipeline.baseline_prepare_cmd` in mill-config.yaml.
            `None` (the default when the key is absent) disables this step entirely, matching
            today's behavior exactly.

    Returns:
        Always 0 -- the baseline stage never signals a pre-launch error via exit code;
        outcomes are communicated through the printed JSON lines.
    """
    batch_verify_triples = _enumerate_batch_verify_triples(plan_base, project_root, git_root)

    status_by_name = {b.get("name"): b for b in _status.read_batches(status_path)}
    batches_needing_computation: list[tuple[str, str, Path | None]] = []
    cached_batches: list[str] = []
    for name, command, cwd in batch_verify_triples:
        entry = status_by_name.get(name, {})
        if entry.get("verify_baseline_failures") is not None:
            cached_batches.append(name)
        else:
            batches_needing_computation.append((name, command, cwd))

    module_wide_needs_computation = (
        module_wide_verify_cmd is not None and _status.get_module_verify_baseline(status_path) is None
    )

    # Case A: nothing per-batch needs computing -- run the module-wide sub-step exactly as before this restructure;
    # no shared checkout is created, since there is nothing to share it with.
    if not batches_needing_computation:
        _run_module_wide_standalone(
            project_root, git_root, status_path, module_wide_verify_cmd, module_wide_cwd_override
        )
        print(
            json.dumps(
                {
                    "stage": "baseline",
                    "substage": "per_batch",
                    "computed": [],
                    "cached": cached_batches,
                    "errored": {},
                }
            )
        )
        return 0

    # Case B: at least one batch needs computing.
    # Resolve the parent branch once, up front, so both the module-wide command (if it also needs computing) and every per-batch command can share one checkout.
    try:
        parent_branch = _parent_branch.resolve(status_path, interactive=False)
    except Exception as e:
        reason = str(e)
        print(f"[millpy-implement] baseline parent-branch resolution failed: {reason}", file=sys.stderr)
        if module_wide_needs_computation:
            print(json.dumps({"stage": "baseline", "substage": "module_wide", "result": "error", "reason": reason}))
        else:
            print(json.dumps(_module_wide_skip_or_cached_payload(module_wide_verify_cmd, status_path)))
        print(
            json.dumps(
                {
                    "stage": "baseline",
                    "substage": "per_batch",
                    "computed": [],
                    "cached": cached_batches,
                    "errored": {name: reason for name, _cmd, _cwd in batches_needing_computation},
                }
            )
        )
        return 0

    # Distinct effective cwd fragments actually in play this invocation -- at most two: the checkout root itself (git_root/plain-string form) and the hub-relative fragment (hub form) -- collected across every batch needing computation PLUS the module-wide command, when it also needs computing.
    cwd_fragments: set[Path | None] = {
        _relative_cwd_fragment(cwd, project_root, git_root) for _name, _cmd, cwd in batches_needing_computation
    }
    if module_wide_needs_computation:
        cwd_fragments.add(_relative_cwd_fragment(module_wide_cwd_override, project_root, git_root))

    # One-time shared setup: checkout + dependency-junction linking at every distinct fragment.
    # A failure here is NOT isolable per-batch -- no batch can run without the shared checkout existing -- so it is caught once, marking every batch needing computation (and, when applicable, the module-wide sub-step) as errored.
    tmp_path: Path | None = None
    try:
        tmp_path = _verify_baseline._checkout_parent_branch(project_root, git_root, parent_branch)
        for fragment in cwd_fragments:
            target = tmp_path / fragment if fragment is not None else tmp_path
            _verify_baseline._link_dependency_dirs(project_root, target)
    except Exception as e:
        reason = f"checkout failed: {e}"
        print(f"[millpy-implement] baseline shared checkout failed: {reason}", file=sys.stderr)
        if module_wide_needs_computation:
            print(json.dumps({"stage": "baseline", "substage": "module_wide", "result": "error", "reason": reason}))
        else:
            print(json.dumps(_module_wide_skip_or_cached_payload(module_wide_verify_cmd, status_path)))
        print(
            json.dumps(
                {
                    "stage": "baseline",
                    "substage": "per_batch",
                    "computed": [],
                    "cached": cached_batches,
                    "errored": {name: reason for name, _cmd, _cwd in batches_needing_computation},
                }
            )
        )
        if tmp_path is not None:
            try:
                _worktree.remove_safe(tmp_path, cwd=git_root, junctions_cfg={})
            except Exception as teardown_exc:
                print(
                    f"[millpy-implement] baseline teardown failed (checkout-failure path): {teardown_exc}",
                    file=sys.stderr,
                )
        return 0

    # Build-once step: run baseline_prepare_cmd (if configured) once per distinct cwd fragment,
    # against the shared checkout, before any verify command executes -- eliminates the cold-build
    # cost otherwise paid inside the first of several doubled verify commands below (#894).
    # Failure here is deliberately non-fatal: it is logged and the verify commands still run,
    # since a real build break will also surface naturally as a verify-command failure signature,
    # which is correct baseline data rather than something to suppress by aborting early.
    if baseline_prepare_cmd:
        for fragment in cwd_fragments:
            target = tmp_path / fragment if fragment is not None else tmp_path
            try:
                prepare_rc, prepare_output = _verify_baseline._run_verify_in(baseline_prepare_cmd, target)
                if prepare_rc != 0:
                    print(
                        f"[millpy-implement] baseline_prepare_cmd failed (cwd={target}, exit={prepare_rc}): {prepare_output.strip()}",
                        file=sys.stderr,
                    )
            except Exception as e:
                print(f"[millpy-implement] baseline_prepare_cmd raised (cwd={target}): {e}", file=sys.stderr)

    try:
        # (a) Module-wide command, if it needs computing this round -- its own try/except, mirroring the standalone path, so a module-wide failure never aborts the per-batch work below.
        if module_wide_needs_computation:
            fragment = _relative_cwd_fragment(module_wide_cwd_override, project_root, git_root)
            effective_tmp_path = tmp_path / fragment if fragment is not None else tmp_path
            try:
                result = _verify_baseline._run_module_wide_verify_algorithm(
                    module_wide_verify_cmd, effective_tmp_path, project_root
                )
            except Exception as e:
                print(f"[millpy-implement] baseline computation failed: {e}", file=sys.stderr)
                module_wide_payload = {
                    "stage": "baseline",
                    "substage": "module_wide",
                    "result": "error",
                    "reason": str(e),
                }
            else:
                _status.set_module_verify_baseline(status_path, result)
                module_wide_payload = {
                    "stage": "baseline",
                    "substage": "module_wide",
                    "result": "computed",
                    "value": result,
                }
        else:
            module_wide_payload = _module_wide_skip_or_cached_payload(module_wide_verify_cmd, status_path)

        # (b) Every batch needing computation, each independently try/excepted so one batch's failure never aborts a sibling.
        computed_names: list[str] = []
        errored: dict[str, str] = {}
        for name, command, cwd in batches_needing_computation:
            fragment = _relative_cwd_fragment(cwd, project_root, git_root)
            effective_cwd = tmp_path / fragment if fragment is not None else None
            try:
                failures = _verify_baseline.compute_batch_baselines(
                    [(name, command, effective_cwd)], tmp_path, project_root
                )[name]
                _status.set_batch_field(status_path, name, "verify_baseline_failures", failures)
            except Exception as e:
                errored[name] = str(e)
                continue
            computed_names.append(name)
    finally:
        try:
            _worktree.remove_safe(tmp_path, cwd=git_root, junctions_cfg={})
        except Exception as teardown_exc:
            print(f"[millpy-implement] baseline teardown failed: {teardown_exc}", file=sys.stderr)

    print(json.dumps(module_wide_payload))
    print(
        json.dumps(
            {
                "stage": "baseline",
                "substage": "per_batch",
                "computed": computed_names,
                "cached": cached_batches,
                "errored": errored,
            }
        )
    )
    return 0


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(
        description="Dispatch or resume a per-batch implementer session."
    )
    parser.add_argument(
        "batch_name",
        nargs="?",
        default=None,
        help="Batch name from the plan overview's Batch Index. Not required for --stage baseline (task-scoped, not batch-scoped).",
    )
    parser.add_argument(
        "--stage",
        choices=["prepare", "finalize", "full", "baseline"],
        default="full",
        help="Stage of execution: prepare (render brief), finalize (process output), full (default, unchanged behavior), or baseline (compute/cache the task-scoped module-wide verify baseline).",
    )
    parser.add_argument(
        "--agent-output",
        help="Path to agent output file (required when --stage finalize).",
    )
    # These flags are accepted for CLI-shape parity with millpy-fix.py and the generic agent-mode dispatch loop (mill-go SKILL.md step 5).
    # millpy-implement.py ignores them;
    # the --stage finalize branch reads the authoritative start_sha and implementer_session from status.md instead.
    parser.add_argument(
        "--start-sha",
        default=None,
        help="SHA captured at prepare stage (ignored by implement; status.md is authoritative).",
    )
    parser.add_argument(
        "--session-id",
        default=None,
        help="Session ID from prepare envelope (ignored by implement; status.md is authoritative).",
    )
    # Accepted for CLI-shape parity with millpy-fix.py and the agent-mode dispatch loop; ignored by implement -- the finalize branch reads start_sha and implementer_session from status.md rather than from the prepare envelope.
    parser.add_argument(
        "--round",
        default=None,
        help=(
            "Accepted for CLI-shape parity with millpy-fix.py and the agent-mode dispatch loop;"
            " ignored by implement (the finalize branch reads start_sha and implementer_session"
            " from status.md)."
        ),
    )
    parser.add_argument(
        "--resume-incomplete",
        action="store_true",
        default=False,
        help=(
            "Resume a partially-completed batch without re-capturing start_sha or"
            " overwriting the original implementer_session. Reads the existing start_sha"
            " and implementer_session from status.md instead of capturing HEAD and"
            " generating a fresh UUID. Skips the capture_snapshot call and the"
            " mill-go: start batch housekeeping commit."
        ),
    )
    args = parser.parse_args(argv)
    if args.stage != "baseline" and not args.batch_name:
        print("batch_name is required unless --stage baseline", file=sys.stderr)
        return 1

    # Common setup
    project_root = _paths.resolve_hub_path()
    mill_dir = project_root / ".millhouse"

    git_root = _paths.resolve_git_root()
    wiki_path = _paths.resolve_wiki_path(git_root)

    try:
        cfg = _review_common.load_config(project_root, mill_dir)
    except _review_common.ReviewError as e:
        print(str(e), file=sys.stderr)
        return 1

    # Fail fast when a full-stage (in-process, synchronous) run is misrouted under agent-mode dispatch. --stage defaults to "full", so a bare invocation and an explicit `--stage full` both hit this guard;
    # agent-mode hubs must instead go through the prepare/finalize two-call split (see mill-go-base/SKILL.md "## Agent-mode dispatch").
    # Checked here -- immediately after cfg loads, before any git config check, slug resolution, or wiki daemon I/O -- so a misconfigured call fails in milliseconds rather than blocking for up to cfg["llm"]["implementer_timeout"] (default 1800s).
    if args.stage == "full" and _agent_dispatch.resolve_dispatch_mode(cfg) == "agent":
        print(
            "millpy-implement.py: --stage full is incompatible with dispatch: agent"
            " config. Use --stage prepare followed by --stage finalize instead"
            " (see mill-go-base/SKILL.md \"## Agent-mode dispatch\").",
            file=sys.stderr,
        )
        return 1

    name_result = _subprocess_util.run(
        ["git", "config", "--global", "--get", "user.name"], cwd=project_root
    )
    email_result = _subprocess_util.run(
        ["git", "config", "--global", "--get", "user.email"], cwd=project_root
    )
    git_name = name_result.stdout.strip()
    git_email = email_result.stdout.strip()
    if not git_name or not git_email:
        print(
            "git config --global user.name and user.email must be set", file=sys.stderr
        )
        return 1

    try:
        slug = _marker.slug_from_branch(git_root, wiki_path, cfg)
    except _marker.MarkerError as e:
        print(str(e), file=sys.stderr)
        return 1
    except WikiStartupError as e:
        print(f"wiki daemon unreachable: {e}", file=sys.stderr)
        return 1

    container_path = _paths.resolve_container_path(git_root)
    project_root = _paths.resolve_active_hub(
        container_path, slug, cfg=cfg, git_root=git_root, skip_slug_validation=True
    )
    mill_dir = project_root / ".millhouse"
    # Reload cfg against the resolve_active_hub()-corrected root: the bootstrap cfg above was loaded against project_root before this correction, so it can miss the hub's own mill-config.yaml whenever the hub lives in a subdirectory of the git repo (see cfg-reload-after-active-hub).
    cfg = _review_common.load_config(project_root, mill_dir)

    plan_dir = cfg.get("paths", {}).get("plan_dir", "_mill/plan/")
    try:
        status_path = _paths.require_status_path(project_root, cfg)
    except _paths.TaskHubError as e:
        print(str(e), file=sys.stderr)
        return 1
    full = _status.read_full(status_path)
    task_title = full["yaml"].get("task", slug)

    branch_result = _subprocess_util.run(
        ["git", "-C", str(project_root), "branch", "--show-current"]
    )
    if branch_result.returncode != 0:
        print(
            json.dumps(
                {
                    "status": "stuck",
                    "stuck_type": "transient",
                    "reason": f"git branch --show-current failed: {branch_result.stderr.strip()}",
                }
            )
        )
        print(branch_result.stderr, file=sys.stderr)
        return 1
    branch = branch_result.stdout.strip()
    if not branch:
        print(
            json.dumps(
                {
                    "status": "stuck",
                    "stuck_type": "transient",
                    "reason": "detached HEAD: no current branch",
                }
            )
        )
        print("detached HEAD: no current branch", file=sys.stderr)
        return 1
    self_fix_rounds = (
        cfg.get("roles", {}).get("implementer", {}).get("self_fix_rounds", 2)
    )
    implementer_cfg = cfg.get("roles", {}).get("implementer", {})
    model_name = implementer_cfg.get("model", "sonnethigh")
    try:
        registry = _reviewers.load(git_root)
        impl_spec = _reviewers.resolve(registry, model_name)
    except _reviewers.ReviewerError as e:
        print(str(e), file=sys.stderr)
        return 1
    impl_model = impl_spec["model"]
    impl_effort = impl_spec.get("effort")
    timeout = impl_spec.get("timeout") or cfg.get("llm", {}).get(
        "implementer_timeout", 1800
    )

    plan_base = _paths.resolve_task_path(project_root, plan_dir)
    overview_path = plan_base / "00-overview.md"
    if not overview_path.exists():
        print(f"overview not found: {overview_path}", file=sys.stderr)
        return 1

    # Read the overview-level module-wide verify command from the overview frontmatter.
    # The overview's first fenced-yaml block is the frontmatter (task/slug/verify/...).
    # A null or absent `verify:` passes None, which makes the module-wide gate a no-op.
    # Read here -- before the batches/batch_entry resolution below -- because the task-scoped `--stage baseline` branch needs this value and never has a `batch_name` to resolve a batch_entry from.
    # Routed through parse_verify_field so a `{cwd: hub|git_root, command: ...}` mapping resolves to the correct verify-subprocess cwd in nested layouts.
    overview_frontmatter = _plan_dag._read_batch_frontmatter(overview_path)
    module_wide_verify_cmd, module_wide_cwd_override = _plan_dag.parse_verify_field(
        overview_frontmatter, project_root, git_root
    )

    # Cached task-scoped baseline read once here so both the finalize and full stages below pass the same value through to _run_verify_gates.
    module_verify_baseline = _status.get_module_verify_baseline(status_path)

    if args.stage == "baseline":
        baseline_prepare_cmd = (cfg.get("pipeline") or {}).get("baseline_prepare_cmd")
        return _run_baseline_stage(
            project_root, git_root, status_path, module_wide_verify_cmd, module_wide_cwd_override, plan_base, baseline_prepare_cmd
        )

    try:
        batches = _plan_dag.extract_batch_index(
            overview_path.read_text(encoding="utf-8")
        )
    except _plan_dag.PlanDAGError as e:
        print(str(e), file=sys.stderr)
        return 1

    batch_entry = next((b for b in batches if b["name"] == args.batch_name), None)
    if batch_entry is None:
        print(f"batch {args.batch_name!r} not found in overview", file=sys.stderr)
        return 1

    batch_file = plan_base / batch_entry["file"]
    plugin_root = Path(__file__).resolve().parent.parent

    # Compute gate inputs used by both the finalize and full stages.
    # card_ids: the set of Card numbers declared in the batch file, read verbatim from each "### Card N:" heading using the same heading shape _plan_validate uses.
    # Card numbers are NOT assumed to be a contiguous 1..N range -- mill-plan numbers cards globally across all batches in a plan, so a later batch's cards may start at e.g. "Card 7".
    # An empty card_ids set (docs-only batch) disables the completeness gate downstream.
    _batch_text = batch_file.read_text(encoding="utf-8")
    card_ids: set[int] = {
        int(n) for n in re.findall(r"(?m)^###\s+Card\s+(\d+)\s*:", _batch_text)
    }
    # commit_none_card_ids: card numbers whose Commit: field is the literal none, computed from the batch file on disk -- feeds the no-content-commit gate's Commit: none carve-out (batch 6, cards 15-16), never trusted from the implementer's own self-report.
    commit_none_card_ids: set[int] = _plan_dag.parse_commit_none_card_ids(_batch_text)

    # parent_branch: resolve non-interactively from status.md;
    # fall back to None on failure (makes the dirty gate a safe no-op rather than crashing).
    try:
        parent_branch = _parent_branch.resolve(status_path, interactive=False)
    except Exception:
        parent_branch = None

    # Stage: finalize
    if args.stage == "finalize":
        if not args.agent_output:
            print("--agent-output is required when --stage finalize", file=sys.stderr)
            return 1
        batches = _status.read_batches(status_path)
        batch_status = next(
            (b for b in batches if b.get("name") == args.batch_name), None
        )
        if batch_status is None:
            print(f"batch {args.batch_name!r} not found in status", file=sys.stderr)
            return 1
        start_sha = batch_status.get("start_sha")
        _safe_batch = _paths.sanitize_filename_component(args.batch_name)
        snapshot_path = (
            project_root / "_mill" / f".cleanliness-snapshot-{_safe_batch}.txt"
        )
        session_id = batch_status.get("implementer_session")
        # Cached, task-scoped per-batch verify baseline (see batch 3/5/6) -- a stored signature-set list, or None when never computed (fail-safe: the verify gate falls back to today's strict any-failure-blocks behavior).
        batch_verify_baseline = batch_status.get("verify_baseline_failures")
        # Resolve batch verify command from the batch file's frontmatter, routing through parse_verify_field so a `{cwd: hub|git_root, command: ...}` mapping resolves to the correct verify-subprocess cwd in nested layouts.
        batch_frontmatter = _plan_dag._read_batch_frontmatter(batch_file)
        verify_cmd, cwd_override = _plan_dag.parse_verify_field(
            batch_frontmatter, project_root, git_root
        )
        return finalize_from_output(
            Path(args.agent_output),
            project_root,
            start_sha=start_sha,
            snapshot_path=snapshot_path,
            session_id=session_id,
            verify_cmd=verify_cmd,
            module_wide_verify_cmd=module_wide_verify_cmd,
            module_verify_baseline=module_verify_baseline,
            batch_verify_baseline=batch_verify_baseline,
            batch_name=args.batch_name,
            status_path=status_path,
            card_ids=card_ids,
            commit_none_card_ids=commit_none_card_ids,
            task_dir=status_path.parent,
            parent_branch=parent_branch,
            git_root=git_root,
            cwd_override=cwd_override,
            module_wide_cwd_override=module_wide_cwd_override,
            git_name=git_name,
            git_email=git_email,
        )

    # Stages: prepare and full (need pre-commit, render, and setup)
    _safe_batch = _paths.sanitize_filename_component(args.batch_name)
    # snapshot_path always points to the same file name (derived from batch name) so a resume dispatch reuses the snapshot written by the original dispatch without re-capturing it, preserving the original new-dirt baseline.
    snapshot_path = project_root / "_mill" / f".cleanliness-snapshot-{_safe_batch}.txt"

    # A re-run of `--stage prepare` (never `--stage full`, whose fresh-mint/transient-retry contract per mill-go-base/SKILL.md step 2 must not change) against a batch that a prior prepare call already dispatched -- state "running" with a session recorded -- must reuse that session_id/start_sha rather than minting fresh state.
    # Without this, a re-dispatched prepare (e.g.
    # mill-go resuming after a transient dispatch failure) would overwrite implementer_session in status.md and make a second "mill-go: start batch" commit, both of which corrupt state the agent-mode dispatch loop and finalize's completeness recount rely on (#625, #635, #643).
    # Resolved once, before the resume/fresh-mint branches below, so the three-way branch reads as: resume-after-incomplete, prepare-reuse, fresh-mint.
    _prepare_reuse_entry = None
    # Set only when the most recent timeline row is a self-resolve marker (see below);
    # the fresh-mint branch reads this even when the block above never runs (e.g. --stage full),
    # so it must be initialized at this same top-level scope regardless of args.stage.
    _self_resolve_remint_ts = None
    if args.stage == "prepare" and not args.resume_incomplete:
        _prepare_batches = _status.read_batches(status_path)
        _prepare_candidate = next(
            (b for b in _prepare_batches if b.get("name") == args.batch_name), None
        )
        if (
            _prepare_candidate is not None
            and _prepare_candidate.get("state") == "running"
            and _prepare_candidate.get("implementer_session")
        ):
            # A self-resolve (mill-go-base/SKILL.md's per-batch self-resolve step) leaves
            # "state: running" and the original implementer_session untouched -- it only appends a
            # "self-resolved-verify-logic" timeline row -- so this reuse heuristic cannot tell a
            # self-resolved re-fire apart from a genuine transient-dispatch-failure re-fire without
            # also consulting the timeline.
            # Withhold reuse exactly once per self-resolve marker: the fresh-mint branch below
            # records self_resolve_remint_at so a *second* prepare call sees _already_reminted and
            # reuses normally, bounding this to one remint rather than an unbounded chain.
            _timeline = _status.read_full(status_path)["timeline"]
            if _timeline:
                _last_parts = _timeline[-1].split(None, 1)
                if len(_last_parts) > 1 and _last_parts[0] == "self-resolved-verify-logic":
                    _self_resolve_remint_ts = _last_parts[1].strip("'\"")
            _already_reminted = (
                _self_resolve_remint_ts is not None
                and _prepare_candidate.get("self_resolve_remint_at") == _self_resolve_remint_ts
            )
            if _self_resolve_remint_ts is None or _already_reminted:
                _prepare_reuse_entry = _prepare_candidate

    if args.resume_incomplete:
        # Resume path: read the original start_sha and implementer_session from status.md.
        # Re-capturing HEAD as start_sha would make the completeness recount under-count a finished batch (because partial-work commits exist before the new start_sha), causing a false-positive incomplete loop.
        # Preserving the original SHA lets finalize count all content commits correctly.
        _resume_batches = _status.read_batches(status_path)
        _resume_batch_entry = next(
            (b for b in _resume_batches if b.get("name") == args.batch_name), None
        )
        if _resume_batch_entry is None:
            print(
                f"batch {args.batch_name!r} not found in status.md for resume",
                file=sys.stderr,
            )
            return 1
        start_sha = _resume_batch_entry.get("start_sha")
        if not start_sha:
            print(
                f"batch {args.batch_name!r} has no start_sha in status.md for resume",
                file=sys.stderr,
            )
            return 1
        # Retain the original implementer_session so the brief's SESSION_ID token and the finalize-reported session_id stay consistent.
        # Finalize reads implementer_session from status.md;
        # a fresh UUID here would diverge from what finalize reports.
        session_id = _resume_batch_entry.get("implementer_session") or str(uuid.uuid4())
        # Do NOT call capture_snapshot: the snapshot was written and committed during the original dispatch.
        # Overwriting it now (with post-partial-work state) and then skipping the commit would corrupt the new-dirt baseline used by finalize.
        # Do NOT call set_batch_fields: the original start_sha/implementer_session must be preserved so the completeness recount from start_sha is accurate.
        # Do NOT make a housekeeping commit: a second "mill-go: start batch" commit would cause _content_commit_count to subtract two housekeeping commits, under-counting the implementer's content commits and producing a false incomplete result.
    elif _prepare_reuse_entry is not None:
        # Prepare-reuse path: a prior `--stage prepare` call already captured start_sha, minted implementer_session, and made the "mill-go: start batch" commit for this batch.
        # Reuse both values verbatim and do none of the state-mutating work the fresh-mint branch below does -- no capture_snapshot, no set_batch_fields, no git add/diff/commit, no push.
        # This branch only reads already-recorded state.
        session_id = _prepare_reuse_entry["implementer_session"]
        start_sha = _prepare_reuse_entry["start_sha"]
    else:
        # Normal (first-pass) dispatch: capture HEAD as start_sha, generate a fresh session_id, update status.md, take a cleanliness snapshot, and make the housekeeping commit so downstream finalize has a stable new-dirt baseline.
        result = _subprocess_util.run(
            ["git", "rev-parse", "HEAD"],
            cwd=project_root,
        )
        if result.returncode != 0:
            print(result.stderr, file=sys.stderr)
            return 1
        start_sha = result.stdout.strip()

        _cleanliness.capture_snapshot(project_root, snapshot_path)

        session_id = str(uuid.uuid4())

        _fresh_mint_fields = {
            "state": "running",
            "start_sha": start_sha,
            "implementer_session": session_id,
        }
        # Record the remint marker only when this fresh mint was actually triggered by an
        # unreacted self-resolve, not an ordinary first-pass dispatch -- so a later prepare
        # call for this same session can detect _already_reminted and reuse it instead of
        # minting a third session on a following transient retry.
        if _self_resolve_remint_ts is not None:
            _fresh_mint_fields["self_resolve_remint_at"] = _self_resolve_remint_ts
        _status.set_batch_fields(status_path, args.batch_name, _fresh_mint_fields)

        # Stage status.md and the cleanliness snapshot unconditionally.
        # On a re-fire the prepare step regenerated implementer_session, so status.md is always dirty;
        # the message-based skip_start_commit check would have missed that mutation and left the session in status.md uncommitted (#563).
        result = _subprocess_util.run(
            [
                "git",
                "add",
                status_path.relative_to(project_root).as_posix(),
                str(snapshot_path.relative_to(project_root)),
            ],
            cwd=project_root,
        )
        if result.returncode != 0:
            print(result.stderr, file=sys.stderr)
            return 1

        # Use a staged-diff emptiness check rather than the last-log message to decide whether to commit.
        # git diff --cached --quiet exits 0 when nothing is staged (all state already committed on a genuine first-fire with matching content) and exits non-zero when at least one file differs -- which is always true on re-fires because the fresh implementer_session UUID dirtied status.md.
        diff_result = _subprocess_util.run(
            ["git", "diff", "--cached", "--quiet"],
            cwd=project_root,
        )

        if diff_result.returncode != 0:
            # Something is staged -- commit and push so the subsequent finalize in-scope dirty gate does not trip on the uncommitted session write.
            result = _subprocess_util.git_commit(
                project_root,
                f"mill-go: start batch {args.batch_name}",
                name=git_name,
                email=git_email,
            )
            if result.returncode != 0:
                print(result.stderr, file=sys.stderr)
                return 1

            result = _subprocess_util.run(
                ["git", "push", "origin", branch],
                cwd=project_root,
            )
            if result.returncode != 0:
                # A failed push here (network blip, transient remote error) must not abort the batch: the housekeeping commit is safely on the local branch, and mill-merge pushes the full branch at task end regardless.
                # Aborting on a push failure would strand the batch in "running" state with no way to retry the prepare stage without also re-minting session_id (#626).
                print(
                    f"[millpy-implement] warning: git push failed ({result.stderr.strip()}); "
                    "continuing -- mill-merge pushes the full branch at task end",
                    file=sys.stderr,
                )

    template_path = plugin_root / "templates" / "implementer-brief.md"
    prompt_text = _render.render(
        template_path,
        {
            "TASK_TITLE": task_title,
            "SLUG": slug,
            "BATCH_NAME": args.batch_name,
            "BATCH_FILE": str(batch_file),
            "OVERVIEW_FILE": str(overview_path),
            "PROJECT_ROOT": str(project_root),
            "WIKI_PATH": str(wiki_path),
            "SELF_FIX_ROUNDS": str(self_fix_rounds),
            "ROUND": "1",
            "SESSION_ID": session_id,
            "LANGUAGE_SKILLS": _agent_dispatch.language_skills_directive(batch_file),
            # PARENT_BRANCH lets the implementer verify whether a test failure is pre-existing (present on parent) vs. introduced by this batch.
            # When parent_branch could not be resolved, use empty string so the token always substitutes;
            # the brief instructs the implementer to skip the parent check when the value is empty.
            "PARENT_BRANCH": parent_branch or "",
            # START_SHA: the original batch start SHA on a resume-after-incomplete dispatch;
            # empty string on a normal first-pass dispatch.
            # Always included because _render.render raises KeyError on any unresolved token,
            # and the brief now contains <START_SHA> in its resume-after-incomplete instruction.
            "START_SHA": start_sha if args.resume_incomplete else "",
        },
    )

    max_chars = cfg.get("llm", {}).get("max_implementer_prompt_chars", 0)
    if max_chars > 0 and len(prompt_text) > max_chars:
        print(
            json.dumps(
                {
                    "status": "stuck",
                    "stuck_type": "transient",
                    "reason": f"brief exceeds max_implementer_prompt_chars ({len(prompt_text)} chars)",
                }
            )
        )
        return 0

    # Stage: prepare
    if args.stage == "prepare":
        briefs_dir = _paths.resolve_task_path(project_root, "_mill/briefs/")
        model_tier = _agent_dispatch.model_to_tier(impl_model)
        return emit_prepare(
            briefs_dir,
            "implement",
            args.batch_name,
            1,
            prompt_text,
            model_tier,
            session_id,
            start_sha=start_sha,
            effort=impl_effort,
        )

    # Stage: full (default)
    try:
        output, _ = _implementer_claude.run(
            prompt_text,
            model=impl_model,
            effort=impl_effort,
            session_id=session_id,
            resume=False,
            cwd=project_root,
            timeout=timeout,
        )
    except _llm_claude.LLMError as e:
        result = _subprocess_util.run(
            ["git", "rev-list", "--count", f"{start_sha}..HEAD"], cwd=project_root
        )
        if result.returncode == 0:
            commits_made = int(result.stdout.strip())
        else:
            commits_made = 0
        error_reason = str(e)
        stuck_type = classify_stuck_type(error_reason)
        print(
            json.dumps(
                {
                    "status": "stuck",
                    "stuck_type": stuck_type,
                    "reason": error_reason,
                    "commits_made": commits_made,
                }
            )
        )
        print(error_reason, file=sys.stderr)
        return 1
    # Resolve batch verify command from the batch file's frontmatter for full stage, routing through parse_verify_field so a `{cwd: hub|git_root, command: ...}` mapping resolves to the correct verify-subprocess cwd in nested layouts.
    batch_frontmatter = _plan_dag._read_batch_frontmatter(batch_file)
    verify_cmd, cwd_override = _plan_dag.parse_verify_field(
        batch_frontmatter, project_root, git_root
    )
    # Cached, task-scoped per-batch verify baseline (see batch 3/5/6), read fresh here (mirroring the resume_incomplete branch's own lookup pattern above) since the earlier module_verify_baseline read at the top of main() has no per-batch equivalent to piggyback on.
    _full_stage_batches = _status.read_batches(status_path)
    _full_stage_batch_entry = next(
        (b for b in _full_stage_batches if b.get("name") == args.batch_name), None
    )
    batch_verify_baseline = (
        _full_stage_batch_entry.get("verify_baseline_failures")
        if _full_stage_batch_entry is not None
        else None
    )
    return _forward_output(
        output,
        project_root,
        start_sha=start_sha,
        snapshot_path=snapshot_path,
        session_id=session_id,
        verify_cmd=verify_cmd,
        module_wide_verify_cmd=module_wide_verify_cmd,
        module_verify_baseline=module_verify_baseline,
        batch_verify_baseline=batch_verify_baseline,
        batch_name=args.batch_name,
        status_path=status_path,
        card_ids=card_ids,
        commit_none_card_ids=commit_none_card_ids,
        task_dir=status_path.parent,
        parent_branch=parent_branch,
        git_root=git_root,
        cwd_override=cwd_override,
        module_wide_cwd_override=module_wide_cwd_override,
    )


if __name__ == "__main__":
    sys.exit(main())
