"""
mill-fold — append a fold entry to a task in the wiki's Home.md.

Resolves the wiki clone via ``_paths.resolve_wiki_path``. Note: ``.millhouse/wiki``
is a junction for IDE/terminal convenience only — scripts never use it as a
code path. Acquires the shared ``.mill-lock`` around the read-append-sidebar-commit
sequence, then optionally closes the GitHub issue after the wiki commit succeeds
and the lock is released.

Operation order (``fold-operation-order`` shared decision):
    lock → parse → unclaimed-only-guard → fetch_one (GH path only) → body-append →
    sidebar regen → commit/push → release → optional GH close-with-comment

Unclaimed-only fold guard (``unclaimed-only-allowlist`` shared decision):
    Fold targets must be unclaimed: status is None AND not deferred.
    Any claimed, terminal, blocked, or deferred task refuses the fold.
    The allowlist auto-refuses any future status value — safe in the event
    of silent GitHub issue loss on refused folds.

GitHub issue close-comment string (``close-comment-strings`` shared decision):
    "Folded into wiki task: <slug>"

Slug rules (``Home.schema.md``): kebab-case matching ``[a-z][a-z0-9-]*``.

Usage:
    python plugins/mill/scripts/millpy-fold.py <target_slug> --issue <N>
    python plugins/mill/scripts/millpy-fold.py <target_slug> --scope <text>

Exit codes:
    0 — fold appended and pushed (GH close may have soft-failed; see stderr)
    1 — validation, environment, unclaimed-only-guard, or GH-state error
"""
from __future__ import annotations

import argparse
import re
import sys

import _gh_issues
from wiki import _client as wiki
from _paths import resolve_git_root, resolve_wiki_path

_SLUG_RE = re.compile(r"^[a-z][a-z0-9-]*$")


def _build_fold_line(issue_dict: dict | None, scope_text: str | None) -> str:
    assert (issue_dict is None) != (scope_text is None), (
        "_build_fold_line requires exactly one of issue_dict or scope_text"
    )
    if issue_dict is not None:
        return f"- Sources: #{issue_dict['number']} — {issue_dict['title']}"
    return f"- Folded in: {scope_text}"


def main(argv: list[str] | None = None, *, _fetch_one=None, _close_with_comment=None) -> int:
    parser = argparse.ArgumentParser(
        description="Append a fold entry to a wiki Home.md task."
    )
    parser.add_argument(
        "target_slug",
        help="Task slug to fold into — kebab-case, e.g. 'fix-foo'.",
    )
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument(
        "--issue", "-i",
        type=int,
        metavar="N",
        help="GitHub issue number to fold in (GH path).",
    )
    group.add_argument(
        "--scope",
        metavar="TEXT",
        help="Scope item text to fold in (scope path).",
    )
    args = parser.parse_args(argv)

    target_slug = args.target_slug
    if not _SLUG_RE.match(target_slug):
        raise SystemExit(f"Invalid slug {target_slug!r}: must match [a-z][a-z0-9-]*")

    git_root = resolve_git_root()
    wiki_path = resolve_wiki_path(git_root)

    fetch_one_fn = _fetch_one or _gh_issues.fetch_one
    close_with_comment_fn = _close_with_comment or _gh_issues.close_with_comment

    issue = None

    home_path = wiki_path / "Home.md"
    if not home_path.exists():
        raise SystemExit(f"Wiki not found at {wiki_path}.")

    tasks = wiki.list_tasks_brief(wiki_path)
    target_task = next((t for t in tasks if t["slug"] == target_slug), None)
    if target_task is None:
        raise SystemExit(f"Slug {target_slug!r} not found in Home.md.")

    status = target_task.get("status")
    deferred = target_task.get("deferred", False)
    if status is not None or deferred:
        blocking_state = "deferred" if status is None and deferred else status
        raise SystemExit(
            f"Cannot fold into {target_slug!r}: task is not unclaimed "
            f"(status: {blocking_state!r}). Only unclaimed backlog tasks accept fold-ins."
        )

    if args.issue is not None:
        try:
            issue = fetch_one_fn(args.issue, git_root=git_root)
        except _gh_issues.GhError as exc:
            raise SystemExit(str(exc)) from exc

        draft_line = _build_fold_line(issue, None)

        if sys.stdin.isatty():
            for _attempt in range(3):
                print(draft_line)
                choice = input("1) Use as-is (Recommended) / 2) Edit / 3) Abort\n> ").strip()
                if choice == "1":
                    fold_line = draft_line
                    break
                elif choice == "2":
                    new_title = input("Enter new title: ").strip()
                    issue = dict(issue)
                    issue["title"] = new_title
                    fold_line = _build_fold_line(issue, None)
                    break
                elif choice == "3":
                    raise SystemExit("Aborted by user.")
            else:
                raise SystemExit("Aborted by user.")
        else:
            fold_line = draft_line
    else:
        fold_line = _build_fold_line(None, args.scope)

    # Append fold line to the brief field
    current_brief = target_task.get("brief") or ""
    new_brief = ((current_brief + "\n" + fold_line) if current_brief else fold_line)
    wiki.upsert_task(wiki_path, target_slug, brief=new_brief)

    if args.issue is not None:
        try:
            close_with_comment_fn(
                args.issue,
                f"Folded into wiki task: {target_slug}",
                git_root=git_root,
            )
        except _gh_issues.GhError as exc:
            print(
                f"Warning: wiki commit succeeded but issue close failed: {exc}",
                file=sys.stderr,
            )

    print(f"Folded into wiki task: {target_slug!r}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
