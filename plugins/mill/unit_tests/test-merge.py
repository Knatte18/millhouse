"""Unit tests for plugins/mill/scripts/_merge.py (entry-side steps and framework)."""
from __future__ import annotations

import signal
import subprocess
import sys
import tempfile
import time
from pathlib import Path
from unittest.mock import patch

HUB = Path(__file__).resolve().parent.parent.parent.parent
SCRIPTS = HUB / "plugins" / "mill" / "scripts"
sys.path.insert(0, str(SCRIPTS))

import _marker  # noqa: E402
import _merge  # noqa: E402
import _parent_branch  # noqa: E402
import _status  # noqa: E402

SLUG = "my-task"
BRANCH = f"hanf/{SLUG}"


def completed(returncode: int = 0, stdout: str = "", stderr: str = "") -> subprocess.CompletedProcess:
    return subprocess.CompletedProcess([], returncode, stdout, stderr)


class FakeOps(_merge.Ops):
    """Ops with scripted return values; records git calls and phase/notify/archive calls."""

    def __init__(self, git_rules=None, **returns):
        self.subproc_s = 0.0
        self.git_rules = list(git_rules or [])
        self.returns = returns
        self.calls: list[list[str]] = []
        self.phase_calls: list[tuple] = []
        self.notify_calls: list[tuple] = []
        self.archive_calls: list[tuple] = []
        self.liveness_calls: list[str] = []

    def _ret(self, name, default=None):
        value = self.returns.get(name, default)
        if isinstance(value, BaseException):
            raise value
        return value

    def run(self, argv, cwd=None):
        self.calls.append(list(argv))
        for tokens, outcome in self.git_rules:
            if all(token in argv for token in tokens):
                return outcome(argv) if callable(outcome) else outcome
        return completed()

    def task_data(self, git_root, wiki_path, cfg):
        return self._ret("task_data", {"slug": SLUG, "branch": BRANCH, "task_title": "T"})

    def check_liveness(self, branch, git_root):
        self.liveness_calls.append(branch)
        return self._ret("check_liveness", True)

    def resolve_dead_parent(self, branch, git_root, cfg):
        return self._ret("resolve_dead_parent")

    def pr_state(self, branch, cwd):
        return self._ret("pr_state", {"state": "none", "number": None, "error": None})

    def get_task(self, wiki_path, slug):
        return self._ret("get_task")

    def set_phase(self, wiki_path, slug, phase):
        self.phase_calls.append((slug, phase))

    def archive_tag(self, worktree, slug, child_branch):
        self.archive_calls.append((slug, child_branch))
        return self._ret("archive_tag", {"action": "created", "tag": f"archive/{slug}"})

    def resolve_git_root(self):
        return self.returns["git_root"]

    def resolve_wiki_path(self, git_root):
        return self.returns["git_root"].parent / "wiki"

    def resolve_container_path(self, git_root):
        return self.returns["git_root"].parent

    def resolve_hub_path(self):
        return self.returns["git_root"]

    def load_config(self, hub_root, git_root):
        return self.returns.get("cfg", {"paths": {"status_md": "_mill/status.md"}, "git": {"base_branch": "main"}})

    def resolve_active_hub(self, container_path, slug, cfg, git_root):
        return git_root

    def resolve_worktrees_dir(self, cfg, git_root):
        return self.returns["worktrees_dir"]

    def is_inplace(self, slug, git_root, cfg):
        return self.returns.get("is_inplace", True)

    def resolve_parent(self, status_path, slug):
        return self._ret("resolve_parent", "main")

    def notify(self, event, detail, **context):
        self.notify_calls.append((event, detail, context))

    def now_iso(self):
        return "2026-01-01T00:00:00Z"


