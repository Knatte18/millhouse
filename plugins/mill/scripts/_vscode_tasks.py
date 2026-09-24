"""
VS Code session-task rendering helper.

Every task worktree gets a `.vscode/tasks.json` whose tasks start a named `claude` session for one
mill phase (`<slug>:<phase>`), with the model and effort taken from the `spawn.sessions` config.
`mill-spawn` and `millpy-session-tasks` share the *rendering and writing* of that file.
They do **not** share the *decision* of when to write — the caller decides.

Public API:
    TASK_SPECS, LABEL_PREFIX, DEFAULT_SESSIONS, MANAGED_MARKER
    Phase vocabulary, task label prefix, built-in model/effort defaults and the first-line marker
    that identifies a file as mill-managed.
    resolve_sessions(sessions_cfg)
    Return a complete ``{phase: {"model", "effort"}}`` mapping, falling back per key to defaults.
    build_command(name, phase, model, effort, flag=None)
    Return the shell command that starts one named claude session.
    render_tasks(name, sessions_cfg=None)
    Return the rendered tasks.json text.
    write_tasks(target, name, sessions_cfg=None)
    Render and write tasks.json, returning "created", "unchanged", "updated" or "replaced".
"""
from __future__ import annotations

import json
import re
from pathlib import Path

import _render

_TEMPLATE_PATH = Path(__file__).resolve().parent.parent / "templates" / "vscode-tasks.json"

LABEL_PREFIX = "mill: "
MANAGED_MARKER = "// managed by mill"

DEFAULT_SESSIONS: dict[str, dict[str, str]] = {
    "start": {"model": "opus", "effort": "medium"},
    "plan": {"model": "opus", "effort": "medium"},
    "go": {"model": "sonnet", "effort": "high"},
    "quick": {"model": "sonnet", "effort": "high"},
}

# (task_key, phase, flag) in the order the tasks appear in tasks.json.
TASK_SPECS: tuple[tuple[str, str, str | None], ...] = (
    ("start", "start", None),
    ("start-auto", "start", "--auto"),
    ("start-orch", "start", "--orch"),
    ("plan", "plan", None),
    ("go", "go", None),
    ("quick", "quick", None),
)

_TOKEN_VALUE_RE = re.compile(r"[A-Za-z0-9._\[\]:-]+")
_FORBIDDEN_NAME_CHARS = re.compile(r'["\\$`\x00-\x1f\x7f]')


def _resolve_session_value(phase_cfg: object, phase: str, key: str) -> str:
    """Return one stripped model/effort value, or the default when absent or empty."""
    raw = phase_cfg.get(key) if isinstance(phase_cfg, dict) else None
    value = str(raw).strip() if raw is not None else ""
    if not value:
        return DEFAULT_SESSIONS[phase][key]
    if value.startswith("-") or not _TOKEN_VALUE_RE.fullmatch(value):
        raise ValueError(f"spawn.sessions.{phase}.{key}: invalid value {value!r}")
    return value


def resolve_sessions(sessions_cfg: dict | None) -> dict[str, dict[str, str]]:
    """
    Merge the configured ``spawn.sessions`` mapping over ``DEFAULT_SESSIONS`` per key.

    Returns a mapping with every phase in ``DEFAULT_SESSIONS`` and a ``model`` and ``effort`` for each.

    Raises:
        ValueError: A value is not a plain token (letters, digits, ``.``, ``_``, ``-``, ``[``,
            ``]``, ``:``; not starting with ``-``).
    """
    cfg = sessions_cfg if isinstance(sessions_cfg, dict) else {}
    return {
        phase: {
            key: _resolve_session_value(cfg.get(phase), phase, key)
            for key in ("model", "effort")
        }
        for phase in DEFAULT_SESSIONS
    }


def _prompt(phase: str, flag: str | None) -> str:
    """Build the initial prompt; the single place to change if the slash form stops working."""
    return f"/mill-{phase}" if flag is None else f"/mill-{phase} {flag}"


def build_command(
    name: str,
    phase: str,
    model: str,
    effort: str,
    flag: str | None = None,
) -> str:
    """Return the ``claude`` command line that starts the session ``<name>:<phase>``."""
    prompt = _prompt(phase, flag)
    return f'claude -n "{name}:{phase}" --model {model} --effort {effort} "{prompt}"'


def _validate_name(name: str) -> None:
    if not name:
        raise ValueError("session name must not be empty")
    if _FORBIDDEN_NAME_CHARS.search(name):
        raise ValueError(f"session name contains a forbidden character: {name!r}")


def render_tasks(name: str, sessions_cfg: dict | None = None) -> str:
    """
    Render the tasks.json template with one command per entry of ``TASK_SPECS``.

    Args:
        name: Session name prefix, normally the task slug.
        sessions_cfg: The ``spawn.sessions`` config mapping; missing keys use defaults.

    Returns:
        The rendered tasks.json text, starting with ``MANAGED_MARKER``.

    Raises:
        ValueError: ``name`` is empty or contains ``"``, a backslash, ``$``, a backtick or a
            control character, or a session value is invalid.
    """
    _validate_name(name)
    sessions = resolve_sessions(sessions_cfg)
    values: dict[str, str] = {}
    for task_key, phase, flag in TASK_SPECS:
        command = build_command(
            name, phase, sessions[phase]["model"], sessions[phase]["effort"], flag
        )
        token = "CMD_" + task_key.upper().replace("-", "_")
        values[token] = json.dumps(command)[1:-1]
    return _render.render(_TEMPLATE_PATH, values)


def write_tasks(target: Path, name: str, sessions_cfg: dict | None = None) -> str:
    """
    Render tasks.json and write it to ``target``, creating parent directories as needed.

    An existing file that mill did not write (no ``MANAGED_MARKER`` first line) is copied to
    ``<target name>.bak`` beside it before being overwritten.

    Returns:
        ``"created"`` (no file before), ``"unchanged"`` (identical, not rewritten),
        ``"updated"`` (managed file overwritten) or ``"replaced"`` (unmanaged file backed up
        and overwritten).
    """
    content = render_tasks(name, sessions_cfg)
    target.parent.mkdir(parents=True, exist_ok=True)
    if not target.exists():
        target.write_text(content, encoding="utf-8")
        return "created"
    existing = target.read_text(encoding="utf-8")
    if existing == content:
        return "unchanged"
    if existing.startswith(MANAGED_MARKER):
        target.write_text(content, encoding="utf-8")
        return "updated"
    target.with_name(target.name + ".bak").write_text(existing, encoding="utf-8")
    target.write_text(content, encoding="utf-8")
    return "replaced"
