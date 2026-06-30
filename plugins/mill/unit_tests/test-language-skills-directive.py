"""Unit tests for _agent_dispatch.language_skills_directive.

Covers:
  - Go-only files: detects golang-comments, golang-testing, code-quality
  - Python-only files: detects python-comments, python-testing, code-quality
  - C#-only files: detects csharp-comments, csharp-testing, code-quality
  - Mixed languages: both sets present, code-quality once
  - Non-recognized languages (md, yaml): code-quality only
  - Context: vs Edits/Creates: Context files excluded from detection
  - Rendering: directive renders into both implementer and fixer briefs
  - Tools section: both briefs include Skill in Available tools
"""
from __future__ import annotations

import sys
import tempfile
from pathlib import Path

HUB = Path(__file__).resolve().parent.parent.parent.parent
SCRIPTS_DIR = HUB / "plugins" / "mill" / "scripts"
TEMPLATES_DIR = HUB / "plugins" / "mill" / "templates"
sys.path.insert(0, str(SCRIPTS_DIR))

import _agent_dispatch  # noqa: E402
import _render  # noqa: E402


def _write_batch_file(tmp_dir: Path, edits: str = "none", creates: str = "none", context: str = "none") -> Path:
    """Write a minimal batch file and return its path."""
    batch_path = tmp_dir / "01-test.md"
    content = f"""# Batch: test

```yaml
task: "Test"
batch: test
number: 1
cards: 1
verify: null
depends-on: []
```

## Cards

### Card 1: Test

- **Context:** {context}
- **Edits:** {edits}
- **Creates:** {creates}
- **Deletes:** none
- **Requirements:** Test.
- **Commit:** test: implement test
"""
    batch_path.write_text(content, encoding="utf-8")
    return batch_path


def test_go_files_only() -> None:
    """Batch with only .go files detects golang-comments, golang-testing, code-quality."""
    with tempfile.TemporaryDirectory() as tmp:
        batch_path = _write_batch_file(Path(tmp), edits="`foo.go`, `bar.go`")
        directive = _agent_dispatch.language_skills_directive(batch_path)

        assert "## Required skills" in directive, "Missing Required skills heading"
        assert "`golang-comments`" in directive, "Missing golang-comments"
        assert "`golang-testing`" in directive, "Missing golang-testing"
        assert "`code-quality`" in directive, "Missing code-quality"
        assert "Go" in directive, "Missing 'Go' language name"
        assert "`python-comments`" not in directive, "Should not have python-comments"
        print("PASS test_go_files_only")


def test_python_files_only() -> None:
    """Batch with only .py files detects python-comments, python-testing, code-quality."""
    with tempfile.TemporaryDirectory() as tmp:
        batch_path = _write_batch_file(Path(tmp), edits="`script.py`, `module.py`")
        directive = _agent_dispatch.language_skills_directive(batch_path)

        assert "## Required skills" in directive, "Missing Required skills heading"
        assert "`python-comments`" in directive, "Missing python-comments"
        assert "`python-testing`" in directive, "Missing python-testing"
        assert "`code-quality`" in directive, "Missing code-quality"
        assert "Python" in directive, "Missing 'Python' language name"
        assert "`golang-comments`" not in directive, "Should not have golang-comments"
        print("PASS test_python_files_only")


def test_csharp_files_only() -> None:
    """Batch with only .cs files detects csharp-comments, csharp-testing, code-quality."""
    with tempfile.TemporaryDirectory() as tmp:
        batch_path = _write_batch_file(Path(tmp), edits="`Program.cs`, `Utils.cs`")
        directive = _agent_dispatch.language_skills_directive(batch_path)

        assert "## Required skills" in directive, "Missing Required skills heading"
        assert "`csharp-comments`" in directive, "Missing csharp-comments"
        assert "`csharp-testing`" in directive, "Missing csharp-testing"
        assert "`code-quality`" in directive, "Missing code-quality"
        assert "C#" in directive, "Missing 'C#' language name"
        assert "`golang-comments`" not in directive, "Should not have golang-comments"
        print("PASS test_csharp_files_only")


