# Batch: cross-references

```yaml
task: 'mill-merge: run the deterministic path as one script'
batch: cross-references
number: 5
cards: 2
verify: PYTHONPATH= uv run --project plugins/mill python -m py_compile plugins/mill/integration_tests/test-merge.py
depends-on: [4]
```

## Batch Scope

Retargets every reference to the old `mill-merge` step numbers (Step 2/4/5/7, Entry Step 4, "Card 1") at the new script and skill sections, so no doc points at a step that no longer exists.
Text-only edits;
no behavior change.

## Cards

### Card 9: retarget skill and CLAUDE.md references

- **Context:**
  - `plugins/mill/skills/mill-merge/SKILL.md`
  - `plugins/mill/scripts/_merge.py`
- **Edits:**
  - `plugins/mill/skills/mill-merge-in/SKILL.md`
  - `plugins/mill/skills/mill-status/SKILL.md`
  - `plugins/mill/skills/mill-go-base/SKILL.md`
  - `CLAUDE.md`
- **Creates:** none
- **Deletes:** none
- **Moves:** none
- **Requirements:**
  Name the new locations by stable identifier: the step functions in `plugins/mill/scripts/_merge.py` (`step_parent`, `step_merge_in_check`, `step_cleanup_commit`, `step_squash`, `step_wiki_done`) and the section headings of the rewritten `plugins/mill/skills/mill-merge/SKILL.md` (`## Callback: merge-in`, `## Callback: confirm-parent`).
  - `plugins/mill/skills/mill-merge-in/SKILL.md`:
    Entry step 3's "as of the Card 1 fix (`mill-merge/SKILL.md` Step 2)" sentence -> `mill-merge` calls this skill only from its `merge-in` callback (`## Callback: merge-in`), always passing its resolved parent branch;
    the "Liveness check (#817)" paragraph's two references to `mill-merge/SKILL.md` Entry Step 4 -> the dead-parent protocol and message texts implemented by `_merge.step_parent` (whose status-absent branch also skips the liveness check);
    the "#977 scenario" sentence -> `mill-merge` passes its status-absent `git.base_branch` fallback through the `merge-in` callback;
    the "Caller propagation (#977 follow-up)" paragraph -> the caller is `mill-merge`'s `## Callback: merge-in`, which re-runs `millpy-merge.py` with `--parent <substituted>` on every later re-run;
    the rebind-safety paragraph's reference to `mill-merge/SKILL.md` Entry Step 4's warning -> `_merge.step_parent`, which resolves `status_path` through the slug-driven active-hub lookup;
    the "dispatched from `mill-merge`'s Step 2" / "`mill-merge`'s own Entry Step 4" sentence -> the `merge-in` callback / `millpy-merge.py`'s parent step;
    the Step 3.5 `millpy-bg` callout "first `millpy-bg` call site in `mill-merge-in/SKILL.md` or `mill-merge/SKILL.md`" -> drop the `mill-merge` half;
    the Step 6 report template line "If this skill was called from mill-merge Step 2, that caller must rebind ..." -> "If this skill was called from mill-merge's merge-in callback, mill-merge must pass --parent <substituted_parent_branch> on every later millpy-merge.py re-run."
    Keep all other wording.
  - `plugins/mill/skills/mill-status/SKILL.md` table: `mill-merge Step 5 (both PR-creation paths)` -> `mill-merge branch-protection fallback (_merge.step_squash)`;
    `mill-merge Step 7 (post-squash)` -> `mill-merge after the squash (_merge.step_wiki_done)`.
  - `plugins/mill/skills/mill-go-base/SKILL.md` line containing `mirrors mill-merge's own Step 5 fallback` -> `mirrors mill-merge's status-absent wiki fallback (_merge.step_phase_gate)`.
    Change nothing else in that file.
  - `CLAUDE.md` hard-constraints bullet: `mill-merge` Step 4's cleanup commit -> `mill-merge`'s cleanup commit (`_merge.step_cleanup_commit`).
  Gate: after the edits, `grep -nE "mill-merge(/SKILL.md)?\`?'?s? (own )?(Entry )?Step [0-9]|Card 1 fix" plugins/mill/skills/mill-merge-in/SKILL.md plugins/mill/skills/mill-status/SKILL.md plugins/mill/skills/mill-go-base/SKILL.md CLAUDE.md` prints nothing.
- **Commit:** `docs(mill): retarget old mill-merge step references to millpy-merge`

### Card 10: retarget integration-test comments

- **Context:**
  - `plugins/mill/scripts/_merge.py`
- **Edits:**
  - `plugins/mill/integration_tests/test-merge.py`
- **Creates:** none
- **Deletes:** none
- **Moves:** none
- **Requirements:**
  Comment-only edits in `plugins/mill/integration_tests/test-merge.py`; no code line changes.
  The module docstring line "Flow under test (mirrors mill-merge SKILL.md step numbering):" -> "Flow under test (mirrors the `_merge.py` step order):", and retarget each numbered item in that docstring list that names a mill-merge step to the matching `_merge.py` step function name.
  The comment `# === Child cleanup commit (mirror mill-merge Step 4) ===` -> `(mirror _merge.step_cleanup_commit)`.
  The comment citing "mill-merge/SKILL.md's Step 5" for the dirty-parent check -> `_merge.step_squash`'s dirty-parent check.
  The comment `# --- Perform squash-merge with restore step (mill-merge Step 5) ---` -> `(mirror _merge.step_squash)`.
  The comment "Mirror mill-merge's corrected Entry Step 5 phase-gate logic ... this logic is orchestration prose in SKILL.md, not an importable function" -> it mirrors `_merge.step_phase_gate` (now importable; the test keeps its own replica).
  Leave comments about `mill-merge-in` steps unchanged.
- **Commit:** `test(mill-merge): retarget integration-test comments to _merge.py steps`

## Batch Tests

`verify:` byte-compiles `plugins/mill/integration_tests/test-merge.py` to prove card 10's comment edits left it syntactically valid.
Card 9 edits markdown only;
its grep gate runs inside the card.
