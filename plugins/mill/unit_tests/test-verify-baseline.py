"""
Unit test for `plugins/mill/scripts/_verify_baseline.py`.

Case 1 regresses #615/#620: the module-wide verify baseline's transient `git worktree add` failed
with "Filename too long" on deep-path Windows repos because `core.longpaths` was not set for that
throwaway checkout, silently disabling the baseline gate.
This case asserts the `git worktree add` argv `compute_baseline` builds always carries `-c
core.longpaths=true` immediately after the `-C <git_root>` pair and before the `worktree` token --
the exact shape the fix in `_verify_baseline.py` produces.

Case 2 mitigates #629: a long `.scratch/verify-baseline-<uuid4().hex>/` prefix (32 hex characters)
could itself push a deep-fixture Windows repo over MAX_PATH.
This case asserts the transient-worktree directory basename `compute_baseline` builds matches
`verify-baseline-<12 hex chars>` -- the shortened `uuid.uuid4().hex[:12]` slice, not the full
32-character string.

Follows the monkeypatch/in-memory fixture style of `test-worktree.py`: no real git is invoked.
`_subprocess_util.run` is monkeypatched to fabricate a successful `rev-parse` result and to capture
the `worktree add` argv;
`_run_verify_in` is stubbed to return `(0, "")` so `compute_baseline` short-circuits to "clean" on
the first verify;
`_junction.create` and `_worktree.remove_safe` are stubbed to no-ops since no real filesystem
worktree is ever created.

Cases (b)/(c) cover `compute_batch_baselines`'s basic multi-command computation directly against a
mocked `checkout_path`: (b) confirms two distinct commands each get their own, independent
(non-aliased) signature list keyed by name;
(c) confirms a command with zero recognized FAIL-marker lines on both runs maps to `[]` (present,
not an absent dict key).

Cases (d)/(e) cover `compute_batch_baselines`'s union-of-two-runs corroboration and mixed-cwd
dependency-linking orchestration: (d) confirms a signature that only reproduces on one of the two
runs still ends up in the union (neither run's set silently overwrites the other's);
(e) exercises `_link_dependency_dirs` called at two distinct resolved target paths against one
shared mocked `checkout_path` (mirroring how a future shared-checkout orchestrator calls it once per
distinct effective-cwd fragment), then `compute_batch_baselines` with commands resolving to each of
those two paths via their `cwd_override` entries.

Cases (f)-(i) regress #1098, where `compute_batch_baselines` ran every verify command twice
unconditionally and keyed its loop on the batch name, so a plan whose last batch verifies the union
of the earlier batches executed each suite four times instead of once: (f) two names sharing one
`(command, effective_cwd)` pair evaluate it once and each still get a non-aliased list;
(g) a command exiting 0 with zero signatures runs once, not twice;
(h) the skip is gated on the zero exit code, so a non-zero exit with no recognized signatures is
still re-run;
(i) dedup is keyed on the pair, so one command string at two distinct cwds stays two units of work.

Cases (j)-(m) regress #1101, where that dedup could never fire in production because the only caller
drives one batch per call (to keep its per-batch try/except isolation), re-creating the call-local
cache empty every time, and where no verify run had any timeout at all: (j) a caller-owned
`pair_cache` makes the dedup span calls while still handing back independent list objects;
(k) omitting it keeps the old call-local behaviour, so the shared cache is opt-in;
(l) `timeout_seconds` reaches `subprocess.run` and a `TimeoutExpired` propagates to the caller's
"leave the baseline unset" fail-safe instead of being swallowed into a bogus baseline;
(m) omitting it imposes no ceiling.
"""
from __future__ import annotations

import re
import subprocess
import sys
import tempfile
from pathlib import Path
from unittest.mock import MagicMock, patch

HUB = Path(__file__).resolve().parent.parent.parent.parent
sys.path.insert(0, str(HUB / "plugins" / "mill" / "scripts"))

from _verify_baseline import (
    _link_dependency_dirs,
    compute_baseline,
    compute_batch_baseline_on_demand,
    compute_batch_baselines,
)


