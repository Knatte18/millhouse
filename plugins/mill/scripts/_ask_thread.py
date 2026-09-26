"""
Deterministic helpers for escalating a stuck autonomous run to a named session (default: its parent).

Renders the message sent to the target, computes the give-up deadline,
and parses the reply file into an action plus guidance, or free text for open questions.
Nothing here talks to the harness; the ``ask-thread`` skill does the sending and waiting.

Public API:
    REPLY_REL_PATH, DEFAULT_TIMEOUT_MINUTES, ACTIONS, GUIDANCE_SUFFIX_MAX, SITES
    to_ascii(text) -> str
    parse_actions(actions_csv, site=None) -> list[str]
    timeout_minutes(cfg) -> int
    reply_path(worktree_root) -> Path
    unreachable_suffix(target) -> str
    halt_suffix(guidance) -> str
    new_ask_id() -> str
    ask_id_line(ask_id) -> str
    build_message(*, slug, worktree_root, reply_file, giveup_utc, ask_id, reply_to=None,
                  site=None, reason=None, actions=None, questions=None) -> str
    prepare(*, ..., site=None, reason=None, actions=None, questions=None, target=None,
            reply_to=None, ask_id=None, now=None) -> dict
    consume(reply_file, ask_id, actions=None) -> dict
"""
from __future__ import annotations

import re
import secrets
from datetime import datetime, timedelta, timezone
from pathlib import Path

import yaml

import _paths
import _status

REPLY_REL_PATH = "_mill/ask-reply.md"
DEFAULT_TIMEOUT_MINUTES = 60
ACTIONS = ("retry", "approve", "halt")
GUIDANCE_SUFFIX_MAX = 200

_HALT_TEXT = "the run stops here and waits for the operator"

SITES: dict[str, dict] = {
    "go-batch": {
        "label": "mill-go per-batch stuck escalation",
        "actions": {
            "retry": "mill-go records your guidance in the batch plan file and re-runs the batch implementer once",
            "halt": _HALT_TEXT,
        },
    },
    "go-holistic-cap": {
        "label": "mill-go holistic review round cap",
        "actions": {
            "approve": "mill-go accepts the holistic review as-is and proceeds to handoff",
            "retry": "mill-go passes your guidance to the holistic fixer and runs one extra review round",
            "halt": _HALT_TEXT,
        },
    },
    "go-handoff-nits": {
        "label": "mill-go handoff unfixed-nits gate",
        "actions": {
            "retry": "mill-go re-runs the NIT-fix pass once with your guidance",
            "halt": _HALT_TEXT,
        },
    },
    "go-handoff-done-gate": {
        "label": "mill-go handoff done gate",
        "actions": {
            "retry": "mill-go re-dispatches mill-done-gate-fixer once with your guidance and re-runs the done gate",
            "halt": _HALT_TEXT,
        },
    },
    "plan-cap": {
        "label": "mill-plan plan review round cap",
        "actions": {
            "approve": "mill-plan approves the plan with the remaining BLOCKING findings waived",
            "retry": "mill-plan applies your guidance to the plan files and runs one extra review round",
            "halt": _HALT_TEXT,
        },
    },
    "start-cap": {
        "label": "mill-start --auto discussion review round cap",
        "actions": {
            "approve": "mill-start accepts discussion.md as-is and hands off to mill-plan",
            "retry": "mill-start applies your guidance to discussion.md and runs one extra review round",
            "halt": _HALT_TEXT,
        },
    },
    "quick-gate": {
        "label": "mill-quick done gate",
        "actions": {
            "retry": "mill-quick applies your guidance as a fix and re-runs the done gate once",
            "halt": _HALT_TEXT,
        },
    },
}

_YAML_BLOCK = re.compile(r"^```yaml[ \t]*\n(.*?)^```[ \t]*$", re.DOTALL | re.MULTILINE)


def to_ascii(text: str) -> str:
    """Replace every non-ASCII character with ``?`` so Windows cp1252 stdout never crashes."""
    return text.encode("ascii", "replace").decode("ascii")


def parse_actions(actions_csv: str, site: str | None = None) -> list[str]:
    """
    Split a comma-separated action list into an ordered, de-duplicated list.

    Raises ValueError when the list is empty, holds an action outside ``ACTIONS``,
    names an unknown ``site``, or holds an action the given ``site`` does not accept.
    """
    if site is not None and site not in SITES:
        raise ValueError(f"unknown site {site!r}; expected one of {sorted(SITES)}")
    actions: list[str] = []
    for item in actions_csv.split(","):
        item = item.strip()
        if item and item not in actions:
            actions.append(item)
    if not actions:
        raise ValueError("no actions given")
    for action in actions:
        if action not in ACTIONS:
            raise ValueError(f"unknown action {action!r}; expected one of {list(ACTIONS)}")
        if site is not None and action not in SITES[site]["actions"]:
            raise ValueError(f"site {site!r} does not accept action {action!r}")
    return actions


