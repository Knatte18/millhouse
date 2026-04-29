"""Bulk-mode reviewer using Claude Sonnet at max effort."""
from _llm_claude import run_bulk

MODE = "bulk"


def run(
    prompt_text: str,
    *,
    session_id: str | None = None,
    resume: bool = False,
) -> tuple[str, str]:
    """Bulk-mode reviewer; forwards session_id/resume to the LLM provider and returns (text, session_id)."""
    return run_bulk(
        prompt_text,
        model="claude-sonnet-4-6",
        effort="max",
        session_id=session_id,
        resume=resume,
    )
