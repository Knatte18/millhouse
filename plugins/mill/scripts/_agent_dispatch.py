"""
_agent_dispatch -- shared Agent tool dispatch helpers.

Exports
-------
resolve_dispatch_mode(cfg: dict) -> str
    Read cfg["llm"]["claude"]["dispatch"], validate it is one of
    {"subprocess","psmux","agent"}, and return it. Defaults to "subprocess".
    Raises ValueError on unrecognized value.

model_to_tier(model: str) -> str
    Map a concrete model id to an Agent-tool tier. claude-sonnet-* -> "sonnet",
    claude-opus-* -> "opus", claude-haiku-* -> "haiku".
    Raises ValueError on unrecognized family.

write_brief(briefs_dir: Path, role: str, scope: str, round_n: int, prompt_text: str) -> Path
    Write a brief file to briefs_dir/<role>-<sanitized_scope>-r<round_n>.md,
    creating parent directories. The scope component is sanitized for Windows
    filename safety (colons, slashes, etc. become hyphens). Returns the path
    of the written file. Example role: "implement".

language_skills_directive(batch_file: Path) -> str
    Detect languages from a batch file's touched files (Edits/Creates only)
    and return a markdown block naming the required language skills plus code-quality.

SUBAGENT_REVIEWER, SUBAGENT_IMPLEMENTER
    String constants for subagent type names.
"""
from __future__ import annotations

from pathlib import Path

import _paths
import _review_common

__all__ = [
    "resolve_dispatch_mode",
    "model_to_tier",
    "write_brief",
    "language_skills_directive",
    "SUBAGENT_REVIEWER",
    "SUBAGENT_IMPLEMENTER",
]

SUBAGENT_REVIEWER = "mill:mill-reviewer"
SUBAGENT_IMPLEMENTER = "mill:mill-implementer"

VALID_DISPATCH_MODES = {"subprocess", "psmux", "agent"}
MODEL_FAMILIES = {
    "claude-sonnet": "sonnet",
    "claude-opus": "opus",
    "claude-haiku": "haiku",
}


def resolve_dispatch_mode(cfg: dict) -> str:
    """Resolve the dispatch mode from config.

    Args:
        cfg: Configuration dict (top-level, with llm.claude.dispatch).

    Returns:
        The dispatch mode: "subprocess", "psmux", or "agent".

    Raises:
        ValueError: If dispatch value is unrecognized.
    """
    llm_cfg = cfg.get("llm", {})
    claude_cfg = llm_cfg.get("claude", {})
    mode = claude_cfg.get("dispatch", "subprocess")

    if mode not in VALID_DISPATCH_MODES:
        raise ValueError(f"Unknown dispatch mode: {mode!r}")

    return mode


def model_to_tier(model: str) -> str:
    """Map a model id to an Agent-tool tier.

    Args:
        model: Concrete model id, e.g., "claude-sonnet-4-6".

    Returns:
        Tier string: "sonnet", "opus", or "haiku".

    Raises:
        ValueError: If model family is unrecognized.
    """
    for family, tier in MODEL_FAMILIES.items():
        if model.startswith(family):
            return tier
    raise ValueError(f"Unrecognized model family: {model!r}")


def write_brief(
    briefs_dir: Path,
    role: str,
    scope: str,
    round_n: int,
    prompt_text: str,
) -> Path:
    """Write a brief file and return its path.

    Args:
        briefs_dir: Parent directory for briefs.
        role: Role name (e.g., "implement").
        scope: Scope name (e.g., "code-review"). Sanitized for filename safety.
        round_n: Round number (integer).
        prompt_text: Full prompt text to write (UTF-8).

    Returns:
        Path to the written file.
    """
    briefs_dir = Path(briefs_dir)
    briefs_dir.mkdir(parents=True, exist_ok=True)
    sanitized_scope = _paths.sanitize_filename_component(scope)
    brief_path = briefs_dir / f"{role}-{sanitized_scope}-r{round_n}.md"
    brief_path.write_text(prompt_text, encoding="utf-8")
    return brief_path


def language_skills_directive(batch_file: Path) -> str:
    """Detect languages from a batch's touched files and return a skills block.

    Reads the batch file's ``Edits`` and ``Creates`` fields (not ``Context``)
    and both endpoints of every ``Moves:`` pair (source and destination) for
    language detection, then detects languages by file suffix.  Move endpoints
    are included because a rename is still an edit of that language: the
    implementer needs the right comment and testing skills whether the file is
    being moved, created, or directly edited.

    For each detected language, names the matching ``{lang}-comments`` and
    ``{lang}-testing`` skills plus ``code-quality`` for all batches.

    Args:
        batch_file: Path to the batch file.

    Returns:
        Markdown block starting with "## Required skills" naming the skills.
        Block includes prose specifying which languages are touched.
    """
    # Collect explicitly touched file paths from Edits and Creates (not Context
    # which is read-only context for the implementer).
    touched_paths = _review_common.parse_batch_refs(
        batch_file, fields=("Edits", "Creates")
    )

    # Also collect both endpoints of each Moves: pair.  A renamed file still
    # belongs to the same language family, and the implementer must load the
    # appropriate skills to handle inline comments and tests correctly.
    moves = _review_common.parse_moves(batch_file)
    move_endpoints = [p for pair in moves for p in pair]

    # Merge into a single deduplicated candidate list while preserving order.
    # touched_paths wins if a path appears in both (order is insertion-stable).
    all_candidate_paths: list[str] = list(touched_paths)
    touched_set = set(touched_paths)
    for p in move_endpoints:
        if p not in touched_set:
            all_candidate_paths.append(p)

    # Language mapping: extension -> (human name, skill prefix)
    LANG_MAP = {
        ".go": ("Go", "golang"),
        ".py": ("Python", "python"),
        ".cs": ("C#", "csharp"),
    }

    # Detect languages by file suffix, preserving first-seen order
    detected_langs: list[tuple[str, str]] = []
    seen_langs: set[str] = set()
    for path_str in all_candidate_paths:
        for ext, (human_name, prefix) in LANG_MAP.items():
            if path_str.lower().endswith(ext):
                if human_name not in seen_langs:
                    detected_langs.append((human_name, prefix))
                    seen_langs.add(human_name)
                break

    # Build skills list
    skills = ["`code-quality`"]
    for _, prefix in detected_langs:
        skills.append(f"`{prefix}-comments`")
        skills.append(f"`{prefix}-testing`")

    # Build prose
    if detected_langs:
        lang_list = ", ".join(h for h, _ in detected_langs)
        prose = f"This batch touches {lang_list} files. Before editing any file, load and follow these skills (non-optional): {', '.join(skills)}"
    else:
        prose = f"Before editing any file, load and follow this skill (non-optional): {skills[0]}"

    return f"## Required skills\n\n{prose}"