def _run_compute_baseline_capturing_worktree_add(tmp: str) -> tuple[str, list[list[str]]]:
    """
    Run `compute_baseline` against a fully-mocked git/subprocess layer and return its result plus
    every `git worktree add` argv it issued.

    `_subprocess_util.run` is monkeypatched to fabricate a successful `rev-parse` result and to
    capture the `worktree add` argv;
    `_run_verify_in` is stubbed to return `(0, "")` so `compute_baseline` short-circuits to "clean"
    on the first verify;
    `_junction.create` and `_worktree.remove_safe` are stubbed to no-ops since no real filesystem
    worktree is ever created.
    """
    # tempfile.TemporaryDirectory (passed in by the caller) keeps compute_baseline's unconditional `project_root/.scratch` mkdir (see _verify_baseline.py:148-149) landing in an auto-cleaned path rather than a stray real directory.
    project_root = Path(tmp) / "project"
    project_root.mkdir()
    git_root = Path(tmp) / "git-root"
    git_root.mkdir()

    captured_worktree_add_argv: list[list[str]] = []

    def _fake_run(argv: list[str], **kwargs) -> MagicMock:
        if "rev-parse" in argv:
            return MagicMock(returncode=0, stdout="deadbeefcafe\n", stderr="")
        if "worktree" in argv:
            captured_worktree_add_argv.append(argv)
            return MagicMock(returncode=0, stdout="", stderr="")
        raise AssertionError(f"unexpected argv in fake _subprocess_util.run: {argv!r}")

    with patch("_verify_baseline._subprocess_util.run", side_effect=_fake_run):
        with patch("_verify_baseline._run_verify_in", return_value=(0, "")):
            with patch("_verify_baseline._junction.create"):
                with patch("_verify_baseline._worktree.remove_safe"):
                    result = compute_baseline(project_root, git_root, "main", "echo ok")

    return result, captured_worktree_add_argv


def _case_b_independent_signature_lists() -> None:
    """
    Case (b): two distinct commands each get their own, independent (non-aliased) signature list
    keyed by name.
    """
    checkout_path = Path("/fake/checkout")
    project_root = Path("/fake/project")

    def _fake_run_verify_in(command: str, cwd: Path, timeout_seconds=None) -> tuple[int, str]:
        del cwd, timeout_seconds
        if command == "cmd-a":
            return 1, "--- FAIL: TestA (0.01s)\n"
        if command == "cmd-b":
            return 1, "--- FAIL: TestB (0.02s)\n"
        raise AssertionError(f"unexpected command: {command!r}")

    commands = [("batchA", "cmd-a", None), ("batchB", "cmd-b", None)]
    with patch("_verify_baseline._run_verify_in", side_effect=_fake_run_verify_in):
        result = compute_batch_baselines(commands, checkout_path, project_root)

    assert len(result) == 2, f"expected 2 entries, got {len(result)}: {result!r}"
    assert result["batchA"] == ["--- FAIL: TestA (0.01s)"], result["batchA"]
    assert result["batchB"] == ["--- FAIL: TestB (0.02s)"], result["batchB"]
    assert result["batchA"] is not result["batchB"], (
        "expected independent (non-aliased) list objects per command"
    )

    print(
        "PASS: compute_batch_baselines returns independent signature lists "
        "keyed by name for distinct commands"
    )


def _case_c_zero_failures_returns_empty_list() -> None:
    """
    Case (c): a command with zero recognized FAIL-marker lines on both runs maps to [] (present, not
    an absent dict key).
    """
    checkout_path = Path("/fake/checkout")
    project_root = Path("/fake/project")

    with patch("_verify_baseline._run_verify_in", return_value=(0, "ok, nothing failed\n")):
        result = compute_batch_baselines(
            [("clean-batch", "cmd-clean", None)], checkout_path, project_root
        )

    assert "clean-batch" in result, f"expected 'clean-batch' key present, got {result!r}"
    assert result["clean-batch"] == [], (
        f"expected empty list for zero-failure command, got {result['clean-batch']!r}"
    )

    print(
        "PASS: compute_batch_baselines maps a zero-failure command to a "
        "present-but-empty signature list"
    )


