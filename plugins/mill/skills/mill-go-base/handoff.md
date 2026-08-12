# mill-go-base: Handoff

**Nit-enforcement gate.**
Check for approved scopes with unfixed nits:

```python
from pathlib import Path
import _nit_gate
unfixed_nits = _nit_gate.compute_unfixed_nits(worktree_root, reviews_dir, status_path)
```

If `unfixed_nits` is non-empty, self-resolve once: for each `scope` in `unfixed_nits`, locate that scope's latest code-review file by mirroring `_nit_gate._find_final_code_review`'s own matching exactly (`_review_common.RE_SIMPLE`/`RE_BATCH`, both anchored at the filename start): for `holistic`, a match is a filename where the leading `<timestamp>-` is immediately followed by `code-review-r<digits>.md` with nothing else in between (RE_SIMPLE, type `code`) — do NOT use an unanchored glob like `*-code-review-r*.md` for this, since a per-batch scope whose name itself starts with `r` (e.g. `retry-fix` -> `...-code-review-retry-fix-r1.md`) contains that substring and would be wrongly picked up;
for a per-batch scope, a match is a filename where the leading `<timestamp>-` is immediately followed by `code-review-{scope}-r<digits>.md` with `{scope}` matching this batch's exact name (RE_BATCH, type `code`, batch `{scope}`).
Among matching files, sort by filename descending (the leading timestamp makes this chronological) and take the first.

**Prior-blocking digest.**
```bash
PYTHONPATH="${CLAUDE_PLUGIN_ROOT}/scripts" "$MILL_PYTHON" -c "
import _prior_blocking, pathlib
digest = _prior_blocking.build_digest(pathlib.Path('<reviews_dir-abs-path>'), scope='batch', batch_name='<scope>')
pathlib.Path('<briefs_dir>/prior-blocking-<scope>-r<N>.txt').write_text(digest, encoding='utf-8')
"
```
Use `scope='batch', batch_name='<scope>'` when `<scope>` is a per-batch scope name, or `scope='holistic'` (no `batch_name`) when `<scope> == "holistic"`, writing to `<briefs_dir>/prior-blocking-<scope>-r<N>.txt` or `<briefs_dir>/prior-blocking-holistic-r<H>.txt` respectively (same naming convention as `## Execute` step 4 and `## Holistic code review` step 4).
As with those two sites, this is called at every round with no round guard — `build_digest` returns `""` when there is no prior BLOCKING history yet, and `millpy-fix.py` renders an empty digest file as `"(none)"`.

Dispatch the NIT-fix pass for that review file using the identical CLI and args already documented for the in-flow NIT-fix pass: see `## Execute` step 4's `APPROVE` branch for the per-batch shape (`<cli> = millpy-fix.py`, `<args> = --scope batch --batch-name <scope> --review-file <review-file-abs-path> --round <N> --nits-only`) or `## Holistic code review` step 4 for the holistic shape (`--scope holistic --review-file <review-file-abs-path> --round <H> --nits-only`);
`<N>`/`<H>` are read from the review filename.
That identical shape now includes `--prior-blocking <digest-path>` too (per `## Execute` step 4's and `## Holistic code review` step 4's edits to those two sites), so this site's dispatch carries it automatically with no separate argument string of its own.
This dispatch is this site's audit trail per Shared Decision `audit-trail-via-status-timeline`: no separate `_status.append_phase` call is added here, because the dispatched NIT-fix pass's `--stage finalize` call already appends the `nits-fixed-<scope>` marker to status.md on completion (see the Handoff section's existing "Manual recovery note" paragraph, unedited by this batch) — that marker, not a new `self-resolved-nits` row, is the intended record of this self-resolve action.
After the dispatch completes, re-run `_nit_gate.compute_unfixed_nits(worktree_root, reviews_dir, status_path)`.

If it is STILL non-empty, halt with: `BLOCKED: unfixed nits in scope(s): <scope-list> -- NIT-fix pass did not clear them` where `<scope-list>` is the joined list of scope names.
Do NOT set `phase: done` when the gate fires;
the task remains in its current phase so the operator can inspect and re-run `/mill-go`.

**Manual recovery note.**
The gate above requires a `nits-fixed-<scope>` row in status.md's timeline for each scope that has any `[NIT]` findings in its final code-review file — it does not inspect commits directly.
A classed `[NIT:<class>]` heading counts identically to a bare `[NIT]` heading for this requirement.
Under Agent-mode dispatch this marker is written automatically by the NIT-fix pass's `--stage finalize` call (see "## Agent-mode dispatch" step 6).
If an operator instead completes or verifies a NIT-fix pass manually, outside this documented flow (e.g. recovering from an orphaned or crashed fixer session), the gate still requires the marker to be appended by hand: `_status.append_phase(status_path, f"nits-fixed-{scope}", _timestamp.now_utc_iso())`, where `scope` is the batch name or `"holistic"`.

If the list is empty, proceed to terminal cleanliness gate.

**Terminal cleanliness gate.**
Resolve the parent branch and check for in-scope uncommitted changes:

```python
parent_branch = _parent_branch.resolve(status_path, interactive=False)
in_scope_dirt = _cleanliness.compute_terminal_dirt(worktree_root, task_dir, parent_branch)
```

If `in_scope_dirt` is non-empty, self-resolve once: this is the agent's own uncommitted work on the task branch, so commit it directly — `_status.append_phase(status_path, "self-resolved-terminal-dirt", _timestamp.now_utc_iso())`, then `git -C <worktree> add <in_scope_dirt files> <status_path> && git -C <worktree> commit -m "<VARIANT_LABEL>: commit in-scope work at task completion"` (folding the status.md append into the same commit as the audit trail, per Shared Decision `audit-trail-via-status-timeline`;
no push — matches every other Builder-owned Handoff-phase commit in `## Board discipline`).
Re-run `_cleanliness.compute_terminal_dirt(worktree_root, task_dir, parent_branch)`.

