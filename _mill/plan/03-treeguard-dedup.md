# Batch: treeguard-dedup

```yaml
task: 'mill-go-base: remove subprocess/psmux dispatch branches'
batch: 'treeguard-dedup'
number: 3
cards: 2
verify: PYTHONPATH= uv run --project plugins/mill python plugins/mill/unit_tests/run-all.py --only test-guards.py test-mill-go-variants.py test-skill-helper-drift.py
depends-on: [2]
```

## Batch Scope

Collapses the twelve near-verbatim tree-guard checkpoint paragraphs in `SKILL.md` into one named block plus twelve one-line references.
It runs after batch 2 because the strip already removed the one sentence that differed between copies ("this does not apply to the subprocess/psmux branch"), leaving text that is mechanically identical and therefore safe to fold.
It runs before batch 4 because four of the twelve references live in sections that batch 4 moves into companion files, and those companion files must be able to reference the named block by its final name and path.

Batch-local decision: the named block is placed in `## Agent-mode dispatch`, in the slot vacated by the deleted poll-loop and cleanup blocks, so it stays on the hot path that batch 4's `extract-cold-path` decision deliberately keeps inline.

## Cards

### Card 12: Define the named tree-guard checkpoint block

- **Context:**
  - `_mill/discussion.md`
- **Edits:**
  - `plugins/mill/skills/mill-go-base/SKILL.md`
- **Creates:** none
- **Deletes:** none
- **Moves:** none
- **Requirements:**
  Add one block to `## Agent-mode dispatch`, positioned between the `**Agent-mode properties:**` bullet list and the `**Why not fork?**` paragraph.
  Give it the bold lead-in `**Tree-guard checkpoint block.**` so it is addressable by name, and define exactly two forms:
  - a **pre-dispatch form**, invoked immediately before a dispatch;
  - a **post-dispatch form**, invoked immediately after that dispatch returns (for review dispatches, after prepare through finalize, including any validator-fix or retry re-invocation cycle within the same dispatch).
  Both forms carry the same body, stated once: `result = _treeguard.check_and_restore(worktree_root, "_mill", git_root=git_root)`, then `if result["triggered"]: _status.append_recovery_log(status_path, result["timestamp"], result["restored_paths"])`.
  Move the two `signature:` lines currently attached to the first checkpoint occurrence in `### 3. Code Review loop` into this block verbatim, so each helper's signature is still documented inline exactly once, per the file's own `**Helper signatures are documented inline.**` principle: `signature: _treeguard.check_and_restore(worktree: Path, tracked_root: str = "_mill", *, git_root: Path | None = None) -> dict` returning `{"triggered": bool, "restored_paths": list[str], "timestamp": str | None}`, and `signature: _status.append_recovery_log(status_path: Path, timestamp: str, restored_paths: list[str]) -> None`.
  Carry over, once, the rationale sentence that currently appears at the post-dispatch occurrences: the post-dispatch form brackets the out-of-process execution window that `worktree_snapshot_guard` cannot see, and the block must not be invoked from inside the Agent-mode dispatch pattern's own numbered steps — it belongs at each call site, since that pattern also serves non-review dispatch.
  State that the block is referenced by name from this file and from the skill's companion files, and that a companion file names it as `**Tree-guard checkpoint block**` in `plugins/mill/skills/mill-go-base/SKILL.md`.
  Do not remove any existing checkpoint paragraph in this card; card 13 does that.
- **Commit:** `docs(mill-go-base): define the named tree-guard checkpoint block`

### Card 13: Replace the twelve checkpoint paragraphs with references

- **Context:**
  - `_mill/discussion.md`
- **Edits:**
  - `plugins/mill/skills/mill-go-base/SKILL.md`
- **Creates:** none
- **Deletes:** none
- **Moves:** none
- **Requirements:**
  Enumerate every occurrence of `_treeguard.check_and_restore(` in the file and replace each paragraph with a single line naming the block and the form.
  There are twelve, and the file states this count itself in the sentence "All 11 other tree-guard checkpoints in this file (5 more in this section, 7 in `## Holistic code review`) share this identical signature and guard shape." — delete that sentence too, since after this card no occurrence carries an inline signature for the others to be measured against.
  The twelve are, in file order: in `### 3. Code Review loop`, the loop-header checkpoint before the `reviewing-{batch_name}-r{N}` phase append, sub-step 2's pre-dispatch, sub-step 2's post-dispatch, sub-step 4.5's pre-dispatch, and sub-step 4.5's post-dispatch; in `## Holistic code review`, step 2's checkpoint before the `holistic-reviewing` phase append, step 3's pre-dispatch, step 3's post-dispatch, sub-step 3.5's pre-dispatch, sub-step 3.5's post-dispatch, sub-step 3.6's pre-dispatch, and sub-step 3.6's post-dispatch.
  Each replacement line must state which form applies, where it fires relative to the surrounding step, and point at the named block by its exact name.
  Two of the twelve are not dispatch-bracketing and fire before a phase-append-and-commit rather than around an agent call — the `### 3. Code Review loop` loop-header one and `## Holistic code review` step 2's.
  Use the pre-dispatch form for both and keep their existing "before the append_phase/commit below" positional wording so the call site stays unambiguous.
  Preserve, at their current sites, the two sentences that are site-specific rather than boilerplate: the `### 3. Code Review loop` loop-header note about closing the same-file modify-then-delete window, and sub-step 3.6's requirement that its pre-dispatch checkpoint fires before re-running sub-step 3 with the swapped reviewer.
  After this card, `_treeguard.check_and_restore(` must appear exactly once in the file — inside the named block.
- **Commit:** `docs(mill-go-base): replace the twelve tree-guard paragraphs with block references`

## Batch Tests

`verify:` runs the same three existing tests as batch 2 via `run-all.py --only`.
`test-skill-helper-drift.py` is the load-bearing one for this batch: it extracts every `_<module>.<fn>(` reference from each SKILL.md and asserts it resolves to a shipped function, so it directly covers card 13's rewrite of twelve `_treeguard.check_and_restore(` / `_status.append_recovery_log(` call sites down to one.
`test-guards.py` and `test-mill-go-variants.py` stay in the list as regression coverage for the file-level invariants (wiki-cwd allowlist, `<VARIANT_LABEL>` parameterization) that any large edit to this file can disturb.

The new guard `test-mill-go-base-agent-only.py` is still red at this point — its companion-file assertions do not go green until batch 4 — so it is deliberately not in this batch's `--only` list.
