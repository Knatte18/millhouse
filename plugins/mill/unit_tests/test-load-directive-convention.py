"""Guard the load-directive convention: `scribe:prose`, then `scribe:conversation`, then `mill:conventions`.

A line naming `scribe:conversation` with a load verb is a load directive;
its file must contain the two-skill phrase "load `scribe:prose`, then `scribe:conversation`".
A line naming `mill:conventions` with a load verb makes the file require the three-skill phrase
"load `scribe:prose`, then `scribe:conversation`, then `mill:conventions`".
A referential mention with no load verb is out of scope and must never be flagged.
A separate forbidden-name scan rejects every reference to the retired mill skill names
and to the retired `plugins/{python,csharp,golang}/` paths.

Covers:
  - check_text: three-skill directive passes
  - check_text: two-skill directive passes
  - check_text: scribe:conversation load directive with no scribe:prose fails
  - check_text: scribe:conversation loaded before scribe:prose fails
  - check_text: mill:conventions load directive in a file with only the two-skill phrase fails
  - check_text: referential mention with no load verb passes
  - check_text: canonical directive followed by a later referential mention passes
  - check_forbidden: flags each retired mill skill name and retired plugin paths
  - check_forbidden: passes mill:conventions, scribe:prose and mill:workflow
  - Tree-walk: every shipped SKILL.md / template file passes check_text
  - Tree-walk: every forbidden-scan file passes check_forbidden
"""
from __future__ import annotations

import re
import sys
from pathlib import Path

HUB = Path(__file__).resolve().parent.parent.parent.parent

_LOAD_VERB_RE = re.compile(r"\b(?:Load|load|loads|loading)\b")
_CONVERSATION_RE = re.compile(r"scribe:conversation")
_CONVENTIONS_RE = re.compile(r"mill:conventions")
_TWO_SKILL_RE = re.compile(r"[Ll]oad\s+`scribe:prose`\s*,?\s*then\s+`scribe:conversation`")
_THREE_SKILL_RE = re.compile(
    r"[Ll]oad\s+`scribe:prose`\s*,\s*then\s+`scribe:conversation`\s*,\s*then\s+`mill:conventions`"
)
_RETIRED_NAMES = "prose|conversation|code-quality|code-comments|testing|handoff"
_FORBIDDEN_RE = re.compile(
    rf"mill:(?:{_RETIRED_NAMES})\b"
    rf"|plugins/mill/skills/(?:{_RETIRED_NAMES})/"
    r"|plugins/(?:python|csharp|golang)/"
)
_SKIPPED_PART_NAMES = {"_mill", ".venv", "node_modules", ".scratch"}


def check_text(text: str) -> str | None:
    """
    Apply the load-directive convention to one file's text.

    A line naming `scribe:conversation` with a load verb on the same line makes the file
    require the two-skill phrase somewhere in its text;
    a line naming `mill:conventions` with a load verb makes it require the three-skill phrase.
    Anchoring on the phrase rather than a positional comparison keeps a correct file
    with later referential mentions passing.

    Returns:
        None if the file passes (out of scope, or in scope and compliant).
        A failure reason string naming the first offending line otherwise.
    """
    lines = text.splitlines()
    conventions_lines = [
        line for line in lines if _CONVENTIONS_RE.search(line) and _LOAD_VERB_RE.search(line)
    ]
    if conventions_lines and not _THREE_SKILL_RE.search(text):
        return (
            "load directive names mill:conventions without loading scribe:prose, "
            f"scribe:conversation, mill:conventions in that order: {conventions_lines[0]!r}"
        )

    conversation_lines = [
        line for line in lines if _CONVERSATION_RE.search(line) and _LOAD_VERB_RE.search(line)
    ]
    if conversation_lines and not _TWO_SKILL_RE.search(text):
        return (
            "load directive does not load scribe:prose before scribe:conversation: "
            f"{conversation_lines[0]!r}"
        )

    return None


def check_forbidden(text: str) -> str | None:
    """Return a reason naming the first line that references a retired skill name or path, else None."""
    for line in text.splitlines():
        if _FORBIDDEN_RE.search(line):
            return f"references a retired skill name or path: {line.strip()!r}"
    return None


def test_three_skill_directive_passes() -> None:
    """The full three-skill directive passes."""
    text = "Step 0: Load `scribe:prose`, then `scribe:conversation`, then `mill:conventions`."
    assert check_text(text) is None
    print("PASS test_three_skill_directive_passes")


def test_two_skill_directive_passes() -> None:
    """The two-skill directive passes."""
    text = "Step 0: Load `scribe:prose`, then `scribe:conversation` before anything else."
    assert check_text(text) is None
    print("PASS test_two_skill_directive_passes")


def test_conversation_directive_missing_prose_fails() -> None:
    """A load directive naming scribe:conversation with no scribe:prose fails."""
    text = "The document's first line instructs the next agent to load `scribe:conversation`."
    reason = check_text(text)
    assert reason is not None, "expected a failure reason"
    assert "scribe:conversation" in reason
    print("PASS test_conversation_directive_missing_prose_fails")


def test_wrong_order_fails() -> None:
    """A load directive naming scribe:conversation before scribe:prose fails."""
    text = "Load `scribe:conversation`, then `scribe:prose` before reading the rest of the document."
    reason = check_text(text)
    assert reason is not None, "expected a failure reason"
    print("PASS test_wrong_order_fails")


