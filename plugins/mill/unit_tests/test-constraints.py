"""Unit tests for plugins/mill/scripts/_constraints.py."""
from __future__ import annotations

import sys
import tempfile
from pathlib import Path

HUB = Path(__file__).resolve().parent.parent.parent.parent
sys.path.insert(0, str(HUB / "plugins" / "mill" / "scripts"))

import _subprocess_util  # noqa: E402
from _constraints import read_if_exists  # noqa: E402


def main() -> int:
    try:
        # No CONSTRAINTS.md in a freshly-inited repo -> None.
        with tempfile.TemporaryDirectory() as tmp:
            _subprocess_util.run(["git", "init", tmp, "-b", "main"])
            assert read_if_exists(Path(tmp)) is None
            print("PASS: read_if_exists returns None when CONSTRAINTS.md absent")

            (Path(tmp) / "CONSTRAINTS.md").write_text("hello\n", encoding="utf-8")
            assert read_if_exists(Path(tmp)) == "hello\n"
            print("PASS: read_if_exists returns file contents when present")

            # From a subfolder -- exercises the subfolder-friendly resolution.
            sub = Path(tmp) / "sub" / "deeper"
            sub.mkdir(parents=True)
            assert read_if_exists(sub) == "hello\n"
            print("PASS: read_if_exists resolves from a subfolder")

        # Not inside a git repo at all -> None.
        with tempfile.TemporaryDirectory() as tmp:
            non_repo = Path(tmp)
            assert read_if_exists(non_repo) is None
            print("PASS: read_if_exists returns None outside a git repo")

        print("All _constraints unit tests passed.")
        return 0
    except AssertionError as exc:
        print(f"FAIL: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