def _case_d_union_of_two_runs() -> None:
    """
    Case (d): a signature that only reproduces on one of the two runs still ends up in the union --
    neither run's set silently overwrites the other's.
    """
    checkout_path = Path("/fake/checkout")
    project_root = Path("/fake/project")
    call_count = {"n": 0}

    def _fake_run_verify_in(command: str, cwd: Path, timeout_seconds=None) -> tuple[int, str]:
        del cwd, timeout_seconds
        assert command == "cmd-flaky"
        call_count["n"] += 1
        if call_count["n"] == 1:
            return 1, "--- FAIL: TestFlakyA (0.01s)\n"
        return 1, "--- FAIL: TestFlakyB (0.02s)\n"

    with patch("_verify_baseline._run_verify_in", side_effect=_fake_run_verify_in):
        result = compute_batch_baselines(
            [("flaky-batch", "cmd-flaky", None)], checkout_path, project_root
        )

    assert result["flaky-batch"] == [
        "--- FAIL: TestFlakyA (0.01s)",
        "--- FAIL: TestFlakyB (0.02s)",
    ], f"expected union of both runs' signatures, got {result['flaky-batch']!r}"

    print(
        "PASS: compute_batch_baselines unions signatures from both runs "
        "instead of one run's set overwriting the other"
    )


def _case_e_mixed_cwd_dependency_linking() -> None:
    """
    Case (e): `_link_dependency_dirs` called at two distinct resolved target paths against one
    shared checkout (mirroring how a future shared-checkout orchestrator calls it once per distinct
    effective-cwd fragment), then `compute_batch_baselines` with commands resolving to each of those
    two paths via their `cwd_override` entries -- confirming each command runs at its own cwd within
    the one shared checkout and dependency dirs are linked at both resolved paths.
    """
    with tempfile.TemporaryDirectory() as tmp:
        project_root = Path(tmp) / "project"
        project_root.mkdir()
        (project_root / ".venv").mkdir()

        checkout_path = Path(tmp) / "checkout"
        checkout_path.mkdir()
        target_git_root = checkout_path
        target_hub = checkout_path / "hub"
        target_hub.mkdir()

        linked_calls: list[tuple[Path, Path]] = []

        def _fake_junction_create(src: Path, dst: Path) -> None:
            linked_calls.append((src, dst))

        with patch("_verify_baseline._junction.create", side_effect=_fake_junction_create):
            _link_dependency_dirs(project_root, target_git_root)
            _link_dependency_dirs(project_root, target_hub)

        assert linked_calls == [
            (project_root / ".venv", target_git_root / ".venv"),
            (project_root / ".venv", target_hub / ".venv"),
        ], f"expected dependency dirs linked at both resolved paths, got {linked_calls!r}"

        seen_cwds: list[tuple[str, Path]] = []

        def _fake_run_verify_in(command: str, cwd: Path, timeout_seconds=None) -> tuple[int, str]:
            del timeout_seconds
            seen_cwds.append((command, cwd))
            return 0, "ok\n"

        commands = [
            ("root-batch", "cmd-root", target_git_root),
            ("hub-batch", "cmd-hub", target_hub),
        ]
        with patch("_verify_baseline._run_verify_in", side_effect=_fake_run_verify_in):
            result = compute_batch_baselines(commands, checkout_path, project_root)

        assert result == {"root-batch": [], "hub-batch": []}, result

        # One run each, not two: both commands exit 0 with no signatures, so the corroboration
        # re-run is skipped (#1098).
        root_cwds = [cwd for command, cwd in seen_cwds if command == "cmd-root"]
        hub_cwds = [cwd for command, cwd in seen_cwds if command == "cmd-hub"]
        assert root_cwds == [target_git_root], root_cwds
        assert hub_cwds == [target_hub], hub_cwds

        print(
            "PASS: compute_batch_baselines runs each command at its own "
            "resolved cwd within one shared checkout, with dependency dirs "
            "linked at both resolved paths"
        )


