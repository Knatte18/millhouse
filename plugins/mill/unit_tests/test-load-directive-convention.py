"""Guard the load-directive convention: `mill:prose` before `mill:conversation`.

Any line that both names `mill:conversation` and carries a load verb is a load directive, and every
such line's file must also name `mill:prose` and must contain the canonical ordering phrase
somewhere in its text.
A referential mention of `mill:conversation` with no load verb (e.g. "per `mill:conversation`
rules", "see `mill:conversation`'s file-writing rule") is out of scope and must never be flagged.

Covers:
  - check_text: canonical directive passes
  - check_text: load directive naming mill:conversation with no mill:prose fails
  - check_text: referential mention with no load verb passes
  - check_text: load directive naming mill:conversation before mill:prose fails
  - check_text: canonical directive followed by a later bare referential mention passes
  - Tree-walk: every shipped SKILL.md / template file passes check_text
"""
from __future__ import annotations

import re
import sys
from pathlib import Path

HUB = Path(__file__).resolve().parent.parent.parent.parent

_LOAD_VERB_RE = re.compile(r"\b(?:Load|load|loads|loading)\b")
_CONVERSATION_RE = re.compile(r"mill:conversation")
_PROSE_RE = re.compile(r"mill:prose")
_CANONICAL_RE = re.compile(r"[Ll]oad\s+`mill:prose`\s*,?\s*(?:then|and)\s+`mill:conversation`")


def check_text(text: str) -> str | None:
    """
    Apply the load-directive convention's three-step rule to one file's text.

    Step 1 (discrimination): a line is in scope only if it names `mill:conversation`
    and carries a load verb on the same line.
    A file with no in-scope line is not a load directive site and passes vacuously.

    Step 2 (co-presence): an in-scope file that never mentions `mill:prose` anywhere
    fails, since a load directive that never loads `mill:prose` cannot satisfy the ordering rule.

    Step 3 (order): an in-scope file must also contain at least one line matching the
    canonical wording "load `mill:prose`[,] then/and `mill:conversation`".
    Anchoring on this exact phrase, rather than a per-line or first-occurrence positional
    comparison, is required -- see the plan's `convention-test-anchors-on-canonical-wording`
    Shared Decision for why every positional alternative fails a file that is already correct.

    Returns:
        None if the file passes (out of scope, or in scope and compliant).
        A failure reason string naming the offending line otherwise.
    """
    in_scope_lines = [
        line for line in text.splitlines()
        if _CONVERSATION_RE.search(line) and _LOAD_VERB_RE.search(line)
    ]
    if not in_scope_lines:
        return None

    if not _PROSE_RE.search(text):
        return f"load directive names mill:conversation with no mill:prose anywhere: {in_scope_lines[0]!r}"

    if not _CANONICAL_RE.search(text):
        return f"load directive does not load mill:prose before mill:conversation: {in_scope_lines[0]!r}"

    return None


def test_canonical_directive_passes() -> None:
    """A correct canonical directive line passes."""
    text = "Step 0: Load `mill:prose`, then `mill:conversation` before anything else."
    assert check_text(text) is None
    print("PASS test_canonical_directive_passes")


def test_load_directive_missing_prose_fails() -> None:
    """A load directive naming mill:conversation with no mill:prose anywhere fails."""
    text = "The document's first line instructs the next agent to load `mill:conversation`."
    reason = check_text(text)
    assert reason is not None, "expected a failure reason"
    assert "mill:conversation" in reason
    print("PASS test_load_directive_missing_prose_fails")


def test_referential_mention_passes() -> None:
    """A referential mention of mill:conversation with no load verb passes."""
    text = "Save to `.scratch/handoff.md` (see `mill:conversation`'s file-writing rule)."
    assert check_text(text) is None
    print("PASS test_referential_mention_passes")


def test_wrong_order_fails() -> None:
    """A load directive naming mill:conversation before mill:prose fails."""
    text = "Load `mill:conversation`, then `mill:prose` before reading the rest of the document."
    reason = check_text(text)
    assert reason is not None, "expected a failure reason"
    print("PASS test_wrong_order_fails")


def test_canonical_directive_then_later_referential_mention_passes() -> None:
    """A correct canonical directive followed later by a bare referential mention still passes.

    This is the case that separates the order check from the discrimination rule: the later
    referential line must not be mistaken for a second, mis-ordered load directive.
    """
    text = (
        "Step 0: Load `mill:prose`, then `mill:conversation` before anything else.\n"
        "Later on, per `mill:conversation` rules, format prompts as numbered lists.\n"
    )
    assert check_text(text) is None
    print("PASS test_canonical_directive_then_later_referential_mention_passes")


def _shipped_files() -> list[Path]:
    """Return every file the real load-directive convention applies to, relative to HUB.

    Walks `plugins/*/skills/**/SKILL.md` and `plugins/mill/templates/*.md`.
    Excludes `.claude/skills/` (repo-local, not shipped) and `plugins/mill/scripts/*.py`
    (script-level prompt builders are covered by test-language-skills-directive.py instead,
    which asserts rendered content rather than pattern-matching source).
    """
    files = sorted(HUB.glob("plugins/*/skills/**/SKILL.md"))
    files += sorted(HUB.glob("plugins/mill/templates/*.md"))
    return files


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


def main() -> int:
    tests = [
        test_canonical_directive_passes,
        test_load_directive_missing_prose_fails,
        test_referential_mention_passes,
        test_wrong_order_fails,
        test_canonical_directive_then_later_referential_mention_passes,
        test_tree_walk_shipped_surface,
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
