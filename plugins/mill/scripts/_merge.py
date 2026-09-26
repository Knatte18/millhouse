"""
Deterministic path of the ``mill-merge`` skill, called by ``millpy-merge.py``.

Each step of the merge is a function ``step_*(ctx, ops)`` registered in ``STEPS``.
A step signals "stop here" by raising ``Stop`` (a halt for the operator, or a callback the calling
model must answer before re-running with an extra flag).
Every external effect goes through one ``Ops`` instance so unit tests can substitute a fake.
``run_merge`` walks ``STEPS`` in order, times each step, and returns a JSON-able result dict.
"""
from __future__ import annotations

import dataclasses
import datetime
import os
import signal
import threading
import time
from collections.abc import Callable
from pathlib import Path

import _archive_tag
import _config
import _inplace
import _marker
import _notify
import _parent_branch
import _paths
import _pr_state
import _status
import _subprocess_util
import _timestamp
from wiki import _client

_ASCII_REPLACEMENTS = {"—": " -- ", "→": " -> "}


def _ascii(text: str) -> str:
    """
    Map ``text`` to pure ASCII for Windows cp1252 stdout safety.

    U+2014 becomes `` -- ``, U+2192 becomes `` -> ``, any other non-ASCII character becomes ``?``.
    """
    out = []
    for char in text:
        if char in _ASCII_REPLACEMENTS:
            out.append(_ASCII_REPLACEMENTS[char])
        elif ord(char) < 128:
            out.append(char)
        else:
            out.append("?")
    return "".join(out)


class Terminated(BaseException):
    """Raised by the SIGTERM handler; a BaseException so no ``except Exception`` swallows it."""


class Stop(Exception):
    """
    Signals that the run stops at the current step.

    Attributes:
        status: ``"halt"``, ``"callback"``, or ``"ok"``.
        reason: one-line operator-facing explanation.
        action: callback name the calling model must handle (callbacks only).
        resume: extra argv to append when re-running; ``None`` means re-running is not the fix,
            ``[]`` means fix the cause and re-run unchanged.
        data: structured payload for the caller.
        report: extra report lines.
        step: when set, overrides the executing step's name in the result.
    """

    def __init__(
        self,
        status: str,
        reason: str,
        *,
        action: str | None = None,
        resume: list[str] | None = None,
        data: dict | None = None,
        report: list[str] | None = None,
        step: str | None = None,
    ):
        super().__init__(reason)
        self.status = status
        self.reason = reason
        self.action = action
        self.resume = resume
        self.data = data
        self.report = report
        self.step = step


def halt(reason: str, *, resume: list[str] | None, data: dict | None = None, step: str | None = None) -> Stop:
    """Build a ``halt`` Stop; callers ``raise`` the result."""
    return Stop("halt", reason, resume=resume, data=data, step=step)


def callback(action: str, reason: str, *, resume: list[str] | None, data: dict | None, report: list[str] | None) -> Stop:
    """Build a ``callback`` Stop asking the calling model to act, then re-run with ``resume``."""
    return Stop("callback", reason, action=action, resume=resume, data=data, report=report)


@dataclasses.dataclass
class MergeOptions:
    """Command-line options of one merge run."""

    merged_in: bool = False
    confirm_parent: str | None = None
    parent: str | None = None


@dataclasses.dataclass
class Ctx:
    """Mutable run state shared by all steps."""

    opts: MergeOptions | None = None
    git_root: Path | None = None
    wiki_path: Path | None = None
    container_path: Path | None = None
    cfg: dict | None = None
    slug: str | None = None
    active_branch: str | None = None
    mode: str | None = None
    worktree_root: Path | None = None
    status_path: Path | None = None
    task_dir: Path | None = None
    task_dir_rel: str | None = None
    task_dir_git_rel: str | None = None
    parent_branch: str | None = None
    phase: str | None = None
    cached_task: str | None = None
    cached_task_description: str | None = None
    child_branch: str | None = None
    route: str | None = None
    parent_path: Path | None = None
    archive: dict = dataclasses.field(default_factory=dict)
    warnings: list[str] = dataclasses.field(default_factory=list)
    report: list[str] = dataclasses.field(default_factory=list)
    timings: list[dict] = dataclasses.field(default_factory=list)


