"""
Render + mutate ``status.md`` — the per-task state file.

mill-spawn writes the initial file via :func:`render_initial`; all
later skills (mill-start, mill-plan, mill-go) mutate fields with
:func:`update_field` or :func:`append_phase`, and mill-go owns the
``## Batches`` section via :func:`init_batches` / :func:`set_batch_field`
/ :func:`read_batches`.

Why ``## Batches`` is its own fenced-yaml block rather than a key inside
the top ``` ```yaml ``` ``` block: the top block contains
``task_description: |`` — a literal-block scalar whose indentation is
fragile. Re-serialising the whole top block via ``yaml.safe_dump`` to
mutate one list item would risk collapsing the block scalar into a
quoted string. Keeping ``batches:`` in its own section lets us parse
and rewrite just that block, never touching the top block.

Public API:
    render_initial(task_title, task_description, timestamp,
                   parent_branch, slug, branch) -> str
    read_full(status_path) -> dict
    read_parent_branch(status_path) -> str | None
    read_slug(status_path) -> str
    read_branch(status_path, *, cfg, slug) -> str
    update_field(status_path, key, value) -> None
    set_blocked(status_path, reason, *, timestamp) -> None
    append_phase(status_path, phase, timestamp) -> None
    init_batches(status_path, names) -> None
    set_batch_field(status_path, name, key, value) -> None
    set_batch_fields(status_path, name, fields) -> None
    read_batches(status_path) -> list[dict]
    read_status(status_path) -> dict
"""
from __future__ import annotations

import re
from pathlib import Path

import yaml

from _yaml_writer import quote_scalar

_TOKEN_RE = re.compile(r"<([A-Z][A-Z0-9_]*)>")
_YAML_FENCE = "```yaml"
_TIMELINE_FENCE = "```text"

_TEMPLATE_PATH = (
    Path(__file__).resolve().parent.parent
    / "templates"
    / "status-discussing.md"
)


def _strip_leading_comment(text: str) -> str:
    """Drop the leading ``<!-- ... -->`` template header if present.

    The template file has a human-facing HTML comment describing its
    tokens; that comment is useful for anyone browsing the repo but
    would be noise in an actual ``status.md``. We strip only a comment
    that starts at the very first character of the file — trailing
    comments or comments mid-file are preserved.
    """
    stripped = text.lstrip()
    if not stripped.startswith("<!--"):
        return text
    close = stripped.find("-->")
    if close == -1:
        return text
    after = stripped[close + len("-->"):].lstrip("\r\n")
    return after


def render_initial(
    task_title: str,
    task_description: str,
    timestamp: str,
    parent_branch: str,
    slug: str,
    branch: str,
) -> str:
    """
    Render the phase=discussing status.md for ``task_title``.

    Reads the template once per call (cheap; the file is tiny), strips
    the leading documentation comment, and substitutes placeholders via
    ``_render.render``. Callers typically write the returned string to
    ``<wiki>/active/<slug>/status.md``.

    Args:
        task_title: Human-readable task name; appears as the YAML
            ``task:`` value.
        task_description: One-or-more-paragraph description; injected
            under the YAML ``task_description: |`` key so multi-line
            values render as a literal block. Newlines in the input are
            preserved as-is; the template's ``  `` indent applies to the
            first line only, so multi-line values remain valid YAML only
            when the caller does not include leading spaces.
        timestamp: ISO-8601 UTC timestamp for the timeline entry,
            e.g. ``"2026-04-22T14:32:05Z"``.
        parent_branch: The branch the hub was on at spawn time. mill-merge
            / mill-cleanup read this to know where to merge back to.

    Returns:
        The rendered status.md text, including trailing newline.
    """
    template = _TEMPLATE_PATH.read_text(encoding="utf-8")
    body = _strip_leading_comment(template)
    tokens = {
        "TASK_TITLE": quote_scalar(task_title),
        # TASK_DESCRIPTION renders inside `task_description: |` (literal block);
        # block scalars handle colons natively and quoting would be parsed as data.
        "TASK_DESCRIPTION": task_description,
        "TIMESTAMP": quote_scalar(timestamp),
        "PARENT_BRANCH": quote_scalar(parent_branch),
        "SLUG": quote_scalar(slug),
        "BRANCH": quote_scalar(branch),
    }
    for key, value in tokens.items():
        body = body.replace(f"<{key}>", value)
    # Mirror _render.render's strictness: reject any unresolved token so a
    # template evolving under a caller's feet fails loudly instead of
    # emitting half-rendered status files.
    unresolved = sorted(set(_TOKEN_RE.findall(body)))
    if unresolved:
        raise KeyError(
            f"Unresolved tokens in status template: {unresolved!r}"
        )
    return body


