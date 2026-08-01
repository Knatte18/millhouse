# Batch: mill-go-handoff-gates

```yaml
task: 'Non-interactive pipeline: only mill-start''s interview may prompt the operator'
batch: mill-go-handoff-gates
number: 4
cards: 4
verify: null
depends-on: [3]
```

## Batch Scope

`mill-go/SKILL.md`'s `## Handoff` section has three sequential cleanup gates — Nit-enforcement, Terminal cleanliness, and Scope violations cleanup — that today halt immediately on any finding with NO existing autonomous-mode branch at all (unlike the sites in batches 2 and 3, which had a `pipeline.autonomous_mode: true` branch to make unconditional). Each gate gets new one-shot self-resolve logic per Shared Decision `self-resolve-then-escalate-on-repeat`: dispatch the NIT-fix pass, commit in-scope dirt, or classify-and-clean untracked files, respectively — then re-check the gate once before falling back to today's halt message. The three gates are independent paragraphs with distinct trigger conditions, so each is its own card. This batch depends on batch 3 (both edit `mill-go/SKILL.md`).

## Cards

### Card 8: Self-resolve mill-go's Nit-enforcement gate

- **Context:**
  - `plugins/mill/scripts/_nit_gate.py`
  - `plugins/mill/scripts/_review_common.py`
- **Edits:**
  - `plugins/mill/skills/mill-go/SKILL.md`
- **Creates:** none
- **Deletes:** none
- **Moves:** none
- **Requirements:**

  The `## Handoff` section's `**Nit-enforcement gate.**` paragraph currently reads exactly:

```
**Nit-enforcement gate.** Check for approved scopes with unfixed nits:

```python
  from pathlib import Path
  import _nit_gate
  unfixed_nits = _nit_gate.compute_unfixed_nits(worktree_root, reviews_dir, status_path)
```

If `unfixed_nits` is non-empty, halt with:
`BLOCKED: unfixed nits in scope(s): <scope-list> -- run the NIT-fix pass before completing`
where `<scope-list>` is the joined list of scope names. Do NOT set `phase: done` when the gate fires; the task remains in its current phase so the operator can run the NIT-fix pass and re-run `/mill-go`.
```

  Replace the "If `unfixed_nits` is non-empty" paragraph (leave the `**Nit-enforcement gate.**` intro sentence and the Python code block above it unchanged) with:

```
If `unfixed_nits` is non-empty, self-resolve once: for each `scope` in `unfixed_nits`, locate that scope's latest code-review file by mirroring `_nit_gate._find_final_code_review`'s own matching exactly (`_review_common.RE_SIMPLE`/`RE_BATCH`, both anchored at the filename start): for `holistic`, a match is a filename where the leading `<timestamp>-` is immediately followed by `code-review-r<digits>.md` with nothing else in between (RE_SIMPLE, type `code`) — do NOT use an unanchored glob like `*-code-review-r*.md` for this, since a per-batch scope whose name itself starts with `r` (e.g. `retry-fix` -> `...-code-review-retry-fix-r1.md`) contains that substring and would be wrongly picked up; for a per-batch scope, a match is a filename where the leading `<timestamp>-` is immediately followed by `code-review-{scope}-r<digits>.md` with `{scope}` matching this batch's exact name (RE_BATCH, type `code`, batch `{scope}`). Among matching files, sort by filename descending (the leading timestamp makes this chronological) and take the first. Dispatch the NIT-fix pass for that review file using the identical CLI, args, and dispatch-mode handling already documented for the in-flow NIT-fix pass: see `## Execute` step 4's `APPROVE` branch for the per-batch shape (`<cli> = millpy-fix.py`, `<args> = --scope batch --batch-name <scope> --review-file <review-file-abs-path> --round <N> --nits-only`) or `## Holistic code review` step 4 for the holistic shape (`--scope holistic --review-file <review-file-abs-path> --round <H> --nits-only`); `<N>`/`<H>` are read from the review filename. After the dispatch completes, re-run `_nit_gate.compute_unfixed_nits(worktree_root, reviews_dir, status_path)`.

