"""
Deterministic helpers for escalating a stuck autonomous run to its parent session.

Renders the message sent to the parent, computes the give-up deadline,
and parses the parent's reply file into an action plus guidance.
Nothing here talks to the harness; the ``ask-parent`` skill does the sending and waiting.

Public API:
    REPLY_REL_PATH, DEFAULT_TIMEOUT_MINUTES, ACTIONS, GUIDANCE_SUFFIX_MAX, SITES
    to_ascii(text) -> str
    parse_actions(actions_csv, site=None) -> list[str]
    timeout_minutes(cfg) -> int
    reply_path(worktree_root) -> Path
    unreachable_suffix(parent_thread) -> str
    halt_suffix(guidance) -> str
    build_message(...) -> str
    prepare(...) -> dict
    consume(reply_file, actions) -> dict
"""
from __future__ import annotations

import re
from datetime import datetime, timedelta, timezone
from pathlib import Path

import yaml

import _paths
import _status

REPLY_REL_PATH = "_mill/parent-reply.md"
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


def unreachable_suffix(parent_thread: str) -> str:
    """Return the blocked-reason suffix used when messaging the parent fails."""
    return to_ascii(f" (parent_thread {parent_thread} unreachable)")


def halt_suffix(guidance: str) -> str:
    """Return the blocked-reason suffix carrying the first guidance line, or ``""`` when there is none."""
    for raw_line in guidance.splitlines():
        line = raw_line.strip()
        if line:
            return f" -- parent: {to_ascii(line)[:GUIDANCE_SUFFIX_MAX]}"
    return ""


def build_message(
    *,
    slug: str,
    site: str,
    reason: str,
    worktree_root: Path,
    reply_file: Path,
    actions: list[str],
    giveup_utc: str,
) -> str:
    """
    Render the self-describing plain-ASCII message sent to the parent session.

    The parent needs no mill skill to answer: the message names the accepted actions
    and the exact reply-file shape.
    """
    one_line_reason = " ".join(reason.splitlines())
    lines = [
        f"[mill] Task {slug} is about to halt and asks you (its parent session) for a decision.",
        f"Site: {site} ({SITES[site]['label']})",
        f"Blocked reason: {one_line_reason}",
        f"Worktree: {worktree_root}",
        f"Reply file: {reply_file}",
        f"Answer by {giveup_utc} UTC; after that the task halts for the operator.",
        "",
        "Accepted actions:",
    ]
    lines += [f"- {action}: {SITES[site]['actions'][action]}" for action in actions]
    lines += [
        "",
        "Reply by writing the reply file in one operation, with this exact shape:",
        "```yaml",
        f"action: <one of: {', '.join(actions)}>",
        "```",
        "<free-text guidance for the task: what to change, or why to stop>",
    ]
    return to_ascii("\n".join(lines))


def prepare(
    *,
    status_path: Path,
    worktree_root: Path,
    cfg: dict,
    slug: str,
    site: str,
    reason: str,
    actions: list[str],
    now: datetime | None = None,
) -> dict:
    """
    Decide whether to escalate and, if so, build everything the skill needs to send and wait.

    Deletes any stale reply file first so a late reply from an earlier escalation never leaks in.

    Returns:
        ``{"escalate": False, "reason": ...}`` when escalation is disabled or the task has no
        ``parent_thread``; otherwise ``{"escalate": True, "parent_thread", "reply_path",
        "giveup_s", "message", "unreachable_suffix"}``.
    """
    reply_file = reply_path(worktree_root)
    reply_file.unlink(missing_ok=True)

    minutes = timeout_minutes(cfg)
    if minutes <= 0:
        return {"escalate": False, "reason": "disabled"}

    parent = _status.read_parent_thread(status_path)
    if parent is None:
        return {"escalate": False, "reason": "no parent_thread"}

    giveup_s = minutes * 60
    deadline = (now or datetime.now(timezone.utc)) + timedelta(seconds=giveup_s)
    giveup_utc = deadline.strftime("%Y-%m-%dT%H:%M:%SZ")
    return {
        "escalate": True,
        "parent_thread": parent,
        "reply_path": str(reply_file),
        "giveup_s": giveup_s,
        "message": build_message(
            slug=slug,
            site=site,
            reason=reason,
            worktree_root=worktree_root,
            reply_file=reply_file,
            actions=actions,
            giveup_utc=giveup_utc,
        ),
        "unreachable_suffix": unreachable_suffix(parent),
    }


def consume(reply_file: Path, actions: list[str]) -> dict:
    """
    Parse and delete the parent's reply file.

    Any missing file, missing or invalid yaml block, missing ``action:``, or action outside
    ``actions`` degrades to ``halt``.

    Returns:
        ``{"action", "guidance", "halt_suffix"}``; ``halt_suffix`` is non-empty only for ``halt``.
    """
    if not reply_file.exists():
        return {"action": "halt", "guidance": "", "halt_suffix": ""}
    text = reply_file.read_text(encoding="utf-8", errors="replace")
    # Delete before parsing so the file is gone on every path.
    reply_file.unlink(missing_ok=True)

    action = "halt"
    match = _YAML_BLOCK.search(text)
    if match is None:
        guidance = text.strip()
    else:
        guidance = text[match.end():].strip()
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
