"""mill-descope-batch — remove a not-yet-started batch from an approved plan.

Run from inside the task's worktree.
Given a batch name, refuses to proceed if any surviving batch still depends on it, or if the
batch has already started work (state other than ``pending`` in ``status.md``).
Otherwise edits the plan overview's Batch Index, moves the batch's card file out of the plan
directory into a sibling ``descoped/`` directory, prunes the batch from ``status.md``, and
commits + pushes the result on the task branch.
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

_SCRIPTS = Path(__file__).resolve().parent
sys.path.insert(0, str(_SCRIPTS))

import _marker
import _paths
import _plan_dag
import _review_common
import _status
import _subprocess_util
import _timestamp


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Remove a not-yet-started batch from the plan's Batch Index."
    )
    parser.add_argument("batch_name", help="The `name:` value of the batch to descope.")
    args = parser.parse_args()
    batch_name = args.batch_name

    # Step 1: resolve git_root, wiki_path, active_hub, cfg, slug -- mirrors millpy-abandon.py's
    # own steps 1-3.
    git_root = _paths.resolve_git_root()
    wiki_path = _paths.resolve_wiki_path(git_root)
    hub_dir = _paths.resolve_hub_path()
    mill_dir = hub_dir / ".millhouse"
    cfg = _review_common.load_config(hub_dir, mill_dir)
    try:
        slug = _marker.slug_from_branch(git_root, wiki_path, cfg)
    except _marker.MarkerError as exc:
        sys.exit(f"Error: mill-descope-batch must run from a worktree. ({exc})")

    container_path = _paths.resolve_container_path(git_root)
    active_hub = _paths.resolve_active_hub(
        container_path, slug, cfg=cfg, git_root=git_root,
    )
    mill_dir = active_hub / ".millhouse"
    cfg = _review_common.load_config(active_hub, mill_dir)

    # Step 2: resolve status_path and plan_dir the same way mill-go-base's Path Setup does.
    status_path = _paths.resolve_task_path(active_hub, cfg["paths"]["status_md"])
    plan_dir = _paths.resolve_task_path(active_hub, cfg["paths"]["plan_dir"])

    # Step 3: read the Batch Index.
    overview_path = plan_dir / "00-overview.md"
    overview_text = overview_path.read_text(encoding="utf-8")
    batches = _plan_dag.extract_batch_index(overview_text)

    # Step 4: find the batch's index entry.
    entry = next((b for b in batches if b.get("name") == batch_name), None)
    if entry is None:
        sys.exit(f"Error: batch {batch_name!r} not found in the plan.")

    # Step 5: safety guard -- refuse a batch that has already started work.
    # A batch not yet seeded into status.md's ## Batches block (status_batches is [] before
    # mill-go's own Prepare phase has run init_batches, or the name is simply absent) has by
    # definition not started any work, so it is safe to remove.
    status_batches = _status.read_batches(status_path)
    status_entry = next((b for b in status_batches if b.get("name") == batch_name), None)
    if status_entry is not None:
        state = status_entry.get("state")
        if state != "pending":
            sys.exit(
                f"Error: batch {batch_name!r} is state {state!r}, not 'pending' -- "
                f"only a not-yet-started batch can be descoped."
            )

    # Step 6: refuse if any surviving batch still depends on this one.
    dependents = _plan_dag.find_dependents(batches, batch_name)
    if dependents:
        sys.exit(
            f"Error: batch(es) {dependents} still depend on {batch_name!r} -- "
            f"descope them first or edit their depends-on."
        )

    # Step 7: rewrite the Batch Index and write it back.
    new_overview_text = _plan_dag.remove_batch_from_index(overview_text, batch_name)
    overview_path.write_text(new_overview_text, encoding="utf-8")

    # Step 8: move the batch's card file out of plan_dir into a sibling descoped/ directory.
    batch_file = entry["file"]
    descoped_dir = plan_dir.parent / "descoped"
    descoped_dir.mkdir(parents=True, exist_ok=True)
    mv_result = _subprocess_util.run(
        [
            "git", "-C", str(active_hub), "mv",
            str((plan_dir / batch_file).relative_to(active_hub)),
            str((descoped_dir / batch_file).relative_to(active_hub)),
        ]
    )
    if mv_result.returncode != 0:
        sys.exit(f"Error: git mv failed: {mv_result.stderr.strip()!r}")

    # Step 9-10: prune the batch from status.md and record the descope in the timeline.
    _status.remove_batch(status_path, batch_name)
    _status.append_phase(status_path, f"descoped-{batch_name}", _timestamp.now_utc_iso())

    # Step 11: commit.
    add_result = _subprocess_util.run(
        [
            "git", "-C", str(active_hub), "add", "-A",
            str(plan_dir.relative_to(active_hub)),
            str(descoped_dir.relative_to(active_hub)),
            str(status_path.relative_to(active_hub)),
        ]
    )
    if add_result.returncode != 0:
        sys.exit(f"Error: git add failed: {add_result.stderr.strip()!r}")
    commit_result = _subprocess_util.run(
        [
            "git", "-C", str(active_hub), "commit", "-m",
            f"mill-descope-batch: remove {batch_name} from {slug}",
        ]
    )
    if commit_result.returncode != 0:
        sys.exit(f"Error: git commit failed: {commit_result.stderr.strip()!r}")

    # Step 12: push.
    push_result = _subprocess_util.run(["git", "-C", str(active_hub), "push"])
    if push_result.returncode != 0:
        sys.exit(f"Error: git push failed: {push_result.stderr.strip()!r}")

    # Step 13: success.
    print(f"Descoped {batch_name!r} from {slug}.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