def timeout_minutes(cfg: dict) -> int:
    """Return the parent-reply wait in minutes from ``pipeline.parent_escalation_timeout_minutes``, defaulting to 60."""
    value = (cfg.get("pipeline") or {}).get("parent_escalation_timeout_minutes", DEFAULT_TIMEOUT_MINUTES)
    if value is None:
        return DEFAULT_TIMEOUT_MINUTES
    try:
        return int(value)
    except (TypeError, ValueError):
        return DEFAULT_TIMEOUT_MINUTES


def reply_path(worktree_root: Path) -> Path:
    """Return the path the parent writes its reply to."""
    return _paths.resolve_task_path(worktree_root, REPLY_REL_PATH)


def unreachable_suffix(target: str) -> str:
    """Return the blocked-reason suffix used when messaging the parent fails."""
    return to_ascii(f" (parent_thread {target} unreachable)")


def halt_suffix(guidance: str) -> str:
    """Return the blocked-reason suffix carrying the first guidance line, or ``""`` when there is none."""
    for raw_line in guidance.splitlines():
        line = raw_line.strip()
        if line:
            return f" -- parent: {to_ascii(line)[:GUIDANCE_SUFFIX_MAX]}"
    return ""


def new_ask_id() -> str:
    """Return a fresh 8-hex-digit id that correlates one question batch with its reply."""
    return secrets.token_hex(4)


def ask_id_line(ask_id: str) -> str:
    """Return the line a reply must start with to answer the question batch ``ask_id``."""
    return f"ask-id: {ask_id}"


def _reply_instructions(
    *, ask_id: str, reply_file: Path, reply_to: str | None, shape_lines: list[str]
) -> list[str]:
    """Render the how-to-answer block shared by action and open mode."""
    lines = [
        "",
        "Reply rules:",
        f"- The first non-empty line of your reply must be exactly: {ask_id_line(ask_id)}",
        "- Keep the answer short.",
    ]
    if reply_to is None:
        lines.append(f"- Answer by writing the reply file {reply_file} in one operation.")
    else:
        lines += [
            f"- Write the complete reply (the ask-id line plus the answer) to {reply_file} in one operation,",
            f"  AND send ONE SendMessage to {reply_to} with the same text.",
            f"  For a long answer the message may instead be the ask-id line plus: answered, see {reply_file}",
        ]
    lines += ["", "Reply shape:", ask_id_line(ask_id)]
    lines += shape_lines
    return lines


def build_message(
    *,
    slug: str,
    worktree_root: Path,
    reply_file: Path,
    giveup_utc: str,
    ask_id: str,
    reply_to: str | None = None,
    site: str | None = None,
    reason: str | None = None,
    actions: list[str] | None = None,
    questions: str | None = None,
) -> str:
    """
    Render the self-describing plain-ASCII message sent to the target session.

    Action mode (``site``, ``reason``, ``actions``) asks for a decision from a fixed action list;
    open mode (``questions``) asks free-form questions.
    The target needs no mill skill to answer: the message names the reply file, the ``ask-id`` line
    and the exact reply shape.
    Raises ValueError unless exactly one of the two modes is fully given.
    """
    action_inputs = (site, reason, actions)
    action_mode = all(value is not None for value in action_inputs)
    open_mode = questions is not None
    if action_mode == open_mode or (open_mode and any(value is not None for value in action_inputs)):
        raise ValueError("give either site, reason and actions, or questions")

    if open_mode:
        lines = [
            f"[mill] Task {slug} has questions for you and waits for your answer.",
            f"Worktree: {worktree_root}",
            f"Reply file: {reply_file}",
            f"Answer by {giveup_utc} UTC; after that the task asks its operator instead.",
            "",
            "Questions:",
            questions,
        ]
        shape = ["<your answers, by question number>"]
    else:
        one_line_reason = " ".join(reason.splitlines())
        lines = [
            f"[mill] Task {slug} is about to halt and asks you for a decision.",
            f"Site: {site} ({SITES[site]['label']})",
            f"Blocked reason: {one_line_reason}",
            f"Worktree: {worktree_root}",
            f"Reply file: {reply_file}",
            f"Answer by {giveup_utc} UTC; after that the task halts for the operator.",
            "",
            "Accepted actions:",
        ]
        lines += [f"- {action}: {SITES[site]['actions'][action]}" for action in actions]
        shape = [
            "```yaml",
            f"action: <one of: {', '.join(actions)}>",
            "```",
            "<free-text guidance for the task: what to change, or why to stop>",
        ]
    lines += _reply_instructions(ask_id=ask_id, reply_file=reply_file, reply_to=reply_to, shape_lines=shape)
    return to_ascii("\n".join(lines))


