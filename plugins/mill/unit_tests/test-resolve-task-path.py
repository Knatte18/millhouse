"""Unit tests for _paths.resolve_task_path compat fallback."""
from __future__ import annotations

import sys
import tempfile
import unittest
from pathlib import Path

HUB = Path(__file__).resolve().parent.parent.parent.parent
SCRIPTS_DIR = HUB / "plugins" / "mill" / "scripts"
sys.path.insert(0, str(SCRIPTS_DIR))

from _paths import resolve_task_path  # noqa: E402


class TestResolveTaskPath(unittest.TestCase):
    def test_mill_exists_returns_mill(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "_mill").mkdir()
            (root / "_mill" / "status.md").write_text("", encoding="utf-8")
            got = resolve_task_path(root, "_mill/status.md")
        self.assertEqual(got, root / "_mill" / "status.md")

    def test_task_compat_fallback(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "task").mkdir()
            (root / "task" / "status.md").write_text("", encoding="utf-8")
            got = resolve_task_path(root, "_mill/status.md")
        self.assertEqual(got, root / "task" / "status.md")

    def test_neither_exists_returns_mill(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            got = resolve_task_path(root, "_mill/status.md")
        self.assertEqual(got, root / "_mill" / "status.md")

    def test_both_exist_primary_wins(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "_mill").mkdir()
            (root / "_mill" / "status.md").write_text("", encoding="utf-8")
            (root / "task").mkdir()
            (root / "task" / "status.md").write_text("", encoding="utf-8")
            got = resolve_task_path(root, "_mill/status.md")
        self.assertEqual(got, root / "_mill" / "status.md")

    def test_non_mill_path_no_fallback(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "task").mkdir()
            (root / "task" / "status.md").write_text("", encoding="utf-8")
            got = resolve_task_path(root, "custom/status.md")
        self.assertEqual(got, root / "custom" / "status.md")


if __name__ == "__main__":
    unittest.main()
