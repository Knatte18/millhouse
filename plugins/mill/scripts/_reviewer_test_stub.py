"""In-process stub reviewer used by unit-test flow harnesses.

The stub does not call any LLM. Tests seed a module-level queue with
`(text, session_id)` tuples via `seed(...)`; each call to `run(...)`
pops the next tuple and returns it. The optional `prompt_observer`
callback receives every prompt the backend sends, letting tests
assert on prompt shape (manifest presence, re-attached section,
etc).

Public API:
    seed()              — load response queue and clear captured-prompts log
    set_prompt_observer() — attach callback fired per run call
    captured_prompts()  — return all (prompt_text, kwargs) tuples captured
    run()               — pop next seeded response; capture kwargs including timeout

Tests that need to simulate LLMError monkey-patch `run`; the stub itself only
handles the seeded-queue path.
"""
from __future__ import annotations

import threading
from collections import deque
from typing import Callable

MODE = "bulk"

# Module-level state — shared across threads so ThreadPoolExecutor
# workers spawned by `_review_plan.run` see the same seeded queue
# as the test thread. `deque.popleft()` is atomic under the GIL, so
# the hot path needs no lock; mutations from `seed()` and
# `captured_prompts()` are guarded by `_lock` to avoid races during
# test setup/teardown.
_queue: deque[tuple[str, str]] = deque()
_prompts: list[tuple[str, dict]] = []
_observer: Callable[[str, dict], None] | None = None
_lock = threading.Lock()


def seed(responses: list[tuple[str, str]]) -> None:
    """Seed the response queue. Call before invoking the backend.

    Each response is `(verdict_text, session_id)`. The stub returns
    them in order. Subsequent `run` calls past the queue length raise
    RuntimeError so a test mistake (under-seeded queue) is loud.
    Also clears the captured-prompts log so each test starts fresh.
    """
    with _lock:
        _queue.clear()
        _queue.extend(responses)
        _prompts.clear()


def set_prompt_observer(cb: Callable[[str, dict], None] | None) -> None:
    """Attach a callback fired with `(prompt_text, kwargs)` per run call."""
    global _observer
    with _lock:
        _observer = cb


def captured_prompts() -> list[tuple[str, dict]]:
    """Return all `(prompt_text, kwargs)` tuples captured this run."""
    with _lock:
        return list(_prompts)


def run(
    prompt_text: str,
    *,
    session_id: str | None = None,
    resume: bool = False,
    timeout: int | None = None,
    effort: str | None = None,
) -> tuple[str, str]:
    kwargs = {"session_id": session_id, "resume": resume, "timeout": timeout, "effort": effort}
    with _lock:
        _prompts.append((prompt_text, kwargs))
        observer = _observer
    if observer is not None:
        observer(prompt_text, kwargs)
    try:
        return _queue.popleft()  # GIL-atomic
    except IndexError:
        raise RuntimeError(
            "_reviewer_test_stub queue empty — test did not seed enough responses"
        )