def prepare(
    *,
    status_path: Path,
    worktree_root: Path,
    cfg: dict,
    slug: str,
    site: str | None = None,
    reason: str | None = None,
    actions: list[str] | None = None,
    questions: str | None = None,
    target: str | None = None,
    reply_to: str | None = None,
    ask_id: str | None = None,
    now: datetime | None = None,
) -> dict:
    """
    Decide whether to escalate and, if so, build everything the skill needs to send and wait.

    Deletes any stale reply file first so a late reply from an earlier ask never leaks in.
    The target is ``target`` when given, else the task's ``parent_thread``.
    Action mode is disabled by a timeout of 0; open mode is never disabled and falls back to the default wait.

    Returns:
        ``{"escalate": False, "reason": ...}`` when disabled or no target resolves; otherwise
        ``{"escalate": True, "target", "ask_id", "reply_path", "giveup_s", "message", "unreachable_suffix"}``.
    """
    reply_file = reply_path(worktree_root)
    reply_file.unlink(missing_ok=True)

    minutes = timeout_minutes(cfg)
    if minutes <= 0:
        if questions is None:
            return {"escalate": False, "reason": "disabled"}
        minutes = DEFAULT_TIMEOUT_MINUTES

    resolved = target if target is not None else _status.read_parent_thread(status_path)
    if resolved is None:
        return {"escalate": False, "reason": "no target"}

    resolved_ask_id = ask_id if ask_id is not None else new_ask_id()
    giveup_s = minutes * 60
    deadline = (now or datetime.now(timezone.utc)) + timedelta(seconds=giveup_s)
    giveup_utc = deadline.strftime("%Y-%m-%dT%H:%M:%SZ")
    return {
        "escalate": True,
        "target": resolved,
        "ask_id": resolved_ask_id,
        "reply_path": str(reply_file),
        "giveup_s": giveup_s,
        "message": build_message(
            slug=slug,
            worktree_root=worktree_root,
            reply_file=reply_file,
            giveup_utc=giveup_utc,
            ask_id=resolved_ask_id,
            reply_to=reply_to,
            site=site,
            reason=reason,
            actions=actions,
            questions=questions,
        ),
        "unreachable_suffix": unreachable_suffix(resolved),
    }


def consume(reply_file: Path, ask_id: str, actions: list[str] | None = None) -> dict:
    """
    Parse and delete the reply file for the question batch ``ask_id``.

    A reply counts only when its first non-empty line, trailing whitespace stripped,
    equals ``ask-id: <ask_id>``; a missing file or any other first line is no reply.
    With ``actions`` the body is parsed as an action plus guidance and a missing, invalid or
    unaccepted action degrades to ``halt``; without ``actions`` the stripped body is returned.

    Returns:
        With ``actions``: ``{"action", "guidance", "halt_suffix"}``; ``halt_suffix`` is non-empty only for ``halt``.
        Without: ``{"reply": <text>}``, empty when there is no reply.
    """
    no_reply = {"action": "halt", "guidance": "", "halt_suffix": ""} if actions is not None else {"reply": ""}
    if not reply_file.exists():
        return no_reply
    text = reply_file.read_text(encoding="utf-8", errors="replace")
    # Delete before parsing so the file is gone on every path.
    reply_file.unlink(missing_ok=True)

    lines = text.splitlines(keepends=True)
    first = next((index for index, line in enumerate(lines) if line.strip()), None)
    if first is None or lines[first].rstrip() != ask_id_line(ask_id):
        return no_reply
    body = "".join(lines[first + 1:])
    if actions is None:
        return {"reply": body.strip()}

    action = "halt"
    match = _YAML_BLOCK.search(body)
    if match is None:
        guidance = body.strip()
    else:
        guidance = body[match.end():].strip()
        try:
            parsed = yaml.safe_load(match.group(1))
        except yaml.YAMLError:
            parsed = None
        if isinstance(parsed, dict) and isinstance(parsed.get("action"), str):
            action = parsed["action"].strip().lower()
    if action not in actions:
        action = "halt"
    return {
        "action": action,
        "guidance": guidance,
        "halt_suffix": halt_suffix(guidance) if action == "halt" else "",
    }