def _case_f_identical_command_and_cwd_runs_once() -> None:
    """
    Case (f) regresses #1098: two batch names sharing one `(command, effective_cwd)` pair run the
    command once, not once per name -- and each still gets its own, non-aliased list object.

    Uses a failing command so the corroboration re-run is not itself skipped;
    the assertion is about the pair being evaluated once (2 runs total), not four times.
    """
    checkout_path = Path("/fake/checkout")
    project_root = Path("/fake/project")
    runs: list[str] = []

    def _fake_run_verify_in(command: str, cwd: Path, timeout_seconds=None) -> tuple[int, str]:
        del cwd, timeout_seconds
        runs.append(command)
        return 1, "--- FAIL: TestShared (0.01s)\n"

    commands = [
        ("batch1", "dotnet test Suite", None),
        ("batch3", "dotnet test Suite", None),
    ]
    with patch("_verify_baseline._run_verify_in", side_effect=_fake_run_verify_in):
        result = compute_batch_baselines(commands, checkout_path, project_root)

    assert runs == ["dotnet test Suite", "dotnet test Suite"], (
        f"expected the shared command evaluated once (2 runs), got {len(runs)} runs: {runs!r}"
    )
    assert result["batch1"] == ["--- FAIL: TestShared (0.01s)"], result["batch1"]
    assert result["batch3"] == result["batch1"], result["batch3"]
    assert result["batch1"] is not result["batch3"], (
        "expected independent (non-aliased) list objects even for a shared command"
    )

    print(
        "PASS: compute_batch_baselines evaluates an identical (command, cwd) pair "
        "once and fans independent copies out to every batch name"
    )


def _case_g_green_run_skips_corroboration_rerun() -> None:
    """
    Case (g) regresses #1098: a command that exits 0 with zero extracted signatures is run once, not
    twice -- there is nothing for the second run to corroborate.
    """
    checkout_path = Path("/fake/checkout")
    project_root = Path("/fake/project")
    runs: list[str] = []

    def _fake_run_verify_in(command: str, cwd: Path, timeout_seconds=None) -> tuple[int, str]:
        del cwd, timeout_seconds
        runs.append(command)
        return 0, "Passed!  - Failed: 0, Passed: 412\n"

    with patch("_verify_baseline._run_verify_in", side_effect=_fake_run_verify_in):
        result = compute_batch_baselines(
            [("green-batch", "cmd-green", None)], checkout_path, project_root
        )

    assert len(runs) == 1, f"expected a single run for a green command, got {runs!r}"
    assert result == {"green-batch": []}, result

    print(
        "PASS: compute_batch_baselines skips the corroboration re-run when "
        "run 1 exits 0 with zero failure signatures"
    )


def _case_h_nonzero_exit_without_signatures_still_reruns() -> None:
    """
    Case (h): the run-2 skip is gated on a ZERO exit code, not on the signature list alone.

    A command that fails without emitting any line `_extract_failure_signatures` recognizes (a build
    break, a crashed runner) is still re-run, so a signature that only surfaces on the second
    attempt reaches the baseline.
    """
    checkout_path = Path("/fake/checkout")
    project_root = Path("/fake/project")
    runs: list[str] = []

    def _fake_run_verify_in(command: str, cwd: Path, timeout_seconds=None) -> tuple[int, str]:
        del cwd, timeout_seconds
        runs.append(command)
        if len(runs) == 1:
            return 1, "error CS0246: the type or namespace could not be found\n"
        return 1, "--- FAIL: TestLate (0.03s)\n"

    with patch("_verify_baseline._run_verify_in", side_effect=_fake_run_verify_in):
        result = compute_batch_baselines(
            [("broken-batch", "cmd-broken", None)], checkout_path, project_root
        )

    assert len(runs) == 2, (
        f"expected a re-run after a non-zero exit with no signatures, got {runs!r}"
    )
    assert result["broken-batch"] == ["--- FAIL: TestLate (0.03s)"], result["broken-batch"]

    print(
        "PASS: compute_batch_baselines still re-runs a non-zero-exit command "
        "that emitted no recognized failure signatures"
    )


