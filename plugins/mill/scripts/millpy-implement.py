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


def _baseline_exclusion_prefixes(project_root: Path, git_root: Path) -> tuple[str, str]:
    """
    Return the two path-prefix strings that a baseline preflight check must never treat as dirt.

    `_mill/` and `.millhouse/` are working-state directories a task's own machinery legitimately
    writes to (status.md, snapshots, config.local.yaml) even before batch 1 dispatches -- neither
    represents "implementation work has started".
    Both prefixes are re-anchored to the hub fragment (`project_root.relative_to(git_root)`) so a
    nested-layout task (hub is a subdirectory of the git repo) excludes `<hub-fragment>/_mill/`, not
    the git-root-relative `_mill/` a flat-layout task would exclude.

    This is the single source of truth for the exclusion set -- both
    `_baseline_preflight_skip_reason` (Card 10) and `_warn_new_dirt`'s callers (Card 11) call this
    rather than re-deriving the re-anchoring inline, so the two checks cannot drift apart.

    Args:
        project_root: Absolute path to the task worktree root (the mill hub).
        git_root: Absolute path to the repo root `git` commands run against.

    Returns:
        `(<fragment>_mill/, <fragment>.millhouse/)`, where `<fragment>` is
        `project_root.relative_to(git_root)` followed by `/`,
        or the empty string in a flat layout (`project_root == git_root`).
    """
    fragment = project_root.relative_to(git_root)
    prefix = "" if fragment == Path(".") else f"{fragment.as_posix()}/"
    return (f"{prefix}_mill/", f"{prefix}.millhouse/")


def _baseline_preflight_skip_reason(project_root: Path, git_root: Path, status_path: Path) -> str | None:
    """
    Return a skip reason when the task worktree is not yet safe for eager baseline capture, or None.

    Implements Decision `preflight-precondition-guard`: `--stage baseline` capture is only valid
    while the task worktree's tracked source content still equals the merge-base content -- once an
    implementer has committed real changes, a "baseline" computed from the current tree would no
    longer describe the parent branch's own pre-edit state.

    The only load-bearing check is whether any path has changed, per `git diff --name-only`, between
    `git merge-base HEAD <parent>` and `HEAD` -- NOT `git status --porcelain` (an uncommitted dirty
    tracked file outside `_mill/`/`.millhouse/` is the separate, advisory `preflight-dirt-warning`
    case Card 11 covers; it never blocks capture on its own, per the "Why a dirty tree only warns"
    rationale in `_mill/discussion.md`'s `preflight-precondition-guard` Decision).

    This function performs no capture itself and mutates nothing -- it is a pure gate, and is called
    exactly ONCE per `--stage baseline` invocation, by `_run_baseline_stage`, before either half
    attempts anything.
    Neither `_run_module_wide_standalone` nor `_run_per_batch_baseline_standalone` calls this
    function itself -- each instead receives the already-computed skip reason as a parameter from
    `_run_baseline_stage`, so the guard's two `git` calls never run twice in one invocation.

    Args:
        project_root: Absolute path to the task worktree root (the mill hub).
        git_root: Absolute path to the repo root `git` commands run against.
        status_path: Absolute path to the task's status.md file.

    Returns:
        A human-readable skip reason string when the precondition does not hold (parent
        unresolvable, `merge-base` fails, or a changed path falls outside the exclusion set);
        `None` when the precondition holds and capture may proceed.
    """
    try:
        parent_branch = _parent_branch.resolve(status_path, interactive=False)
    except Exception as e:
        return f"baseline preflight: parent-branch resolution failed: {e}"

    merge_base_result = _subprocess_util.run(
        ["git", "-C", str(git_root), "merge-base", "HEAD", parent_branch]
    )
    if merge_base_result.returncode != 0:
        return (
            f"baseline preflight: git merge-base HEAD {parent_branch!r} failed: "
            f"{merge_base_result.stderr.strip()}"
        )
    merge_base_sha = merge_base_result.stdout.strip()

    diff_result = _subprocess_util.run(
        ["git", "-C", str(git_root), "diff", "--name-only", merge_base_sha, "HEAD"]
    )
    if diff_result.returncode != 0:
        return (
            f"baseline preflight: git diff --name-only {merge_base_sha} HEAD failed: "
            f"{diff_result.stderr.strip()}"
        )

    exclusion_prefixes = _baseline_exclusion_prefixes(project_root, git_root)
    for changed_path in diff_result.stdout.splitlines():
        changed_path = changed_path.strip()
        if changed_path and not changed_path.startswith(exclusion_prefixes):
            return f"worktree is not pre-edit: {changed_path!r} differs from merge-base {merge_base_sha}"
    return None