def write_status(path: Path, *, phase="done", slug=SLUG, parent="main", task="My task", drop=()):
    """Write a status.md fixture; ``drop`` lists yaml keys whose rows are removed."""
    text = _status.render_initial(task, "Description", "2026-01-01T00:00:00Z", parent, slug, BRANCH)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")
    _status.append_phase(path, phase, "2026-01-01T00:00:01Z")
    if drop:
        lines = [ln for ln in path.read_text(encoding="utf-8").split("\n") if ln.split(":")[0] not in drop]
        path.write_text("\n".join(lines), encoding="utf-8")


def make_ctx(tmp: Path, **opts) -> _merge.Ctx:
    git_root = tmp / "git"
    git_root.mkdir(exist_ok=True)
    ctx = _merge.Ctx(opts=_merge.MergeOptions(**opts))
    ctx.git_root = git_root
    ctx.wiki_path = tmp / "wiki"
    ctx.cfg = {"paths": {"status_md": "_mill/status.md"}, "git": {"base_branch": "main"}}
    ctx.slug = SLUG
    ctx.active_branch = BRANCH
    ctx.mode = "worktree"
    ctx.worktree_root = git_root
    ctx.status_path = git_root / "_mill" / "status.md"
    return ctx


def make_ops(tmp: Path, **kwargs) -> FakeOps:
    git_root = tmp / "git"
    git_root.mkdir(exist_ok=True)
    kwargs.setdefault("worktrees_dir", tmp / "wtdir")
    return FakeOps(git_root=git_root, **kwargs)


def expect_stop(fn, ctx, ops) -> _merge.Stop:
    try:
        fn(ctx, ops)
    except _merge.Stop as stop:
        return stop
    raise AssertionError("expected Stop, none raised")


def porcelain(*entries: str) -> str:
    return "\n\n".join(entries) + "\n"


# ---------------------------------------------------------------------------
# Framework
# ---------------------------------------------------------------------------


def test_ascii_mapping():
    assert _merge._ascii("a—b→cé") == "a -- b -> c?"
    assert _merge._ascii("plain") == "plain"


def test_parse_worktrees_three_entries():
    text = (
        "worktree /repo/main\nHEAD abc\nbranch refs/heads/main\n\n"
        "worktree /repo/wts/x\nHEAD def\nbranch refs/heads/hanf/x\nprunable gitdir file missing\n\n"
        "worktree /repo/wts/y\nHEAD 123\ndetached\n"
    )
    assert _merge._parse_worktrees(text) == [
        {"path": Path("/repo/main"), "branch": "refs/heads/main", "detached": False, "prunable": False},
        {"path": Path("/repo/wts/x"), "branch": "refs/heads/hanf/x", "detached": False, "prunable": True},
        {"path": Path("/repo/wts/y"), "branch": None, "detached": True, "prunable": False},
    ]


def _noop(ctx, ops):
    return None


def test_runner_skips_and_halts():
    calls = []

    def first(ctx, ops):
        calls.append("first")

    def stopper(ctx, ops):
        calls.append("stopper")
        raise _merge.halt("nope", resume=None)

    def never(ctx, ops):
        calls.append("never")

    steps = [
        ("skipped", _noop, lambda c: False),
        ("first", first, _merge.always),
        ("stopper", stopper, _merge.always),
        ("never", never, _merge.always),
    ]
    with patch.object(_merge, "STEPS", steps):
        result = _merge.run_merge(_merge.MergeOptions(), FakeOps())
    assert calls == ["first", "stopper"]
    assert result["status"] == "halt"
    assert result["step"] == "stopper"
    assert result["resume"] is None
    assert [t["step"] for t in result["timings"]] == ["first", "stopper"]
    assert set(result) == {"status", "route", "step", "reason", "action", "resume", "data", "warnings", "timings", "report"}


def test_runner_propagates_plain_exception():
    def boom(ctx, ops):
        raise RuntimeError("boom")

    with patch.object(_merge, "STEPS", [("boom", boom, _merge.always)]):
        try:
            _merge.run_merge(_merge.MergeOptions(), FakeOps())
        except RuntimeError as exc:
            assert str(exc) == "boom"
        else:
            raise AssertionError("RuntimeError should propagate")


