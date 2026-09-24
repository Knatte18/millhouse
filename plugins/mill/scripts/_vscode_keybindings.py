"""
VS Code user-level keybindings merge helper.

The six session tasks rendered by `_vscode_tasks` get one `alt+shift+N` shortcut each.
Shortcuts live in the user-level `keybindings.json` (a JSONC file), because VS Code has no
workspace-level keybindings.
mill owns only a marker-delimited block inside that file;
everything outside the block is preserved byte-for-byte.
Existing user bindings on the same keys always win: the conflicting mill binding is skipped
and reported as a warning.

Public API:
    BLOCK_BEGIN, BLOCK_END, KeybindingsParseError
    Marker comments delimiting the mill block, and the error raised for unusable files.
    desired_bindings()
    Return the six binding dicts derived from ``_vscode_tasks.TASK_SPECS``.
    keybindings_path(platform=None, *, env=None, home=None)
    Return the stable-``Code`` user keybindings.json path for a platform.
    strip_jsonc(text)
    Return JSONC text reduced to plain JSON.
    merge_bindings(text)
    Return ``(new_text, warnings)`` with the mill block inserted, replaced or removed.
    write_bindings(path=None, *, platform=None)
    Merge into the file on disk, returning ``(status, warnings)``. Never prints.
"""
from __future__ import annotations

import json
import os
import sys
from collections.abc import Iterator
from pathlib import Path

import _vscode_tasks

BLOCK_BEGIN = "// mill:begin"
BLOCK_END = "// mill:end"

_CODE = "code"
_STRING = "string"
_COMMENT = "comment"

_BLOCK_MARKER_INDENT = "  "
_BLOCK_ENTRY_INDENT = "    "


class KeybindingsParseError(ValueError):
    """The keybindings file is not a JSONC array mill can merge into."""


def desired_bindings() -> list[dict]:
    """Return one runTask binding per ``TASK_SPECS`` entry, keyed ``alt+shift+1`` upward."""
    return [
        {
            "key": f"alt+shift+{number}",
            "command": "workbench.action.tasks.runTask",
            "args": f"{_vscode_tasks.LABEL_PREFIX}{task_key}",
        }
        for number, (task_key, _phase, _flag) in enumerate(_vscode_tasks.TASK_SPECS, start=1)
    ]


def keybindings_path(
    platform: str | None = None,
    *,
    env: dict | None = None,
    home: Path | None = None,
) -> Path:
    """
    Return the stable-``Code`` user keybindings.json path for ``platform``.

    Raises:
        ValueError: The platform is unsupported, or ``APPDATA`` is unset on ``win32``.
    """
    platform = sys.platform if platform is None else platform
    if platform.startswith("linux"):
        return (Path.home() if home is None else home) / ".config" / "Code" / "User" / "keybindings.json"
    if platform == "win32":
        appdata = (os.environ if env is None else env).get("APPDATA")
        if not appdata:
            raise ValueError("APPDATA is not set; cannot locate the VS Code user directory")
        return Path(appdata) / "Code" / "User" / "keybindings.json"
    if platform == "darwin":
        base = Path.home() if home is None else home
        return base / "Library" / "Application Support" / "Code" / "User" / "keybindings.json"
    raise ValueError(f"unsupported platform for VS Code keybindings: {platform!r}")


def _scan(text: str) -> Iterator[tuple[int, str, str]]:
    """Yield ``(index, char, kind)`` for every character, kind being code, string or comment."""
    length = len(text)
    index = 0
    while index < length:
        if text[index] == '"':
            end = index + 1
            while end < length and text[end] != '"':
                end += 2 if text[end] == "\\" else 1
            end = min(end + 1, length)
            kind = _STRING
        elif text.startswith("//", index):
            end = text.find("\n", index)
            end = length if end == -1 else end
            kind = _COMMENT
        elif text.startswith("/*", index):
            end = text.find("*/", index + 2)
            end = length if end == -1 else end + 2
            kind = _COMMENT
        else:
            end = index + 1
            kind = _CODE
        for position in range(index, end):
            yield position, text[position], kind
        index = end