class Ops:
    """
    The real effect boundary: subprocesses, path/config resolution, wiki, notifications, the clock.

    Timed methods add their elapsed wall time to ``subproc_s`` so the runner can report how much
    of each step went to git and network calls.
    """

    subproc_s: float = 0.0

    def _timed(self, fn, *args, **kwargs):
        start = time.monotonic()
        try:
            return fn(*args, **kwargs)
        finally:
            self.subproc_s += time.monotonic() - start

    def run(self, argv: list[str], cwd: Path | None = None):
        return self._timed(_subprocess_util.run, argv, cwd=cwd, quiet_nonzero=True)

    def task_data(self, git_root, wiki_path, cfg):
        return self._timed(_marker.task_data, git_root, wiki_path, cfg)

    def check_liveness(self, branch, git_root):
        return self._timed(_parent_branch.check_liveness, branch, git_root)

    def resolve_dead_parent(self, branch, git_root, cfg):
        return self._timed(_parent_branch.resolve_dead_parent, branch, git_root, cfg)

    def pr_state(self, branch, cwd):
        return self._timed(_pr_state.resolve_pr_state, branch, cwd)

    def get_task(self, wiki_path, slug):
        return self._timed(_client.get_task, wiki_path, slug)

    def set_phase(self, wiki_path, slug, phase):
        return self._timed(_client.set_phase, wiki_path, slug, phase)

    def archive_tag(self, worktree, slug, child_branch):
        return self._timed(_archive_tag.create_or_resolve, worktree, slug, child_branch)

    def resolve_git_root(self):
        return _paths.resolve_git_root()

    def resolve_wiki_path(self, git_root):
        return _paths.resolve_wiki_path(git_root)

    def resolve_container_path(self, git_root):
        return _paths.resolve_container_path(git_root)

    def resolve_hub_path(self):
        return _paths.resolve_hub_path()

    def load_config(self, hub_root, git_root):
        return _config.load_config(hub_root, git_root)

    def resolve_active_hub(self, container_path, slug, cfg, git_root):
        return _paths.resolve_active_hub(container_path, slug, cfg=cfg, git_root=git_root)

    def resolve_worktrees_dir(self, cfg, git_root):
        return _paths.resolve_worktrees_dir(cfg, git_root)

    def is_inplace(self, slug, git_root, cfg):
        return _inplace.is_inplace(slug, git_root, cfg)

    def resolve_parent(self, status_path, slug):
        return _parent_branch.resolve(status_path, interactive=False, expected_slug=slug)

    def notify(self, event, detail, **context):
        return _notify.notify(event, detail, **context)

    def now(self) -> datetime.datetime:
        return datetime.datetime.now(datetime.timezone.utc)

    def now_iso(self) -> str:
        return _timestamp.now_utc_iso()

    def pid(self) -> int:
        return os.getpid()


def _last_output_line(completed) -> str:
    """Return the last non-empty stderr (else stdout) line of a finished process."""
    for stream in (completed.stderr, completed.stdout):
        lines = [line.strip() for line in (stream or "").splitlines() if line.strip()]
        if lines:
            return lines[-1]
    return "no output"


def _git_ok(ctx: Ctx, ops: Ops, argv: list[str], *, cwd: Path | None = None, what: str):
    """Run ``argv`` through ``ops`` and halt with a named message on a non-zero exit."""
    completed = ops.run(argv, cwd)
    if completed.returncode != 0:
        raise halt(f"{what} failed: {_last_output_line(completed)}", resume=[])
    return completed


def _commit_status(ctx: Ctx, ops: Ops, message: str) -> None:
    """Stage status.md, commit it with ``message``, and push."""
    root = str(ctx.git_root)
    _git_ok(ctx, ops, ["git", "-C", root, "add", str(ctx.status_path)], what="git add status.md")
    _git_ok(ctx, ops, ["git", "-C", root, "commit", "-m", message], what="git commit status.md")
    _git_ok(ctx, ops, ["git", "-C", root, "push"], what="git push")


def _parse_worktrees(porcelain: str) -> list[dict]:
    """
    Parse ``git worktree list --porcelain`` output.

    Returns one dict per worktree, main worktree first, with keys ``path`` (Path), ``branch`` (the
    ``refs/heads/...`` value or None), ``detached`` (bool), and ``prunable`` (bool).
    """
    entries = []
    for block in porcelain.split("\n\n"):
        lines = [line for line in block.splitlines() if line.strip()]
        if not lines:
            continue
        entry = {"path": None, "branch": None, "detached": False, "prunable": False}
        for line in lines:
            key, _, value = line.partition(" ")
            if key == "worktree":
                entry["path"] = Path(value)
            elif key == "branch":
                entry["branch"] = value
            elif key == "detached":
                entry["detached"] = True
            elif key == "prunable":
                entry["prunable"] = True
        entries.append(entry)
    return entries


