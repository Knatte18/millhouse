"""Unit tests for plugins/mill/scripts/_merge.py (entry-side steps and framework)."""
from __future__ import annotations

import datetime
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

import _marker
import _merge
import _parent_branch
import _status

NOW = datetime.datetime(2026, 1, 1, 12, 0, 0, tzinfo=datetime.timezone.utc)
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
        self.cwds: list = []

    def _ret(self, name, default=None):
        value = self.returns.get(name, default)
        if isinstance(value, BaseException):
            raise value
        return value

    def run(self, argv, cwd=None):
        self.calls.append(list(argv))
        self.cwds.append(cwd)
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

    def now(self):
        return self.returns.get("now", NOW)

    def pid(self):
        return 4242


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
    assert _merge._ascii("a\u2014b\u2192c\u00e9") == "a -- b -> c?"
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


# ---------------------------------------------------------------------------
# Cleanup commit
# ---------------------------------------------------------------------------


def cleanup_ctx(tmp: Path, *, task_dir_exists: bool) -> _merge.Ctx:
    ctx = make_ctx(tmp)
    ctx.task_dir = ctx.git_root / "_mill"
    if task_dir_exists:
        ctx.task_dir.mkdir(exist_ok=True)
    ctx.task_dir_git_rel = "_mill"
    return ctx


def commands(ops: FakeOps, verb: str) -> list[list[str]]:
    return [argv for argv in ops.calls if verb in argv]


def test_cleanup_no_hits_no_warnings():
    with tempfile.TemporaryDirectory() as td:
        tmp = Path(td)
        ctx = cleanup_ctx(tmp, task_dir_exists=False)
        ops = make_ops(tmp, git_rules=[(["grep"], completed(1))])
        _merge.step_cleanup_commit(ctx, ops)
        assert ctx.warnings == []
        assert commands(ops, "rm") == []
        assert commands(ops, "commit") == []


def test_cleanup_worktree_and_wiki_hits_warn_and_continue():
    with tempfile.TemporaryDirectory() as td:
        tmp = Path(td)
        ctx = cleanup_ctx(tmp, task_dir_exists=False)
        wiki = str(ctx.wiki_path)

        def grep(argv):
            return completed(0, "Home.md:3:[x](_mill/discussion.md)\n") if wiki in argv else completed(0, "docs/a.md:1:[y](../_mill/discussion.md)\n")

        ops = make_ops(tmp, git_rules=[(["grep"], grep)])
        _merge.step_cleanup_commit(ctx, ops)
        assert ctx.warnings == [
            "permanent-doc citation of _mill/discussion.md is about to go dead: docs/a.md:1:[y](../_mill/discussion.md)",
            "permanent-doc citation of _mill/discussion.md is about to go dead: wiki:Home.md:3:[x](_mill/discussion.md)",
        ]
        wiki_grep = [argv for argv in ops.calls if wiki in argv and "grep" in argv]
        assert len(wiki_grep) == 1 and wiki_grep[0][:3] == ["git", "-C", wiki]
        assert all(cwd != ctx.wiki_path for cwd in ops.cwds)


def test_cleanup_task_dir_present_removes_then_commits():
    with tempfile.TemporaryDirectory() as td:
        tmp = Path(td)
        ctx = cleanup_ctx(tmp, task_dir_exists=True)
        ops = make_ops(tmp, git_rules=[(["diff", "--cached"], completed(1))])
        _merge.step_cleanup_commit(ctx, ops)
        root = str(ctx.git_root)
        verbs = [argv[3] for argv in ops.calls if argv[3] in ("rm", "commit")]
        assert verbs == ["rm", "commit"]
        assert ["git", "-C", root, "commit", "-m", "chore: pre-merge cleanup"] in ops.calls