def _case_i_same_command_distinct_cwds_not_deduped() -> None:
    """
    Case (i): dedup is keyed on the `(command, effective_cwd)` pair -- one command string run at two
    distinct cwds is two distinct units of work, not one.
    """
    checkout_path = Path("/fake/checkout")
    project_root = Path("/fake/project")
    seen_cwds: list[Path] = []

    def _fake_run_verify_in(command: str, cwd: Path, timeout_seconds=None) -> tuple[int, str]:
        del command, timeout_seconds
        seen_cwds.append(cwd)
        return 1, f"--- FAIL: Test{cwd.name} (0.01s)\n"

    commands = [
        ("root-batch", "make test", Path("/fake/checkout")),
        ("sub-batch", "make test", Path("/fake/checkout/sub")),
    ]
    with patch("_verify_baseline._run_verify_in", side_effect=_fake_run_verify_in):
        result = compute_batch_baselines(commands, checkout_path, project_root)

    assert seen_cwds == [
        Path("/fake/checkout"),
        Path("/fake/checkout"),
        Path("/fake/checkout/sub"),
        Path("/fake/checkout/sub"),
    ], seen_cwds
    assert result["root-batch"] == ["--- FAIL: Testcheckout (0.01s)"], result["root-batch"]
    assert result["sub-batch"] == ["--- FAIL: Testsub (0.01s)"], result["sub-batch"]

    print(
        "PASS: compute_batch_baselines keys dedup on (command, cwd), so one "
        "command string at two distinct cwds stays two units of work"
    )


def _case_j_caller_owned_pair_cache_spans_calls() -> None:
    """
    Case (j) regresses #1101: a caller-owned `pair_cache` makes the dedup span calls.

    The production call site drives one batch per call (single-element list) to keep its per-batch
    try/except isolation, so a call-local cache is re-created empty every time and can never fire.
    With a shared `pair_cache`, the second call's identical pair is served from the cache instead of
    re-running the command -- and still hands back an independent list object.
    """
    checkout_path = Path("/fake/checkout")
    project_root = Path("/fake/project")
    runs: list[str] = []

    def _fake_run_verify_in(command: str, cwd: Path, timeout_seconds=None) -> tuple[int, str]:
        del cwd, timeout_seconds
        runs.append(command)
        return 1, "--- FAIL: TestShared (0.01s)\n"

    pair_cache: dict = {}
    with patch("_verify_baseline._run_verify_in", side_effect=_fake_run_verify_in):
        first = compute_batch_baselines(
            [("batch1", "dotnet test Suite", None)],
            checkout_path,
            project_root,
            pair_cache=pair_cache,
        )
        second = compute_batch_baselines(
            [("batch3", "dotnet test Suite", None)],
            checkout_path,
            project_root,
            pair_cache=pair_cache,
        )

    assert len(runs) == 2, (
        f"expected the shared pair evaluated once across both calls (2 runs), got {runs!r}"
    )
    assert second["batch3"] == ["--- FAIL: TestShared (0.01s)"], second["batch3"]
    assert second["batch3"] is not first["batch1"], (
        "expected an independent list object per name, not the cached list itself"
    )
    assert second["batch3"] is not pair_cache[("dotnet test Suite", checkout_path)], (
        "expected a copy, not the cache's own list object"
    )

    print(
        "PASS: compute_batch_baselines dedups across calls when the caller "
        "owns and threads a pair_cache"
    )


