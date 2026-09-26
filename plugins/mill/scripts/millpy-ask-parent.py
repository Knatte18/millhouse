"""millpy-ask-parent.py — parent-escalation CLI (prepare / consume).

Wraps the _ask_parent.py API so the ask-parent skill can call it without inline Python.
Each subcommand prints one JSON line on stdout.

Subcommands:
    prepare --site <id> --reason <text> --actions <csv> — decide whether to escalate
    and render the message for the parent session
    consume --actions <csv> — parse and delete the parent's reply file

Exit codes:
    0 on success;
    1 on invalid arguments or config (one ASCII line on stderr, nothing on stdout)
"""
from __future__ import annotations

import argparse
import json
import sys

import _ask_parent
import _config
import _paths
import _status


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(
        description="Parent escalation CLI — prepare the message to the parent session or consume its reply."
    )
    sub = parser.add_subparsers(dest="command", required=True)

    prepare_p = sub.add_parser("prepare", help="Decide whether to escalate and render the message.")
    prepare_p.add_argument("--site", required=True, help="Escalation site id.")
    prepare_p.add_argument("--reason", required=True, help="Why the run is about to halt.")
    prepare_p.add_argument("--actions", required=True, help="Comma-separated accepted actions.")

    consume_p = sub.add_parser("consume", help="Parse and delete the parent's reply file.")
    consume_p.add_argument("--actions", required=True, help="Comma-separated accepted actions.")

    args = parser.parse_args(argv)

    try:
        if args.command == "prepare":
            git_root = _paths.resolve_git_root()
            worktree_root = _paths.resolve_hub_path()
            cfg = _config.load_config(worktree_root, git_root)
            status_path = _paths.status_path(worktree_root, cfg)
            slug = _status.read_slug(status_path)
            actions = _ask_parent.parse_actions(args.actions, args.site)
            result = _ask_parent.prepare(
                status_path=status_path,
                worktree_root=worktree_root,
                cfg=cfg,
                slug=slug,
                site=args.site,
                reason=args.reason,
                actions=actions,
            )
        else:
            worktree_root = _paths.resolve_hub_path()
            actions = _ask_parent.parse_actions(args.actions)
            result = _ask_parent.consume(_ask_parent.reply_path(worktree_root), actions)
    except (ValueError, KeyError) as exc:
        print(_ask_parent.to_ascii(f"[ask-parent] {exc}"), file=sys.stderr)
        return 1

    print(json.dumps(result))
    return 0


if __name__ == "__main__":
    sys.exit(main())
