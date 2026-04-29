"""Tool-use reviewer using Claude Sonnet at max effort."""
from _llm_claude import run_tool_use

MODE = "tool-use"


def run(
    prompt_text: str,
    *,
    session_id: str | None = None,
    resume: bool = False,
) -> tuple[str, str]:
    """Tool-use reviewer; forwards session_id/resume to the LLM provider and returns (text, session_id)."""
    return run_tool_use(
        prompt_text,
        model="claude-sonnet-4-6",
        effort="max",
        session_id=session_id,
        resume=resume,
    )