def test_cleanup_commit_failure_resets_and_halts():
    with tempfile.TemporaryDirectory() as td:
        tmp = Path(td)
        ctx = cleanup_ctx(tmp, task_dir_exists=True)
        ops = make_ops(
            tmp, git_rules=[(["diff", "--cached"], completed(1)), (["commit"], completed(1, "", "hook failed"))]
        )
        stop = expect_stop(_merge.step_cleanup_commit, ctx, ops)
        assert ["git", "-C", str(ctx.git_root), "reset", "--hard", "HEAD"] in ops.calls
        assert stop.reason == "cleanup-commit failed: hook failed; task branch reset to HEAD. Re-run /mill-merge."


# ---------------------------------------------------------------------------
# Squash
# ---------------------------------------------------------------------------

PARENT = "main"
CHILD = BRANCH


def squash_setup(tmp: Path, *, mode="worktree", rules=None, **returns):
    """Build ctx/ops for step_squash with the parent worktree in ``tmp / "parent"``."""
    parent_dir = tmp / "parent"
    parent_dir.mkdir(exist_ok=True)
    ctx = make_ctx(tmp)
    ctx.mode = mode
    ctx.parent_branch = PARENT
    ctx.child_branch = CHILD
    ctx.cached_task = "My task"
    ctx.cached_task_description = "Description"
    ctx.task_dir_rel = "_mill"
    listing = f"worktree {parent_dir}\nHEAD abc\nbranch refs/heads/{PARENT}\n"
    all_rules = list(rules or []) + [(["worktree", "list"], completed(0, listing))]
    ops = make_ops(tmp, git_rules=all_rules, **returns)
    return ctx, ops, parent_dir


def lock_path(parent_dir: Path) -> Path:
    return parent_dir / ".scratch" / "merge.lock"


STAGED = (["diff", "--cached", "--quiet"], completed(1))


def resets(ops: FakeOps) -> list[list[str]]:
    return [argv for argv in ops.calls if "reset" in argv and "--hard" in argv]


def test_squash_lock_acquired_and_released():
    with tempfile.TemporaryDirectory() as td:
        ctx, ops, parent_dir = squash_setup(Path(td), rules=[STAGED])
        seen = {}

        def push(argv):
            seen["lock"] = lock_path(parent_dir).read_text(encoding="utf-8")
            return completed()

        ops.git_rules.insert(0, (["push"], push))
        _merge.step_squash(ctx, ops)
        assert seen["lock"] == f"4242\n2026-01-01T12:00:00Z\n{CHILD}\n"
        assert not lock_path(parent_dir).exists()


def test_squash_stale_lock_overwritten():
    with tempfile.TemporaryDirectory() as td:
        ctx, ops, parent_dir = squash_setup(Path(td), rules=[STAGED])
        lock_path(parent_dir).parent.mkdir()
        lock_path(parent_dir).write_text("1\n2026-01-01T11:54:00Z\nother/branch\n", encoding="utf-8")
        _merge.step_squash(ctx, ops)
        assert commands(ops, "merge") != []


def test_squash_fresh_foreign_lock_halts_with_lock_step():
    with tempfile.TemporaryDirectory() as td:
        ctx, ops, parent_dir = squash_setup(Path(td))
        lock_path(parent_dir).parent.mkdir()
        lock_path(parent_dir).write_text("77\n2026-01-01T11:58:00Z\nother/branch\n", encoding="utf-8")
        stop = expect_stop(_merge.step_squash, ctx, ops)
        assert stop.step == "lock"
        assert stop.resume == []
        assert stop.data == {
            "lock_path": str(lock_path(parent_dir)),
            "pid": "77",
            "timestamp": "2026-01-01T11:58:00Z",
            "branch": "other/branch",
        }
        assert len(ops.calls) == 1 and "worktree" in ops.calls[0]
        assert lock_path(parent_dir).exists()