If it is STILL non-empty, halt with:
`BLOCKED: unfixed nits in scope(s): <scope-list> -- NIT-fix pass did not clear them`
where `<scope-list>` is the joined list of scope names. Do NOT set `phase: done` when the gate fires; the task remains in its current phase so the operator can inspect and re-run `/mill-go`.
```

  Preserve the existing "If the list is empty, proceed to terminal cleanliness gate." sentence that follows — do not remove or duplicate it.
- **Commit:** `docs(mill-go): self-resolve Handoff nit-enforcement gate`

### Card 9: Self-resolve mill-go's Terminal cleanliness gate

- **Context:** none
- **Edits:**
  - `plugins/mill/skills/mill-go/SKILL.md`
- **Creates:** none
- **Deletes:** none
- **Moves:** none
- **Requirements:**

  The `**Terminal cleanliness gate.**` paragraph currently reads exactly:

```
**Terminal cleanliness gate.** Resolve the parent branch and check for in-scope uncommitted changes:

```python
  parent_branch = _parent_branch.resolve(status_path, interactive=False)
  in_scope_dirt = _cleanliness.compute_terminal_dirt(worktree_root, task_dir, parent_branch)
```

If `in_scope_dirt` is non-empty, halt with:
`BLOCKED: dirty working tree at task completion -- <N> file(s) uncommitted: <file-list>. Commit or discard before proceeding.`
where `<N>` is the count of dirty lines and `<file-list>` is the filenames extracted from the in-scope dirt. Do NOT set `phase: done` when the gate fires; the task remains in its current phase so the operator can inspect and fix.
```

  Replace the "If `in_scope_dirt` is non-empty" paragraph (leave the intro sentence and the Python code block above it unchanged) with:

```
If `in_scope_dirt` is non-empty, self-resolve once: this is the agent's own uncommitted work on the task branch, so commit it directly — `_status.append_phase(status_path, "self-resolved-terminal-dirt", _timestamp.now_utc_iso())`, then `git -C <worktree> add <in_scope_dirt files> <status_path> && git -C <worktree> commit -m "mill-go: commit in-scope work at task completion"` and push (folding the status.md append into the same commit as the audit trail, per Shared Decision `audit-trail-via-status-timeline`). Re-run `_cleanliness.compute_terminal_dirt(worktree_root, task_dir, parent_branch)`.

If it is STILL non-empty (e.g. the commit or the re-check itself failed, or new dirt appeared concurrently), halt with:
`BLOCKED: dirty working tree at task completion -- <N> file(s) uncommitted: <file-list>. Commit or discard before proceeding.`
where `<N>` is the count of dirty lines and `<file-list>` is the filenames extracted from the in-scope dirt. Do NOT set `phase: done` when the gate fires; the task remains in its current phase so the operator can inspect and fix.
```

  Preserve the existing "If the list is empty, proceed to scope violations cleanup." sentence that follows.
- **Commit:** `docs(mill-go): self-resolve Handoff terminal cleanliness gate`

### Card 10: Self-resolve mill-go's Scope violations cleanup gate

- **Context:** none
- **Edits:**
  - `plugins/mill/skills/mill-go/SKILL.md`
- **Creates:** none
- **Deletes:** none
- **Moves:** none
- **Requirements:**

  The `**Scope violations cleanup gate.**` paragraph currently reads exactly:

```
**Scope violations cleanup gate.** Clean up ephemeral build artifacts that may have been left by verify runs:

```python
  removed_paths, blocking_paths = _cleanliness.clean_ephemeral_scope_violations(worktree_root, git_root)
```

