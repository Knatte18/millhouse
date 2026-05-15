"""Model-agnostic Claude implementer.

Used by mill-go as the per-batch worker. Unlike reviewer modules, run()
returns (text, session_id) so the builder can persist the id for resume.

Public API:
    run(prompt_text, *, model, effort, session_id, resume, cwd, timeout=1800)
        Invoke claude as the per-batch implementer. model and effort are
        caller-supplied. Returns (text, session_id).
"""
from __future__ import annotations

from pathlib import Path

from _llm_claude import run_implementer

MODE = "implementer"


def run(
    prompt_text: str,
    *,
    model: str,
    effort: str | None,
    session_id: str | None = None,
    resume: bool = False,
    cwd: Path | str | None = None,
    timeout: int = 1800,
) -> tuple[str, str]:
    return run_implementer(
        prompt_text,
        model=model,
        effort=effort,
        session_id=session_id,
        resume=resume,
        cwd=cwd,
        timeout=timeout,
    )