def test_runner_ok_carries_last_step_name():
    steps = [("a", _noop, _merge.always), ("b", _noop, _merge.always), ("c", _noop, lambda c: False)]
    with patch.object(_merge, "STEPS", steps):
        result = _merge.run_merge(_merge.MergeOptions(), FakeOps())
    assert result["status"] == "ok"
    assert result["step"] == "b"


def test_stop_step_override_names_result_step():
    def locker(ctx, ops):
        raise _merge.halt("locked", resume=[], step="lock")

    with patch.object(_merge, "STEPS", [("squash", locker, _merge.always)]):
        result = _merge.run_merge(_merge.MergeOptions(), FakeOps())
    assert result["step"] == "lock"
    assert result["timings"][0]["step"] == "squash"


def test_result_report_ends_with_timing_lines():
    ctx = _merge.Ctx()
    ctx.report.append("note")
    ctx.timings = [
        {"step": "entry", "wall_s": 1.0, "subproc_s": 0.5},
        {"step": "parent", "wall_s": 2.0, "subproc_s": 0.25},
    ]
    result = _merge._result(ctx, _merge.halt("bad — thing", resume=[]), "parent")
    assert result["report"] == [
        "note",
        "bad  --  thing",
        "[mill-merge] entry: 1.00s (git/net 0.50s)",
        "[mill-merge] parent: 2.00s (git/net 0.25s)",
        "[mill-merge] total: 3.00s",
    ]
    assert result["reason"] == "bad  --  thing"


def test_ops_timed_accumulates_subproc_time():
    ops = _merge.Ops()
    assert ops._timed(lambda x: x + 1, 1) == 2
    ops._timed(time.sleep, 0.02)
    assert ops.subproc_s >= 0.02

    def failing():
        time.sleep(0.02)
        raise ValueError("x")

    before = ops.subproc_s
    try:
        ops._timed(failing)
    except ValueError:
        pass
    assert ops.subproc_s >= before + 0.02


def test_sigterm_handler_raises_terminated_and_restores():
    original = signal.getsignal(signal.SIGTERM)
    previous = _merge._install_sigterm()
    try:
        handler = signal.getsignal(signal.SIGTERM)
        try:
            handler(signal.SIGTERM, None)
        except _merge.Terminated:
            pass
        else:
            raise AssertionError("handler should raise Terminated")
    finally:
        _merge._restore_sigterm(previous)
    assert signal.getsignal(signal.SIGTERM) == original


def test_git_ok_halts_with_last_output_line():
    with tempfile.TemporaryDirectory() as tmp:
        ctx = make_ctx(Path(tmp))
        ops = make_ops(Path(tmp), git_rules=[(["push"], completed(1, "", "first\nrejected\n"))])
        stop = expect_stop(lambda c, o: _merge._git_ok(c, o, ["git", "push"], what="git push"), ctx, ops)
        assert stop.reason == "git push failed: rejected"
        assert stop.resume == []


# ---------------------------------------------------------------------------
# Entry step
# ---------------------------------------------------------------------------


def entry_ops(tmp: Path, worktrees: str, **kwargs) -> FakeOps:
    return make_ops(tmp, git_rules=[(["worktree", "list"], completed(0, worktrees))], **kwargs)


def other_main(tmp: Path) -> str:
    return f"worktree {tmp / 'elsewhere'}\nHEAD a\nbranch refs/heads/main\n"


def commit_calls(ops: FakeOps) -> list[list[str]]:
    return [c for c in ops.calls if "commit" in c]


def test_entry_marker_error_halts():
    with tempfile.TemporaryDirectory() as tmp:
        tmp = Path(tmp)
        ops = entry_ops(tmp, other_main(tmp), task_data=_marker.MarkerError("x"))
        stop = expect_stop(_merge.step_entry, _merge.Ctx(opts=_merge.MergeOptions()), ops)
        assert stop.status == "halt"
        assert stop.resume is None
        assert "no registered task branch" in stop.reason