Log the removed artifacts (ASCII-only). If `blocking_paths` is non-empty, halt with:
`BLOCKED: out-of-scope untracked file(s): <file-list>`
where `<file-list>` is the comma-separated list of blocking paths. Do NOT set `phase: done` when the gate fires; the task remains in its current phase so the operator can inspect and manually remove the files.
```

  Replace the "Log the removed artifacts" paragraph (leave the intro sentence and the Python code block above it unchanged) with:

```
Log the removed artifacts (ASCII-only). If `blocking_paths` is non-empty, self-resolve once: for each path in `blocking_paths`, classify it against the plan's `All Files Touched` list and the batch cards' `Edits:`/`Creates:` fields — a path that matches a planned target is in-scope work: `git -C <worktree> add <path>` and commit it as part of the single audit-trail commit below; a path that clearly matches a known ephemeral/cruft pattern (build artifacts, editor swap files, and similar — the same category `clean_ephemeral_scope_violations` already auto-removes, just not caught by its fixed pattern list) and matches neither a planned target: remove it (`git -C <worktree> clean -f -- <path>`) and log the removal (ASCII-only) the same way as the auto-removed ephemeral artifacts above; a path that cannot be confidently classified either way: leave it untouched (neither `add` nor `clean`) so it correctly reappears in `blocking_paths` on the re-run below and is caught by the halt. After classifying every path in `blocking_paths`: `_status.append_phase(status_path, "self-resolved-scope-violation", _timestamp.now_utc_iso())`, then `git -C <worktree> add <status_path> && git -C <worktree> commit -m "mill-go: commit in-scope files at task completion"` and push (folding the status.md append into the same commit as the audit trail, per Shared Decision `audit-trail-via-status-timeline`; the cruft removals via `git clean` are untracked-file deletions and have nothing to stage). Re-run `_cleanliness.clean_ephemeral_scope_violations(worktree_root, git_root)`.

If `blocking_paths` is STILL non-empty (a path could not be classified with confidence against the plan), halt with:
`BLOCKED: out-of-scope untracked file(s): <file-list>`
where `<file-list>` is the comma-separated list of blocking paths. Do NOT set `phase: done` when the gate fires; the task remains in its current phase so the operator can inspect and manually remove the files.
```

  Preserve the existing "If the list is empty, proceed normally." sentence that follows.
- **Commit:** `docs(mill-go): self-resolve Handoff scope-violations cleanup gate`

### Card 11: Fix mill-go's stale Step 0b operator-prompt framing

- **Context:** none
- **Edits:**
  - `plugins/mill/skills/mill-go/SKILL.md`
- **Creates:** none
- **Deletes:** none
- **Moves:** none
- **Requirements:**

  This card must run after batches 2 and 3 land (both remove the operator prompts this line describes) — the `depends-on: [3]` edge on this batch already guarantees that ordering; this card just documents which prior batches its accuracy depends on.

  In `## Entry`, `**Step 0b: Load \`mill:conversation\`.**` currently reads exactly:

```
**Step 0b: Load `mill:conversation`.** Load the `mill:conversation` skill via the Skill tool, unconditionally, immediately after Step 0 and before any other Entry step or phase. This file's `### Stuck escalation` prompts (in `## Agent-mode dispatch`) and the holistic-rounds-exhausted prompt (in `## Holistic code review`) are operator-facing prompts that depend on `mill:conversation`'s numbered-options rule (banning `AskUserQuestion`) being active, so it must be loaded before any of those prompts can be built.
```

  Replace it with:

```
**Step 0b: Load `mill:conversation`.** Load the `mill:conversation` skill via the Skill tool, unconditionally, immediately after Step 0 and before any other Entry step or phase. mill-go no longer surfaces any operator-facing prompt (the former `### Stuck escalation` prompts and the holistic-rounds-exhausted prompt are now unconditional self-resolve-then-escalate or halt paths — see `### Stuck escalation` and `## Holistic code review`); this skill is loaded defensively in case a future addition needs its numbered-options convention.
```
- **Commit:** `docs(mill-go): fix stale Step 0b operator-prompt framing`

## Batch Tests

`verify: null` — this batch edits only `plugins/mill/skills/mill-go/SKILL.md`'s `## Handoff` section, a prose file interpreted by Claude Code at skill-invocation time. `_nit_gate.py` is read-only Context for Card 8 (to confirm the file-matching convention it mirrors) and is not modified. There is no runnable test surface for this batch. Correctness is verified by plan review (byte-exact old/new text matching against the actual worktree source) and, downstream, by mill-go's code review reading the resulting diff.