def always(ctx: Ctx) -> bool:
    """Applicability predicate for steps that run on every route."""
    return True


STEPS: list[tuple[str, Callable[[Ctx, Ops], None], Callable[[Ctx], bool]]] = []


def _install_sigterm():
    """Install a SIGTERM handler raising ``Terminated``; returns the previous handler or None."""
    if threading.current_thread() is not threading.main_thread():
        return None

    def _raise_terminated(signum, frame):
        raise Terminated()

    return signal.signal(signal.SIGTERM, _raise_terminated)


def _restore_sigterm(prev) -> None:
    """Restore the handler returned by ``_install_sigterm`` (no-op when none was installed)."""
    if prev is not None:
        signal.signal(signal.SIGTERM, prev)


def _result(ctx: Ctx, stop: Stop | None, step: str) -> dict:
    """
    Build the JSON-able result dict of a run.

    ``report`` is the ctx report lines, the stop's own report lines (its reason when a halt gave
    none), then one line per timed step and a total line.
    """
    report = list(ctx.report)
    if stop is not None:
        report.extend(stop.report if stop.report else ([stop.reason] if stop.status == "halt" else []))
    for entry in ctx.timings:
        report.append(
            f"[mill-merge] {entry['step']}: {entry['wall_s']:.2f}s (git/net {entry['subproc_s']:.2f}s)"
        )
    total = sum(entry["wall_s"] for entry in ctx.timings)
    report.append(f"[mill-merge] total: {total:.2f}s")
    return {
        "status": stop.status if stop is not None else "ok",
        "route": ctx.route,
        "step": step,
        "reason": _ascii(stop.reason) if stop is not None else "",
        "action": stop.action if stop is not None else None,
        "resume": stop.resume if stop is not None else None,
        "data": (stop.data or {}) if stop is not None else {},
        "warnings": [_ascii(w) for w in ctx.warnings],
        "timings": ctx.timings,
        "report": [_ascii(line) for line in report],
    }


def run_merge(opts: MergeOptions, ops: Ops | None = None) -> dict:
    """
    Execute every applicable step in ``STEPS`` and return the result dict.

    A ``Stop`` raised by a step ends the run and becomes the result; any other exception
    propagates.
    Steps whose ``applies`` predicate is false are skipped without a timing entry.
    """
    ops = ops if ops is not None else Ops()
    ctx = Ctx(opts=opts)
    previous_handler = _install_sigterm()
    stop = None
    step_name = ""
    try:
        for name, fn, applies in STEPS:
            if not applies(ctx):
                continue
            step_name = name
            ops.subproc_s = 0.0
            started = time.monotonic()
            try:
                fn(ctx, ops)
            except Stop as raised:
                stop = raised
                step_name = raised.step or name
            finally:
                ctx.timings.append(
                    {
                        "step": name,
                        "wall_s": round(time.monotonic() - started, 3),
                        "subproc_s": round(ops.subproc_s, 3),
                    }
                )
            if stop is not None:
                break
    finally:
        _restore_sigterm(previous_handler)
    return _result(ctx, stop, step_name)