def test_entry_inplace_without_worktree_dir_skips_stale_edge():
    with tempfile.TemporaryDirectory() as tmp:
        tmp = Path(tmp)
        write_status(tmp / "git" / "_mill" / "status.md")
        ops = entry_ops(tmp, other_main(tmp), is_inplace=True)
        ctx = _merge.Ctx(opts=_merge.MergeOptions())
        _merge.step_entry(ctx, ops)
        assert ctx.mode == "inplace"
        assert ctx.slug == SLUG
        assert ctx.task_dir_rel == "_mill"
        assert ctx.task_dir_git_rel == "_mill"
        assert commit_calls(ops) == []
        assert "self-resolved" not in ctx.status_path.read_text(encoding="utf-8")


def test_entry_stale_edge_entry_absent_writes_rows_and_commits():
    with tempfile.TemporaryDirectory() as tmp:
        tmp = Path(tmp)
        write_status(tmp / "git" / "_mill" / "status.md", phase="done")
        (tmp / "wtdir" / SLUG).mkdir(parents=True)
        ops = entry_ops(tmp, other_main(tmp), is_inplace=False)
        ctx = _merge.Ctx(opts=_merge.MergeOptions())
        _merge.step_entry(ctx, ops)
        assert ctx.mode == "inplace"
        text = ctx.status_path.read_text(encoding="utf-8")
        assert "self-resolved-stale-worktree-inplace" in text
        yaml_block = _status.read_full(ctx.status_path)["yaml"]
        assert yaml_block["phase"] == "done"
        assert len(commit_calls(ops)) == 1
        assert commit_calls(ops)[0][-1] == "mill-merge: self-resolved stale-worktree ambiguity (inplace)"
        assert any("push" in c for c in ops.calls)


def test_entry_stale_edge_matching_live_entry_is_no_op():
    with tempfile.TemporaryDirectory() as tmp:
        tmp = Path(tmp)
        write_status(tmp / "git" / "_mill" / "status.md")
        wt_dir = tmp / "wtdir" / SLUG
        wt_dir.mkdir(parents=True)
        listing = other_main(tmp) + f"\nworktree {wt_dir}\nHEAD b\nbranch refs/heads/{BRANCH}\n"
        ops = entry_ops(tmp, listing, is_inplace=False)
        ctx = _merge.Ctx(opts=_merge.MergeOptions())
        _merge.step_entry(ctx, ops)
        assert ctx.mode == "worktree"
        assert commit_calls(ops) == []


def test_entry_stale_edge_detached_entry_halts():
    with tempfile.TemporaryDirectory() as tmp:
        tmp = Path(tmp)
        write_status(tmp / "git" / "_mill" / "status.md")
        wt_dir = tmp / "wtdir" / SLUG
        wt_dir.mkdir(parents=True)
        listing = other_main(tmp) + f"\nworktree {wt_dir}\nHEAD b\ndetached\n"
        ops = entry_ops(tmp, listing, is_inplace=False)
        stop = expect_stop(_merge.step_entry, _merge.Ctx(opts=_merge.MergeOptions()), ops)
        assert stop.resume is None
        assert "inconclusive" in stop.reason


def test_entry_main_worktree_in_worktree_mode_halts():
    with tempfile.TemporaryDirectory() as tmp:
        tmp = Path(tmp)
        (tmp / "git").mkdir()
        listing = f"worktree {tmp / 'git'}\nHEAD a\nbranch refs/heads/main\n"
        ops = entry_ops(tmp, listing, is_inplace=False)
        stop = expect_stop(_merge.step_entry, _merge.Ctx(opts=_merge.MergeOptions()), ops)
        assert stop.resume is None
        assert "requires in-place mode" in stop.reason
        assert SLUG in stop.reason and BRANCH in stop.reason