def _case_k_omitted_pair_cache_stays_call_local() -> None:
    """
    Case (k): omitting `pair_cache` keeps the old call-local behaviour -- two separate calls with
    the same pair each evaluate it, so the shared cache is genuinely opt-in.
    """
    checkout_path = Path("/fake/checkout")
    project_root = Path("/fake/project")
    runs: list[str] = []

    def _fake_run_verify_in(command: str, cwd: Path, timeout_seconds=None) -> tuple[int, str]:
        del cwd, timeout_seconds
        runs.append(command)
        return 1, "--- FAIL: TestShared (0.01s)\n"

    with patch("_verify_baseline._run_verify_in", side_effect=_fake_run_verify_in):
        compute_batch_baselines([("batch1", "cmd", None)], checkout_path, project_root)
        compute_batch_baselines([("batch3", "cmd", None)], checkout_path, project_root)

    assert len(runs) == 4, f"expected 2 runs per independent call (4 total), got {runs!r}"

    print(
        "PASS: compute_batch_baselines without a pair_cache stays call-local, "
        "so the shared cache is opt-in"
    )


def _case_l_timeout_propagates() -> None:
    """
    Case (l) regresses #1101: `timeout_seconds` reaches `subprocess.run`, and a `TimeoutExpired`
    propagates to the caller rather than being swallowed into a fabricated non-zero exit.

    A swallowed timeout would feed truncated output into the signature extractor and cache a bogus
    baseline;
    propagating lets the caller apply its existing "leave the baseline unset" fail-safe.
    Also asserts nothing is written to `pair_cache` for the pair that raised, so a later call can
    retry it.
    """
    checkout_path = Path("/fake/checkout")
    project_root = Path("/fake/project")
    seen_timeouts: list[float | None] = []

    def _fake_subprocess_run(*args, **kwargs):
        seen_timeouts.append(kwargs.get("timeout"))
        raise subprocess.TimeoutExpired(cmd="cmd-hang", timeout=kwargs.get("timeout"))

    pair_cache: dict = {}
    with patch("_verify_baseline.subprocess.run", side_effect=_fake_subprocess_run):
        try:
            compute_batch_baselines(
                [("hung-batch", "cmd-hang", None)],
                checkout_path,
                project_root,
                pair_cache=pair_cache,
                timeout_seconds=90.0,
            )
        except subprocess.TimeoutExpired:
            pass
        else:
            raise AssertionError("expected TimeoutExpired to propagate to the caller")

    assert seen_timeouts == [90.0], (
        f"expected timeout_seconds forwarded to subprocess.run, got {seen_timeouts!r}"
    )
    assert pair_cache == {}, (
        f"expected nothing cached for a pair whose evaluation raised, got {pair_cache!r}"
    )

    print(
        "PASS: compute_batch_baselines forwards timeout_seconds to subprocess.run "
        "and lets TimeoutExpired propagate without caching the failed pair"
    )


def _case_m_no_timeout_by_default() -> None:
    """
    Case (m): omitting `timeout_seconds` passes `timeout=None` to `subprocess.run` -- no ceiling is
    imposed on repos that have not configured one.
    """
    checkout_path = Path("/fake/checkout")
    project_root = Path("/fake/project")
    seen_timeouts: list[float | None] = []

    def _fake_subprocess_run(*args, **kwargs):
        seen_timeouts.append(kwargs.get("timeout"))
        return MagicMock(returncode=0, stdout="ok\n", stderr="")

    with patch("_verify_baseline.subprocess.run", side_effect=_fake_subprocess_run):
        result = compute_batch_baselines(
            [("plain-batch", "cmd-plain", None)], checkout_path, project_root
        )

    assert result == {"plain-batch": []}, result
    assert seen_timeouts == [None], (
        f"expected timeout=None when no ceiling is configured, got {seen_timeouts!r}"
    )

    print("PASS: compute_batch_baselines imposes no subprocess timeout by default")


