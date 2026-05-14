"""
Single template-substitution helper used by every mill artefact format.

Per the v2 format-discipline rules, every artefact type lives as a `.md`
template in `plugins/mill/templates/` with `<PLACEHOLDER>` tokens.

Public API:
    render(template_path, values)
    render_cached(template_path, values)
"""
from __future__ import annotations

import functools
import re
from pathlib import Path

_TOKEN_RE = re.compile(r"<([A-Z][A-Z0-9_]*)>")


def _strip_leading_comment(text: str) -> str:
    stripped = text.lstrip()
    if not stripped.startswith("<!--"):
        return text
    close = stripped.find("-->")
    if close == -1:
        return text
    after = stripped[close + len("-->"):].lstrip("\r\n")
    return after


@functools.lru_cache(maxsize=None)
def _read_template(path: Path) -> str:
    return _strip_leading_comment(path.read_text(encoding="utf-8"))


def render(template_path: Path, values: dict[str, str]) -> str:
    text = _strip_leading_comment(template_path.read_text(encoding="utf-8"))
    missing: list[str] = []

    def replace(match: re.Match[str]) -> str:
        name = match.group(1)
        if name not in values:
            missing.append(name)
            return match.group(0)
        return values[name]

    rendered = _TOKEN_RE.sub(replace, text)
    if missing:
        raise KeyError(f"Unresolved template tokens: {sorted(set(missing))}")
    return rendered


def render_cached(template_path: Path, values: dict[str, str]) -> str:
    """Cached variant of render() -- file read is memoised via lru_cache."""
    text = _read_template(template_path)
    result = text
    for name, val in values.items():
        result = result.replace(f"<{name}>", val)
    return result
