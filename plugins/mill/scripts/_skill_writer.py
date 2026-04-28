"""
Helpers for the mill-skills-from-scripts skill.

Exposes the skip-list constant + two functions used by the skill body
to produce per-script SKILL.md files. The skill itself (LLM-driven)
drafts the body content; this module owns the deterministic file IO
+ filtering. No `if __name__ == "__main__":` block — this is a helper,
not a CLI entry point.

Public API:
    SKILL_GENERATOR_SKIP — list of skill names whose SKILL.md must not
        be regenerated (hand-written, judgment-heavy bodies).
    iter_target_scripts(plugins_root) — return the list of script paths
        eligible for skill generation.
    write_skill_file(skill_name, body, plugins_root) — write a
        generated SKILL.md to the canonical path. Always overwrites.
"""
from __future__ import annotations

from pathlib import Path

import _shortcuts

# Skill names (with hyphen, no `py` infix) whose SKILL.md is hand-written
# and must survive regeneration. Today only `mill-add` qualifies — its
# body is judgment-heavy (slug derivation, summary writing,
# proposal-extraction heuristics). `mill-skills-index` is also
# hand-written but is excluded one layer up (not in SHORTCUT_SCRIPTS),
# so does NOT appear here.
SKILL_GENERATOR_SKIP: list[str] = ["mill-add"]


def _stem_to_skill_name(stem: str) -> str:
    """Map a script stem like ``"millpy-spawn"`` to skill name ``"mill-spawn"``.

    The rename convention adds a ``py`` infix to scripts but skill
    names keep the bare ``mill-`` prefix. This helper drops the ``py``.
    """
    if not stem.startswith("millpy-"):
        raise ValueError(f"Expected stem to start with 'millpy-': {stem!r}")
    return "mill-" + stem.removeprefix("millpy-")


def iter_target_scripts(plugins_root: Path) -> list[Path]:
    """Return paths of scripts eligible for skill generation.

    Reads the canonical user-callable list from
    ``_shortcuts.SHORTCUT_SCRIPTS`` (post-rename: 13 entries with
    ``millpy-`` prefix). Maps each stem to a path under
    ``<plugins_root>/mill/scripts/<stem>.py``. Filters out scripts
    whose corresponding skill name is in :data:`SKILL_GENERATOR_SKIP`.

    Args:
        plugins_root: Filesystem path to the ``plugins/`` directory
            (production callers pass the resolved hub path; tests pass
            a tempdir whose layout mirrors the real one).

    Returns:
        List of ``Path`` objects, one per eligible script. Order
        matches ``SHORTCUT_SCRIPTS``. Paths are NOT verified to exist
        on disk — callers that care can ``.exists()`` each entry.
    """
    result: list[Path] = []
    for stem in _shortcuts.SHORTCUT_SCRIPTS:
        skill_name = _stem_to_skill_name(stem)
        if skill_name in SKILL_GENERATOR_SKIP:
            continue
        result.append(plugins_root / "mill" / "scripts" / f"{stem}.py")
    return result


def write_skill_file(skill_name: str, body: str, plugins_root: Path) -> Path:
    """Write a generated SKILL.md to ``<plugins_root>/mill/skills/<skill_name>/SKILL.md``.

    Always overwrites — re-running the generator reproduces the file
    from current docstrings (idempotent under stable inputs). Creates
    the parent directory if missing.

    Args:
        skill_name: Skill name with hyphen (e.g. ``"mill-spawn"``),
            not ``"mill:spawn"`` and not ``"millpy-spawn"``.
        body: Full SKILL.md content as a string. Must include the
            ``---`` frontmatter and trailing newline.
        plugins_root: Filesystem path to the ``plugins/`` directory.

    Returns:
        The ``Path`` to the written SKILL.md file.
    """
    target_dir = plugins_root / "mill" / "skills" / skill_name
    target_dir.mkdir(parents=True, exist_ok=True)
    target = target_dir / "SKILL.md"
    target.write_text(body, encoding="utf-8")
    return target