def test_mixed_languages() -> None:
    """Batch with mixed .go and .py files detects both sets; code-quality once."""
    with tempfile.TemporaryDirectory() as tmp:
        batch_path = _write_batch_file(
            Path(tmp),
            edits="`main.go`, `script.py`",
            creates="`utils.go`, `helper.py`"
        )
        directive = _agent_dispatch.language_skills_directive(batch_path)

        assert "## Required skills" in directive, "Missing Required skills heading"
        # Go skills
        assert "`golang-comments`" in directive, "Missing golang-comments"
        assert "`golang-testing`" in directive, "Missing golang-testing"
        # Python skills
        assert "`python-comments`" in directive, "Missing python-comments"
        assert "`python-testing`" in directive, "Missing python-testing"
        # code-quality appears exactly once
        count = directive.count("`code-quality`")
        assert count == 1, f"code-quality should appear once, got {count}"
        # Language names mentioned
        assert "Go" in directive, "Missing 'Go' language name"
        assert "Python" in directive, "Missing 'Python' language name"
        print("PASS test_mixed_languages")


def test_no_recognized_languages() -> None:
    """Batch with only .md/.yaml files detects code-quality only, no -comments/-testing."""
    with tempfile.TemporaryDirectory() as tmp:
        batch_path = _write_batch_file(Path(tmp), edits="`README.md`, `config.yaml`")
        directive = _agent_dispatch.language_skills_directive(batch_path)

        assert "## Required skills" in directive, "Missing Required skills heading"
        assert "`code-quality`" in directive, "Missing code-quality"
        assert "`python-comments`" not in directive, "Should not have python-comments"
        assert "`golang-comments`" not in directive, "Should not have golang-comments"
        assert "`csharp-comments`" not in directive, "Should not have csharp-comments"
        print("PASS test_no_recognized_languages")


def test_context_excluded() -> None:
    """Batch with .go in Context: and .py in Edits: detects Python skills, not Go."""
    with tempfile.TemporaryDirectory() as tmp:
        batch_path = _write_batch_file(
            Path(tmp),
            context="`existing.go`",
            edits="`new.py`"
        )
        directive = _agent_dispatch.language_skills_directive(batch_path)

        assert "## Required skills" in directive, "Missing Required skills heading"
        # Should detect Python from Edits
        assert "`python-comments`" in directive, "Missing python-comments"
        assert "`python-testing`" in directive, "Missing python-testing"
        # Should NOT detect Go from Context
        assert "`golang-comments`" not in directive, "Should not have golang-comments (Context is excluded)"
        assert "Python" in directive, "Missing 'Python' language name"
        assert "Go" not in directive, "Should not mention 'Go' (Context is excluded)"
        print("PASS test_context_excluded")


def test_render_implementer_brief() -> None:
    """Directive renders into implementer-brief.md and Skill appears in Tools."""
    with tempfile.TemporaryDirectory() as tmp:
        batch_path = _write_batch_file(Path(tmp), edits="`test.py`")

        template_path = TEMPLATES_DIR / "implementer-brief.md"
        assert template_path.exists(), f"Template not found: {template_path}"

        # Render with actual directive. START_SHA is included because _render.render
        # raises KeyError on any unresolved token and the brief now contains <START_SHA>.
        tokens = {
            "TASK_TITLE": "Test",
            "SLUG": "test",
            "BATCH_NAME": "test-batch",
            "BATCH_FILE": str(batch_path),
            "OVERVIEW_FILE": str(Path(tmp) / "overview.md"),
            "PROJECT_ROOT": str(Path(tmp)),
            "WIKI_PATH": str(Path(tmp) / "wiki"),
            "SELF_FIX_ROUNDS": "2",
            "ROUND": "1",
            "SESSION_ID": "test-session-id",
            "PARENT_BRANCH": "main",
            "LANGUAGE_SKILLS": _agent_dispatch.language_skills_directive(batch_path),
            "START_SHA": "",
        }
        rendered = _render.render(template_path, tokens)

        # Check directive content appears
        assert "## Required skills" in rendered, "Required skills heading not in rendered template"
        assert "python-comments" in rendered, "python-comments not in rendered template"
        # Check Skill is in Tools section
        assert "Skill" in rendered, "Skill not in rendered template"
        tools_section = rendered[rendered.find("## Tools"):rendered.find("##", rendered.find("## Tools") + 1)]
        assert "Skill" in tools_section, "Skill not in Tools section"
        print("PASS test_render_implementer_brief")


