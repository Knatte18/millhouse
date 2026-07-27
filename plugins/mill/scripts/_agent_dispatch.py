"""
_agent_dispatch -- shared Agent tool dispatch helpers.

Exports
-------
resolve_dispatch_mode(cfg: dict) -> str
    Read cfg["llm"]["claude"]["dispatch"], validate it is one of
    {"subprocess","psmux","agent"}, and return it. Defaults to "agent".
    Raises ValueError on unrecognized value.

model_to_tier(model: str) -> str
    Map a concrete model id to an Agent-tool tier. claude-sonnet-* -> "sonnet",
    claude-opus-* -> "opus", claude-haiku-* -> "haiku".
    Raises ValueError on unrecognized family.

resolve_subagent_type(base: str, effort: str | None) -> str
    Append an effort-tier suffix ("-low"/"-medium"/"-high"/"-xhigh"/"-max") to a base
    subagent_type string when effort names a recognized tier. Falls back to
    base unchanged for None or any unrecognized value -- never raises.

write_brief(briefs_dir: Path, role: str, scope: str, round_n: int, prompt_text: str, output_contract: bool = False) -> Path
    Write a brief file to briefs_dir/<role>-<sanitized_scope>-r<round_n>.md,
    creating parent directories. The scope component is sanitized for Windows
    filename safety (colons, slashes, etc. become hyphens). Returns the path
    of the written file. Example role: "implement". Always unlinks a stale
    ".out.md" next to the brief first. When output_contract is True (default
    False), appends an output-contract footer naming the absolute ".out.md"
    path and requiring a one-line "WROTE <path>" chat ack.

output_path_for(brief_path: Path) -> Path
    Return the brief path with its trailing ".md" replaced by ".out.md" --
    the single home of the ".md" -> ".out.md" rule every agent-mode
    dispatcher and reviewer relies on. Preserves the parent directory and
    absoluteness of the input path.

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
    "resolve_subagent_type",
    "write_brief",
    "output_path_for",
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
EFFORT_TIERED_SUBAGENT_TYPES = frozenset({"low", "medium", "high", "xhigh", "max"})


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
    mode = claude_cfg.get("dispatch", "agent")

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


def resolve_subagent_type(base: str, effort: str | None) -> str:
    """Compute the tier-suffixed subagent_type for an Agent-tool dispatch.

    This is the single place every envelope-construction call site computes
    a tier-suffixed subagent_type string, rather than each re-implementing
    the "{base}-{effort}" f-string pattern inline.

    Args:
        base: The base subagent_type, e.g. SUBAGENT_REVIEWER or
            SUBAGENT_IMPLEMENTER.
        effort: The resolved alias's effort tier, or None when the alias
            carries no effort field.

    Returns:
        base unchanged when effort is None or not a member of
        EFFORT_TIERED_SUBAGENT_TYPES -- this fallback is deliberate and
        forward-compatible: an unrecognized future tier (e.g. someone adding
        "effort: ultra" to mill-agents.yaml before a matching agent-definition
        file exists) degrades to today's base behavior rather than raising
        or constructing a subagent_type with no matching file on disk.
        Otherwise returns f"{base}-{effort}", e.g.
        resolve_subagent_type(SUBAGENT_REVIEWER, "high") ->
        "mill:mill-reviewer-high".
    """
    if effort is None or effort not in EFFORT_TIERED_SUBAGENT_TYPES:
        return base
    return f"{base}-{effort}"


def write_brief(
    briefs_dir: Path,
    role: str,
    scope: str,
    round_n: int,
    prompt_text: str,
    output_contract: bool = False,
) -> Path:
    """Write a brief file and return its path.

    Two behaviours run on every call, regardless of ``output_contract``:
    the brief is written to briefs_dir/<role>-<sanitized_scope>-r<round_n>.md,
    and any stale ``.out.md`` left over from a prior dispatch to that same
    path is unlinked first. The unlink matters because a transient-retry
    re-dispatch reuses the same role/scope/round -- hence the same
    ``.out.md`` path -- so without it an attempt-1 output file could be
    misread as attempt-2's result (e.g. a stale ``APPROVE`` from a reviewer
    that never actually ran this round).

    When ``output_contract`` is True, an output-contract footer is appended
    to ``prompt_text`` before writing: it names the absolute ``.out.md``
    path (via ``output_path_for``) as the file the agent must write its full
    report to, and instructs the agent's final chat message to be a one-line
    ``WROTE <path>`` ack and nothing else. This flag defaults to False so
    every pre-existing caller keeps writing ``prompt_text`` byte-for-byte.

    Args:
        briefs_dir: Parent directory for briefs.
        role: Role name (e.g., "implement").
        scope: Scope name (e.g., "code-review"). Sanitized for filename safety.
        round_n: Round number (integer).
        prompt_text: Full prompt text to write (UTF-8).
        output_contract: When True, append the output-contract footer
            described above. Defaults to False (no footer, no behaviour
            change from today).

    Returns:
        Path to the written brief file (never a tuple -- callers that need
        the output path call ``output_path_for`` themselves).
    """
    briefs_dir = Path(briefs_dir)
    briefs_dir.mkdir(parents=True, exist_ok=True)
    sanitized_scope = _paths.sanitize_filename_component(scope)
    brief_path = briefs_dir / f"{role}-{sanitized_scope}-r{round_n}.md"

    # Unconditionally clear any stale output from a prior dispatch to this
    # same brief path. Runs for every role, agent-mode or not: without it, a
    # transient-retry re-dispatch (same role/scope/round) could read back an
    # attempt-1 output as attempt-2's result.
    output_path_for(brief_path).unlink(missing_ok=True)

    text_to_write = prompt_text
    if output_contract:
        text_to_write = prompt_text + _build_output_contract_footer(brief_path)

    brief_path.write_text(text_to_write, encoding="utf-8")
    return brief_path


def output_path_for(brief_path: Path) -> Path:
    """Return the ``.out.md`` path a brief's agent-mode output is written to.

    This is the single home of the ``.md`` -> ``.out.md`` rule: every
    briefs/<role>-<scope>-r<round>.md file has a corresponding
    briefs/<role>-<scope>-r<round>.out.md that an agent-mode dispatch writes
    its full report to. Callers that need the output path (the dispatcher
    itself, or a caller unlinking a stale prior output) compute it from the
    brief path through this function rather than re-deriving the suffix swap
    inline, so the rule has exactly one definition.

    Args:
        brief_path: Path to a brief file, ending in ".md". May be relative
            or absolute; absoluteness is preserved in the result.

    Returns:
        The same path with the trailing ".md" replaced by ".out.md".
    """
    return Path(brief_path).with_suffix(".out.md")


def _build_output_contract_footer(brief_path: Path) -> str:
    """Return the output-contract footer appended when ``output_contract=True``.

    States the absolute ``.out.md`` path (as literal text, never an
    ``<UPPERCASE>`` token) that the agent must write its full report to, and
    disambiguates the interaction with the review templates' existing
    ``MILL_REVIEW_BEGIN`` / ``MILL_REVIEW_END`` wrapping instruction: that
    wrapped report is the *content of the file*, not something to also repeat
    in chat. The chat reply is a one-line ack and nothing else, so the
    orchestrator never has to read (or pay context for) the full report.

    Args:
        brief_path: Path to the brief this footer is appended to.

    Returns:
        Markdown footer text, including its own leading blank-line
        separator from the preceding prompt body.
    """
    out_path = output_path_for(brief_path)
    return (
        "\n\n---\n\n"
        "## Output contract\n\n"
        f"Write your full report to this file: {out_path}\n\n"
        "Any format the prompt above asks for (including a "
        "`MILL_REVIEW_BEGIN` / `MILL_REVIEW_END` wrapped report) is the "
        f"content of {out_path} -- write it there, not into chat.\n\n"
        "Your final chat message must be exactly one line and nothing "
        f"else: `WROTE {out_path}`\n"
    )


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
