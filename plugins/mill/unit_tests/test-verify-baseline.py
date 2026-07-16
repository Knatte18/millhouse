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
`_run_verify_in` is stubbed to return 0 so `compute_baseline` short-circuits
to "clean" on the first verify; `_junction.create` and
`_worktree.remove_safe` are stubbed to no-ops since no real filesystem
worktree is ever created.
"""
from __future__ import annotations

import re
import sys
import tempfile
from pathlib import Path
from unittest.mock import MagicMock, patch

HUB = Path(__file__).resolve().parent.parent.parent.parent
sys.path.insert(0, str(HUB / "plugins" / "mill" / "scripts"))

from _verify_baseline import compute_baseline  # noqa: E402


def _run_compute_baseline_capturing_worktree_add(tmp: str) -> tuple[str, list[list[str]]]:
    """
    Run `compute_baseline` against a fully-mocked git/subprocess layer and
    return its result plus every `git worktree add` argv it issued.

    `_subprocess_util.run` is monkeypatched to fabricate a successful
    `rev-parse` result and to capture the `worktree add` argv; `_run_verify_in`
    is stubbed to return 0 so `compute_baseline` short-circuits to "clean" on
    the first verify; `_junction.create` and `_worktree.remove_safe` are
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
        with patch("_verify_baseline._run_verify_in", return_value=0):
            with patch("_verify_baseline._junction.create"):
                with patch("_verify_baseline._worktree.remove_safe"):
                    result = compute_baseline(project_root, git_root, "main", "echo ok")

    return result, captured_worktree_add_argv


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

        print("All _verify_baseline unit tests passed.")
        return 0
    except AssertionError as exc:
        print(f"FAIL: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