def _split_fences(text: str, fence_open: str) -> tuple[int, int]:
    """
    Return ``(block_start, block_end)`` line indices for the first fenced
    block opened by ``fence_open``. Indices point at the content lines
    (between the open and close fences), i.e. ``text.splitlines()``
    slice ``[block_start:block_end]`` is the body.

    Raises ``ValueError`` if the block is missing or unterminated.
    """
    lines = text.splitlines()
    start: int | None = None
    for i, line in enumerate(lines):
        if line.strip() == fence_open:
            start = i + 1
            break
    if start is None:
        raise ValueError(f"No {fence_open} block in status file")
    for j in range(start, len(lines)):
        if lines[j].strip() == "```":
            return (start, j)
    raise ValueError(f"Unterminated {fence_open} block in status file")


def update_field(status_path: Path, key: str, value: str) -> None:
    """
    Rewrite ``<key>:`` in the top ``` ```yaml ``` ``` block of ``status_path``.

    Only single-line ``key: value`` rows are supported — multi-line
    ``task_description: |`` style blocks cannot be updated via this
    helper because the indent rules require awareness of the surrounding
    block-scalar shape. Callers that need multi-line updates should
    re-render the whole file.

    Args:
        status_path: Absolute path to the status.md file.
        key: YAML key to mutate (must already exist in the block).
        value: Written via ``_yaml_writer.quote_scalar`` so values
            containing YAML-special characters (``:``, ``#``, leading
            ``-``, etc.) are quoted automatically. Strict-key behaviour is
            preserved — ``key`` must already exist in the YAML block;
            absent keys raise ``ValueError``.

    Raises:
        ValueError: the file lacks a yaml block, the block is
            unterminated, or ``key`` is not present at a scalar row.
    """
    text = status_path.read_text(encoding="utf-8")
    lines = text.splitlines(keepends=True)
    start, end = _split_fences(text, _YAML_FENCE)
    key_pattern = re.compile(rf"^({re.escape(key)}:\s*).*$")
    for i in range(start, end):
        stripped = lines[i].rstrip("\r\n")
        match = key_pattern.match(stripped)
        if match is None:
            continue
        eol = lines[i][len(stripped):]
        lines[i] = f"{key}: {quote_scalar(value)}{eol}"
        status_path.write_text("".join(lines), encoding="utf-8")
        return
    raise ValueError(f"Key {key!r} not found in yaml block of {status_path}")