def step_entry(ctx: Ctx, ops: Ops) -> None:
    """
    Resolve mode and load config; bind slug, branch, and task paths on ``ctx``.

    Halts when the worktree has no registered task branch.
    The stale-worktree edge exists for one ambiguity: the branch matches cwd AND
    ``<worktrees-dir>/<slug>/`` exists on disk.
    It is only evaluated when that directory exists, otherwise every in-place run would take the
    "entry absent" branch and write a spurious timeline row.
    When the directory has no matching live registration it is in-place cruft: mode becomes
    ``inplace`` and the phase is round-tripped through two timeline rows, restoring the original
    ``phase:`` because the phase gate expects exactly ``done`` or ``pr-pending``.
    A detached or otherwise inconclusive registration halts rather than guessing.
    """
    ctx.git_root = ops.resolve_git_root()
    ctx.wiki_path = ops.resolve_wiki_path(ctx.git_root)
    ctx.container_path = ops.resolve_container_path(ctx.git_root)
    ctx.cfg = ops.load_config(ops.resolve_hub_path(), ctx.git_root)
    try:
        active = ops.task_data(ctx.git_root, ctx.wiki_path, ctx.cfg)
    except _marker.MarkerError:
        raise halt(
            "This worktree has no registered task branch -- `mill-merge` needs `status.md` to know "
            "the parent branch. Run `mill-claim` to convert this worktree to a tracked task, or "
            "merge manually.",
            resume=None,
        )
    ctx.slug = active["slug"]
    ctx.active_branch = active["branch"]
    inplace = ops.is_inplace(ctx.slug, ctx.git_root, ctx.cfg)
    ctx.mode = "inplace" if inplace else "worktree"

    porcelain = _git_ok(
        ctx, ops, ["git", "-C", str(ctx.git_root), "worktree", "list", "--porcelain"], what="git worktree list"
    ).stdout
    worktrees = _parse_worktrees(porcelain)

    ctx.worktree_root = ops.resolve_active_hub(ctx.container_path, ctx.slug, ctx.cfg, ctx.git_root)
    ctx.status_path = _paths.resolve_task_path(ctx.worktree_root, ctx.cfg["paths"]["status_md"])
    ctx.task_dir = ctx.status_path.parent
    ctx.task_dir_rel = ctx.task_dir.relative_to(ctx.worktree_root).as_posix()
    ctx.task_dir_git_rel = ctx.task_dir.relative_to(ctx.git_root).as_posix()

    worktree_dir = ops.resolve_worktrees_dir(ctx.cfg, ctx.git_root) / ctx.slug
    if worktree_dir.is_dir():
        _resolve_stale_worktree_edge(ctx, ops, worktrees, worktree_dir)

    if ctx.mode == "worktree" and worktrees and worktrees[0]["path"].resolve() == ctx.git_root.resolve():
        raise halt(
            "mill-merge from the main worktree requires in-place mode (no separate worktree exists "
            f"for the active slug). The active marker says `{ctx.slug}` is on branch "
            f"`{ctx.active_branch}`; mill-merge cannot proceed.",
            resume=None,
        )


def _resolve_stale_worktree_edge(ctx: Ctx, ops: Ops, worktrees: list[dict], worktree_dir: Path) -> None:
    """Disambiguate a worktree directory that may be a stale registration (see ``step_entry``)."""
    target = worktree_dir.resolve()
    entry = next((w for w in worktrees if w["path"].resolve() == target), None)
    expected_branch = f"refs/heads/{ctx.active_branch}"
    if entry is not None and not entry["prunable"]:
        if entry["branch"] == expected_branch:
            return
        if entry["branch"] is None:
            raise halt(
                f"The branch matches the current cwd AND `{worktree_dir}` exists, but the "
                "`git worktree list --porcelain` output was inconclusive; stopping rather than guessing.",
                resume=None,
            )
    ctx.mode = "inplace"
    if not ctx.status_path.exists():
        return
    original_phase = _status.read_full(ctx.status_path)["yaml"].get("phase")
    _status.append_phase(ctx.status_path, f"self-resolved-stale-worktree-{ctx.mode}", ops.now_iso())
    _status.append_phase(ctx.status_path, original_phase, ops.now_iso())
    _commit_status(ctx, ops, f"mill-merge: self-resolved stale-worktree ambiguity ({ctx.mode})")


