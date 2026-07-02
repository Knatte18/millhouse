"""Unit tests for millpy-skills-index.py's frontmatter-handling logic.

Covers the #589 fix: `_scan()` must distinguish a genuine YAML parse failure
in a SKILL.md's frontmatter block (a `FrontmatterParseError`, reported with
the underlying `yaml.YAMLError` message) from the unrelated case of a
SKILL.md that has no `---`-delimited frontmatter block at all (reported as
"missing frontmatter"). Both cases still drop the skill from the scan
result -- this test only asserts the two failure modes are diagnosable via
distinct stderr messages, not that either becomes tolerated.

Loads millpy-skills-index.py via importlib.util.spec_from_file_location
(its hyphenated filename cannot be `import`ed directly -- same pattern used
by test-abandon.py) and calls `_scan(repo_root)` directly against a fixture
tree built with `safe_temp_dir()`, with no subprocess or real git involved.
"""
from __future__ import annotations

import contextlib
import importlib.util
import io
import sys
from pathlib import Path

HUB = Path(__file__).resolve().parent.parent.parent.parent
SCRIPTS = HUB / "plugins" / "mill" / "scripts"
sys.path.insert(0, str(SCRIPTS))

from _test_helpers import safe_temp_dir  # noqa: E402

_SKILLS_INDEX_SRC = SCRIPTS / "millpy-skills-index.py"


def _load_skills_index_module():
    """Load millpy-skills-index.py as a module named `mill_skills_index`.

    Uses `mill_skills_index` (not `__main__`) so the `if __name__ ==
    "__main__"` block at the bottom of the script does not fire on import.
    """
    spec = importlib.util.spec_from_file_location(
        "mill_skills_index", str(_SKILLS_INDEX_SRC)
    )
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _write_skill_md(repo_root: Path, plugin: str, name: str, body: str) -> Path:
    """Write `<repo_root>/plugins/<plugin>/skills/<name>/SKILL.md` with `body`."""
    skill_dir = repo_root / "plugins" / plugin / "skills" / name
    skill_dir.mkdir(parents=True, exist_ok=True)
    skill_md = skill_dir / "SKILL.md"
    skill_md.write_text(body, encoding="utf-8")
    return skill_md


def main() -> int:
    passed = 0
    failed = 0

    def ok(name: str) -> None:
        nonlocal passed
        passed += 1
        print(f"PASS: {name}")

    def fail(name: str, exc: Exception) -> None:
        nonlocal failed
        failed += 1
        print(f"FAIL: {name}: {exc}", file=sys.stderr)

    module = _load_skills_index_module()

    # --- (a) valid frontmatter -> included in _scan()'s result ---
    try:
        with safe_temp_dir() as tmp:
            _write_skill_md(
                tmp,
                "testplugin",
                "test-skill-a",
                (
                    "---\n"
                    "name: test-skill-a\n"
                    'description: "One-shot: does a thing"\n'
                    "---\n"
                    "\n"
                    "# Test Skill A\n"
                ),
            )
            result = module._scan(tmp)
            assert "testplugin" in result, f"testplugin missing from scan result: {result}"
            names = [entry["name"] for entry in result["testplugin"]]
            assert "test-skill-a" in names, f"test-skill-a missing from entries: {names}"
            ok("valid frontmatter -> included in _scan() result")
    except Exception as exc:
        fail("valid frontmatter -> included in _scan() result", exc)

    # --- (b) no frontmatter block -> absent, stderr says "missing frontmatter" ---
    try:
        with safe_temp_dir() as tmp:
            _write_skill_md(
                tmp,
                "testplugin",
                "test-skill-b",
                "# Test Skill B\n\nNo frontmatter here.\n",
            )
            stderr_capture = io.StringIO()
            with contextlib.redirect_stderr(stderr_capture):
                result = module._scan(tmp)
            assert "testplugin" not in result, (
                f"testplugin should be absent (no skills survived): {result}"
            )
            stderr_text = stderr_capture.getvalue()
            assert "missing frontmatter" in stderr_text, (
                f"'missing frontmatter' not in stderr: {stderr_text!r}"
            )
            ok("no frontmatter block -> absent from result, stderr says 'missing frontmatter'")
    except Exception as exc:
        fail("no frontmatter block -> absent from result, stderr says 'missing frontmatter'", exc)

    # --- (c) unquoted-colon parse failure (#589 repro) ---
    try:
        with safe_temp_dir() as tmp:
            _write_skill_md(
                tmp,
                "testplugin",
                "test-skill-c",
                (
                    "---\n"
                    "name: test-skill-c\n"
                    "description: One-shot: does a thing\n"
                    "---\n"
                    "\n"
                    "# Test Skill C\n"
                ),
            )
            stderr_capture = io.StringIO()
            with contextlib.redirect_stderr(stderr_capture):
                result = module._scan(tmp)
            assert "testplugin" not in result, (
                f"testplugin should be absent (parse failure drops the skill): {result}"
            )
            stderr_text = stderr_capture.getvalue()
            assert "parse error" in stderr_text, (
                f"'parse error' not in stderr: {stderr_text!r}"
            )
            assert "missing frontmatter" not in stderr_text, (
                f"'missing frontmatter' must NOT appear for a parse failure "
                f"-- the two failure modes must be distinguishable: {stderr_text!r}"
            )
            ok(
                "unquoted-colon parse failure -> absent from result, stderr says "
                "'parse error' (not 'missing frontmatter')"
            )
    except Exception as exc:
        fail(
            "unquoted-colon parse failure -> absent from result, stderr says "
            "'parse error' (not 'missing frontmatter')",
            exc,
        )

    print("", file=sys.stderr)
    if failed:
        print(f"FAIL -- {failed} of {passed + failed}", file=sys.stderr)
        return 1
    print(f"PASS -- all {passed} tests", file=sys.stderr)
    return 0


if __name__ == "__main__":
    sys.exit(main())