def set_blocked(status_path: Path, reason: str, *, timestamp: str) -> None:
    """
    Transition a task into the blocked state in ``status.md``.

    Three mutations happen atomically from the caller's viewpoint:

    1. ``phase:`` in the top yaml block is overwritten with ``blocked``
       (via ``_yaml_writer.quote_scalar`` for consistency with
       ``append_phase``).
    2. ``blocked_reason:`` in the top yaml block is written with ``reason``
       (via ``_yaml_writer.quote_scalar``). If the key already exists it is
       rewritten in place; if absent, a new row is inserted immediately after
       the ``phase:`` row.
    3. A ``blocked  '<quoted timestamp>'`` row is appended to the
       ``## Timeline`` code block.

    The function reads and writes the file exactly once.

    Args:
        status_path: Absolute path to the status.md file.
        reason: Human-readable explanation for the block; written through
            ``_yaml_writer.quote_scalar`` so colons and other YAML-special
            characters are handled automatically.
        timestamp: ISO-8601 UTC timestamp for the timeline row; written
            through ``_yaml_writer.quote_scalar`` to match
            ``render_initial``'s quoted form.

    Raises:
        ValueError: yaml block is missing / malformed, ``phase:`` key is
            absent from the yaml block, or the timeline block is absent.
    """
    text = status_path.read_text(encoding="utf-8")
    lines = text.splitlines(keepends=True)

    y_start, y_end = _split_fences(text, _YAML_FENCE)

    # Step 1: Rewrite phase: blocked.
    phase_line_idx: int | None = None
    for i in range(y_start, y_end):
        stripped = lines[i].rstrip("\r\n")
        match = re.match(r"^(phase:\s*).*$", stripped)
        if match is None:
            continue
        eol = lines[i][len(stripped):]
        lines[i] = f"phase: {quote_scalar('blocked')}{eol}"
        phase_line_idx = i
        break
    if phase_line_idx is None:
        raise ValueError(f"phase: key missing from yaml block of {status_path}")

    # Step 2: Write blocked_reason: — rewrite in place or insert after phase:.
    # y_end is still valid (no insertion has happened yet).
    blocked_reason_idx: int | None = None
    for i in range(y_start, y_end):
        stripped = lines[i].rstrip("\r\n")
        match = re.match(r"^(blocked_reason:\s*).*$", stripped)
        if match is None:
            continue
        blocked_reason_idx = i
        break
    if blocked_reason_idx is not None:
        stripped = lines[blocked_reason_idx].rstrip("\r\n")
        eol = lines[blocked_reason_idx][len(stripped):]
        lines[blocked_reason_idx] = f"blocked_reason: {quote_scalar(reason)}{eol}"
    else:
        lines.insert(phase_line_idx + 1, f"blocked_reason: {quote_scalar(reason)}\n")

    # Step 3: Append to Timeline block.
    rewritten = "".join(lines)
    tl_lines = rewritten.splitlines(keepends=True)
    tl_text = "".join(tl_lines)
    t_start, t_end = _split_fences(tl_text, _TIMELINE_FENCE)
    phase_label = "blocked"
    new_row = f"{phase_label}  {quote_scalar(timestamp)}\n"
    tl_lines.insert(t_end, new_row)
    status_path.write_text("".join(tl_lines), encoding="utf-8")


def append_phase(status_path: Path, phase: str, timestamp: str) -> None:
    """
    Record a phase transition in ``status.md``.

    Two mutations happen atomically from the caller's viewpoint:

    1. ``phase:`` in the top yaml block is overwritten with the new value.
    2. A ``<phase>  <timestamp>`` row is appended to the ``## Timeline``
       code block.

    The function reads, rewrites, and writes the file once — we don't use
    ``update_field`` for step 1 because it would re-read and re-write the
    file, doubling I/O for no gain. When the new phase is anything other
    than ``blocked``, any existing ``blocked_reason:`` row in the top yaml
    block is removed in the same write — ``blocked_reason:`` only has
    meaning while ``phase: blocked``.

    Args:
        status_path: Absolute path to the status.md file.
        phase: Written via ``_yaml_writer.quote_scalar`` inside the YAML
            block. Phase names from the closed v2 set (``discussing``,
            ``planning``, ``coding``, ``done``, plus per-round variants
            like ``plan-review-r1``) are YAML-safe and pass through
            unquoted; the helper guards against future phase names that
            might contain YAML-special characters.
        timestamp: ISO-8601 UTC timestamp for the timeline row.
            The value is written through `_yaml_writer.quote_scalar` so the
            on-disk row matches `render_initial`'s quoted form.

    Raises:
        ValueError: yaml block is missing / malformed, ``phase:`` key is
            absent from the yaml block, or the timeline block is absent.
    """
    text = status_path.read_text(encoding="utf-8")
    lines = text.splitlines(keepends=True)

    y_start, y_end = _split_fences(text, _YAML_FENCE)
    updated_phase = False
    for i in range(y_start, y_end):
        stripped = lines[i].rstrip("\r\n")
        match = re.match(r"^(phase:\s*).*$", stripped)
        if match is None:
            continue
        eol = lines[i][len(stripped):]
        lines[i] = f"phase: {quote_scalar(phase)}{eol}"
        updated_phase = True
        break
    if not updated_phase:
        raise ValueError(f"phase: key missing from yaml block of {status_path}")

    # Auto-clear blocked_reason: when transitioning to a non-blocked phase.
    # blocked_reason: only has meaning while phase: blocked; leaving the row
    # behind after advancing past blocked produces stale, misleading status.md.
    # Mirrors set_blocked's in-place row discovery (lines 244-258) in inverse:
    # same scan, but delete the line instead of rewriting it.
    if phase != "blocked":
        for i in range(y_start, y_end):
            stripped = lines[i].rstrip("\r\n")
            if re.match(r"^blocked_reason:\s*", stripped):
                del lines[i]
                # y_end is no longer valid after deletion, but we exit the
                # loop immediately — no further indices used inside the yaml
                # range.
                break

    # Timeline block: insert a new row at the end of the ```text block.
    # We need to find the fences in the rewritten text, not the original,
    # since the yaml-block edit above changed offsets.
    rewritten = "".join(lines)
    tl_lines = rewritten.splitlines(keepends=True)
    tl_text = "".join(tl_lines)
    t_start, t_end = _split_fences(tl_text, _TIMELINE_FENCE)
    # Aligned columns — phase name padded so timestamps line up in common
    # phases ("discussing" / "discussed" / "planning" / "coding" / "done").
    # We use two spaces as the separator; callers can post-fix alignment
    # if a new phase breaks the visual column.
    new_row = f"{phase}  {quote_scalar(timestamp)}\n"
    tl_lines.insert(t_end, new_row)
    status_path.write_text("".join(tl_lines), encoding="utf-8")


