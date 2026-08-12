"""
Single-reviewer dispatcher.

Takes a fully-flattened reviewer spec (as returned by _reviewers.resolve) and dispatches to the
appropriate _llm_<provider> module.
The spec carries all dispatch information — provider, model, effort, tooluse — so no per-call
overrides are needed or accepted.

Spec contract:
    { "type": "single", "provider": "<name>", # e.g. "claude";
        drives importlib.import_module("_llm_<provider>") "model": "<model-id>", "effort":
            "<effort>", # optional; passed verbatim to the LLM provider "tooluse": bool, # false →
            run_bulk;
        true → run_tool_use
    }

Cluster specs are detected and raise ReviewerError immediately — cluster dispatch is deferred to
task 13.

`run()` still returns today's `(text, session_id)` 2-tuple even though every provider it dispatches
into now returns a `ReviewerCallResult`.
The two-line unwrap at each dispatch site is a deliberately temporary adapter, removed in the
dispatcher-flip batch once the three review backends are updated to consume `ReviewerCallResult`
directly.
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
        ReviewerError: when spec.type == "cluster", provider is unknown, or the provider module
        cannot be imported.
    """
    if spec["type"] == "cluster":
        from _reviewers import ReviewerError
        raise ReviewerError("cluster dispatch not yet implemented; see task 13")

    provider = spec.get("provider")

    if provider == "test_stub":
        import _reviewer_test_stub as stub
        # Temporary unwrap: removed once _reviewer_single.run itself returns ReviewerCallResult in
        # the dispatcher-flip batch.
        result = stub.run(
            prompt_text,
            session_id=session_id,
            resume=resume,
            timeout=timeout,
            effort=spec.get("effort"),
        )
        return result.text, result.session_id

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

    # Temporary unwrap: removed once _reviewer_single.run itself returns ReviewerCallResult in the
    # dispatcher-flip batch.
    result = fn(prompt_text, **kwargs)
    return result.text, result.session_id
