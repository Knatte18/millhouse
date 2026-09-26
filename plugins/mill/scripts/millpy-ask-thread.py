"""millpy-ask-thread.py — ask-a-named-session CLI (prepare / consume / resolve).

Wraps the _ask_thread.py API so the ask-thread skill can call it without inline Python.
Each subcommand prints one JSON line on stdout.

Subcommands:
    prepare --site <id> --reason <text> --actions <csv> [--reply-to <name>] — automatic mode:
    decide whether to escalate and render the message for the parent session
    prepare --questions-file <path> [--to <name>] [--reply-to <name>] — direct mode:
    render open questions for the named session (default parent)
    consume --ask-id <id> (--actions <csv> | --open) — parse and delete the reply file
    resolve [--to <name>] — print the target session as {"target": name-or-null}

Exit codes:
    0 on success;
    1 on invalid arguments or config (one ASCII line on stderr, nothing on stdout)
"""
from __future__ import annotations

import argparse
import json
import sys

import _ask_thread
import _config
import _paths
import _status


def _resolve_status(worktree_root):
    git_root = _paths.resolve_git_root()
    cfg = _config.load_config(worktree_root, git_root)
    return cfg, _paths.status_path(worktree_root, cfg)


def _prepare(args) -> dict:
    automatic = (args.site, args.reason, args.actions)
    worktree_root = _paths.resolve_hub_path()
    if args.questions_file is None:
        if any(value is None for value in automatic):
            raise ValueError("prepare needs --site, --reason and --actions, or --questions-file")
        if args.to is not None:
            raise ValueError("--to applies only to --questions-file")
        questions = None
    else:
        if any(value is not None for value in automatic):
            raise ValueError("--questions-file cannot be combined with --site, --reason or --actions")
        with open(args.questions_file, encoding="utf-8") as handle:
            questions = handle.read()
    cfg, status_path = _resolve_status(worktree_root)
    slug = _status.read_slug(status_path)
    if questions is None:
        return _ask_thread.prepare(
            status_path=status_path,
            worktree_root=worktree_root,
            cfg=cfg,
            slug=slug,
            site=args.site,
            reason=args.reason,
            actions=_ask_thread.parse_actions(args.actions, args.site),
            reply_to=args.reply_to,
        )
    return _ask_thread.prepare(
        status_path=status_path,
        worktree_root=worktree_root,
        cfg=cfg,
        slug=slug,
        questions=questions,
        target=args.to,
        reply_to=args.reply_to,
    )


def _consume(args) -> dict:
    if args.ask_id is None:
        raise ValueError("consume needs --ask-id")
    if (args.actions is None) == (not args.open):
        raise ValueError("consume needs exactly one of --actions or --open")
    worktree_root = _paths.resolve_hub_path()
    actions = _ask_thread.parse_actions(args.actions) if args.actions is not None else None
    return _ask_thread.consume(_ask_thread.reply_path(worktree_root), args.ask_id, actions)


def _resolve(args) -> dict:
    worktree_root = _paths.resolve_hub_path()
    _, status_path = _resolve_status(worktree_root)
    if not status_path.exists():
        raise ValueError(f"not a mill task worktree: no status.md at {status_path}")
    target = args.to if args.to is not None else _status.read_parent_thread(status_path)
    return {"target": target}


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(
        description="Thread ask CLI -- prepare a message to a named session, consume its reply, or resolve the target."
    )
    sub = parser.add_subparsers(dest="command", required=True)

    prepare_p = sub.add_parser("prepare", help="Decide whether to ask and render the message.")
    prepare_p.add_argument("--site", help="Escalation site id (automatic mode).")
    prepare_p.add_argument("--reason", help="Why the run is about to halt (automatic mode).")
    prepare_p.add_argument("--actions", help="Comma-separated accepted actions (automatic mode).")
    prepare_p.add_argument("--questions-file", help="UTF-8 file with open questions (direct mode).")
    prepare_p.add_argument("--to", help="Target session name (direct mode); default parent_thread.")
    prepare_p.add_argument("--reply-to", help="Session name the target also answers via SendMessage.")

    consume_p = sub.add_parser("consume", help="Parse and delete the reply file for one ask id.")
    consume_p.add_argument("--ask-id", help="The ask_id printed by prepare.")
    consume_p.add_argument("--actions", help="Comma-separated accepted actions (automatic mode).")
    consume_p.add_argument("--open", action="store_true", help="Return the free-text reply (direct mode).")

    resolve_p = sub.add_parser("resolve", help="Print the target session for direct mode.")
    resolve_p.add_argument("--to", help="Target session name; default parent_thread.")

    args = parser.parse_args(argv)
    handlers = {"prepare": _prepare, "consume": _consume, "resolve": _resolve}

    try:
        result = handlers[args.command](args)
    except (ValueError, KeyError, OSError) as exc:
        print(_ask_thread.to_ascii(f"[ask-thread] {exc}"), file=sys.stderr)
        return 1

    print(json.dumps(result))
    return 0


if __name__ == "__main__":
    sys.exit(main())