# ---------------------------------------------------------------------------
# Parent step
# ---------------------------------------------------------------------------


def test_parent_status_absent_uses_base_branch_and_notice():
    with tempfile.TemporaryDirectory() as tmp:
        tmp = Path(tmp)
        ctx = make_ctx(tmp)
        ctx.cfg["git"]["base_branch"] = "trunk"
        ops = make_ops(tmp)
        _merge.step_parent(ctx, ops)
        assert ctx.parent_branch == "trunk"
        assert ctx.report == [
            "status.md absent; assuming parent branch is `trunk` (config `base_branch`) -- if this "
            "task's true parent differs (e.g. a stacked branch merging into something other than "
            "`base_branch`), abort and resolve manually."
        ]
        assert ops.liveness_calls == []


def test_parent_missing_row_blocks_and_halts():
    with tempfile.TemporaryDirectory() as tmp:
        tmp = Path(tmp)
        ctx = make_ctx(tmp)
        write_status(ctx.status_path, drop=("parent_branch",))
        ops = make_ops(tmp, resolve_parent=_parent_branch.ParentBranchError("no parent"))
        stop = expect_stop(_merge.step_parent, ctx, ops)
        assert stop.resume == []
        assert stop.reason.startswith(f"BLOCKED: status.md is missing the parent_branch: row for {SLUG}")
        yaml_block = _status.read_full(ctx.status_path)["yaml"]
        assert yaml_block["phase"] == "blocked"
        assert yaml_block["blocked_reason"] == f"missing parent_branch: row for {SLUG}"
        assert commit_calls(ops)[0][-1] == f"mill-merge: blocked (missing parent_branch: row) for {SLUG}"


def _dead_parent_stop(outcome: dict) -> _merge.Stop:
    with tempfile.TemporaryDirectory() as tmp:
        tmp = Path(tmp)
        ctx = make_ctx(tmp)
        write_status(ctx.status_path, parent="feature")
        ops = make_ops(tmp, resolve_parent="feature", check_liveness=False, resolve_dead_parent=outcome)
        return expect_stop(_merge.step_parent, ctx, ops)


def test_parent_dead_resolved_and_fallback_callback():
    resolved = _dead_parent_stop({"outcome": "resolved", "branch": "main", "hops": ["a", "b"]})
    assert resolved.status == "callback"
    assert resolved.action == "confirm-parent"
    assert resolved.resume == ["--confirm-parent", "main"]
    assert "chain: `a -> b`" in resolved.reason
    assert resolved.data["candidate"] == "main"
    assert resolved.data["parent_branch"] == "feature"
    fallback = _dead_parent_stop({"outcome": "fallback", "reason": "no-tag", "branch": "main", "hops": ["a"]})
    assert fallback.resume == ["--confirm-parent", "main"]
    assert "(`no-tag`)" in fallback.reason
    assert fallback.report == [fallback.reason]


def test_parent_dead_cycle_halts():
    stop = _dead_parent_stop({"outcome": "cycle", "hops": ["a", "b"]})
    assert stop.status == "halt"
    assert stop.resume is None
    assert "10-hop cap" in stop.reason


def test_parent_confirm_parent_rebinds_and_continues():
    with tempfile.TemporaryDirectory() as tmp:
        tmp = Path(tmp)
        ctx = make_ctx(tmp, confirm_parent="main")
        write_status(ctx.status_path, parent="feature")
        ops = make_ops(tmp, resolve_parent="feature", check_liveness=False)
        _merge.step_parent(ctx, ops)
        assert ctx.parent_branch == "main"
        assert _status.read_full(ctx.status_path)["yaml"]["parent_branch"] == "main"
        assert commit_calls(ops)[0][-1] == f"mill-merge: rebind dead parent branch for {SLUG}"
        assert ctx.report == ["Rebound dead parent branch feature -> main."]


