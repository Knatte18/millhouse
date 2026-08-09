# Batch: mill-go-treeguard-explicit-guard

```yaml
task: 'mill-go/mill-plan/mill-merge: dispatch-classification, watchdog, entry-gate, and implementer-compliance gaps (round 2)'
batch: mill-go-treeguard-explicit-guard
number: 2
cards: 2
verify: null
depends-on: [1]
```

## Batch Scope

`#783`: `mill-go/SKILL.md` has 12 tree-guard checkpoint call sites (confirmed by full-file grep for `_treeguard`/`check_and_restore`/`append_recovery_log` — exactly 12 matches, no 13th site), spanning "### 3. Code Review loop" (lines ~638, 675, 710, 775, 780) and "## Holistic code review" (lines ~1026, 1038, 1079, 1088, 1093, 1126, 1133).
Every one of the 12 currently documents the guard as prose only ("on trigger, call `_status.append_recovery_log(...)`") with no explicit `if result["triggered"]:` structure — this is the actual crash bug: `_treeguard.check_and_restore` returns `result["timestamp"] = None` whenever `result["triggered"]` is `False`, and `_status.append_recovery_log(status_path: Path, timestamp: str, restored_paths: list[str]) -> None` raises `TypeError` if handed `None` for `timestamp`. An orchestrator following today's unguarded prose literally would call `append_recovery_log` unconditionally every time, crashing on every non-triggered checkpoint.
This batch rewrites all 12 call sites to show the guard explicitly, and adds one `signature:` note (at the first occurrence only, line ~638) for both `_treeguard.check_and_restore` and `_status.append_recovery_log`, per this file's own established convention of stating a helper's signature once at its first occurrence with a forward-reference note (e.g. the existing `_parent_branch.resolve` signature at line ~612 and `_status.phase_entry_timestamp` at line ~664) rather than repeating it at every call site.
This batch depends on batch 1 (`mill-go-dispatch-classification-observability`) purely because both edit `plugins/mill/skills/mill-go/SKILL.md` and the plan DAG requires a strict order between any two batches sharing an `Edits:` target file — the two batches' edit regions do not overlap (batch 1 touches step 4's classification bullets at lines ~258-357 and step 6.5 at lines ~325-343; this batch touches the 12 tree-guard sites at lines ~638-1133) and carry no logical dependency on each other's content.
No batch-local decisions differ from `## Shared Decisions` in the overview.

## Cards

### Card 7: Add explicit `if result["triggered"]:` guard (+ signature note) to the 5 tree-guard sites in "### 3. Code Review loop"

- **Context:** none
- **Edits:**
  - `plugins/mill/skills/mill-go/SKILL.md`
- **Creates:** none
- **Deletes:** none
- **Moves:** none
- **Requirements:**
  Rewrite each of the 5 tree-guard checkpoint call sites inside "### 3. Code Review loop" (at lines ~638, 675, 710, 775, 780 as of this writing — locate by the literal string "Tree-guard checkpoint" within that section, do not rely on line numbers which will have shifted after batch 1's edits landed) from today's prose form ("call `_treeguard.check_and_restore(worktree_root, "_mill", git_root=git_root)` — on trigger, call `_status.append_recovery_log(...)`") to an explicit two-line form showing the guard, e.g.:
  `result = _treeguard.check_and_restore(worktree_root, "_mill", git_root=git_root)` then, on its own line, `if result["triggered"]: _status.append_recovery_log(status_path, result["timestamp"], result["restored_paths"])`.
  Preserve every site's surrounding sentence exactly (the "pre-dispatch"/"post-dispatch"/"immediately before the append_phase/commit below" qualifiers, the "Agent-mode only" scoping note, and any adjacent sentence about the subprocess/psmux branch being unaffected) — only the guard's own two-line shape changes at each of the 5 sites, nothing else in the surrounding prose.
  At the first of the 5 sites (the one inside "For each round `N` from 1 to `roles.code-review.batch.rounds`:", immediately preceding the existing `_status.append_phase(status_path, f"reviewing-{batch_name}-r{N}", ...)` line) add one new sentence immediately after the rewritten guard: the confirmed signatures — `_treeguard.check_and_restore(worktree: Path, tracked_root: str = "_mill", *, git_root: Path | None = None) -> dict` returning `{"triggered": bool, "restored_paths": list[str], "timestamp": str | None}`; `_status.append_recovery_log(status_path: Path, timestamp: str, restored_paths: list[str]) -> None` — with a forward-reference note that all 11 other tree-guard checkpoints in the file (5 more in this section, 7 in "## Holistic code review") share this identical signature and guard shape.
  Do not add the signature note at any of the other 4 sites in this section.
- **Commit:** `docs(mill-go): add explicit treeguard guard + signature note to Code Review loop sites`

### Card 8: Add explicit `if result["triggered"]:` guard to the 7 tree-guard sites in "## Holistic code review"

- **Context:** none
- **Edits:**
  - `plugins/mill/skills/mill-go/SKILL.md`
- **Creates:** none
- **Deletes:** none
- **Moves:** none
- **Requirements:**
  Rewrite each of the 7 tree-guard checkpoint call sites inside "## Holistic code review" (at lines ~1026, 1038, 1079, 1088, 1093, 1126, 1133 as of this writing — locate by the literal string "Tree-guard checkpoint" within that section) from today's prose form to the identical explicit two-line guard shape Card 7 applied: `result = _treeguard.check_and_restore(worktree_root, "_mill", git_root=git_root)` then `if result["triggered"]: _status.append_recovery_log(status_path, result["timestamp"], result["restored_paths"])`.
  Preserve every site's surrounding sentence exactly, including the two sites with additional numbering/indentation context (the site inside step 3.6's rate-limit-fallback sub-step `3.` which is indented as a nested list item, and its paired post-redispatch continuation) — match each site's existing indentation level, only the guard's own two-line shape changes.
  Do not add a signature note at any of these 7 sites — Card 7 already added the one signature note (at the first occurrence in "### 3. Code Review loop") with a forward-reference covering all 12 sites; do not duplicate it here.
- **Commit:** `docs(mill-go): add explicit treeguard guard to Holistic code review sites`

## Batch Tests

`verify: null` — this batch is a mechanical `SKILL.md` prose rewrite (no Python code changes; `_treeguard.py`/`_status.py`'s own implementations are already correct per `_mill/discussion.md`'s Decisions, out of scope here) with no executable surface.
Verification is confirming all 12 call sites now show the explicit `if result["triggered"]:` guard, that exactly one signature note is present (at the first "### 3. Code Review loop" site) and matches `_treeguard.py`/`_status.py`'s real signatures verbatim, and that no site's surrounding prose (Agent-mode-only scoping, pre/post-dispatch qualifiers, indentation) was disturbed.