def strip_jsonc(text: str) -> str:
    """Remove comments outside strings and trailing commas before ``]`` or ``}``."""
    kept = [(char, kind) for _i, char, kind in _scan(text) if kind != _COMMENT]
    output: list[str] = []
    for position, (char, kind) in enumerate(kept):
        if kind == _CODE and char == ",":
            lookahead = position + 1
            while lookahead < len(kept) and kept[lookahead][1] == _CODE and kept[lookahead][0].isspace():
                lookahead += 1
            if lookahead < len(kept) and kept[lookahead][1] == _CODE and kept[lookahead][0] in "]}":
                continue
        output.append(char)
    return "".join(output)


def _find_top_level_array_end(text: str) -> tuple[int, int]:
    """
    Locate the top-level array's closing ``]``.

    Returns:
        ``(close_index, last_token_index)`` where ``last_token_index`` is the last non-whitespace
        code character before the ``]`` (the opening ``[`` for an empty array).
    """
    depth = 0
    last_token = -1
    for index, char, kind in _scan(text):
        if kind != _CODE or char.isspace():
            continue
        if char in "[{":
            depth += 1
        elif char in "]}":
            depth -= 1
            if depth == 0:
                return index, last_token
        last_token = index
    raise KeybindingsParseError("could not find the closing bracket of the top-level array")


def _find_comment_marker(text: str, marker: str, start: int = 0) -> int:
    """Return the index of the first ``marker`` at or after ``start`` inside a comment, or -1."""
    span_start = -1
    span_chars: list[str] = []
    for index, char, kind in _scan(text):
        if kind == _COMMENT:
            if span_start == -1:
                span_start = index
            span_chars.append(char)
            if index != len(text) - 1:
                continue
        if span_start != -1:
            found = "".join(span_chars).find(marker, max(0, start - span_start))
            if found != -1:
                return span_start + found
            span_start = -1
            span_chars = []
    return -1


def _find_block(text: str) -> tuple[int, int] | None:
    """Return the ``(start, end)`` span of the mill block: begin-line start to end-line end."""
    begin = _find_comment_marker(text, BLOCK_BEGIN)
    if begin == -1:
        return None
    end_marker = _find_comment_marker(text, BLOCK_END, begin)
    if end_marker == -1:
        raise KeybindingsParseError(f"found {BLOCK_BEGIN} without a matching {BLOCK_END}")
    start = text.rfind("\n", 0, begin) + 1
    end = text.find("\n", end_marker)
    return start, len(text) if end == -1 else end


def _normalise_key(key: str) -> str:
    return "".join(key.split()).lower()


def _render_block(bindings: list[dict], trailing_comma: bool) -> str:
    lines = [_BLOCK_MARKER_INDENT + BLOCK_BEGIN]
    for position, binding in enumerate(bindings):
        is_last = position == len(bindings) - 1
        comma = "," if (not is_last or trailing_comma) else ""
        lines.append(_BLOCK_ENTRY_INDENT + json.dumps(binding) + comma)
    lines.append(_BLOCK_MARKER_INDENT + BLOCK_END)
    return "\n".join(lines)


def _entries_follow(text: str) -> bool:
    """Return True when a code token other than the closing ``]`` follows in ``text``."""
    for _index, char, kind in _scan(text):
        if kind == _CODE and not char.isspace():
            return char != "]"
    return False


def _parse_entries_outside_block(remainder: str) -> list:
    try:
        parsed = json.loads(strip_jsonc(remainder))
    except json.JSONDecodeError as error:
        raise KeybindingsParseError(f"keybindings.json does not parse: {error}") from error
    if not isinstance(parsed, list):
        raise KeybindingsParseError("keybindings.json top-level value is not an array")
    return parsed


