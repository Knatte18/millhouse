"""
Single template-substitution helper used by every mill artefact format.

Per the v2 format-discipline rules (see ``specs/00-overview.md``), every
artefact type — plan, status, review prompt, implementer brief, slug —
lives as a ``.md`` template in ``plugins/mill/templates/`` with
``<PLACEHOLDER>`` tokens. There is deliberately one substitution function
for every format; no format-specific rendering code is allowed anywhere
else in the codebase.

Token grammar is intentionally narrow: uppercase identifiers inside
angle brackets, e.g. ``<SLUG>``, ``<COMMIT_MSG>``, ``<PLAN_BODY>``. The
first character must be an uppercase letter so prose like "<a>" or HTML
tags in templates are not accidentally matched. Lowercase-starting or
mixed-case tokens are left untouched.

Unresolved placeholders are a hard error: rendering raises ``KeyError``
listing the missing token names. This catches typos in callers and
prevents half-rendered documents from reaching the wiki.

Public API:
    render(template_path, values)
        Read the template, substitute every ``<TOKEN>`` from ``values``,
        return the rendered string. Raises ``KeyError`` on any
        unresolved token.
"""
from __future__ import annotations

import re
import sys
from pathlib import Path

# Match uppercase-identifier tokens wrapped in angle brackets. The
# leading-uppercase constraint avoids eating angle-brackets from prose or
# HTML that happens to appear inside a template body.
_TOKEN_RE = re.compile(r"<([A-Z][A-Z0-9_]*)>")


def render(template_path: Path, values: dict[str, str]) -> str:
    """
    Render a template by substituting ``<TOKEN>`` placeholders from ``values``.

    The template file is read as UTF-8. Each ``<TOKEN>`` match is looked
    up in ``values``; on a miss, the token name is recorded and the
    original ``<TOKEN>`` text is left in place so the error message can
    report every missing token in one pass (rather than failing on the
    first and forcing the caller to iterate).

    Args:
        template_path: Path to the ``.md`` template file.
        values: Mapping of token name → replacement string. Token names
            are the bare identifier without angle brackets (e.g. ``SLUG``
            not ``<SLUG>``).

    Returns:
        The rendered string, with every ``<TOKEN>`` replaced.

    Raises:
        KeyError: The template referenced one or more tokens not present
            in ``values``. The message lists all missing tokens sorted
            alphabetically.
    """
    # Read the template as UTF-8. Templates ship as part of the plugin
    # so encoding is controlled; we don't accept cp1252 fallbacks.
    text = template_path.read_text(encoding="utf-8")

    # Accumulate every missing token name so the error message can report
    # all of them at once. The regex callback cannot raise directly
    # without halting substitution mid-string.
    missing: list[str] = []

    def replace(match: re.Match[str]) -> str:
        name = match.group(1)
        if name not in values:
            missing.append(name)
            # Preserve the original ``<TOKEN>`` in the output so a
            # human reading a failed render can see where each hole was.
            return match.group(0)
        return values[name]

    rendered = _TOKEN_RE.sub(replace, text)
    if missing:
        raise KeyError(f"Unresolved template tokens: {sorted(set(missing))}")
    return rendered
