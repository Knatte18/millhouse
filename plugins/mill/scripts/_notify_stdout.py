"""
Default notify backend — print one structured line to stderr.

This is the baseline every mill-v2 install ships with. It prints a
single line per event so the terminal output stays skimmable while a
long-running mill-go session churns through batches. Richer backends
(toast, Slack, email) replace this module via the ``notify.backend:``
config key.

Format (single line, UTF-8 on stderr):

    [notify] <event>  <detail>  (key1=val1 key2=val2)

The key=val trail is elided when ``context`` is empty. Backends are
free to choose any rendering; downstream parsers should not rely on
stdout-backend output.
"""
from __future__ import annotations

import sys

BACKEND = "stdout"


def _render_context(context: dict) -> str:
    """Render the context dict as a ``(k1=v1 k2=v2)`` suffix string."""
    if not context:
        return ""
    parts = []
    for key in sorted(context):
        value = context[key]
        # Collapse whitespace in values so the line stays single-line;
        # complex structures get repr()'d for diagnostic visibility.
        if isinstance(value, (str, int, float, bool)) or value is None:
            rendered = str(value).replace("\n", " ").replace("\r", "")
        else:
            rendered = repr(value)
        parts.append(f"{key}={rendered}")
    return "  (" + " ".join(parts) + ")"


def send(event: str, detail: str, context: dict) -> None:
    """Write ``[notify] <event>  <detail>  (ctx)`` to stderr."""
    suffix = _render_context(context)
    print(f"[notify] {event}  {detail}{suffix}", file=sys.stderr)


if __name__ == "__main__":
    send("mill-go.test", "smoke check", {"slug": "demo", "round": 2})
    send("mill-go.test", "no ctx", {})
    print("PASS: stdout backend printed two lines above")
