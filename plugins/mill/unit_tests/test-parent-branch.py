"""Unit tests for plugins/mill/scripts/_parent_branch.py."""
from __future__ import annotations

import sys
import tempfile
from pathlib import Path

HUB = Path(__file__).resolve().parent.parent.parent.parent
sys.path.insert(0, str(HUB / "plugins" / "mill" / "scripts"))

from _parent_branch import ParentBranchError, resolve, resolve_for_codeguide  # noqa: E402


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

            assert resolve_for_codeguide(sp) == "main"
            print("PASS: resolve_for_codeguide reads parent from status.md")

            nonexistent = Path(tmp) / "nonexistent-status.md"
            assert resolve_for_codeguide(nonexistent) is None
            print("PASS: resolve_for_codeguide returns None for a missing status.md file")

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
                assert "No parent:" in str(exc)
                print(f"PASS: resolve raises on missing parent non-interactive -- {exc}")
            else:
                raise AssertionError("expected ParentBranchError")

            assert resolve_for_codeguide(sp) is None
            print("PASS: resolve_for_codeguide returns None on missing parent instead of raising")

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
                assert "No parent:" in str(exc)
                print(f"PASS: resolve raises on mismatched expected_slug -- {exc}")
            else:
                raise AssertionError("expected ParentBranchError on slug mismatch")

            assert resolve_for_codeguide(sp, expected_slug="demo-task") == "main"
            print("PASS: resolve_for_codeguide with matching expected_slug reads parent from status.md")

            assert resolve_for_codeguide(sp, expected_slug="other-task") is None
            print("PASS: resolve_for_codeguide returns None on mismatched expected_slug instead of raising")

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

        print("All _parent_branch unit tests passed.")
        return 0
    except AssertionError as exc:
        print(f"FAIL: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
