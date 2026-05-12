"""Unit tests for plugins/mill/scripts/_shortcuts.py and the shortcut-wrapper template."""
from __future__ import annotations

import sys
import tempfile
from pathlib import Path

HUB = Path(__file__).resolve().parent.parent.parent.parent
SCRIPTS_DIR = HUB / "plugins" / "mill" / "scripts"
TEMPLATES_DIR = HUB / "plugins" / "mill" / "templates"
sys.path.insert(0, str(SCRIPTS_DIR))

from _render import render  # noqa: E402
from _shortcuts import SHORTCUT_SCRIPTS, write_all  # noqa: E402

TEMPLATE_PATH = TEMPLATES_DIR / "shortcut-wrapper.ps1"


def main() -> int:
    errors = 0

    # --- render(template, {"SCRIPT": "millpy-status"}) contains uv run call for millpy-status.py ---
    rendered = render(TEMPLATE_PATH, {"SCRIPT": "millpy-status"})
    if "millpy-status.py" not in rendered:
        print("FAIL: rendered template does not contain 'millpy-status.py'", file=sys.stderr)
        errors += 1
    else:
        print("PASS: render substitutes <SCRIPT> -> millpy-status.py in template")
    if "uv run" not in rendered:
        print("FAIL: rendered template does not contain 'uv run'", file=sys.stderr)
        errors += 1
    else:
        print("PASS: rendered template contains uv run")

    # --- write_all against empty tempdir creates one PS1 file per SHORTCUT_SCRIPTS entry ---
    with tempfile.TemporaryDirectory() as tmpdir:
        mill_dir = Path(tmpdir)
        written = write_all(mill_dir)
        expected_count = len(SHORTCUT_SCRIPTS)
        if len(written) != expected_count:
            print(
                f"FAIL: write_all wrote {len(written)} files, expected {expected_count}",
                file=sys.stderr,
            )
            errors += 1
        else:
            print(f"PASS: write_all creates all {expected_count} wrapper files")
        for script in SHORTCUT_SCRIPTS:
            target = mill_dir / f"{script}.ps1"
            if not target.exists():
                print(f"FAIL: PS1 wrapper missing for {script}", file=sys.stderr)
                errors += 1
            else:
                content = target.read_text(encoding="utf-8")
                if f"{script}.py" not in content:
                    print(
                        f"FAIL: wrapper for {script} does not reference {script}.py",
                        file=sys.stderr,
                    )
                    errors += 1
        if errors == 0:
            print("PASS: all wrappers contain the correct script reference")

    # --- write_all against tempdir already containing same files -> returns empty list ---
    with tempfile.TemporaryDirectory() as tmpdir:
        mill_dir = Path(tmpdir)
        write_all(mill_dir)  # first run — writes all
        written_second = write_all(mill_dir)  # second run — all identical
        if written_second:
            print(
                f"FAIL: second write_all returned {len(written_second)} paths, expected 0",
                file=sys.stderr,
            )
            errors += 1
        else:
            print("PASS: second write_all returns empty list (all up-to-date)")

    # --- write_all against tempdir with one stale wrapper -> only that one rewritten ---
    with tempfile.TemporaryDirectory() as tmpdir:
        mill_dir = Path(tmpdir)
        write_all(mill_dir)  # seed all files
        stale_script = SHORTCUT_SCRIPTS[0]
        stale_path = mill_dir / f"{stale_script}.ps1"
        stale_path.write_text("# stale content\n", encoding="utf-8")
        written_third = write_all(mill_dir)
        if len(written_third) != 1:
            print(
                f"FAIL: expected 1 rewritten file, got {len(written_third)}",
                file=sys.stderr,
            )
            errors += 1
        elif written_third[0] != stale_path:
            print(
                f"FAIL: wrong file rewritten: {written_third[0]}",
                file=sys.stderr,
            )
            errors += 1
        else:
            print(f"PASS: only stale wrapper ({stale_script}.ps1) is rewritten")
        # Confirm the stale file now has the correct content
        refreshed = stale_path.read_text(encoding="utf-8")
        if f"{stale_script}.py" not in refreshed:
            print(
                f"FAIL: refreshed wrapper for {stale_script} has wrong content",
                file=sys.stderr,
            )
            errors += 1
        else:
            print(f"PASS: refreshed wrapper for {stale_script} has correct content")

    # --- write_all against tempdir with legacy .py wrappers -> .py files deleted, .ps1 files present ---
    with tempfile.TemporaryDirectory() as tmpdir:
        mill_dir = Path(tmpdir)
        for script in SHORTCUT_SCRIPTS:
            (mill_dir / f"{script}.py").write_text("# legacy wrapper\n", encoding="utf-8")
        write_all(mill_dir)
        legacy_errors = 0
        for script in SHORTCUT_SCRIPTS:
            if (mill_dir / f"{script}.py").exists():
                print(f"FAIL: legacy .py wrapper still exists for {script}", file=sys.stderr)
                legacy_errors += 1
                errors += 1
        for script in SHORTCUT_SCRIPTS:
            if not (mill_dir / f"{script}.ps1").exists():
                print(f"FAIL: PS1 wrapper missing after legacy cleanup for {script}", file=sys.stderr)
                legacy_errors += 1
                errors += 1
        if legacy_errors == 0:
            print(f"PASS: write_all deletes all {len(SHORTCUT_SCRIPTS)} legacy .py wrappers")

    if errors:
        print(f"\n{errors} test(s) FAILED", file=sys.stderr)
        return 1
    print("All shortcut-wrapper unit tests passed.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