def test_parent_flag_skips_status_and_liveness():
    with tempfile.TemporaryDirectory() as tmp:
        tmp = Path(tmp)
        ctx = make_ctx(tmp, parent="stack-base")
        write_status(ctx.status_path, parent="feature")
        before = ctx.status_path.read_bytes()
        ops = make_ops(tmp, check_liveness=False)
        _merge.step_parent(ctx, ops)
        assert ctx.parent_branch == "stack-base"
        assert ops.liveness_calls == []
        assert ops.calls == []
        assert ctx.status_path.read_bytes() == before


# ---------------------------------------------------------------------------
# Phase gate
# ---------------------------------------------------------------------------


def run_phase_gate(tmp: Path, *, status=None, task=None):
    ctx = make_ctx(tmp)
    if status is not None:
        write_status(ctx.status_path, **status)
    ops = make_ops(tmp, get_task=task)
    return ctx, ops


def test_phase_gate_status_done_and_pr_pending():
    for phase in ("done", "pr-pending"):
        with tempfile.TemporaryDirectory() as tmp:
            ctx, ops = run_phase_gate(Path(tmp), status={"phase": phase})
            _merge.step_phase_gate(ctx, ops)
            assert ctx.phase == phase
            assert ctx.cached_task == "My task"
            assert ctx.cached_task_description == "Description"


def test_phase_gate_complete_halts():
    with tempfile.TemporaryDirectory() as tmp:
        ctx, ops = run_phase_gate(Path(tmp), status={"phase": "complete"})
        stop = expect_stop(_merge.step_phase_gate, ctx, ops)
        assert stop.resume is None
        assert stop.reason.startswith("status.md phase is `complete`; mill-merge expects `done`.")


def test_phase_gate_missing_task_key_caches_slug():
    with tempfile.TemporaryDirectory() as tmp:
        ctx, ops = run_phase_gate(Path(tmp), status={"phase": "done"})
        lines = [ln for ln in ctx.status_path.read_text(encoding="utf-8").split("\n") if not ln.startswith("task:")]
        text = "\n".join(lines)
        text = text.replace("task_description: |\n  Description\n", "")
        ctx.status_path.write_text(text, encoding="utf-8")
        _merge.step_phase_gate(ctx, ops)
        assert ctx.cached_task == SLUG
        assert ctx.cached_task_description == SLUG


def test_phase_gate_slug_mismatch_falls_back_to_wiki_with_parenthetical():
    with tempfile.TemporaryDirectory() as tmp:
        ctx, ops = run_phase_gate(Path(tmp), status={"phase": "done", "slug": "other"}, task={"status": "active", "title": "W"})
        stop = expect_stop(_merge.step_phase_gate, ctx, ops)
        assert stop.reason.endswith(f"(status.md slug did not match task slug '{SLUG}')")
    with tempfile.TemporaryDirectory() as tmp:
        ctx, ops = run_phase_gate(Path(tmp), status={"phase": "done", "slug": "other"}, task={"status": "pr-pending", "title": "W"})
        _merge.step_phase_gate(ctx, ops)
        assert ctx.phase == "pr-pending"
        assert ctx.cached_task == "W"


def test_phase_gate_status_absent_wiki_table():
    with tempfile.TemporaryDirectory() as tmp:
        ctx, ops = run_phase_gate(Path(tmp), task={"status": "pr-pending", "title": "Wiki title"})
        _merge.step_phase_gate(ctx, ops)
        assert (ctx.phase, ctx.cached_task, ctx.cached_task_description) == ("pr-pending", "Wiki title", "Wiki title")
    with tempfile.TemporaryDirectory() as tmp:
        ctx, ops = run_phase_gate(Path(tmp), task={"status": "ready-to-merge", "title": "Wiki title"})
        _merge.step_phase_gate(ctx, ops)
        assert ctx.phase == "done"
    with tempfile.TemporaryDirectory() as tmp:
        ctx, ops = run_phase_gate(Path(tmp), task={"status": "active", "title": "x"})
        stop = expect_stop(_merge.step_phase_gate, ctx, ops)
        assert stop.reason == (
            f"_mill/status.md absent and wiki does not show pr-pending or ready-to-merge for '{SLUG}'; "
            "cannot determine merge state."
        )
    with tempfile.TemporaryDirectory() as tmp:
        ctx, ops = run_phase_gate(Path(tmp), task=None)
        stop = expect_stop(_merge.step_phase_gate, ctx, ops)
        assert stop.reason == f"_mill/status.md absent and slug '{SLUG}' not found in wiki; cannot determine merge state."
        assert stop.resume is None


