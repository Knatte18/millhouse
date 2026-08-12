"""Shared LLM-provider exception hierarchy and the shared reviewer-call return dataclass.

Defined here (not inside any specific `_llm_<provider>` module) so callers can catch errors from any
provider with a single `except LLMError` clause.
Each provider module re-exports these classes via `from _llm_common import LLMError,
LLMSessionError, LLMRateLimitError`.
"""
from __future__ import annotations

from dataclasses import dataclass


@dataclass
class ReviewerCallResult:
    """
    Return shape for every reviewer-facing provider call (`run_bulk`, `run_tool_use`, and the
    in-process test stub's `run`).

    `tool_calls` and `cost_usd` are `None` wherever a provider or dispatch mode cannot supply them:
    gemini always, the claude psmux branch always, and the claude subprocess branch when the
    installed CLI's `"result"` event omits the corresponding field.
    `duration_s` is wall-clock seconds for the whole call, including any internal retry.
    """

    text: str
    session_id: str
    duration_s: float | None = None
    tool_calls: int | None = None
    cost_usd: float | None = None


class LLMError(Exception):
    """Raised on timeout, auth failure, or non-zero exit from an LLM-provider CLI.

    Callers use str(exc) to get a human-readable error message.
    Backends catch LLMError at the per-sub-review boundary and record {verdict: "ERROR", file: null,
    error: "<msg>"} in the ReviewResult.
    """

    def __init__(self, message: str, *, duration_s: float | None = None) -> None:
        super().__init__(message)
        self.duration_s = duration_s


class LLMSessionError(LLMError):
    """Raised when an LLM-provider's `--resume <id>` call fails because the session is gone.

    Callers (mill-go's builder) catch this specifically to fall back to a fresh session instead of
    aborting the batch.
    """


class LLMRateLimitError(LLMError):
    """Raised when an LLM-provider CLI exits non-zero AND its output indicates a rate-limit/throttle
    event.

    Backends record verdict: ERROR with error: 'rate_limit: ...'
    and the orchestrator's ERROR-only retry handles it.
    Inherits from LLMError so existing catch sites continue to handle it as a generic provider
    failure unless they specifically want the typed split.
    """