If it is STILL non-empty (e.g. the commit or the re-check itself failed, or new dirt appeared concurrently), halt with: `BLOCKED: dirty working tree at task completion -- <N> file(s) uncommitted: <file-list>. Commit or discard before proceeding.` where `<N>` is the count of dirty lines and `<file-list>` is the filenames extracted from the in-scope dirt.
Do NOT set `phase: done` when the gate fires;
the task remains in its current phase so the operator can inspect and fix.

If the list is empty, proceed to scope violations cleanup.

**Scope violations cleanup gate.**
Clean up ephemeral build artifacts that may have been left by verify runs:

```python
removed_paths, blocking_paths = _cleanliness.clean_ephemeral_scope_violations(worktree_root, git_root)
```

Log the removed artifacts (ASCII-only).
If `blocking_paths` is non-empty, self-resolve once: for each path in `blocking_paths`, classify it against the plan's `All Files Touched` list (in `00-overview.md` — this is the only list checked;
do not open any batch card body to do this classification, per mill-go's own "Lean Builder" principle) — a path that matches an entry in `All Files Touched` is in-scope work: `git -C <worktree> add <path>` and commit it as part of the single audit-trail commit below;
a path that clearly matches a known ephemeral/cruft pattern (build artifacts, editor swap files, and similar — the same category `clean_ephemeral_scope_violations` already auto-removes, just not caught by its fixed pattern list) and matches nothing in `All Files Touched`: remove it (`git -C <worktree> clean -f -- <path>`) and log the removal (ASCII-only) the same way as the auto-removed ephemeral artifacts above;
a path that cannot be confidently classified either way: leave it untouched (neither `add` nor `clean`) so it correctly reappears in `blocking_paths` on the re-run below and is caught by the halt.
After classifying every path in `blocking_paths`: `_status.append_phase(status_path, "self-resolved-scope-violation", _timestamp.now_utc_iso())`, then `git -C <worktree> add <status_path> && git -C <worktree> commit -m "<VARIANT_LABEL>: commit in-scope files at task completion"` (folding the status.md append into the same commit as the audit trail, per Shared Decision `audit-trail-via-status-timeline`;
no push — matches every other Builder-owned Handoff-phase commit in `## Board discipline`;
the cruft removals via `git clean` are untracked-file deletions and have nothing to stage).
Re-run `_cleanliness.clean_ephemeral_scope_violations(worktree_root, git_root)`.

If `blocking_paths` is STILL non-empty (a path could not be classified with confidence against the plan), halt with: `BLOCKED: out-of-scope untracked file(s): <file-list>` where `<file-list>` is the comma-separated list of blocking paths.
Do NOT set `phase: done` when the gate fires;
the task remains in its current phase so the operator can inspect and manually remove the files.

If the list is empty, proceed normally.