# ---------------------------------------------------------------------------
# PR-state gate
# ---------------------------------------------------------------------------


def pr_gate(tmp: Path, pr: dict, phase: str = "done", branch: str = BRANCH):
    ctx = make_ctx(tmp)
    ctx.phase = phase
    ops = make_ops(tmp, pr_state=pr, git_rules=[(["branch", "--show-current"], completed(0, branch + "\n"))])
    return ctx, ops


def test_pr_state_routes():
    with tempfile.TemporaryDirectory() as tmp:
        ctx, ops = pr_gate(Path(tmp), {"state": "merged", "number": 3})
        _merge.step_pr_state(ctx, ops)
        assert (ctx.route, ctx.child_branch) == ("pr-merged", BRANCH)
    with tempfile.TemporaryDirectory() as tmp:
        ctx, ops = pr_gate(Path(tmp), {"state": "closed", "number": 3})
        _merge.step_pr_state(ctx, ops)
        assert ctx.route == "pr-closed"
    with tempfile.TemporaryDirectory() as tmp:
        ctx, ops = pr_gate(Path(tmp), {"state": "none", "number": None})
        _merge.step_pr_state(ctx, ops)
        assert ctx.route == "direct"


def test_pr_state_open_halts_with_number():
    with tempfile.TemporaryDirectory() as tmp:
        ctx, ops = pr_gate(Path(tmp), {"state": "open", "number": 42})
        stop = expect_stop(_merge.step_pr_state, ctx, ops)
        assert stop.reason == "PR #42 is still open -- close or merge it on GitHub, then re-run /mill-merge."
        assert stop.resume == []


def test_pr_state_none_with_error_halts():
    with tempfile.TemporaryDirectory() as tmp:
        ctx, ops = pr_gate(Path(tmp), {"state": "none", "number": None, "error": "gh: not logged in"})
        stop = expect_stop(_merge.step_pr_state, ctx, ops)
        assert stop.reason == f"Could not determine PR state for branch {BRANCH}: gh: not logged in"
        assert stop.resume == []


def test_pr_state_none_pr_pending_halts():
    with tempfile.TemporaryDirectory() as tmp:
        ctx, ops = pr_gate(Path(tmp), {"state": "none", "number": None}, phase="pr-pending")
        stop = expect_stop(_merge.step_pr_state, ctx, ops)
        assert stop.reason == "status.md says pr-pending but no PR on this branch; inspect manually."
        assert stop.resume is None


def test_pr_state_detached_head_halts():
    with tempfile.TemporaryDirectory() as tmp:
        ctx, ops = pr_gate(Path(tmp), {"state": "none"}, branch="")
        stop = expect_stop(_merge.step_pr_state, ctx, ops)
        assert stop.reason.startswith("Detached HEAD in ")
        assert stop.resume is None


# ---------------------------------------------------------------------------
# Merge-in check
# ---------------------------------------------------------------------------


def merge_in_ops(tmp: Path, log_out: str) -> FakeOps:
    return make_ops(
        tmp,
        git_rules=[
            (["log"], completed(0, log_out)),
            (["merge-base"], completed(0)),
        ],
    )