def test_squash_lock_released_on_dirty_halt_push_failure_and_exception():
    scenarios = [
        [(["status", "--porcelain"], completed(0, " M a.py\n"))],
        [STAGED, (["push"], completed(1, "", "fatal: unable to access"))],
        [STAGED, (["merge", "--squash"], RuntimeError("boom"))],
    ]
    for rules in scenarios:
        rules = [
            (tokens, (lambda argv, o=outcome: (_ for _ in ()).throw(o)) if isinstance(outcome, BaseException) else outcome)
            for tokens, outcome in rules
        ]
        with tempfile.TemporaryDirectory() as td:
            ctx, ops, parent_dir = squash_setup(Path(td), rules=rules)
            try:
                _merge.step_squash(ctx, ops)
            except (_merge.Stop, RuntimeError):
                pass
            else:
                raise AssertionError("expected failure")
            assert not lock_path(parent_dir).exists()


def test_squash_dirty_parent_and_diverged_parent_halt_without_reset():
    for rule in (
        (["status", "--porcelain"], completed(0, " M a.py\n")),
        (["merge", "--ff-only"], completed(1, "", "not possible")),
    ):
        with tempfile.TemporaryDirectory() as td:
            ctx, ops, _ = squash_setup(Path(td), rules=[rule])
            stop = expect_stop(_merge.step_squash, ctx, ops)
            assert stop.resume == []
            assert resets(ops) == []
            assert commands(ops, "--squash") == []


def test_squash_landed_unpushed_pushes_without_new_squash():
    with tempfile.TemporaryDirectory() as td:
        ctx, ops, _ = squash_setup(Path(td), rules=[(["origin/main..main"], completed(0, "abc\n"))])
        _merge.step_squash(ctx, ops)
        assert commands(ops, "--squash") == []
        assert len(commands(ops, "push")) == 1


def test_squash_landed_on_origin_skips_squash_and_push():
    with tempfile.TemporaryDirectory() as td:
        ctx, ops, _ = squash_setup(Path(td), rules=[(["origin/main", "--grep=^Mill-Task: my-task$"], completed(0, "abc\n"))])
        _merge.step_squash(ctx, ops)
        assert commands(ops, "--squash") == []
        assert commands(ops, "push") == []
        assert ctx.report == ["Squash for my-task already on origin/main; skipping squash."]


def test_squash_legacy_landed_by_tree_match():
    with tempfile.TemporaryDirectory() as td:
        rules = [
            (["merge-base"], completed(0, "base1\n")),
            (["--name-only", "base1"], completed(0, "src/a.py\n_mill/status.md\n")),
        ]
        ctx, ops, _ = squash_setup(Path(td), rules=rules)
        _merge.step_squash(ctx, ops)
        assert ["git", "-C", str(Path(td) / "parent"), "diff", "--quiet", "origin/main", CHILD, "--", "src/a.py"] in ops.calls
        assert commands(ops, "--squash") == []
        assert commands(ops, "push") == []


def test_squash_fresh_commit_message_and_no_reset_on_success():
    with tempfile.TemporaryDirectory() as td:
        ctx, ops, parent_dir = squash_setup(Path(td), rules=[STAGED])
        _merge.step_squash(ctx, ops)
        assert ["git", "-C", str(parent_dir), "commit", "-m", f"My task\n\nMill-Task: {SLUG}"] in ops.calls
        assert resets(ops) == []


def test_squash_nothing_staged_skips_commit_push_reset():
    with tempfile.TemporaryDirectory() as td:
        ctx, ops, _ = squash_setup(Path(td))
        _merge.step_squash(ctx, ops)
        assert commands(ops, "commit") == []
        assert commands(ops, "push") == []
        assert resets(ops) == []


def test_squash_merge_conflict_halts_and_rolls_back():
    with tempfile.TemporaryDirectory() as td:
        rules = [
            (["merge", "--squash"], completed(1, "", "conflict")),
            (["--diff-filter=U"], completed(0, "a.py\nb.py\n")),
        ]
        ctx, ops, _ = squash_setup(Path(td), rules=rules)
        stop = expect_stop(_merge.step_squash, ctx, ops)
        assert "conflicts: a.py, b.py" in stop.reason
        assert len(resets(ops)) == 1