def _porcelain_snapshot(git_root: Path) -> set[str]:
    """
    Return the set of modified-tracked-path strings from `git -C <git_root> status --porcelain`.

    Used as a before/after pair by `_warn_new_dirt` to detect which paths a verify run left newly
    dirty. `--untracked-files` is deliberately left at its default (untracked files included) since
    a verify run can leave behind new build artifacts that are just as worth naming in the advisory
    warning as a modified tracked file.

    Args:
        git_root: Absolute path to the repo root `git` commands run against.

    Returns:
        The set of paths named by each porcelain status line (everything after the 2-character
        status code and its following space).
    """
    result = _subprocess_util.run(["git", "-C", str(git_root), "status", "--porcelain"])
    paths: set[str] = set()
    for line in result.stdout.splitlines():
        if not line.strip():
            continue
        paths.add(line[3:].strip())
    return paths


def _warn_new_dirt(before: set[str], after: set[str], exclusions: tuple[str, str]) -> None:
    """
    Print an ASCII-only stderr warning naming every path newly dirtied between `before` and `after`.

    Implements Decision `preflight-dirt-warning`: a verify run that leaves behind a modified tracked
    file (or new untracked artifact) outside the exclusion set is worth flagging to the operator, but
    is never blocking, never reverted, and never fails the stage -- purely advisory.
    Reused verbatim by both halves: the module-wide half wraps its own before/after snapshot around
    its 1-2 verify runs, the per-batch half wraps its own before/after snapshot around the whole
    per-batch capture loop.

    Args:
        before: The `_porcelain_snapshot` result taken before the verify run(s).
        after: The `_porcelain_snapshot` result taken after the verify run(s).
        exclusions: The `(mill_prefix, millhouse_prefix)` pair from `_baseline_exclusion_prefixes` --
            a newly-dirty path under either prefix is expected working-state churn, not a warning.
    """
    for path in sorted(after - before):
        if path.startswith(exclusions):
            continue
        print(
            f"[millpy-implement] baseline stage: verify run left {path!r} newly dirty "
            "(advisory only -- not blocking)",
            file=sys.stderr,
        )


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
    preflight_skip_reason: str | None,
    verify_timeout_seconds: float | None = None,
) -> tuple[str, Path, list[str]] | None:
    """
    Run the module-wide baseline sub-step, eagerly and in-worktree, per Decision
    `two-half-stage-ownership`.

    `preflight_skip_reason` is the already-computed result of `_baseline_preflight_skip_reason`,
    passed in by the caller (`_run_baseline_stage`) -- this function never calls that guard itself,
    since the guard is called exactly once per `--stage baseline` invocation.

    Never raises -- every failure path prints a JSON line describing the outcome without persisting
    a baseline verdict, matching the "leave the field unset -> next `_run_verify_gates` call runs
    the gate strictly" fail-safe policy.

    Args:
        project_root: Absolute path to the task worktree root (the mill hub).
        git_root: Absolute path to the repo root `git` commands run against.
        status_path: Absolute path to the task's status.md file.
        module_wide_verify_cmd: The overview's module-wide verify command, or None when unconfigured.
        module_wide_cwd_override: The overview's module-wide verify cwd resolved by
            `parse_verify_field` -- `project_root` (hub), `git_root`, or `None` (plain-string
            `verify:` or absent).
        preflight_skip_reason: The precomputed skip reason from `_baseline_preflight_skip_reason`,
            or `None` when the precondition holds.
        verify_timeout_seconds: Per-run wall-clock ceiling applied to the module-wide verify command,
            or `None` for no ceiling.

    Returns:
        `(module_wide_verify_cmd, effective_cwd, signatures)` when this call actually computed a
        fresh result this invocation (the `"computed"` branch only) -- fed to
        `_run_per_batch_baseline_standalone` as `module_wide_pair_seed` so a batch whose own
        `(command, cwd)` matches this pair reuses the result instead of re-running the suite.
        `None` on every other branch (skipped, cached, or error).
    """
    payload = _module_wide_skip_or_cached_payload(module_wide_verify_cmd, status_path)
    if payload is not None:
        print(json.dumps(payload))
        return None

    if preflight_skip_reason is not None:
        print(
            json.dumps(
                {
                    "stage": "baseline",
                    "substage": "module_wide",
                    "result": "skipped",
                    "reason": preflight_skip_reason,
                }
            )
        )
        return None

    effective_cwd = module_wide_cwd_override if module_wide_cwd_override is not None else git_root

    exclusion_prefixes = _baseline_exclusion_prefixes(project_root, git_root)
    before_snapshot = _porcelain_snapshot(git_root)
    try:
        result, signatures = _verify_baseline.compute_baseline(
            effective_cwd,
            module_wide_verify_cmd,
            timeout_seconds=verify_timeout_seconds,
        )
    except Exception as e:
        print(f"[millpy-implement] baseline computation failed: {e}", file=sys.stderr)
        print(json.dumps({"stage": "baseline", "substage": "module_wide", "result": "error", "reason": str(e)}))
        return None
    after_snapshot = _porcelain_snapshot(git_root)
    _warn_new_dirt(before_snapshot, after_snapshot, exclusion_prefixes)

    _status.set_module_verify_baseline(status_path, result)
    _status.set_module_verify_baseline_signatures(status_path, signatures)
    print(json.dumps({"stage": "baseline", "substage": "module_wide", "result": "computed", "value": result}))
    return (module_wide_verify_cmd, effective_cwd, signatures)


