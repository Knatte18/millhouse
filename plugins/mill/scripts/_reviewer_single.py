"""
Single-reviewer dispatcher.

Takes a fully-flattened reviewer spec (as returned by _reviewers.resolve) and
dispatches to the appropriate _llm_<provider> module. The spec carries all
dispatch information — provider, model, effort, tooluse — so no per-call
overrides are needed or accepted.

Spec contract:
    {
        "type": "single",
        "provider": "<name>",   # e.g. "claude"; drives importlib.import_module("_llm_<provider>")
        "model": "<model-id>",
        "effort": "<effort>",   # optional; passed verbatim to the LLM provider
        "tooluse": bool,        # false → run_bulk; true → run_tool_use
    }

Cluster specs are detected and raise ReviewerError immediately — cluster dispatch
is deferred to task 13.
"""
from __future__ import annotations

import importlib


def run(
    spec: dict,
    prompt_text: str,
    *,
    session_id: str | None = None,
    resume: bool = False,
    timeout: int | None = None,
) -> tuple[str, str]:
    """Dispatch a single-reviewer call via spec.

    Reads spec["provider"] and spec["tooluse"] to select the LLM function.
    Forwards session_id, resume, and (when not None) timeout to the provider.

    Raises:
        ReviewerError: when spec.type == "cluster", provider is unknown, or
            the provider module cannot be imported.
    """
    if spec["type"] == "cluster":
        from _reviewers import ReviewerError
        raise ReviewerError("cluster dispatch not yet implemented; see task 13")

    provider = spec.get("provider")

    if provider == "test_stub":
        import _reviewer_test_stub as stub
        return stub.run(prompt_text, session_id=session_id, resume=resume, timeout=timeout)

    try:
        llm = importlib.import_module(f"_llm_{provider}")
    except ImportError:
        from _reviewers import ReviewerError
        raise ReviewerError(f"Unknown provider: {provider!r}")

    fn = llm.run_tool_use if spec.get("tooluse") else llm.run_bulk

    kwargs: dict = {
        "model": spec["model"],
        "effort": spec.get("effort"),
        "session_id": session_id,
        "resume": resume,
    }
    if timeout is not None:
        kwargs["timeout"] = timeout

    return fn(prompt_text, **kwargs)