def merge_bindings(text: str) -> tuple[str, list[str]]:
    """
    Merge the mill binding block into keybindings JSONC ``text``.

    A desired binding whose key matches (case- and whitespace-insensitively) an entry outside the
    block is skipped with a warning.
    An existing block is replaced in place, or removed when no bindings remain;
    otherwise a new block is inserted before the closing ``]``.
    All text outside the block is preserved byte-for-byte.

    Returns:
        ``(new_text, warnings)``.

    Raises:
        KeybindingsParseError: ``text`` does not parse or its top-level value is not an array.
    """
    if not text.strip():
        return "[\n" + _render_block(_free_bindings([], []), False) + "\n]\n", []

    block_span = _find_block(text)
    remainder = text if block_span is None else text[: block_span[0]] + text[block_span[1] :]
    entries = _parse_entries_outside_block(remainder)

    warnings: list[str] = []
    bindings = _free_bindings(entries, warnings)

    if block_span is not None:
        start, end = block_span
        if not bindings:
            after = end + 1 if text[end : end + 1] == "\n" else end
            return text[:start] + text[after:], warnings
        block = _render_block(bindings, _entries_follow(text[end:]))
        return text[:start] + block + text[end:], warnings

    if not bindings:
        return text, warnings
    close, last_token = _find_top_level_array_end(text)
    block = _render_block(bindings, False)
    comma_at = last_token + 1 if text[last_token] not in "[," else None
    line_start = text.rfind("\n", 0, close) + 1
    if text[line_start:close].strip() == "":
        insertion_point, insertion = line_start, block + "\n"
    else:
        insertion_point, insertion = close, "\n" + block + "\n"
    merged = text[:insertion_point] + insertion + text[insertion_point:]
    # The comma goes right after the previously last entry, which always precedes the insertion.
    if comma_at is not None:
        merged = merged[:comma_at] + "," + merged[comma_at:]
    return merged, warnings


def _free_bindings(entries: list, warnings: list[str]) -> list[dict]:
    """Return the desired bindings not shadowed by ``entries``, appending one warning per clash."""
    taken: dict[str, object] = {}
    for entry in entries:
        if isinstance(entry, dict) and isinstance(entry.get("key"), str):
            taken.setdefault(_normalise_key(entry["key"]), entry.get("command"))
    free: list[dict] = []
    for binding in desired_bindings():
        normalised = _normalise_key(binding["key"])
        if normalised in taken:
            warnings.append(
                f'{binding["key"]} is already bound to {taken[normalised]}; '
                f'skipped mill binding "{binding["args"]}"'
            )
        else:
            free.append(binding)
    return free


def write_bindings(path: Path | None = None, *, platform: str | None = None) -> tuple[str, list[str]]:
    """
    Merge the mill binding block into the user's keybindings.json on disk.

    The VS Code user directory is never created: when it is missing, nothing is written.
    A file that cannot be read or parsed is left untouched.

    Returns:
        ``(status, warnings)`` with status ``"created"``, ``"updated"``, ``"unchanged"`` or
        ``"skipped"``.
    """
    target = keybindings_path(platform) if path is None else path
    if not target.parent.is_dir():
        return "skipped", [f"VS Code user directory {target.parent} not found; skipped mill keybindings"]
    existed = target.exists()
    try:
        original = ""
        if existed:
            with open(target, encoding="utf-8", newline="") as handle:
                original = handle.read()
        merged, warnings = merge_bindings(original)
    except (KeybindingsParseError, OSError, UnicodeDecodeError) as error:
        return "skipped", [f"could not merge into {target} ({error}); skipped all six mill keybindings"]
    if existed and merged == original:
        return "unchanged", warnings
    with open(target, "w", encoding="utf-8", newline="") as handle:
        handle.write(merged)
    return ("updated" if existed else "created"), warnings