def test_merge_in_parent_ahead_raises_callback():
    with tempfile.TemporaryDirectory() as tmp:
        tmp = Path(tmp)
        ctx = make_ctx(tmp)
        ctx.parent_branch = "main"
        ops = merge_in_ops(tmp, "abc123 something\n")
        stop = expect_stop(_merge.step_merge_in_check, ctx, ops)
        assert stop.action == "merge-in"
        assert stop.resume == ["--merged-in"]
        assert stop.data == {"parent_branch": "main", "merge_ref": "origin/main"}
        assert ["git", "-C", str(ctx.git_root), "log", "HEAD..origin/main", "--oneline"] in ops.calls


def test_merge_in_falls_back_to_local_parent_ref():
    with tempfile.TemporaryDirectory() as tmp:
        tmp = Path(tmp)
        ctx = make_ctx(tmp)
        ctx.parent_branch = "main"
        ops = make_ops(
            tmp,
            git_rules=[(["merge-base"], completed(1)), (["log"], completed(0, "abc x\n"))],
        )
        stop = expect_stop(_merge.step_merge_in_check, ctx, ops)
        assert stop.data["merge_ref"] == "main"


def test_merge_in_up_to_date_continues():
    with tempfile.TemporaryDirectory() as tmp:
        tmp = Path(tmp)
        ctx = make_ctx(tmp)
        ctx.parent_branch = "main"
        _merge.step_merge_in_check(ctx, merge_in_ops(tmp, ""))


def run_registered_steps(tmp: Path, ctx_state: dict, opts: _merge.MergeOptions):
    """Run only the registered merge-in-check entry against a prepared route/mode."""
    _name, _fn, applies = next(s for s in _merge.STEPS if s[0] == "merge-in-check")
    ctx = make_ctx(tmp)
    ctx.opts = opts
    ctx.parent_branch = "main"
    for key, value in ctx_state.items():
        setattr(ctx, key, value)
    return ctx, applies


def test_merge_in_check_applicability():
    with tempfile.TemporaryDirectory() as tmp:
        tmp = Path(tmp)
        for state, opts, expected in [
            ({"route": "direct", "mode": "worktree"}, _merge.MergeOptions(), True),
            ({"route": "pr-closed", "mode": "worktree"}, _merge.MergeOptions(), True),
            ({"route": "direct", "mode": "worktree"}, _merge.MergeOptions(merged_in=True), False),
            ({"route": "direct", "mode": "inplace"}, _merge.MergeOptions(), False),
            ({"route": "pr-merged", "mode": "worktree"}, _merge.MergeOptions(), False),
        ]:
            ctx, applies = run_registered_steps(tmp, state, opts)
            assert applies(ctx) is expected, (state, opts)


def test_merge_in_check_skipped_by_runner_when_merged_in():
    with tempfile.TemporaryDirectory() as tmp:
        tmp = Path(tmp)
        steps = [s for s in _merge.STEPS if s[0] == "merge-in-check"]

        def set_route(ctx, ops):
            ctx.route = "direct"
            ctx.mode = "worktree"

        ops = make_ops(tmp)
        with patch.object(_merge, "STEPS", [("route", set_route, _merge.always)] + steps):
            result = _merge.run_merge(_merge.MergeOptions(merged_in=True), ops)
        assert [t["step"] for t in result["timings"]] == ["route"]
        assert ops.calls == []


def test_registered_step_order():
    assert [s[0] for s in _merge.STEPS][:5] == ["entry", "parent", "phase-gate", "pr-state", "merge-in-check"]


def main() -> int:
    tests = [(name, fn) for name, fn in sorted(globals().items()) if name.startswith("test_") and callable(fn)]
    failures = []
    for name, fn in tests:
        try:
            fn()
            print(f"PASS {name}")
        except Exception as exc:  # noqa: BLE001
            print(f"FAIL {name}: {exc!r}", file=sys.stderr)
            failures.append(name)
    print()
    if failures:
        print(f"FAIL -- {len(failures)} of {len(tests)} tests: {failures}", file=sys.stderr)
        return 1
    print(f"All {len(tests)} merge unit tests passed.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