NON_FF = completed(1, "", " ! [rejected] main -> main (fetch first)\n")


def test_squash_non_fast_forward_rebases_and_retries():
    with tempfile.TemporaryDirectory() as td:
        pushes = iter([NON_FF, completed()])
        ctx, ops, _ = squash_setup(Path(td), rules=[STAGED, (["push"], lambda argv: next(pushes))])
        _merge.step_squash(ctx, ops)
        assert len(commands(ops, "push")) == 2
        assert len(commands(ops, "rebase")) == 1
        assert resets(ops) == []


def test_squash_rebase_conflict_aborts_and_rolls_back():
    with tempfile.TemporaryDirectory() as td:
        rules = [
            STAGED,
            (["push"], NON_FF),
            (["rebase", "origin/main"], completed(1)),
            (["--diff-filter=U"], completed(0, "x.py\n")),
        ]
        ctx, ops, parent_dir = squash_setup(Path(td), rules=rules)
        stop = expect_stop(_merge.step_squash, ctx, ops)
        assert "x.py" in stop.reason
        assert ["git", "-C", str(parent_dir), "rebase", "--abort"] in ops.calls
        assert ["git", "-C", str(parent_dir), "reset", "--hard", "origin/main"] in ops.calls


def test_squash_retry_failure_and_other_failure_roll_back():
    for rules in (
        [STAGED, (["push"], completed(1, "", "fatal: network"))],
        [STAGED, (["push"], NON_FF)],
    ):
        with tempfile.TemporaryDirectory() as td:
            ctx, ops, parent_dir = squash_setup(Path(td), rules=rules)
            stop = expect_stop(_merge.step_squash, ctx, ops)
            assert "rolled back to origin/main" in stop.reason
            assert ["git", "-C", str(parent_dir), "reset", "--hard", "origin/main"] in ops.calls


PROTECTED = completed(1, "", "remote: error: GH006: Protected branch update failed")


def test_squash_branch_protection_reuses_existing_pr():
    with tempfile.TemporaryDirectory() as td:
        rules = [STAGED, (["push"], lambda argv: PROTECTED if argv[2] != str(Path(td) / "git") else completed()),
                 (["gh", "pr", "list"], completed(0, '{"number": 5, "url": "https://x/pr/5"}\n'))]
        ctx, ops, parent_dir = squash_setup(Path(td), rules=rules)
        stop = expect_stop(_merge.step_squash, ctx, ops)
        assert stop.status == "ok"
        assert ctx.route == "branch-protection-pr"
        assert stop.data == {"pr_url": "https://x/pr/5", "slug": SLUG, "parent_branch": "main"}
        assert ["git", "-C", str(parent_dir), "reset", "--hard", "origin/main"] in ops.calls
        assert commands(ops, "create") == []
        assert ["git", "-C", str(ctx.git_root), "push", "origin", CHILD] in ops.calls
        assert ops.phase_calls == [(SLUG, "pr-pending")]
        assert len(resets(ops)) == 1


def test_squash_branch_protection_creates_pr_with_parent_base():
    with tempfile.TemporaryDirectory() as td:
        rules = [STAGED, (["push"], lambda argv: PROTECTED if argv[2] != str(Path(td) / "git") else completed()),
                 (["gh", "pr", "create"], completed(0, "Creating PR\nhttps://x/pr/9\n"))]
        ctx, ops, _ = squash_setup(Path(td), rules=rules)
        stop = expect_stop(_merge.step_squash, ctx, ops)
        create = commands(ops, "create")[0]
        assert create[create.index("--base") + 1] == "main"
        assert stop.data["pr_url"] == "https://x/pr/9"


