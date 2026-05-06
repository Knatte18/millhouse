"""Implementer module using Claude Sonnet (default effort).

Used by mill-go as the per-batch worker. Unlike reviewer modules, run()
returns (text, session_id) so the builder can persist the id for resume.

Public API:
    run(prompt_text, *, session_id, resume, cwd, timeout=1800)
        Invoke claude as the per-batch implementer. Returns (text, session_id).
"""
from __future__ import annotations

from pathlib import Path

from _llm_claude import run_implementer

MODE = "implementer"


def run(
    prompt_text: str,
    *,
    session_id: str | None = None,
    resume: bool = False,
    cwd: Path | str | None = None,
    timeout: int = 1800,
) -> tuple[str, str]:
    return run_implementer(
        prompt_text,
        model="claude-sonnet-4-6",
        session_id=session_id,
        resume=resume,
        cwd=cwd,
        timeout=timeout,
    )