# ---------------------------------------------------------------------------
# Batches section — mill-go's per-batch execution state
# ---------------------------------------------------------------------------

_BATCHES_HEADING = "## Batches"
_BATCH_ALLOWED_KEYS = {
    "state",
    "implementer_session",
    "commit_sha",
    "start_sha",
    "review_round",
    "review_file",
    "blocked_reason",
}
_BATCH_STATES = {
    "pending",
    "running",
    "reviewing",
    "fixing",
    "approved",
    "blocked",
}


def _find_batches_block(lines: list[str]) -> tuple[int, int, int, int] | None:
    r"""Locate the batches section's heading and fenced-yaml body.

    Returns ``(heading_idx, fence_open_idx, fence_close_idx, section_end_idx)``
    where:
    - ``heading_idx`` points at the ``## Batches`` line,
    - ``fence_open_idx`` points at ``\`\`\`yaml``,
    - ``fence_close_idx`` points at the closing ``\`\`\``,
    - ``section_end_idx`` is the last-line-inclusive end of the section
      (the next ``## `` heading or EOF).

    Returns ``None`` if the heading is absent.
    """
    heading_idx = None
    for i, line in enumerate(lines):
        if line.rstrip() == _BATCHES_HEADING:
            heading_idx = i
            break
    if heading_idx is None:
        return None

    # Fence discovery is scoped to the section (until next ## heading).
    section_end_idx = len(lines) - 1
    for j in range(heading_idx + 1, len(lines)):
        if lines[j].startswith("## "):
            section_end_idx = j - 1
            break

    fence_open_idx = None
    for j in range(heading_idx + 1, section_end_idx + 1):
        if lines[j].strip() == "```yaml":
            fence_open_idx = j
            break
    if fence_open_idx is None:
        raise ValueError(
            f"{_BATCHES_HEADING} section missing its ```yaml``` block"
        )
    fence_close_idx = None
    for j in range(fence_open_idx + 1, section_end_idx + 1):
        if lines[j].strip() == "```":
            fence_close_idx = j
            break
    if fence_close_idx is None:
        raise ValueError(
            f"{_BATCHES_HEADING} ```yaml``` block is unterminated"
        )
    return (heading_idx, fence_open_idx, fence_close_idx, section_end_idx)