def test_squash_terminated_during_push_rolls_back_and_propagates():
    with tempfile.TemporaryDirectory() as td:
        def push(argv):
            raise _merge.Terminated()

        ctx, ops, parent_dir = squash_setup(Path(td), rules=[STAGED, (["push"], push)])
        try:
            _merge.step_squash(ctx, ops)
        except _merge.Terminated:
            pass
        else:
            raise AssertionError("Terminated should propagate")
        assert ["git", "-C", str(parent_dir), "reset", "--hard", "origin/main"] in ops.calls
        assert not lock_path(parent_dir).exists()


def test_terminated_after_push_does_not_roll_back():
    with tempfile.TemporaryDirectory() as td:
        ops = route_setup(Path(td), route="direct", mode="worktree", archive_tag=_merge.Terminated())
        try:
            _merge.run_merge(_merge.MergeOptions(), ops)
        except _merge.Terminated:
            pass
        else:
            raise AssertionError("Terminated should propagate")
        assert resets(ops) == []
        assert not lock_path(Path(td) / "parent").exists()


def test_squash_inplace_no_lock_no_dirty_check_and_fetch_failure_halts():
    with tempfile.TemporaryDirectory() as td:
        ctx, ops, parent_dir = squash_setup(Path(td), mode="inplace", rules=[STAGED])
        _merge.step_squash(ctx, ops)
        assert not lock_path(parent_dir).exists()
        assert not lock_path(ctx.git_root).exists()
        assert commands(ops, "status") == []
        assert ["git", "-C", str(ctx.git_root), "fetch", "origin", "main"] in ops.calls
    with tempfile.TemporaryDirectory() as td:
        ctx, ops, _ = squash_setup(Path(td), mode="inplace", rules=[(["fetch"], completed(1, "", "no remote"))])
        stop = expect_stop(_merge.step_squash, ctx, ops)
        assert stop.reason == "git fetch origin main failed: no remote"


# ---------------------------------------------------------------------------
# Archive tag, wiki done, notify, and full routes
# ---------------------------------------------------------------------------


def route_setup(tmp: Path, *, route: str, mode: str, extra_rules=None, **returns):
    """Build a full-run setup: entry/parent/phase-gate/pr-state driven by real steps and fakes."""
    git_root = tmp / "git"
    git_root.mkdir(exist_ok=True)
    (tmp / "parent").mkdir(exist_ok=True)
    write_status(git_root / "_mill" / "status.md")
    pr = {"merged": {"state": "merged", "number": 1, "error": None},
          "closed": {"state": "closed", "number": 1, "error": None}}.get(route, {"state": "none", "number": None, "error": None})
    listing = (
        f"worktree {tmp / 'parent'}\nHEAD b\nbranch refs/heads/main\n\n"
        f"worktree {git_root}\nHEAD a\nbranch refs/heads/{BRANCH}\n"
    )
    rules = list(extra_rules or []) + [
        (["branch", "--show-current"], completed(0, BRANCH + "\n")),
        (["worktree", "list"], completed(0, listing)),
        (["diff", "--cached", "--quiet"], completed(1)),
    ]
    ops = make_ops(tmp, git_rules=rules, is_inplace=(mode == "inplace"), pr_state=pr, **returns)
    return ops


def run_route(tmp: Path, route: str, mode: str, opts=None, **kwargs):
    ops = route_setup(tmp, route=route, mode=mode, **kwargs)
    result = _merge.run_merge(opts or _merge.MergeOptions(), ops)
    return result, ops


FULL = ["entry", "parent", "phase-gate", "pr-state", "merge-in-check", "cleanup-commit", "squash",
        "archive-tag", "wiki-done", "notify"]


def step_names(result) -> list[str]:
    return [t["step"] for t in result["timings"]]


def test_route_direct_worktree_runs_every_step():
    with tempfile.TemporaryDirectory() as td:
        tmp = Path(td)
        result, ops = run_route(tmp, "direct", "worktree")
        assert result["status"] == "ok", result
        assert step_names(result) == FULL
        assert ops.phase_calls == [(SLUG, "done")]
        assert result["data"]["archive_tag"] == f"archive/{SLUG}"
        assert not lock_path(tmp / "parent").exists()


