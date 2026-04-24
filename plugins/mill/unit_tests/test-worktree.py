"""Unit tests for plugins/mill/scripts/_worktree.py."""
from __future__ import annotations

import sys
import tempfile
from pathlib import Path

HUB = Path(__file__).resolve().parent.parent.parent.parent
sys.path.insert(0, str(HUB / "plugins" / "mill" / "scripts"))

from _worktree import copy_millhouse  # noqa: E402


def main() -> int:
    try:
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            src = tmp_path / ".millhouse"
            src.mkdir()
            (src / "keep").mkdir()
            (src / "keep" / "file.txt").write_text("hello", encoding="utf-8")
            (src / "wiki").mkdir()
            (src / "wiki" / "decoy.txt").write_text("wiki-alias", encoding="utf-8")
            (src / "active").mkdir()
            (src / "active" / "decoy.txt").write_text("active-alias", encoding="utf-8")
            (src / "plainfile.txt").write_text("top-level", encoding="utf-8")

            dst = tmp_path / "worktree" / ".millhouse"
            copy_millhouse(src, dst, exclude={"wiki", "active"})

            assert (dst / "keep" / "file.txt").read_text(encoding="utf-8") == "hello"
            assert (dst / "plainfile.txt").read_text(encoding="utf-8") == "top-level"
            assert not (dst / "wiki").exists(), "wiki junction alias must not be copied"
            assert not (dst / "active").exists(), "active junction alias must not be copied"
            print("PASS: copy_millhouse propagates non-excluded entries (excludes junction aliases)")

        print("All _worktree unit tests passed.")
        return 0
    except AssertionError as exc:
        print(f"FAIL: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