def _serialise_batches(batches: list[dict]) -> str:
    """Return a deterministic ``batches:`` yaml block body.

    Writes one list entry per batch with keys in a fixed order so diffs
    stay small across edits. Omits keys whose value is ``None`` to keep
    an empty entry visually compact.
    """
    order = [
        "name",
        "state",
        "implementer_session",
        "start_sha",
        "commit_sha",
        "review_round",
        "review_file",
        "blocked_reason",
    ]
    parts = ["batches:"]
    for entry in batches:
        first = True
        for key in order:
            if key not in entry or entry[key] is None:
                continue
            value = entry[key]
            prefix = "  - " if first else "    "
            # str values may contain YAML-special chars (e.g. blocked_reason); ints/bools
            # round-trip via str() and stay unquoted to preserve scalar type.
            if isinstance(value, str):
                parts.append(f"{prefix}{key}: {quote_scalar(value)}")
            else:
                parts.append(f"{prefix}{key}: {value}")
            first = False
        if first:
            # Entry had nothing but name (shouldn't happen, guard anyway).
            parts.append("  - name: " + entry.get("name", "?"))
    return "\n".join(parts) + "\n"


def _write_batches(status_path: Path, batches: list[dict]) -> None:
    """Replace or insert the ``## Batches`` section with ``batches``.

    If the section already exists, the fenced-yaml block is rewritten
    in place (preserving everything around it). If it does not, the
    new section is appended to the end of the file with a leading
    blank-line separator.
    """
    text = status_path.read_text(encoding="utf-8")
    lines = text.splitlines()
    body_yaml = _serialise_batches(batches)
    new_block = [
        _BATCHES_HEADING,
        "",
        "```yaml",
        *body_yaml.rstrip("\n").splitlines(),
        "```",
    ]
    located = _find_batches_block(lines)
    if located is None:
        # Append a new section at the end with leading blank separator.
        if lines and lines[-1].strip() != "":
            lines.append("")
        lines.extend(new_block)
    else:
        heading_idx, _fence_open, _fence_close, section_end = located
        lines = lines[:heading_idx] + new_block + lines[section_end + 1 :]
    status_path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def read_batches(status_path: Path) -> list[dict]:
    """Return the batches list from ``## Batches``, or ``[]`` if absent.

    Raises ``ValueError`` if the section exists but its yaml fence is
    malformed — that is a corruption we want to surface, not silently
    mask with an empty list.
    """
    text = status_path.read_text(encoding="utf-8")
    lines = text.splitlines()
    located = _find_batches_block(lines)
    if located is None:
        return []
    _h, fence_open, fence_close, _end = located
    body = "\n".join(lines[fence_open + 1 : fence_close])
    try:
        data = yaml.safe_load(body) or {}
    except yaml.YAMLError as exc:
        raise ValueError(f"Malformed {_BATCHES_HEADING} yaml: {exc}") from exc
    batches = data.get("batches", []) if isinstance(data, dict) else []
    return batches or []


