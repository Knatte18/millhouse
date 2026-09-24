"""Unit tests for plugins/mill/scripts/_parent_branch.py."""
from __future__ import annotations

import sys
import tempfile
from pathlib import Path
from unittest.mock import MagicMock, patch

HUB = Path(__file__).resolve().parent.parent.parent.parent
sys.path.insert(0, str(HUB / "plugins" / "mill" / "scripts"))

import _parent_branch  # noqa: E402
from _parent_branch import ParentBranchError, resolve  # noqa: E402


def _make_run_mock(returncode: int) -> MagicMock:
    """Return a MagicMock that looks like a CompletedProcess from _subprocess_util.run."""
    mock = MagicMock()
    mock.returncode = returncode
    return mock


def main() -> int:
    try:
        with tempfile.TemporaryDirectory() as tmp:
            sp = Path(tmp) / "status.md"
            sp.write_text(
                "# Status\n"
                "\n"
                "```yaml\n"
                "phase: done\n"
                "task: Demo\n"
                "parent: main\n"
                "```\n",
                encoding="utf-8",
            )
            assert resolve(sp, interactive=False) == "main"
            print("PASS: resolve reads parent from status.md")

            sp.write_text(
                "# Status\n"
                "\n"
                "```yaml\n"
                "phase: done\n"
                "task: Demo\n"
                "```\n",
                encoding="utf-8",
            )
            try:
                resolve(sp, interactive=False)
            except ParentBranchError as exc:
                assert "No parent_branch:" in str(exc)
                print(f"PASS: resolve raises on missing parent non-interactive -- {exc}")
            else:
                raise AssertionError("expected ParentBranchError")

            sp.write_text(
                "# Status\n"
                "\n"
                "```yaml\n"
                "phase: done\n"
                "task: Demo\n"
                "slug: demo-task\n"
                "parent: main\n"
                "```\n",
                encoding="utf-8",
            )
            assert resolve(sp, interactive=False, expected_slug="demo-task") == "main"
            print("PASS: resolve with matching expected_slug reads parent from status.md")

            try:
                resolve(sp, interactive=False, expected_slug="other-task")
            except ParentBranchError as exc:
                assert "No parent_branch:" in str(exc)
                print(f"PASS: resolve raises on mismatched expected_slug -- {exc}")
            else:
                raise AssertionError("expected ParentBranchError on slug mismatch")

            sp.write_text(
                "# Status\n"
                "\n"
                "```yaml\n"
                "phase: done\n"
                "task: Demo\n"
                "parent: main\n"
                "```\n",
                encoding="utf-8",
            )
            assert resolve(sp, interactive=False, expected_slug="anything") == "main"
            print("PASS: resolve with expected_slug is a no-op when status.md has no slug: row")

            # --- parent_branch key, legacy fallback, precedence ---
            sp.write_text("# Status\n\n```yaml\nphase: done\ntask: Demo\nparent_branch: main\n```\n", encoding="utf-8")
            assert resolve(sp, interactive=False) == "main"
            sp.write_text("# Status\n\n```yaml\nphase: done\ntask: Demo\nparent_branch: feat\nparent: main\n```\n", encoding="utf-8")
            assert resolve(sp, interactive=False) == "feat"
            print("PASS: resolve reads parent_branch and prefers it over legacy parent")

            sp.write_text("# Status\n\n```yaml\nphase: done\ntask: Demo\nparent_thread: 'mh:orch'\n```\n", encoding="utf-8")
            try:
                resolve(sp, interactive=False)
            except ParentBranchError as exc:
                assert "No parent_branch:" in str(exc)
            else:
                raise AssertionError("parent_thread alone must not resolve a parent")
            print("PASS: resolve ignores parent_thread")

            sp.write_text("# Status\n\n```yaml\nphase: done\ntask: Demo\nslug: demo-task\nparent_branch: main\n```\n", encoding="utf-8")
            try:
                resolve(sp, interactive=False, expected_slug="other-task")
            except ParentBranchError:
                pass
            else:
                raise AssertionError("expected ParentBranchError on slug mismatch")
            assert resolve(sp, interactive=False, expected_slug="demo-task") == "main"
            print("PASS: resolve applies expected_slug guard to parent_branch files")

            dead_cfg = {"spawn": {"branch_prefix": "test/"}, "git": {"base_branch": "main"}}
            for archived_rows in ("parent_branch: main\n", "parent: main\n"):
                archived = _make_run_mock(0)
                archived.stdout = "# Status\n\n```yaml\nphase: done\n" + archived_rows + "```\n"
                with patch.object(
                    _parent_branch._subprocess_util,
                    "run",
                    side_effect=[_make_run_mock(0), archived, _make_run_mock(0)],
                ):
                    result = _parent_branch.resolve_dead_parent("test/dead-task", Path(tmp), dead_cfg)
                assert result == {"outcome": "resolved", "branch": "main", "hops": ["dead-task"]}, result
            print("PASS: resolve_dead_parent reads parent_branch and legacy parent from archived status.md")

            with patch.object(
                _parent_branch._subprocess_util, "run", return_value=_make_run_mock(0)
            ) as mock_run:
                assert _parent_branch.check_liveness("main", Path(tmp)) is True
                assert mock_run.call_count == 1
            print("PASS: check_liveness returns True when the remote ls-remote check succeeds")

            with patch.object(
                _parent_branch._subprocess_util,
                "run",
                side_effect=[_make_run_mock(1), _make_run_mock(0)],
            ):
                assert _parent_branch.check_liveness("main", Path(tmp)) is True
            print("PASS: check_liveness falls back to the local branch ref when origin lacks it")

            with patch.object(
                _parent_branch._subprocess_util,
                "run",
                side_effect=[_make_run_mock(2), _make_run_mock(1)],
            ):
                assert _parent_branch.check_liveness("main", Path(tmp)) is False
            print("PASS: check_liveness returns False when neither origin nor a local ref exists")

        print("All _parent_branch unit tests passed.")
        return 0
    except AssertionError as exc:
        print(f"FAIL: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