def test_conventions_directive_with_only_two_skill_phrase_fails() -> None:
    """A mill:conventions load directive in a file with only the two-skill phrase fails."""
    text = (
        "Load `scribe:prose`, then `scribe:conversation` first.\n"
        "Then load `mill:conventions` as well.\n"
    )
    reason = check_text(text)
    assert reason is not None, "expected a failure reason"
    assert "mill:conventions" in reason
    print("PASS test_conventions_directive_with_only_two_skill_phrase_fails")


def test_referential_mention_passes() -> None:
    """A referential mention with no load verb passes."""
    text = "Options are numbered, per `scribe:conversation`'s numbered-options rule."
    assert check_text(text) is None
    print("PASS test_referential_mention_passes")


def test_canonical_directive_then_later_referential_mention_passes() -> None:
    """A correct directive followed later by a referential mention still passes.

    The later referential line must not be mistaken for a second, mis-ordered load directive.
    """
    text = (
        "Step 0: Load `scribe:prose`, then `scribe:conversation` before anything else.\n"
        "Later on, per `scribe:conversation` rules, format prompts as numbered lists.\n"
    )
    assert check_text(text) is None
    print("PASS test_canonical_directive_then_later_referential_mention_passes")


def test_forbidden_flags_retired_names_and_paths() -> None:
    """check_forbidden flags each retired mill:<name> form and each retired path."""
    for name in ("prose", "conversation", "code-quality", "code-comments", "testing", "handoff"):
        assert check_forbidden(f"Load `mill:{name}` first.") is not None, name
    assert check_forbidden("see plugins/mill/skills/prose/SKILL.md") is not None
    assert check_forbidden("see plugins/python/skills/python-build/SKILL.md") is not None
    print("PASS test_forbidden_flags_retired_names_and_paths")


def test_forbidden_passes_current_names() -> None:
    """check_forbidden passes text naming mill:conventions, scribe:prose and mill:workflow."""
    text = "Use `mill:conventions`, `scribe:prose` and `mill:workflow`."
    assert check_forbidden(text) is None
    print("PASS test_forbidden_passes_current_names")


def _shipped_files() -> list[Path]:
    """Return every file the load-directive convention applies to, relative to HUB.

    Walks `plugins/*/skills/**/SKILL.md`, `.claude/skills/**/SKILL.md` and `plugins/mill/templates/*.md`.
    Script-level prompt builders are covered by test-language-skills-directive.py instead,
    which asserts rendered content rather than pattern-matching source.
    """
    files = sorted(HUB.glob("plugins/*/skills/**/SKILL.md"))
    files += sorted(HUB.glob(".claude/skills/**/SKILL.md"))
    files += sorted(HUB.glob("plugins/mill/templates/*.md"))
    return files


def _forbidden_scan_files() -> list[Path]:
    """Return every file scanned for retired skill names, excluding this test file.

    Covers `*.md` under `plugins/` and `.claude/skills/`, `*.py` under `plugins/mill/scripts/`,
    `*.md` under `doc/`, and `SKILLS.md` and `CLAUDE.md` at HUB.
    Paths passing through `_mill`, `.venv`, `node_modules` or `.scratch` are skipped.
    """
    candidates: list[Path] = []
    candidates += HUB.glob("plugins/**/*.md")
    candidates += HUB.glob(".claude/skills/**/*.md")
    candidates += HUB.glob("plugins/mill/scripts/**/*.py")
    candidates += HUB.glob("doc/**/*.md")
    candidates += [HUB / "SKILLS.md", HUB / "CLAUDE.md"]
    self_path = Path(__file__).resolve()
    files = {
        path
        for path in candidates
        if path.is_file()
        and path.resolve() != self_path
        and not _SKIPPED_PART_NAMES.intersection(path.relative_to(HUB).parts)
    }
    return sorted(files)


def test_tree_walk_shipped_surface() -> None:
    """Every shipped SKILL.md / template file satisfies the load-directive convention."""
    failures: list[str] = []
    for path in _shipped_files():
        text = path.read_text(encoding="utf-8")
        reason = check_text(text)
        if reason is not None:
            failures.append(f"{path.relative_to(HUB)}: {reason}")
    assert not failures, "load-directive convention violated:\n" + "\n".join(failures)
    print("PASS test_tree_walk_shipped_surface")


def test_tree_walk_forbidden_names() -> None:
    """No scanned file references a retired skill name or path."""
    failures: list[str] = []
    for path in _forbidden_scan_files():
        text = path.read_text(encoding="utf-8")
        reason = check_forbidden(text)
        if reason is not None:
            failures.append(f"{path.relative_to(HUB)}: {reason}")
    assert not failures, "retired skill references found:\n" + "\n".join(failures)
    print("PASS test_tree_walk_forbidden_names")


def main() -> int:
    tests = [
        test_three_skill_directive_passes,
        test_two_skill_directive_passes,
        test_conversation_directive_missing_prose_fails,
        test_wrong_order_fails,
        test_conventions_directive_with_only_two_skill_phrase_fails,
        test_referential_mention_passes,
        test_canonical_directive_then_later_referential_mention_passes,
        test_forbidden_flags_retired_names_and_paths,
        test_forbidden_passes_current_names,
        test_tree_walk_shipped_surface,
        test_tree_walk_forbidden_names,
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