def test_render_fixer_brief() -> None:
    """Directive renders into fixer-batch-brief.md and Skill appears in Tools."""
    with tempfile.TemporaryDirectory() as tmp:
        batch_path = _write_batch_file(Path(tmp), edits="`test.go`")

        template_path = TEMPLATES_DIR / "fixer-batch-brief.md"
        assert template_path.exists(), f"Template not found: {template_path}"

        # Render with actual directive
        tokens = {
            "TASK_TITLE": "Test",
            "SLUG": "test",
            "BATCH_NAME": "test-batch",
            "BATCH_FILE": str(batch_path),
            "OVERVIEW_FILE": str(Path(tmp) / "overview.md"),
            "REVIEW_FILE": str(Path(tmp) / "review.md"),
            "PROJECT_ROOT": str(Path(tmp)),
            "WIKI_PATH": str(Path(tmp) / "wiki"),
            "SESSION_ID": "test-session-id",
            "ROUND": "1",
            "SELF_FIX_ROUNDS": "2",
            "LANGUAGE_SKILLS": _agent_dispatch.language_skills_directive(batch_path),
        }
        rendered = _render.render(template_path, tokens)

        # Check directive content appears
        assert "## Required skills" in rendered, "Required skills heading not in rendered template"
        assert "golang-comments" in rendered, "golang-comments not in rendered template"
        # Check Skill is in Tools section
        assert "Skill" in rendered, "Skill not in rendered template"
        tools_section = rendered[rendered.find("## Tools"):rendered.find("##", rendered.find("## Tools") + 1)]
        assert "Skill" in tools_section, "Skill not in Tools section"
        print("PASS test_render_fixer_brief")


def _write_batch_file_with_moves(
    tmp_dir: Path,
    edits: str = "none",
    creates: str = "none",
    context: str = "none",
    moves: list[tuple[str, str]] | None = None,
) -> Path:
    """Write a minimal batch file with an optional Moves: field and return its path."""
    batch_path = tmp_dir / "01-test.md"
    if moves:
        moves_lines = "\n".join(f"  - `{s}` -> `{d}`" for s, d in moves)
        moves_part = f"\n{moves_lines}"
    else:
        moves_part = " none"
    content = (
        "# Batch: test\n\n"
        "```yaml\n"
        "task: \"Test\"\nbatch: test\nnumber: 1\ncards: 1\nverify: null\ndepends-on: []\n"
        "```\n\n"
        "## Cards\n\n### Card 1: Test\n\n"
        f"- **Context:** {context}\n"
        f"- **Edits:** {edits}\n"
        f"- **Creates:** {creates}\n"
        "- **Deletes:** none\n"
        f"- **Moves:**{moves_part}\n"
        "- **Requirements:** Test.\n"
        "- **Commit:** test: implement test\n"
    )
    batch_path.write_text(content, encoding="utf-8")
    return batch_path


def test_move_only_batch_detects_go_language() -> None:
    """A batch with only Moves: entries (no Edits/Creates) detects Go skills from move paths.

    This is the key regression guard for Card 22: the implementer must receive
    golang-comments and golang-testing even when the batch has zero Edits/Creates
    entries and the only touched files appear as move endpoints.
    """
    with tempfile.TemporaryDirectory() as tmp:
        batch_path = _write_batch_file_with_moves(
            Path(tmp),
            edits="none",
            creates="none",
            moves=[
                ("src/old_handler.go", "src/new_handler.go"),
                ("src/old_service.go", "src/new_service.go"),
            ],
        )
        directive = _agent_dispatch.language_skills_directive(batch_path)

        assert "## Required skills" in directive, "Missing Required skills heading"
        assert "`golang-comments`" in directive, (
            "golang-comments missing from Move-only Go batch"
        )
        assert "`golang-testing`" in directive, (
            "golang-testing missing from Move-only Go batch"
        )
        assert "`code-quality`" in directive, "Missing code-quality"
        assert "Go" in directive, "Missing 'Go' language name in directive"
        # Python/C# skills must not appear when no Python/C# files are involved.
        assert "`python-comments`" not in directive, (
            "python-comments must not appear in a Go-only Move batch"
        )
        assert "`csharp-comments`" not in directive, (
            "csharp-comments must not appear in a Go-only Move batch"
        )
        print("PASS test_move_only_batch_detects_go_language")


def main() -> int:
    tests = [
        test_go_files_only,
        test_python_files_only,
        test_csharp_files_only,
        test_mixed_languages,
        test_no_recognized_languages,
        test_context_excluded,
        test_move_only_batch_detects_go_language,
        test_render_implementer_brief,
        test_render_fixer_brief,
    ]
    failures: list[str] = []
    for fn in tests:
        try:
            fn()
        except AssertionError as exc:
            print(f"FAIL [{fn.__name__}]: {exc}", file=sys.stderr)
            failures.append(fn.__name__)
        except Exception as exc:  # noqa: BLE001
            print(f"ERROR [{fn.__name__}]: {exc}", file=sys.stderr)
            failures.append(fn.__name__)
    if failures:
        print(f"\n{len(failures)} test(s) failed: {failures}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
