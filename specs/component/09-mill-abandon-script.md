# mill-abandon (script)

```yaml
type: script
layer: 04
v1_ref: plugins/mill/skills/mill-abandon/
status: partially discussed — key decisions captured, not ready for full-write
note: "Marks a task as abandoned. Runs FROM the worktree being abandoned, which means it cannot remove itself — actual worktree + active/<slug>/ deletion is done by mill-cleanup from the hub afterwards."
```

## Purpose

Declare "I am not finishing this task." Write the signal so Home.md and `status.md` agree, push it to the wiki, and tell the user to run `mill-cleanup` from the hub to remove the residue.

Destructive wiki writes are gated by an explicit confirmation on stdin (or `--force`) — abandon is easy to trigger by accident.

## Decisions

- **Runs from the worktree being abandoned** — and therefore CANNOT remove its own worktree or delete its own `active/<slug>/` directory. The script refuses to touch the filesystem of the worktree itself (the cwd).
- **What mill-abandon does**:
  1. Append `phase: abandoned` to `<WIKI_PATH>/active/<slug>/status.md` (wiki-locked write).
  2. Commit + push.
  3. Tell the user: "Run `mill-cleanup` from the hub to remove this worktree and its active dir."
- **What mill-abandon does NOT**:
  - Rewrite Home.md. The `[active]` → unclaimed reset is `mill-cleanup`'s job once it has seen `phase: abandoned` in status.md. Reason: Home.md and status.md writes should not diverge across scripts; keeping them in one reconciler (mill-cleanup) avoids half-consistent states.
  - Remove the worktree.
  - Delete `active/<slug>/` on the wiki.
  - Delete the branch.
  - Do anything in the parent worktree.
- **No `[abandoned]` marker in Home.md**: v2 does not use an `[abandoned]` Home.md marker. mill-cleanup resets the marker to *unclaimed* (no marker) when it processes an abandoned task, so the task re-enters the backlog and can be re-claimed by anyone. The abandonment fact lives only in git history (the commit from mill-abandon) and is not preserved as a tombstone.
- **Confirmation**: by default, prompt `Abandon <slug>? (y/N)` on stdin. `--force` skips the prompt (for scripted runs).
- **Entry checks**:
  - cwd is a worktree (not the hub).
  - `.millhouse/active.slug.md` exists → derive slug.
  - `<WIKI_PATH>/active/<slug>/status.md` exists and `phase:` is not already `abandoned` / `done` (refuse re-abandon and re-abandon-after-done).
- **Timestamp invariant**: use shell `date -u +%Y%m%d-%H%M%S` for any timestamp going into status.md timeline; never guess.

## Flow

1. Verify cwd is a worktree (abort if hub).
2. Resolve slug from `.millhouse/active.slug.md`.
3. Load status.md — phase must be something that can be abandoned (not `abandoned`, not `done`).
4. Confirm with user unless `--force`.
5. `wiki.acquire_lock`.
6. `status.md` → append `abandoned` phase (`_status.append_phase`).
7. `_wiki.write_commit_push` the single status.md write with commit message `task: abandon <slug>`.
8. Release wiki lock.
9. Print `Task '<slug>' marked abandoned. Run 'mill-cleanup' from the hub to remove the worktree and active dir, and reset Home.md.`

## Backend

**New:**
- `mill-abandon.py` — CLI entrypoint.
- `_status.py` — `append_phase` (planned).

**Reused:**
- `_wiki.py` (lock + write_commit_push), `_active.py` (planned, slug lookup).

## Out of scope

- No self-cleanup of cwd / worktree / junctions. That's `mill-cleanup`'s job from the hub.
- No history preservation ("why abandoned?" note in status.md). If the user wants a reason recorded, they add a Timeline entry manually before running abandon, or we extend this script with `--reason <text>` later.
- No re-activation path in this script. Because mill-cleanup resets abandoned tasks to unclaimed in Home.md, resuming is just `mill-spawn` picking the task up again from the backlog like any other.

## Open design points

- **`--reason <text>`**: add now or later? Later is fine; can be appended to status.md timeline retroactively.
- **Wiki-lock timeout**: reuse the 30s default from `_wiki.acquire_lock`. Same as mill-merge.
- **Clash with mill-merge / mill-go running**: not addressed. If mill-go is implementing and the user runs mill-abandon, state could be confusing. A guard: reject if `status.md phase:` is `implementing`/`reviewing`/`fixing` and the builder lock exists? Simpler: reject abandonment while `builder.lock` is held.