def read_status(status_path: Path) -> dict:
    """Return a summary dict parsed from ``status_path``.

    Returns:
        ``{"phase": str, "task": str|None, "current_batch": str|None,
        "last_timeline_entry": str|None, "blocked_reason": str|None}``

    Raises:
        ValueError: file missing, no yaml block, yaml parse error,
            missing ``phase:`` key, or ``read_batches`` raises ValueError.
    """
    if not status_path.exists():
        raise ValueError(f"status file not found: {status_path}")
    text = status_path.read_text(encoding="utf-8")

    # Parse top yaml block.
    try:
        y_start, y_end = _split_fences(text, _YAML_FENCE)
    except ValueError as exc:
        raise ValueError(f"Cannot read yaml block in {status_path}: {exc}") from exc
    y_body = "\n".join(text.splitlines()[y_start:y_end])
    try:
        data = yaml.safe_load(y_body) or {}
    except yaml.YAMLError as exc:
        raise ValueError(f"Malformed yaml block in {status_path}: {exc}") from exc
    if not isinstance(data, dict) or "phase" not in data:
        raise ValueError(f"Missing 'phase:' key in yaml block of {status_path}")
    phase = data["phase"]
    task = data.get("task") or None
    blocked_reason = data.get("blocked_reason") or None

    # current_batch: first batch with an active state.
    _ACTIVE_BATCH_STATES = {"running", "reviewing", "fixing", "blocked"}
    batches = read_batches(status_path)  # ValueError propagates
    current_batch = None
    for b in batches:
        if b.get("state") in _ACTIVE_BATCH_STATES:
            current_batch = b.get("name")
            break

    # last_timeline_entry: last non-empty line of the ```text block.
    last_timeline_entry = None
    lines = text.splitlines()
    tl_start = None
    tl_end = None
    in_tl = False
    for i, line in enumerate(lines):
        if line.strip() == _TIMELINE_FENCE:
            tl_start = i + 1
            in_tl = True
            continue
        if in_tl and line.strip() == "```":
            tl_end = i
            break
    if tl_start is not None and tl_end is not None:
        content_lines = [ln.strip() for ln in lines[tl_start:tl_end] if ln.strip()]
        if content_lines:
            last_timeline_entry = content_lines[-1]

    return {
        "phase": phase,
        "task": task,
        "current_batch": current_batch,
        "last_timeline_entry": last_timeline_entry,
        "blocked_reason": blocked_reason,
    }


def read_full(status_path: Path) -> dict:
    """Return the complete yaml block and full timeline from ``status_path``.

    Unlike ``read_status``, which returns a slim summary, this returns the
    raw parsed contents without lossy summarisation — suitable for display
    tools that need to show everything.

    Returns:
        ``{"yaml": dict, "timeline": list[str]}``
        ``yaml`` contains all keys from the top yaml block.
        ``timeline`` is the list of non-empty raw lines from the
        ``## Timeline`` text fence, in file order.

    Raises:
        ValueError: file missing, yaml block missing/unterminated/malformed,
            or timeline block missing/unterminated.
    """
    if not status_path.exists():
        raise ValueError(f"status file not found: {status_path}")
    text = status_path.read_text(encoding="utf-8")

    try:
        y_start, y_end = _split_fences(text, _YAML_FENCE)
    except ValueError as exc:
        raise ValueError(f"Cannot read yaml block in {status_path}: {exc}") from exc
    y_body = "\n".join(text.splitlines()[y_start:y_end])
    try:
        data = yaml.safe_load(y_body) or {}
    except yaml.YAMLError as exc:
        raise ValueError(f"Malformed yaml block in {status_path}: {exc}") from exc
    if not isinstance(data, dict):
        raise ValueError(f"yaml block did not parse as a dict in {status_path}")

    try:
        t_start, t_end = _split_fences(text, _TIMELINE_FENCE)
    except ValueError as exc:
        raise ValueError(f"Cannot read timeline block in {status_path}: {exc}") from exc
    timeline_lines = [
        line.strip()
        for line in text.splitlines()[t_start:t_end]
        if line.strip()
    ]

    return {"yaml": data, "timeline": timeline_lines}


def read_parent_branch(status_path: Path) -> str | None:
    """Return the ``parent:`` value from the top yaml block of ``status_path``.

    Used by ``mill-cleanup`` to determine which branch to check out after
    an in-place task is cleaned up. Returns ``None`` when the file is
    missing, the yaml block is absent or unparseable, or the ``parent:``
    key is not present — callers that need the value to exist must raise
    their own error.

    Args:
        status_path: Absolute path to the task's ``status.md`` file.

    Returns:
        The parent branch name string, or ``None`` on any parse failure.
    """
    try:
        full = read_full(status_path)
        value = full["yaml"].get("parent")
        if not isinstance(value, str) or not value.strip():
            return None
        return value.strip()
    except (ValueError, KeyError, TypeError):
        return None


def read_slug(status_path: Path) -> str:
    """Return the ``slug:`` value from the top yaml block, or the parent dir name.

    Falls back silently to ``status_path.parent.name`` when the field is absent
    — the slug is fully derivable from the directory, so the fallback produces
    no warning.

    Args:
        status_path: Absolute path to the task's ``status.md`` file.

    Returns:
        The slug string.
    """
    try:
        full = read_full(status_path)
        value = full["yaml"].get("slug")
        if isinstance(value, str) and value:
            return value
    except (ValueError, KeyError, TypeError):
        pass
    return status_path.parent.name