def _case_n_on_demand_checks_out_pinned_sha_and_tears_down() -> None:
    """
    Case (n) regresses #1102: `compute_batch_baseline_on_demand` checks out the passed `parent_sha`
    verbatim, calls `compute_batch_baselines` with a single `("_ondemand", verify_cmd, None)`
    triple, returns that entry's signature list, and tears down the transient worktree via
    `_worktree.remove_safe` even when `compute_batch_baselines` raises.
    """
    with tempfile.TemporaryDirectory() as tmp:
        project_root = Path(tmp) / "project"
        project_root.mkdir()
        git_root = Path(tmp) / "git-root"
        git_root.mkdir()
        parent_sha = "d" * 40

        captured_rev_parse_argv: list[list[str]] = []
        captured_worktree_add_argv: list[list[str]] = []

        def _fake_run(argv: list[str], **kwargs) -> MagicMock:
            if "rev-parse" in argv:
                captured_rev_parse_argv.append(argv)
                return MagicMock(returncode=0, stdout=f"{parent_sha}\n", stderr="")
            if "worktree" in argv:
                captured_worktree_add_argv.append(argv)
                return MagicMock(returncode=0, stdout="", stderr="")
            raise AssertionError(f"unexpected argv in fake _subprocess_util.run: {argv!r}")

        captured_batch_baselines_calls: list[tuple] = []

        def _fake_compute_batch_baselines(commands, checkout_path, project_root, **kwargs):
            captured_batch_baselines_calls.append((commands, checkout_path, project_root, kwargs))
            return {"_ondemand": ["--- FAIL: TestOnDemand (0.01s)"]}

        teardown_calls: list[Path] = []

        with (
            patch("_verify_baseline._subprocess_util.run", side_effect=_fake_run),
            patch("_verify_baseline._junction.create"),
            patch(
                "_verify_baseline._worktree.remove_safe",
                side_effect=lambda path, **kw: teardown_calls.append(path),
            ),
            patch(
                "_verify_baseline.compute_batch_baselines",
                side_effect=_fake_compute_batch_baselines,
            ),
        ):
            result = compute_batch_baseline_on_demand(
                project_root, git_root, parent_sha, "cmd-ondemand"
            )

        assert result == ["--- FAIL: TestOnDemand (0.01s)"], result

        # The parent_sha is checked out verbatim.
        assert captured_rev_parse_argv[0][-1] == parent_sha, captured_rev_parse_argv
        assert len(captured_worktree_add_argv) == 1, captured_worktree_add_argv
        assert captured_worktree_add_argv[0][-1] == parent_sha, captured_worktree_add_argv[0]

        # compute_batch_baselines is called with a single ("_ondemand", verify_cmd, None) triple.
        assert len(captured_batch_baselines_calls) == 1, captured_batch_baselines_calls
        commands, _checkout_path, _project_root, _kwargs = captured_batch_baselines_calls[0]
        assert commands == [("_ondemand", "cmd-ondemand", None)], commands

        # Teardown happens exactly once.
        assert len(teardown_calls) == 1, teardown_calls

        print(
            "PASS: compute_batch_baseline_on_demand checks out the pinned "
            "parent_sha and returns the single-command result"
        )

    # Teardown also happens when compute_batch_baselines raises.
    with tempfile.TemporaryDirectory() as tmp:
        project_root = Path(tmp) / "project"
        project_root.mkdir()
        git_root = Path(tmp) / "git-root"
        git_root.mkdir()
        parent_sha = "e" * 40

        def _fake_run(argv: list[str], **kwargs) -> MagicMock:
            if "rev-parse" in argv:
                return MagicMock(returncode=0, stdout=f"{parent_sha}\n", stderr="")
            if "worktree" in argv:
                return MagicMock(returncode=0, stdout="", stderr="")
            raise AssertionError(f"unexpected argv in fake _subprocess_util.run: {argv!r}")

        teardown_calls: list[Path] = []

        def _raising_compute_batch_baselines(*args, **kwargs):
            raise RuntimeError("verify command exploded")

        with (
            patch("_verify_baseline._subprocess_util.run", side_effect=_fake_run),
            patch("_verify_baseline._junction.create"),
            patch(
                "_verify_baseline._worktree.remove_safe",
                side_effect=lambda path, **kw: teardown_calls.append(path),
            ),
            patch(
                "_verify_baseline.compute_batch_baselines",
                side_effect=_raising_compute_batch_baselines,
            ),
        ):
            try:
                compute_batch_baseline_on_demand(
                    project_root, git_root, parent_sha, "cmd-ondemand"
                )
            except RuntimeError:
                pass
            else:
                raise AssertionError("expected RuntimeError to propagate")

        assert len(teardown_calls) == 1, (
            f"expected the transient worktree torn down even on a raised exception, "
            f"got {teardown_calls!r}"
        )

        print(
            "PASS: compute_batch_baseline_on_demand tears down the transient "
            "worktree even when compute_batch_baselines raises"
        )