def step_parent(ctx: Ctx, ops: Ops) -> None:
    """
    Resolve the parent branch and confirm it is still alive.

    ``--parent`` wins outright: no status read, no liveness check, no status write.
    An absent status.md (typical on closed-PR re-entry, where an earlier cleanup commit removed
    the task dir) falls back to the configured base branch with an operator notice.
    Otherwise the ``parent_branch:`` row is read; a missing row blocks the task.
    A dead parent (#817) is never rebound silently: without ``--confirm-parent`` the archive-tag
    chain is walked and the candidate is handed back to the caller as a ``confirm-parent`` callback.
    A chain that never reaches a live branch is a cycle and halts.
    """
    opts = ctx.opts
    if opts.parent:
        ctx.parent_branch = opts.parent
        return
    if not ctx.status_path.exists():
        base_branch = ctx.cfg.get("git", {}).get("base_branch", "main")
        ctx.parent_branch = base_branch
        ctx.report.append(
            f"status.md absent; assuming parent branch is `{base_branch}` (config `base_branch`) -- "
            "if this task's true parent differs (e.g. a stacked branch merging into something other "
            "than `base_branch`), abort and resolve manually."
        )
        return
    try:
        parent = ops.resolve_parent(ctx.status_path, ctx.slug)
    except _parent_branch.ParentBranchError:
        _status.set_blocked(ctx.status_path, f"missing parent_branch: row for {ctx.slug}", timestamp=ops.now_iso())
        _commit_status(ctx, ops, f"mill-merge: blocked (missing parent_branch: row) for {ctx.slug}")
        raise halt(
            f"BLOCKED: status.md is missing the parent_branch: row for {ctx.slug} -- mill-spawn should "
            "have written it; set it manually and re-run /mill-merge.",
            resume=[],
        )
    ctx.parent_branch = parent
    if ops.check_liveness(parent, ctx.git_root):
        return
    if opts.confirm_parent:
        _status.set_parent_branch(ctx.status_path, opts.confirm_parent)
        _commit_status(ctx, ops, f"mill-merge: rebind dead parent branch for {ctx.slug}")
        ctx.parent_branch = opts.confirm_parent
        ctx.report.append(f"Rebound dead parent branch {parent} -> {opts.confirm_parent}.")
        return
    resolution = ops.resolve_dead_parent(parent, ctx.git_root, ctx.cfg)
    chain = " -> ".join(resolution["hops"])
    if resolution["outcome"] == "cycle":
        raise halt(
            f"Archive-tag chain walk for `{parent}` hit its 10-hop cap without resolving a live "
            f"parent (chain: `{chain}`). Investigate manually.",
            resume=None,
        )
    candidate = resolution["branch"]
    if resolution["outcome"] == "resolved":
        text = (
            f"Parent branch `{parent}` no longer exists on origin. It appears to have been merged "
            f"and archived (chain: `{chain}`). The resolved successor parent is `{candidate}`. "
            f"Confirm before mill-merge proceeds against `{candidate}`."
        )
    else:
        text = (
            f"Parent branch `{parent}` no longer exists on origin. No archive-tag chain could "
            f"resolve a successor (`{resolution.get('reason')}`). Falling back to the repo's base "
            f"branch `{candidate}`. Confirm before mill-merge proceeds against `{candidate}`."
        )
    raise callback(
        "confirm-parent",
        text,
        resume=["--confirm-parent", candidate],
        data={
            "parent_branch": parent,
            "outcome": resolution["outcome"],
            "candidate": candidate,
            "hops": resolution["hops"],
            "reason": resolution.get("reason"),
        },
        report=[text],
    )


def step_phase_gate(ctx: Ctx, ops: Ops) -> None:
    """
    Decide from status.md (else the wiki) whether the task is in a mergeable phase.

    status.md is tried first.
    The raw ``slug:`` row is read, not ``_status.read_slug()``, which falls back to the parent
    directory name (always ``_mill``) and so cannot tell "row absent" from "row differs";
    an absent row is a no-op, matching ``_parent_branch``'s ``expected_slug`` check.
    A parse failure or slug mismatch falls through to the wiki: ``pr-pending`` maps to
    ``pr-pending``, ``ready-to-merge`` maps to ``done`` (direct mode's post-cleanup,
    not-yet-squashed signal, which the PR-state gate's ``none`` route relies on).
    Task title and description are cached here because the later cleanup commit deletes status.md;
    the wiki title is the only field available on the fallback route.
    """
    mismatch = False
    from_status = False
    if ctx.status_path.exists():
        try:
            yaml_block = _status.read_full(ctx.status_path)["yaml"]
        except Exception:  # noqa: BLE001 -- any parse failure means fall through to the wiki
            yaml_block = None
        if yaml_block is not None:
            raw_slug = yaml_block.get("slug")
            if raw_slug is not None and raw_slug != ctx.slug:
                mismatch = True
            else:
                from_status = True
                ctx.phase = yaml_block.get("phase")
                ctx.cached_task = yaml_block.get("task") or ctx.slug
                ctx.cached_task_description = yaml_block.get("task_description") or ctx.cached_task
    if not from_status:
        task = ops.get_task(ctx.wiki_path, ctx.slug)
        if task is None:
            raise halt(
                f"_mill/status.md absent and slug '{ctx.slug}' not found in wiki; cannot determine merge state.",
                resume=None,
            )
        if task["status"] == "pr-pending":
            ctx.phase = "pr-pending"
        elif task["status"] == "ready-to-merge":
            ctx.phase = "done"
        else:
            suffix = f" (status.md slug did not match task slug '{ctx.slug}')" if mismatch else ""
            raise halt(
                f"_mill/status.md absent and wiki does not show pr-pending or ready-to-merge for "
                f"'{ctx.slug}'; cannot determine merge state.{suffix}",
                resume=None,
            )
        ctx.cached_task = ctx.cached_task_description = task["title"]
    if ctx.phase not in ("done", "pr-pending"):
        raise halt(
            f"status.md phase is `{ctx.phase}`; mill-merge expects `done`. "
            "If the task is not finished, run mill-go first.",
            resume=None,
        )