def read_branch(status_path: Path, *, cfg: dict, slug: str) -> str:
    """Return the ``branch:`` value from the top yaml block, or derive it.

    Falls back to ``f"{cfg['spawn']['branch_prefix']}{slug}"`` when the prefix
    is non-empty, or bare ``slug`` when the prefix is empty. Emits a one-line
    warning to stderr on the fallback path.

    Args:
        status_path: Absolute path to the task's ``status.md`` file.
        cfg: Loaded mill config dict; must contain ``cfg['spawn']['branch_prefix']``.
        slug: Task slug; used to derive the branch name on the fallback path.

    Returns:
        The branch name string.
    """
    import sys as _sys

    try:
        full = read_full(status_path)
        value = full["yaml"].get("branch")
        if isinstance(value, str) and value:
            return value
    except (ValueError, KeyError, TypeError):
        pass

    prefix = cfg.get("spawn", {}).get("branch_prefix", "")
    derived = f"{prefix}{slug}" if prefix else slug
    print(
        f"[_status] warning: deriving branch from cfg.spawn.branch_prefix for slug={slug}",
        file=_sys.stderr,
    )
    return derived


def init_batches(status_path: Path, names: list[str]) -> None:
    """Seed the ``## Batches`` section with every batch in ``pending`` state.

    Idempotent: calling with the same ``names`` list produces the same
    output. Calling with a different list REPLACES the existing section
    — intended for use only at mill-go's entry before any batch has
    started. Callers resuming an existing run must not pass through
    this function.
    """
    batches = [{"name": n, "state": "pending"} for n in names]
    _write_batches(status_path, batches)


def set_batch_field(
    status_path: Path,
    name: str,
    key: str,
    value: str | int | None,
) -> None:
    """Mutate one field on one batch entry in ``## Batches``.

    Validates ``key`` is in the small known set and (for ``state:``)
    that the value is one of the declared states. Unknown keys raise
    ``ValueError`` so typos fail loudly rather than silently writing a
    field no consumer reads.
    """
    if key not in _BATCH_ALLOWED_KEYS:
        raise ValueError(
            f"Unknown batch field {key!r}; allowed: {sorted(_BATCH_ALLOWED_KEYS)}"
        )
    if key == "state" and value not in _BATCH_STATES:
        raise ValueError(
            f"Unknown batch state {value!r}; allowed: {sorted(_BATCH_STATES)}"
        )
    batches = read_batches(status_path)
    for entry in batches:
        if entry.get("name") == name:
            if value is None:
                entry.pop(key, None)
            else:
                entry[key] = value
            _write_batches(status_path, batches)
            return
    raise ValueError(f"Batch {name!r} not present in {_BATCHES_HEADING}")


def set_batch_fields(
    status_path: Path,
    name: str,
    fields: dict[str, str | int | None],
) -> None:
    """Atomically mutate multiple fields on one batch entry in ``## Batches``.

    Validates all keys before any mutation — a single
    ``read_batches → mutate all → _write_batches`` cycle ensures no
    partial write is possible.
    """
    for key in fields:
        if key not in _BATCH_ALLOWED_KEYS:
            raise ValueError(
                f"Unknown batch field {key!r}; allowed: {sorted(_BATCH_ALLOWED_KEYS)}"
            )
    if "state" in fields and fields["state"] not in _BATCH_STATES:
        raise ValueError(
            f"Unknown batch state {fields['state']!r}; allowed: {sorted(_BATCH_STATES)}"
        )
    batches = read_batches(status_path)
    for entry in batches:
        if entry.get("name") == name:
            for key, value in fields.items():
                if value is None:
                    entry.pop(key, None)
                else:
                    entry[key] = value
            _write_batches(status_path, batches)
            return
    raise ValueError(f"Batch {name!r} not present in {_BATCHES_HEADING}")