**Scope violations handling note.**
The `scope_violations` field in the fixer JSON envelope (present when a fixer detects untracked out-of-scope files) is read and surfaced to the orchestrator.
It is folded into the generic `stuck_type: logic` envelope;
the terminal gate (above) is the authoritative cleanup point for common artifacts like coverage profiling outputs.

**0.
Pre-done gate.**
Read `(cfg.get("pipeline") or {}).get("done_gate")` (deep-merged config;
the `or {}` guard handles the case where `pipeline:` is present but null).
If the value is `None` or absent, skip.
If it is a non-null string, run the command from `git_root` (not hub dir) as a best-effort verify:

```bash
PYTHONPATH="${CLAUDE_PLUGIN_ROOT}/scripts" "$MILL_PYTHON" -c "
import json, sys, subprocess, platform
import _paths, _config
git_root = _paths.resolve_git_root()
hub_root = _paths.resolve_hub_path()
cfg = _config.load_config(hub_root, git_root)
gate_cmd = (cfg.get('pipeline') or {}).get('done_gate')
if not gate_cmd:
    sys.exit(0)
result = subprocess.run(gate_cmd, cwd=git_root, shell=True, capture_output=True, text=True)
if result.returncode != 0:
    out = (result.stdout + result.stderr).strip()
    reason = out[-2000:] if len(out) > 2000 else out
    print(json.dumps({'status': 'blocked', 'reason': f'done gate failed: {reason}'}))
    sys.exit(1)
# dotnet cleanup: if gate command contains 'dotnet' and we are on Windows,
# run build-server shutdown to release process locks before mill-finalize runs.
if platform.system() == 'Windows' and 'dotnet' in gate_cmd.lower():
    subprocess.run(['dotnet', 'build-server', 'shutdown'], capture_output=True, timeout=30)
"
```

Give this Bash-tool call the same extended 600000ms (10-minute) timeout recommended for finalize-stage verify replays above: `gate_cmd` is an arbitrary, potentially slow project command (e.g. a full regression suite) with no bound on runtime, sharing the identical default-2-minute-Bash-timeout risk that motivated the original finalize-stage-CLI fix.

Parse stdout for a JSON line.
If the exit code is non-zero and the JSON line has `status: blocked`, halt with: `BLOCKED: done gate failed — <reason>`.
Do NOT set `phase: done` when the gate fires;
the task remains in its current phase so the operator can investigate the failure. `subprocess.run` with `capture_output=True` does not raise on non-zero exit code — check `result.returncode`.

1. `_status.append_phase(status_path, "done", _timestamp.now_utc_iso())`.
   Commit on the task branch: `git -C <worktree> add <status_path> _mill/briefs/ && git -C <worktree> commit -m "<VARIANT_LABEL>: done {slug}"`.

2. Flip Home.md's task line to `[ready-to-merge]` — the new intermediate state signalling 'mill-go done, mill-merge pending':
   ```bash
   PYTHONPATH="${CLAUDE_PLUGIN_ROOT}/scripts" "$MILL_PYTHON" -c "
   from pathlib import Path; import _paths
   from wiki import _client
   wiki_path = _paths.resolve_wiki_path(_paths.resolve_git_root())
   _client.set_phase(wiki_path, '<slug>', 'ready-to-merge')
   "
   ```
3. `_notify.notify("<VARIANT_LABEL>.done", f"task {slug} complete", slug=slug)`.
4. **Release the builder lock immediately:**
   ```bash
   PYTHONPATH="${CLAUDE_PLUGIN_ROOT}/scripts" "$MILL_PYTHON" "${CLAUDE_PLUGIN_ROOT}/scripts/millpy-builder-lock.py" release
   ```
5. If `pipeline.auto_merge: true` → invoke `/mill-finalize`.
   Otherwise tell the user: "Task complete.
   Run `/mill-finalize` to finalize the task (creates a PR or squashes directly, depending on config)." mill-finalize may halt on `pr-pending` in PR mode — that is expected;
   treat it as completion of step 5 and continue to step 6.
6. If `pipeline.auto_report: true` → invoke `/mill-self-report --auto`.
   **Always fires** at the end of Handoff, including after a `pr-pending` halt in step 5 — do NOT treat the PR-pending message as task termination.
   The skill checks `gh auth` itself and bails cleanly if absent.
   Cross-thread merges and post-PR teardowns are not auto-reflected;
   user can run `/mill-self-report` manually if wanted.