def step_pr_state(ctx: Ctx, ops: Ops) -> None:
    """
    Route the run on the GitHub PR state of the child branch.

    ``merged`` is cleanup-only teardown; the local parent is intentionally NOT fast-forwarded and
    resyncs on the next parent-side fetch/pull.
    ``open`` halts, never auto-closing.
    ``closed`` is the expected success signal of the ``require_pr_to_base`` inspection flow:
    the operator closed the PR without merging, which IS the approval, so the local squash proceeds.
    Caution: in a branch-protected repo the later push may be rejected and trigger the fallback
    that creates a NEW PR, so ``closed`` -> local squash is not guaranteed terminal.
    ``none`` distinguishes a direct merge (phase ``done``) from a lost PR (phase ``pr-pending``).
    """
    completed = _git_ok(
        ctx, ops, ["git", "-C", str(ctx.git_root), "branch", "--show-current"], what="git branch --show-current"
    )
    ctx.child_branch = completed.stdout.strip()
    if not ctx.child_branch:
        raise halt(
            f"Detached HEAD in {ctx.git_root}; mill-merge needs the task branch checked out.", resume=None
        )
    pr = ops.pr_state(ctx.child_branch, ctx.git_root)
    state = pr["state"]
    if state == "merged":
        ctx.route = "pr-merged"
    elif state == "open":
        raise halt(
            f"PR #{pr.get('number')} is still open -- close or merge it on GitHub, then re-run /mill-merge.",
            resume=[],
        )
    elif state == "closed":
        ctx.route = "pr-closed"
    elif pr.get("error"):
        raise halt(
            f"Could not determine PR state for branch {ctx.child_branch}: {pr['error']}", resume=[]
        )
    elif ctx.phase == "done":
        ctx.route = "direct"
    else:
        raise halt("status.md says pr-pending but no PR on this branch; inspect manually.", resume=None)


def step_merge_in_check(ctx: Ctx, ops: Ops) -> None:
    """
    Ask the caller to run mill-merge-in when the parent has commits this branch lacks.

    Mirrors mill-merge-in's no-op check against the child ``git_root``: fetch the parent, prefer
    ``origin/<parent>`` when that ref exists and the local parent is an ancestor of it, then list
    ``HEAD..<merge_ref>``.
    """
    parent = ctx.parent_branch
    root = str(ctx.git_root)
    ops.run(["git", "-C", root, "fetch", "origin", parent])
    merge_ref = parent
    remote_ref = ops.run(["git", "-C", root, "rev-parse", "--verify", "--quiet", f"refs/remotes/origin/{parent}"])
    if remote_ref.returncode == 0:
        ancestor = ops.run(["git", "-C", root, "merge-base", "--is-ancestor", parent, f"origin/{parent}"])
        if ancestor.returncode == 0:
            merge_ref = f"origin/{parent}"
    ahead = _git_ok(ctx, ops, ["git", "-C", root, "log", f"HEAD..{merge_ref}", "--oneline"], what="git log")
    if ahead.stdout.strip():
        reason = f"Parent branch {parent} has commits this branch lacks; run mill-merge-in first."
        raise callback(
            "merge-in",
            reason,
            resume=["--merged-in"],
            data={"parent_branch": parent, "merge_ref": merge_ref},
            report=[reason],
        )


STEPS.append(("entry", step_entry, always))
STEPS.append(("parent", step_parent, always))
STEPS.append(("phase-gate", step_phase_gate, always))
STEPS.append(("pr-state", step_pr_state, always))
STEPS.append(
    (
        "merge-in-check",
        step_merge_in_check,
        lambda c: c.route in ("direct", "pr-closed") and c.mode == "worktree" and not c.opts.merged_in,
    )
)
