# Batch: Lock CLI and mill-go SKILL.md updates

```yaml
task: 19 (A) — mill-go + scripts infra fixes
batch: Lock CLI and mill-go SKILL.md updates
cards: 2
verify: null
depends-on: []
```

## Batch Scope

This batch delivers two tightly coupled changes: (1) a new `millpy-builder-lock.py` CLI script that wraps `_builder_lock.py`'s acquire/release/read API behind a thin command-line interface, and (2) updates to `mill-go SKILL.md` that replace inline Python lock API calls with the new CLI, add a pause/resume note, and introduce a git-status cleanliness gate between the Implement and Code Review steps.

These two changes are one batch because the SKILL.md references the CLI by filename — both must be consistent. The next batch's implementer can read the updated SKILL.md without needing to understand the lock internals; the CLI is the external interface consumed by the orchestrator.

Batch-local decisions: none beyond Shared Decisions.

## Cards

### Card 1: Create millpy-builder-lock.py CLI

- **Reads:**
  - `plugins/mill/scripts/_builder_lock.py`
  - `plugins/mill/scripts/millpy-implement.py`
- **Modifies:** none
- **Creates:**
  - `plugins/mill/scripts/millpy-builder-lock.py`
- **Deletes:** none
- **Requirements:** Create a new CLI script at `plugins/mill/scripts/millpy-builder-lock.py` with three subcommands:

  - `acquire <slug>` — calls `_builder_lock.acquire(mill_dir, slug)`. Exits 0 on success; exits 1 and prints the `LockBusy` exception message to stderr on `LockBusy`.
  - `release` — calls `_builder_lock.release(mill_dir)`. Always exits 0 (idempotent; absence of lock file is not an error).
  - `read` — calls `_builder_lock.read(mill_dir)`. If a lock is held, prints its YAML representation to stdout (two lines: `slug: <value>` and `timestamp: <value>`) and exits 0. If free, prints nothing and exits 1.

  `mill_dir` is always derived as `Path.cwd() / '.millhouse'` — the script must be invoked from the worktree root, consistent with every other millpy script. Follow the same `argparse` structure as `millpy-implement.py`: module docstring, `main(argv=None) -> int`, `if __name__ == "__main__": sys.exit(main())`. No config loading or wiki resolution needed — pure lock operations.

- **Commit:** `feat(scripts): add millpy-builder-lock.py CLI (acquire/release/read)`

### Card 2: Update mill-go SKILL.md

- **Reads:**
  - `plugins/mill/skills/mill-go/SKILL.md`
  - `plugins/mill/scripts/millpy-builder-lock.py`
- **Modifies:**
  - `plugins/mill/skills/mill-go/SKILL.md`
- **Creates:** none
- **Deletes:** none
- **Requirements:** Make four changes to `mill-go SKILL.md`:

  1. **Lock acquire (Entry step 4).** Replace the inline `_builder_lock.acquire(Path(".millhouse"), slug)` call and its `signature:` line with:
     ```
     uv run --project "${CLAUDE_PLUGIN_ROOT}" "${CLAUDE_PLUGIN_ROOT}/scripts/millpy-builder-lock.py" acquire <slug>
     ```
     On exit code 1: surface the stderr message and halt. Remove the `signature: _builder_lock.acquire(...)` line entirely.

  2. **Lock release (Blocked step).** Replace `_builder_lock.release(mill_dir)` with:
     ```
     uv run --project "${CLAUDE_PLUGIN_ROOT}" "${CLAUDE_PLUGIN_ROOT}/scripts/millpy-builder-lock.py" release
     ```
     Remove the `signature: _builder_lock.release(...)` line.

  3. **Lock release (Handoff step 4).** Same replacement as Blocked step. Remove its `signature:` line.

  4. **Pause note.** At the end of the Entry section (after step 6 or the entry phase gate table), add a note:
     > If mill-go is interrupted mid-run, re-run `/mill-go` — it will auto-reclaim the builder lock for the same task (stale-self-lock detection is built in).

  5. **Cleanliness gate.** Add a new numbered step between "2. Parse implementer report" and "3. Code Review loop":

     ### 2b. Cleanliness gate

     After a `success` report: run `git -C <worktree> status --porcelain`. If the output is non-empty (uncommitted files present):
     - `_status.set_batch_field(status_path, batch_name, "state", "blocked")`
     - `_status.set_batch_field(status_path, batch_name, "blocked_reason", "uncommitted working tree after implementer report")`
     - `_status.append_phase(status_path, "blocked", _timestamp.now_utc_iso())`
     - Commit on the task branch: `git -C <worktree> add status.md && git -C <worktree> commit -m "mill-go: blocked on <batch_name> — dirty tree"`
     - Go to *Blocked*.

     If the output is empty, continue to "3. Code Review loop" as normal.

- **Commit:** `docs(mill-go): use lock CLI, add pause note and cleanliness gate`

## Batch Tests

`verify: null` — SKILL.md changes are operator-facing instructions, not runnable code. The builder-lock CLI is verified manually via the smoke test in `discussion.md`. No unit tests are added for the CLI itself (the underlying `_builder_lock.py` API is already covered by `test-builder-lock.py`).
