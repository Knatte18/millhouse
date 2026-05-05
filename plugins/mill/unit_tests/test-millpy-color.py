"""Unit tests for plugins/mill/scripts/millpy-color.py."""
from __future__ import annotations

import importlib.util
import json
import subprocess
import sys
import tempfile
from pathlib import Path
from unittest.mock import MagicMock, patch

HUB = Path(__file__).resolve().parent.parent.parent.parent
sys.path.insert(0, str(HUB / "plugins" / "mill" / "scripts"))

# Load the hyphenated module name via importlib (millpy-color.py cannot be
# imported with a bare `import` because the filename contains a hyphen).
_SCRIPT = HUB / "plugins" / "mill" / "scripts" / "millpy-color.py"
_spec = importlib.util.spec_from_file_location("mill_color", _SCRIPT)
mill_color = importlib.util.module_from_spec(_spec)
sys.modules["mill_color"] = mill_color  # register so patch() can resolve it
_spec.loader.exec_module(mill_color)


def _make_git_repo(tmp: Path) -> Path:
    """Initialise a minimal git repo under ``tmp`` and return its path."""
    subprocess.run(
        ["git", "init", str(tmp)],
        check=True, capture_output=True,
    )
    subprocess.run(
        ["git", "-C", str(tmp), "commit", "--allow-empty", "-m", "init"],
        check=True, capture_output=True,
    )
    return tmp


def _write_settings(path: Path, title: str, color: str = "#000000") -> None:
    """Write a minimal settings.json with the given title and color."""
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps({
            "window.title": title,
            "workbench.colorCustomizations": {
                "titleBar.activeBackground": color,
            },
        }),
        encoding="utf-8",
    )


def main() -> int:
    errors = 0

    # ------------------------------------------------------------------
    # Test: main(["purple"]) calls write_settings with correct hex and
    # preserves the existing window.title from settings.json.
    # ------------------------------------------------------------------
    with tempfile.TemporaryDirectory() as tmpdir:
        repo = Path(tmpdir)
        _make_git_repo(repo)
        settings_path = repo / ".vscode" / "settings.json"
        _write_settings(settings_path, title="MY: existing-title", color="#000000")

        captured_calls: list[dict] = []

        def mock_write_settings(color_hex, target, *, window_title=None, **kwargs):
            captured_calls.append({
                "color_hex": color_hex,
                "target": target,
                "window_title": window_title,
            })

        with (
            patch("mill_color.resolve_git_root", return_value=repo),
            patch("mill_color.resolve_hub_path", return_value=repo),
            patch("mill_color._vscode.write_settings", side_effect=mock_write_settings),
        ):
            rc = mill_color.main(["purple"])

        if rc != 0:
            print(f"FAIL: main(['purple']) returned {rc}, expected 0", file=sys.stderr)
            errors += 1
        elif not captured_calls:
            print("FAIL: write_settings was not called", file=sys.stderr)
            errors += 1
        else:
            call = captured_calls[0]
            if call["color_hex"] != "#7d2d6b":
                print(
                    f"FAIL: expected color_hex='#7d2d6b', got {call['color_hex']!r}",
                    file=sys.stderr,
                )
                errors += 1
            elif call["window_title"] != "MY: existing-title":
                print(
                    f"FAIL: expected window_title='MY: existing-title', got {call['window_title']!r}",
                    file=sys.stderr,
                )
                errors += 1
            else:
                print("PASS: main(['purple']) calls write_settings with correct hex and preserves title")

    # ------------------------------------------------------------------
    # Test: invalid color name exits non-zero.
    # ------------------------------------------------------------------
    with tempfile.TemporaryDirectory() as tmpdir:
        repo = Path(tmpdir)
        _make_git_repo(repo)
        with patch("mill_color.resolve_git_root", return_value=repo):
            rc = mill_color.main(["nonsense"])
        if rc == 0:
            print("FAIL: main(['nonsense']) returned 0, expected non-zero", file=sys.stderr)
            errors += 1
        else:
            print("PASS: main(['nonsense']) exits non-zero")

    # ------------------------------------------------------------------
    # Test: missing color argument exits non-zero (argparse error).
    # ------------------------------------------------------------------
    try:
        rc = mill_color.main([])
        if rc == 0:
            print("FAIL: main([]) returned 0, expected non-zero", file=sys.stderr)
            errors += 1
        else:
            print("PASS: main([]) exits non-zero")
    except SystemExit as exc:
        if exc.code == 0:
            print("FAIL: main([]) raised SystemExit(0), expected non-zero", file=sys.stderr)
            errors += 1
        else:
            print("PASS: main([]) raises SystemExit with non-zero code")

    # ------------------------------------------------------------------
    # Test: settings file and mill_dir use hub_path (cwd), not git_root,
    # when they differ.
    # ------------------------------------------------------------------
    with tempfile.TemporaryDirectory() as tmpdir:
        git_root = Path(tmpdir)
        hub_path = git_root / "src" / "Models"
        hub_path.mkdir(parents=True, exist_ok=True)

        captured_write: list[dict] = []
        captured_read_slug_args: list[Path] = []

        def mock_write_settings2(color_hex, target, *, window_title=None, **kwargs):
            captured_write.append({"color_hex": color_hex, "target": target})

        class _FakeActiveError(Exception):
            pass

        def mock_read_slug(mill_dir: Path) -> str:
            captured_read_slug_args.append(mill_dir)
            raise _FakeActiveError("no active")

        active_mock = MagicMock()
        active_mock.ActiveError = _FakeActiveError
        active_mock.read_slug.side_effect = mock_read_slug

        with (
            patch("mill_color.resolve_git_root", return_value=git_root),
            patch("mill_color.resolve_hub_path", return_value=hub_path),
            patch("mill_color._vscode.write_settings", side_effect=mock_write_settings2),
            patch("mill_color._active", active_mock),
            patch("mill_color.resolve_wiki_path", return_value=git_root / "wiki"),
            patch("mill_color._load_config", return_value={}),
        ):
            rc = mill_color.main(["blue"])

        if rc != 0:
            print(f"FAIL: cwd-not-git-root test returned {rc}, expected 0", file=sys.stderr)
            errors += 1
        else:
            expected_settings = hub_path / ".vscode" / "settings.json"
            if not captured_write or captured_write[0]["target"] != expected_settings:
                print(
                    f"FAIL: settings target should be {expected_settings}, "
                    f"got {captured_write[0]['target'] if captured_write else 'nothing'}",
                    file=sys.stderr,
                )
                errors += 1
            else:
                expected_mill_dir = hub_path / ".millhouse"
                if not captured_read_slug_args or captured_read_slug_args[0] != expected_mill_dir:
                    print(
                        f"FAIL: read_slug mill_dir should be {expected_mill_dir}, "
                        f"got {captured_read_slug_args[0] if captured_read_slug_args else 'nothing'}",
                        file=sys.stderr,
                    )
                    errors += 1
                else:
                    print(
                        "PASS: settings and mill_dir use hub_path (cwd), not git_root, "
                        "when they differ"
                    )

    if errors:
        print(f"\n{errors} test(s) FAILED", file=sys.stderr)
        return 1
    print("All mill-color unit tests passed.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
