"""
Notification API — one function, pluggable backend.

v1 mill had a ``notify`` entrypoint that never quite landed. v2 flips
the architecture: we own a tiny API surface, and the backend is swapped
out by config. Skills (mill-go, mill-plan, mill-abandon, …) call
:func:`notify` with a structured event; the backend decides whether
that turns into a stdout line, a toast, a Slack post, or an email.

The API mirrors the review subsystem's discipline: the caller does NOT
know which backend is loaded. Adding a new backend is a matter of
dropping ``_notify_<backend>.py`` next to this file and flipping the
config key — no skill code changes.

Config:
    notify:
      backend: stdout          # (default) — _notify_stdout.py
      # backend: toast / slack / email / etc. in future specs.

Backend contract (every ``_notify_<name>.py`` module):
    BACKEND = "<name>"         # module constant
    def send(event: str, detail: str, context: dict) -> None: ...

Public API:
    NotifyError       — raised on backend misconfiguration / load failure
    notify(event, detail, **context) -> None
        Dispatch one notification. Never raises on backend delivery
        failure (a broken toast notifier must not bring mill-go down);
        delivery errors are logged to stderr and swallowed. Config /
        load errors DO raise NotifyError — they are programming errors
        that need fixing, not runtime hiccups.
"""
from __future__ import annotations

import importlib
import sys
from functools import lru_cache
from pathlib import Path

import yaml


class NotifyError(Exception):
    """Raised on config / backend-module load failure. Not on delivery."""


_DEFAULT_BACKEND = "stdout"


def _load_backend_name() -> str:
    """Read ``notify.backend`` from wiki/config.yaml (with local overlay).

    We resolve this lazily on first call and cache the result. Mill
    workflows are long-lived single-process sessions; reading config
    once per process is correct and avoids importing ``_review_common``
    (which pulls in most of the review subsystem).

    Resolution order:
    - ``<CWD>/.millhouse/wiki/config.yaml`` (shared) +
      ``<CWD>/.millhouse/config.local.yaml`` (overlay)
    - Any failure falls back to the default ``stdout`` backend with a
      stderr warning — notifications are a nice-to-have, not a hard
      dependency.
    """
    cwd = Path.cwd()
    shared = cwd / ".millhouse" / "wiki" / "config.yaml"
    local = cwd / ".millhouse" / "config.local.yaml"

    def _load_or_empty(path: Path) -> dict:
        try:
            text = path.read_text(encoding="utf-8")
        except FileNotFoundError:
            return {}
        try:
            data = yaml.safe_load(text) or {}
        except yaml.YAMLError:
            return {}
        return data if isinstance(data, dict) else {}

    merged: dict = {}
    for path in (shared, local):
        section = _load_or_empty(path).get("notify", {})
        if isinstance(section, dict):
            merged.update(section)
    backend = merged.get("backend", _DEFAULT_BACKEND)
    if not isinstance(backend, str) or not backend:
        print(
            f"[_notify] warning: notify.backend is not a string; falling back to {_DEFAULT_BACKEND!r}",
            file=sys.stderr,
        )
        return _DEFAULT_BACKEND
    return backend


@lru_cache(maxsize=1)
def _load_backend():
    """Import and return the configured backend module.

    Raises NotifyError if the module is missing or does not expose
    ``BACKEND`` + ``send``.
    """
    name = _load_backend_name()
    module_name = f"_notify_{name}"
    try:
        module = importlib.import_module(module_name)
    except ModuleNotFoundError as exc:
        raise NotifyError(
            f"Notify backend {name!r} requested but {module_name}.py not found"
        ) from exc
    if getattr(module, "BACKEND", None) != name:
        raise NotifyError(
            f"Notify backend module {module_name} lacks BACKEND = {name!r}"
        )
    if not callable(getattr(module, "send", None)):
        raise NotifyError(
            f"Notify backend {module_name} lacks a callable send(event, detail, context)"
        )
    return module


def notify(event: str, detail: str, **context) -> None:
    """Dispatch one notification via the configured backend.

    Args:
        event: short dotted identifier (e.g. ``"mill-go.blocked"``,
            ``"mill-plan.approved"``) — backends may filter on this.
        detail: one-line human-readable message. Keep it short — detail
            strings may appear in OS toast popups or chat messages.
        **context: arbitrary serialisable metadata (slug, batch name,
            round number, etc.). Backends render this as JSON or a
            key=value trail; callers should not embed it into
            ``detail`` themselves.

    Delivery failures are logged to stderr and swallowed. A broken
    toast daemon must never crash the orchestrator.
    """
    try:
        backend = _load_backend()
    except NotifyError as exc:
        print(f"[_notify] backend load failed, dropping notification: {exc}", file=sys.stderr)
        return
    try:
        backend.send(event, detail, dict(context))
    except Exception as exc:  # noqa: BLE001 — any delivery failure is swallowed
        print(
            f"[_notify] delivery via {backend.BACKEND} failed for event={event!r}: {exc}",
            file=sys.stderr,
        )


def _reset_cache_for_tests() -> None:
    """Clear the backend cache so tests can reconfigure notify on the fly."""
    _load_backend.cache_clear()
