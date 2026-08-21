# Batch: validator-checks-skill-doc-sync

```yaml
task: "mill-plan SKILL.md: Phase Plan Review gate, convergence, and DAG-validation correctness bugs"
batch: validator-checks-skill-doc-sync
number: 3
cards: 1
verify: null
depends-on: [1, 2]
```

## Batch Scope

This batch carries the two small `mill-plan/SKILL.md` Step 1.5 fix-table edits that Batch 2's
#887 and #868 cards deliberately left out (to keep Batch 2 under the `batch-oversized` context-token
cap — see Batch 2's own Batch Scope note). Depends on Batch 1 (both touch `mill-plan/SKILL.md`;
different, non-overlapping rows in the same Step 1.5 fix table — Batch 1 touches the
`out-of-worktree-target` row only) to avoid `parallel-modifies-overlap`, and on Batch 2 (this
batch's fix-table text describes the check behavior Batch 2 implements — read after write, in
sequence, even though the two batches share no file). `verify: null` — pure `mill-plan/SKILL.md`
prose, nothing to run (same rationale as Batch 1).

## Cards

### Card 11: #887 + #868 — Step 1.5 fix-table sync for the two new/changed validator checks

- **Context:** none
- **Edits:**
  - `plugins/mill/skills/mill-plan/SKILL.md`
- **Creates:** none
- **Deletes:** none
- **Moves:** none
- **Requirements:**
  In the Step 1.5 fix table, add a new row immediately after the existing `parallel-modifies-overlap`
  row: `| cross-batch-creates-no-depends-on | If one batch logically depends on the other, add the
  missing \`depends-on\` edge to the dependent batch — both the per-batch file's frontmatter
  \`depends-on:\` and the overview's Batch Index entry for that batch, per the existing
  \`depends-on-batch-mismatch\` discipline (both sides must name the identical dependency set). If
  the dependency is genuinely ambiguous (e.g. it's unclear which batch should own the edge), halt —
  not auto-fixable. |` (match the existing table's column-alignment style loosely — exact whitespace
  padding is not required, GFM tables render correctly regardless). This documents the
  `cross-batch-creates-no-depends-on` check Batch 2's Card 8 adds to `_plan_validate.py`.

  In the same table, replace the `non-existent-path` row's mechanical-fix cell — currently "A path
  declared as a `Creates:` target anywhere in this plan counts as existing for `Context:`/`Edits:`
  purposes; this row fires only for paths that are neither on disk nor declared as a `Creates:`
  target anywhere in the plan. If the path is a typo of an existing file, correct it. If it is meant
  to be a new `Creates:` target that does not yet appear anywhere in the plan, add it as a `Creates:`
  entry in the appropriate card. If neither applies, the planner intended to read a file that does
  not exist — halt; this is not mechanically fixable." — with the same text plus one new sentence
  inserted before the final "If neither applies..." sentence: "For a `Context:`-only reference (never
  `Edits:`/`Creates:`/`Deletes:`) to a not-yet-existing path that IS confirmed git-ignored under its
  own source root, this check no longer fires at all — no fix needed; that is the intended,
  already-passing case for a runtime-produced, gitignored artefact. If neither applies..." (i.e.,
  splice the new sentence in, keeping "If neither applies, the planner intended..." as the final
  sentence, unchanged). This documents the gitignore-aware soft-fail Batch 2's Card 10 adds to
  `_check_non_existent_path`.
- **Commit:** `docs(mill-plan): sync Step 1.5 fix table for cross-batch-creates-no-depends-on and gitignore-aware non-existent-path`

## Batch Tests

Pure `mill-plan/SKILL.md` prose — no Python code changes, nothing to run. `verify: null`.
