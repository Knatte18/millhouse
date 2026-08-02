"""
Unit test for `plugins/mill/scripts/_verify_baseline.py`.

Case 1 regresses #615/#620: the module-wide verify baseline's transient
`git worktree add` failed with "Filename too long" on deep-path Windows
repos because `core.longpaths` was not set for that throwaway checkout,
silently disabling the baseline gate. This case asserts the `git worktree
add` argv `compute_baseline` builds always carries `-c core.longpaths=true`
immediately after the `-C <git_root>` pair and before the `worktree` token
-- the exact shape the fix in `_verify_baseline.py` produces.

Case 2 mitigates #629: a long `.scratch/verify-baseline-<uuid4().hex>/`
prefix (32 hex characters) could itself push a deep-fixture Windows repo
over MAX_PATH. This case asserts the transient-worktree directory basename
`compute_baseline` builds matches `verify-baseline-<12 hex chars>` -- the
shortened `uuid.uuid4().hex[:12]` slice, not the full 32-character string.

Follows the monkeypatch/in-memory fixture style of `test-worktree.py`: no
real git is invoked. `_subprocess_util.run` is monkeypatched to fabricate a
successful `rev-parse` result and to capture the `worktree add` argv;
`_run_verify_in` is stubbed to return `(0, "")` so `compute_baseline`
short-circuits to "clean" on the first verify; `_junction.create` and
`_worktree.remove_safe` are stubbed to no-ops since no real filesystem
worktree is ever created.

Cases (b)/(c) cover `compute_batch_baselines`'s basic multi-command
computation directly against a mocked `checkout_path`: (b) confirms two
distinct commands each get their own, independent (non-aliased) signature
list keyed by name; (c) confirms a command with zero recognized FAIL-marker
lines on both runs maps to `[]` (present, not an absent dict key).

Cases (d)/(e) cover `compute_batch_baselines`'s union-of-two-runs
corroboration and mixed-cwd dependency-linking orchestration: (d) confirms
a signature that only reproduces on one of the two runs still ends up in
the union (neither run's set silently overwrites the other's); (e) exercises
`_link_dependency_dirs` called at two distinct resolved target paths against
one shared mocked `checkout_path` (mirroring how a future shared-checkout
orchestrator calls it once per distinct effective-cwd fragment), then
`compute_batch_baselines` with commands resolving to each of those two
paths via their `cwd_override` entries.
"""
from __future__ import annotations

import re
import sys
import tempfile
from pathlib import Path
from unittest.mock import MagicMock, patch

HUB = Path(__file__).resolve().parent.parent.parent.parent
sys.path.insert(0, str(HUB / "plugins" / "mill" / "scripts"))

from _verify_baseline import (
    _link_dependency_dirs,
    compute_baseline,
    compute_batch_baselines,
)


def _run_compute_baseline_capturing_worktree_add(tmp: str) -> tuple[str, list[list[str]]]:
    """
    Run `compute_baseline` against a fully-mocked git/subprocess layer and
    return its result plus every `git worktree add` argv it issued.

    `_subprocess_util.run` is monkeypatched to fabricate a successful
    `rev-parse` result and to capture the `worktree add` argv; `_run_verify_in`
    is stubbed to return `(0, "")` so `compute_baseline` short-circuits to
    "clean" on the first verify; `_junction.create` and `_worktree.remove_safe` are
    stubbed to no-ops since no real filesystem worktree is ever created.
    """
    # tempfile.TemporaryDirectory (passed in by the caller) keeps
    # compute_baseline's unconditional `project_root/.scratch` mkdir (see
    # _verify_baseline.py:148-149) landing in an auto-cleaned path rather
    # than a stray real directory.
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
    Case (b): two distinct commands each get their own, independent
    (non-aliased) signature list keyed by name.
    """
    checkout_path = Path("/fake/checkout")
    project_root = Path("/fake/project")

    def _fake_run_verify_in(command: str, cwd: Path) -> tuple[int, str]:
        del cwd
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
    Case (c): a command with zero recognized FAIL-marker lines on both runs
    maps to [] (present, not an absent dict key).
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
    Case (d): a signature that only reproduces on one of the two runs still
    ends up in the union -- neither run's set silently overwrites the
    other's.
    """
    checkout_path = Path("/fake/checkout")
    project_root = Path("/fake/project")
    call_count = {"n": 0}

    def _fake_run_verify_in(command: str, cwd: Path) -> tuple[int, str]:
        del cwd
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
    Case (e): `_link_dependency_dirs` called at two distinct resolved target
    paths against one shared checkout (mirroring how a future shared-checkout
    orchestrator calls it once per distinct effective-cwd fragment), then
    `compute_batch_baselines` with commands resolving to each of those two
    paths via their `cwd_override` entries -- confirming each command runs
    at its own cwd within the one shared checkout and dependency dirs are
    linked at both resolved paths.
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

        def _fake_run_verify_in(command: str, cwd: Path) -> tuple[int, str]:
            seen_cwds.append((command, cwd))
            return 0, "ok\n"

        commands = [
            ("root-batch", "cmd-root", target_git_root),
            ("hub-batch", "cmd-hub", target_hub),
        ]
        with patch("_verify_baseline._run_verify_in", side_effect=_fake_run_verify_in):
            result = compute_batch_baselines(commands, checkout_path, project_root)

        assert result == {"root-batch": [], "hub-batch": []}, result

        root_cwds = [cwd for command, cwd in seen_cwds if command == "cmd-root"]
        hub_cwds = [cwd for command, cwd in seen_cwds if command == "cmd-hub"]
        assert root_cwds == [target_git_root, target_git_root], root_cwds
        assert hub_cwds == [target_hub, target_hub], hub_cwds

        print(
            "PASS: compute_batch_baselines runs each command at its own "
            "resolved cwd within one shared checkout, with dependency dirs "
            "linked at both resolved paths"
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

        # Case 2: the transient-worktree directory basename uses the
        # shortened, 12-hex-character uuid4().hex slice (#629 Windows
        # MAX_PATH mitigation), not the full 32-character hex string.
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

            # The worktree-add target path sits immediately after 'add' and
            # before the parent SHA (the last argv token).
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

        print("All _verify_baseline unit tests passed.")
        return 0
    except AssertionError as exc:
        print(f"FAIL: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
