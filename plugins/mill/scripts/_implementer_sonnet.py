"""Implementer module using Claude Sonnet (default effort).

Used by mill-go as the per-batch worker. Unlike reviewer modules, run()
returns (text, session_id) so the builder can persist the id for resume.
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
) -> tuple[str, str]:
    return run_implementer(
        prompt_text,
        model="claude-sonnet-4-6",
        session_id=session_id,
        resume=resume,
        cwd=cwd,
    )


if __name__ == "__main__":
    assert MODE == "implementer", f"Expected MODE='implementer', got {MODE!r}"
    assert callable(run), "run must be callable"
    import inspect
    sig = inspect.signature(run)
    assert "session_id" in sig.parameters
    assert "resume" in sig.parameters
    assert "cwd" in sig.parameters
    print("PASS: MODE == 'implementer'")
    print("PASS: run is callable with session_id/resume/cwd")
    print("All smoke tests passed.")
