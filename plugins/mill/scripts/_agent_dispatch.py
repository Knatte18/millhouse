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
    Write a brief file to briefs_dir/<role>-<scope>-r<round_n>.md,
    create parent directories, and return the path.

SUBAGENT_REVIEWER, SUBAGENT_IMPLEMENTER
    String constants for subagent type names.
"""
from __future__ import annotations

from pathlib import Path

__all__ = [
    "resolve_dispatch_mode",
    "model_to_tier",
    "write_brief",
    "SUBAGENT_REVIEWER",
    "SUBAGENT_IMPLEMENTER",
]

SUBAGENT_REVIEWER = "mill-reviewer"
SUBAGENT_IMPLEMENTER = "mill-implementer"

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
        role: Role name (e.g., "mill-implementer").
        scope: Scope name (e.g., "code-review").
        round_n: Round number (integer).
        prompt_text: Full prompt text to write (UTF-8).

    Returns:
        Path to the written file.
    """
    briefs_dir = Path(briefs_dir)
    briefs_dir.mkdir(parents=True, exist_ok=True)
    brief_path = briefs_dir / f"{role}-{scope}-r{round_n}.md"
    brief_path.write_text(prompt_text, encoding="utf-8")
    return brief_path
