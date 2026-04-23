"""Unit tests for plugins/mill/scripts/_parent_branch.py."""
from __future__ import annotations

import sys
import tempfile
from pathlib import Path

HUB = Path(__file__).resolve().parent.parent.parent.parent
sys.path.insert(0, str(HUB / "plugins" / "mill" / "scripts"))

from _parent_branch import ParentBranchError, resolve  # noqa: E402


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
                assert "No parent:" in str(exc)
                print(f"PASS: resolve raises on missing parent non-interactive -- {exc}")
            else:
                raise AssertionError("expected ParentBranchError")

        print("All _parent_branch unit tests passed.")
        return 0
    except AssertionError as exc:
        print(f"FAIL: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