def test_route_direct_inplace_omits_merge_in_and_lock():
    with tempfile.TemporaryDirectory() as td:
        result, _ops = run_route(Path(td), "direct", "inplace")
        assert result["status"] == "ok", result
        assert step_names(result) == [n for n in FULL if n != "merge-in-check"]
        assert not lock_path(Path(td) / "parent").exists()


def test_route_pr_merged_skips_squash_and_merge_in():
    with tempfile.TemporaryDirectory() as td:
        result, ops = run_route(Path(td), "merged", "worktree")
        assert result["status"] == "ok", result
        assert step_names(result) == [n for n in FULL if n not in ("merge-in-check", "squash")]
        assert ops.phase_calls == [(SLUG, "done")]


def test_route_pr_closed_matches_direct():
    with tempfile.TemporaryDirectory() as td:
        result, ops = run_route(Path(td), "closed", "worktree")
        assert result["status"] == "ok", result
        assert step_names(result) == FULL
        assert ops.phase_calls == [(SLUG, "done")]


def test_route_branch_protection_ends_at_squash():
    with tempfile.TemporaryDirectory() as td:
        protected = [(["push"], lambda argv: PROTECTED if argv[2] == str(Path(td) / "parent") else completed()),
                     (["gh", "pr", "create"], completed(0, "https://x/pr/3\n"))]
        result, ops = run_route(Path(td), "direct", "worktree", extra_rules=protected)
        assert result["status"] == "ok"
        assert result["route"] == "branch-protection-pr"
        assert step_names(result)[-1] == "squash"
        assert result["data"]["pr_url"] == "https://x/pr/3"
        assert ops.phase_calls == [(SLUG, "pr-pending")]
        assert ops.archive_calls == []


def test_route_post_merge_failures_halt_without_rollback():
    for key, value in (("archive_tag", RuntimeError("tag boom")),):
        with tempfile.TemporaryDirectory() as td:
            result, ops = run_route(Path(td), "direct", "worktree", **{key: value})
            assert result["status"] == "halt"
            assert result["reason"].startswith("Merge landed on main")
            assert resets(ops) == []
            assert not lock_path(Path(td) / "parent").exists()
    with tempfile.TemporaryDirectory() as td:
        ops = route_setup(Path(td), route="direct", mode="worktree")

        def failing_set_phase(wiki_path, slug, phase):
            raise RuntimeError("wiki down")

        ops.set_phase = failing_set_phase
        result = _merge.run_merge(_merge.MergeOptions(), ops)
        assert result["reason"].startswith("Merge landed on main")
        assert resets(ops) == []
        assert not lock_path(Path(td) / "parent").exists()


def test_route_archive_push_failure_warns():
    with tempfile.TemporaryDirectory() as td:
        tag = {"action": "created", "tag": f"archive/{SLUG}", "push_failed": True, "push_error": "denied"}
        result, _ = run_route(Path(td), "direct", "worktree", archive_tag=tag)
        assert result["warnings"] == [
            f"archive tag push failed -- reconcile archive/{SLUG} with remote manually: denied"
        ]


def test_route_results_are_ascii():
    for route, mode in (("direct", "worktree"), ("merged", "worktree"), ("closed", "worktree"), ("direct", "inplace")):
        with tempfile.TemporaryDirectory() as td:
            tag = {"action": "moved", "tag": f"archive/{SLUG}", "moved_aside_to": "archive/x-old", "push_failed": True, "push_error": "d"}
            result, _ = run_route(Path(td), route, mode, archive_tag=tag)
            strings = [result["reason"], *result["report"], *result["warnings"]]
            assert all(s.isascii() for s in strings), strings


def test_registered_step_order_full():
    assert [s[0] for s in _merge.STEPS] == FULL


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