def main() -> int:
    try:
        # Case 1: core.longpaths=true is always present in the worktree-add argv.
        with tempfile.TemporaryDirectory() as tmp:
            result, captured_worktree_add_argv = _run_compute_baseline_capturing_worktree_add(
                tmp
            )

            assert result == "clean", f"expected 'clean', got {result!r}"

            assert len(captured_worktree_add_argv) == 1, (
                f"expected exactly one 'git worktree add' call, got "
                f"{len(captured_worktree_add_argv)}"
            )
            argv = captured_worktree_add_argv[0]

            # -c core.longpaths=true must appear as an adjacent pair.
            longpaths_index = None
            for i, token in enumerate(argv[:-1]):
                if token == "-c" and argv[i + 1] == "core.longpaths=true":
                    longpaths_index = i
                    break
            assert longpaths_index is not None, (
                f"expected '-c core.longpaths=true' pair in worktree-add argv: {argv!r}"
            )

            # It must sit after the -C <git_root> pair and before the 'worktree' token.
            c_index = argv.index("-C")
            worktree_index = argv.index("worktree")
            assert c_index < longpaths_index < worktree_index, (
                f"expected order -C ... -c core.longpaths=true ... worktree, got {argv!r}"
            )

            print(
                "PASS: compute_baseline's git worktree add carries "
                "-c core.longpaths=true between -C <git_root> and 'worktree'"
            )

        # Case 2: the transient-worktree directory basename uses the shortened, 12-hex-character uuid4().hex slice (#629 Windows MAX_PATH mitigation), not the full 32-character hex string.
        with tempfile.TemporaryDirectory() as tmp:
            result, captured_worktree_add_argv = _run_compute_baseline_capturing_worktree_add(
                tmp
            )

            assert result == "clean", f"expected 'clean', got {result!r}"

            assert len(captured_worktree_add_argv) == 1, (
                f"expected exactly one 'git worktree add' call, got "
                f"{len(captured_worktree_add_argv)}"
            )
            argv = captured_worktree_add_argv[0]

            # The worktree-add target path sits immediately after 'add' and before the parent SHA (the last argv token).
            add_index = argv.index("add")
            tmp_path_arg = argv[add_index + 1]
            basename = Path(tmp_path_arg).name

            pattern = re.compile(r"^verify-baseline-[0-9a-f]{12}$")
            assert pattern.match(basename), (
                f"expected transient-worktree basename to match "
                f"{pattern.pattern!r}, got {basename!r}"
            )

            print(
                "PASS: compute_baseline's transient-worktree directory basename "
                "matches the shortened 'verify-baseline-<12 hex chars>' pattern"
            )

        _case_b_independent_signature_lists()
        _case_c_zero_failures_returns_empty_list()
        _case_d_union_of_two_runs()
        _case_e_mixed_cwd_dependency_linking()
        _case_f_identical_command_and_cwd_runs_once()
        _case_g_green_run_skips_corroboration_rerun()
        _case_h_nonzero_exit_without_signatures_still_reruns()
        _case_i_same_command_distinct_cwds_not_deduped()
        _case_j_caller_owned_pair_cache_spans_calls()
        _case_k_omitted_pair_cache_stays_call_local()
        _case_l_timeout_propagates()
        _case_m_no_timeout_by_default()
        _case_n_on_demand_checks_out_pinned_sha_and_tears_down()

        print("All _verify_baseline unit tests passed.")
        return 0
    except AssertionError as exc:
        print(f"FAIL: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
