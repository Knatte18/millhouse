# Batch: skill-rewrite

```yaml
task: 'mill-merge: run the deterministic path as one script'
batch: skill-rewrite
number: 4
cards: 1
verify: PYTHONPATH= uv run --project plugins/mill python plugins/mill/unit_tests/test-guards.py
depends-on: [3]
```

## Batch Scope

Replaces the 591-line step-by-step `plugins/mill/skills/mill-merge/SKILL.md` with a dispatch skill of about 100 lines that runs `millpy-merge.py`, branches on its JSON, and handles the two callbacks and the lock wait (discussion Decision `skill-md-shape`).

## Cards

### Card 8: rewrite mill-merge SKILL.md around millpy-merge.py

- **Context:**
  - `plugins/mill/scripts/_merge.py`
  - `plugins/mill/scripts/millpy-merge.py`
  - `plugins/mill/skills/mill-merge-in/SKILL.md`
- **Edits:**
  - `plugins/mill/skills/mill-merge/SKILL.md`
- **Creates:** none
- **Deletes:** none
- **Moves:** none
- **Requirements:**
  Rewrite `plugins/mill/skills/mill-merge/SKILL.md` in full, keeping the `---` frontmatter `name:` and `description:` lines byte-identical (so root `SKILLS.md` stays current).
  Target about 100 lines, semantic line breaks, no per-step rationale prose (that lives in `_merge.py` docstrings).
  Sections, in order:

  1. Title, the `Wiki access` blockquote, role line (integration engineer; never force-merge, never lose work), and the three cross-worktree invariants (run from the child worktree;
     never `cd` to the parent;
     parent git ops go through `git -C <parent-path>`, which the script does).
  2. `## Run` — the invocation in cache form, run with the Bash tool `timeout: 600000`:
     `PYTHONPATH="${CLAUDE_PLUGIN_ROOT}/scripts" "$MILL_PYTHON" "${CLAUDE_PLUGIN_ROOT}/scripts/millpy-merge.py" [args]`.
     Parse the last stdout line as JSON.
     Print every `report` line verbatim, then every `warnings` entry prefixed `WARNING: `.
     State that `args` accumulate within one `/mill-merge` invocation: each re-run passes the stop's `resume` list, and once a `--parent <new>` has been passed it is passed on every later re-run.
  3. `## Branch on the result` — a table on `status` / `action` / `step`:
     `ok` -> done (report already printed; for `route: "branch-protection-pr"` the PR URL is in `data.pr_url` and teardown completes on a later `/mill-merge` after the PR lands);
     `halt` with `step: "lock"` -> the lock-wait procedure;
     any other `halt` -> stop and report (the reason already tells the operator what to fix and whether to re-run);
     `callback` `merge-in` -> the merge-in procedure;
     `callback` `confirm-parent` -> the confirm-parent procedure.
  4. `## Callback: merge-in` — invoke the `mill-merge-in` skill with `data.parent_branch` as its positional argument.
     If it fails, halt and report (no lock is held).
     If its report carries `Substituted parent branch: <old> -> <new>`, add `--parent <new>` to the args.
     Re-run the script with `resume` (`--merged-in`) appended.
  5. `## Callback: confirm-parent` — the `report` already holds the operator message;
     ask with a numbered list per `mill:conversation` (`1) Proceed against <data.candidate> (Recommended)`, `2) Halt`);
     on 1 re-run with `resume` (`--confirm-parent <candidate>`) appended;
     on 2 halt.
  6. `## Lock wait` — arm the `Monitor` tool on a poll loop that checks `data.lock_path` every 10 s and prints one line when the file is gone or its second line (timestamp) is older than 5 min, giving up with a `TIMEOUT` line after 5 min;
     write the loop with `[ -f ... ]`, `head -n 2 | tail -n 1`, and `date` only (no `sed`).
     On the event, re-run the script once with the same args;
     a second `lock` halt is reported to the operator with the holder info from `data`.
  7. `## No JSON` — a non-zero exit with no JSON line is a crash or a hard kill: report the stderr tail and tell the operator to re-run `/mill-merge`.
     State once: the script rolls the parent back to `origin/<parent_branch>` and releases the lock itself on any failure or SIGTERM before the squash reaches origin;
     after a `SIGKILL` the lock goes stale in 5 min and a half-applied squash surfaces on the next run as the dirty-parent halt, whose text says how to commit or reset it;
     once the squash is on origin nothing is rolled back (post-squash halts say `Merge landed on <parent> but ...`).
  8. `## Report` — the no-self-report note carried over from the old `### 9. Notify + report` paragraph (reflection is mill-go's job;
     run `/mill-self-report` manually when invoked standalone).
  9. `## Board discipline` — the old section's bullets, keeping `Merge-lock file lives at <parent-path>/.scratch/merge.lock` and the rule that phase transitions go through the status helper, never a hand edit of status.md.

  The new file must not contain `sed`, a `.wiki` path on a command line, or any `cd` to the wiki or parent.
- **Commit:** `docs(mill-merge): rewrite SKILL.md as a millpy-merge.py dispatcher`

## Batch Tests

`verify:` runs `plugins/mill/unit_tests/test-guards.py`, whose `no_wiki_cwd` and related scans read every skill file, including this one.
The rewritten skill has no other runnable surface.
