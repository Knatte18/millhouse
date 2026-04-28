"""Unit tests for plugins/mill/scripts/_skill_writer.py."""
from __future__ import annotations

import sys
import tempfile
from pathlib import Path

HUB = Path(__file__).resolve().parent.parent.parent.parent
SCRIPTS_DIR = HUB / "plugins" / "mill" / "scripts"
sys.path.insert(0, str(SCRIPTS_DIR))

import _skill_writer  # noqa: E402 — module under test (does not exist yet; tests must FAIL)


def main() -> int:
    errors = 0

    # --- SKILL_GENERATOR_SKIP is ["mill-add"] exactly ---
    if _skill_writer.SKILL_GENERATOR_SKIP != ["mill-add"]:
        print(
            f"FAIL: SKILL_GENERATOR_SKIP is {_skill_writer.SKILL_GENERATOR_SKIP!r}, expected ['mill-add']",
            file=sys.stderr,
        )
        errors += 1
    else:
        print("PASS: SKILL_GENERATOR_SKIP == ['mill-add']")
    if not isinstance(_skill_writer.SKILL_GENERATOR_SKIP, list):
        print(
            f"FAIL: SKILL_GENERATOR_SKIP is {type(_skill_writer.SKILL_GENERATOR_SKIP).__name__}, expected list",
            file=sys.stderr,
        )
        errors += 1
    else:
        print("PASS: SKILL_GENERATOR_SKIP is a list")

    # --- iter_target_scripts returns the 12 expected paths ---
    expected_stems = sorted([
        "millpy-list",
        "millpy-status",
        "millpy-inspect",
        "millpy-spawn",
        "millpy-claim",
        "millpy-cleanup",
        "millpy-abandon",
        "millpy-color",
        "millpy-terminal",
        "millpy-vscode",
        "millpy-worktree",
        "millpy-fetch-issues",
    ])
    with tempfile.TemporaryDirectory() as tmpdir:
        tmp = Path(tmpdir)
        scripts_dir = tmp / "mill" / "scripts"
        scripts_dir.mkdir(parents=True)
        # Touch one file per SHORTCUT_SCRIPTS entry (13 total)
        from _shortcuts import SHORTCUT_SCRIPTS  # noqa: E402
        for stem in SHORTCUT_SCRIPTS:
            (scripts_dir / f"{stem}.py").touch()

        result = _skill_writer.iter_target_scripts(tmp)
        if len(result) != 12:
            print(
                f"FAIL: iter_target_scripts returned {len(result)} paths, expected 12",
                file=sys.stderr,
            )
            errors += 1
        else:
            print("PASS: iter_target_scripts returns 12 paths")

        for path in result:
            if not isinstance(path, Path):
                print(
                    f"FAIL: result item is {type(path).__name__}, expected Path",
                    file=sys.stderr,
                )
                errors += 1
                break
            if not str(path).endswith(".py"):
                print(f"FAIL: path does not end with .py: {path}", file=sys.stderr)
                errors += 1
            stem_part = path.name
            if not stem_part.startswith("millpy-"):
                print(
                    f"FAIL: path filename does not start with 'millpy-': {path}",
                    file=sys.stderr,
                )
                errors += 1
        else:
            print("PASS: all returned paths end with .py and start with millpy-")

        returned_stems = sorted(p.stem for p in result)
        if returned_stems != expected_stems:
            print(
                f"FAIL: returned stems {returned_stems!r} != expected {expected_stems!r}",
                file=sys.stderr,
            )
            errors += 1
        else:
            print("PASS: iter_target_scripts returns exactly the 12 expected stems")

        # Confirm millpy-add.py (skill mill-add) is absent (skip-listed)
        returned_names = [p.name for p in result]
        if "millpy-add.py" in returned_names:
            print("FAIL: millpy-add.py must be absent (mill-add is skip-listed)", file=sys.stderr)
            errors += 1
        else:
            print("PASS: millpy-add.py absent from iter_target_scripts result")

    # --- write_skill_file writes to the correct path ---
    with tempfile.TemporaryDirectory() as tmpdir:
        tmp = Path(tmpdir)

        # First call: file must be created
        written = _skill_writer.write_skill_file("mill-spawn", "test body content\n", tmp)
        expected_path = tmp / "mill" / "skills" / "mill-spawn" / "SKILL.md"
        if not expected_path.exists():
            print(
                f"FAIL: write_skill_file did not create {expected_path}",
                file=sys.stderr,
            )
            errors += 1
        else:
            print("PASS: write_skill_file creates SKILL.md at correct path")
        content = expected_path.read_text(encoding="utf-8") if expected_path.exists() else ""
        if content != "test body content\n":
            print(
                f"FAIL: SKILL.md content is {content!r}, expected 'test body content\\n'",
                file=sys.stderr,
            )
            errors += 1
        else:
            print("PASS: write_skill_file writes expected content")
        if written != expected_path:
            print(
                f"FAIL: write_skill_file returned {written!r}, expected {expected_path!r}",
                file=sys.stderr,
            )
            errors += 1
        else:
            print("PASS: write_skill_file returns the written Path")

        # Second call: file must be overwritten (not appended)
        _skill_writer.write_skill_file("mill-spawn", "overwritten content\n", tmp)
        overwritten = expected_path.read_text(encoding="utf-8")
        if overwritten != "overwritten content\n":
            print(
                f"FAIL: second write_skill_file did not overwrite; content is {overwritten!r}",
                file=sys.stderr,
            )
            errors += 1
        else:
            print("PASS: second write_skill_file overwrites (does not append)")

        # Third call: hyphenated skill name — directory must be created
        hyphen_path = tmp / "mill" / "skills" / "mill-fetch-issues" / "SKILL.md"
        _skill_writer.write_skill_file("mill-fetch-issues", "fetch body\n", tmp)
        if not (tmp / "mill" / "skills" / "mill-fetch-issues").is_dir():
            print(
                "FAIL: directory mill-fetch-issues/ not created for hyphenated skill name",
                file=sys.stderr,
            )
            errors += 1
        else:
            print("PASS: write_skill_file creates directory for hyphenated skill name")
        if not hyphen_path.exists():
            print(
                f"FAIL: SKILL.md not written for mill-fetch-issues at {hyphen_path}",
                file=sys.stderr,
            )
            errors += 1
        else:
            print("PASS: SKILL.md written for mill-fetch-issues")

    if errors:
        print(f"\n{errors} test(s) FAILED", file=sys.stderr)
        return 1
    print("All skill-writer unit tests passed.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