def _run_baseline_stage(
    project_root: Path,
    git_root: Path,
    status_path: Path,
    module_wide_verify_cmd: str | None,
    module_wide_cwd_override: Path | None,
    plan_base: Path,
    baseline_prepare_cmd: str | None,
    verify_timeout_seconds: float | None = None,
) -> int:
    """
    Compute (idempotent, no-op-if-already-cached) the module-wide baseline and persist it, and
    idempotently pin the parent branch's tip SHA for later on-demand per-batch computation.

    Two INDEPENDENT sub-steps run on every invocation, in either order, since neither depends on the
    other's outcome: (1) the module-wide `module_verify_baseline` scalar, computed standalone via
    `_run_module_wide_standalone`'s own `compute_baseline` checkout;
    and (2) the cheap `baseline_parent_sha` pin via `_pin_baseline_parent_sha` (a `git rev-parse`,
    not a checkout).

    Per-batch `verify_baseline_failures` computation is NOT part of this stage -- it moved to an
    on-demand call inside `_implementer_common._run_verify_gates` (#1102), which computes a batch's
    own baseline lazily, only the first time that batch's own verify gate actually fails, instead of
    eagerly for every batch before batch 1 ever dispatches.
    `plan_base` and `baseline_prepare_cmd` remain accepted parameters -- unused by this simplified
    function's own logic -- to keep both existing call sites in `main` unchanged; removing them would
    force an unrelated change to every call site for no behavioral gain.

    Never raises -- every failure path prints a JSON line describing the outcome and returns 0.

    Args:
        project_root: Absolute path to the task worktree root.
        git_root: Absolute path to the repo root `git` commands run against.
        status_path: Absolute path to the task's status.md file.
        module_wide_verify_cmd: The overview's module-wide verify command,
            or None when no module-wide verify is configured for this task.
        module_wide_cwd_override: The overview's module-wide verify cwd resolved by
            parse_verify_field -- one of project_root (hub_root), git_root, or None (plain-string
            verify: or absent).
        plan_base: Unused by this function's own logic;
            accepted for call-site parity.
        baseline_prepare_cmd: Unused by this function's own logic;
            accepted for call-site parity.
        verify_timeout_seconds: Per-run wall-clock ceiling applied to the module-wide verify command,
            or `None` for no ceiling -- read by the caller from
            `pipeline.baseline_verify_timeout_minutes` in mill-config.yaml.
            A timeout raises inside `_run_module_wide_standalone`, which already handles it as
            "computation failed, leave the baseline unset."

    Returns:
        Always 0 -- the baseline stage never signals a pre-launch error via exit code;
        outcomes are communicated through the printed JSON line.
    """
    del plan_base, baseline_prepare_cmd  # unused; kept for call-site parity, see docstring.

    _run_module_wide_standalone(
        project_root,
        git_root,
        status_path,
        module_wide_verify_cmd,
        module_wide_cwd_override,
        verify_timeout_seconds,
    )
    _pin_baseline_parent_sha(git_root, status_path)
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
    # --start-sha is honored at --stage finalize when passed (non-empty), falling back to status.md otherwise.
    parser.add_argument(
        "--start-sha",
        default=None,
        help="SHA captured at prepare stage; honored at --stage finalize when passed (non-empty), falling back to status.md otherwise.",
    )
    # These flags are accepted for CLI-shape parity with millpy-fix.py and the generic agent-mode dispatch loop (mill-go SKILL.md step 5).
    # millpy-implement.py ignores them;
    # the --stage finalize branch reads the authoritative start_sha and implementer_session from status.md instead.
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
        pipeline_cfg = cfg.get("pipeline") or {}
        baseline_prepare_cmd = pipeline_cfg.get("baseline_prepare_cmd")
        timeout_minutes = pipeline_cfg.get("baseline_verify_timeout_minutes")
        verify_timeout_seconds = float(timeout_minutes) * 60 if timeout_minutes else None
        return _run_baseline_stage(
            project_root,
            git_root,
            status_path,
            module_wide_verify_cmd,
            module_wide_cwd_override,
            plan_base,
            baseline_prepare_cmd,
            verify_timeout_seconds,
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
        start_sha = args.start_sha if args.start_sha else batch_status.get("start_sha")
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
        git_name=git_name,
        git_email=git_email,
    )


if __name__ == "__main__":
    sys.exit(main())
