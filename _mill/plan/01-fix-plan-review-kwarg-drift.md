# Batch: fix-plan-review-kwarg-drift

```yaml
task: 'mill-plan: Phase Plan Review''s 4b/4c/4d re-validate gate says "7 kwargs", drops done_gate'
batch: fix-plan-review-kwarg-drift
number: 1
cards: 1
verify: null
depends-on: []
```

## Batch Scope

This batch corrects a doc-consistency drift in `plugins/mill/skills/mill-plan/SKILL.md`: Phase: Plan's own self-validate call already passes 8 keyword arguments to `_plan_validate.run` (including `done_gate`), but Phase: Plan Review's steps 4b, 4c, and 4d each describe their own re-validate call as reusing "the identical 7 keyword arguments" / "the same 7 kwargs" and omit `done_gate` from the enumerated list. This is the task's entire scope — one file, three prose sites, no code change. There is no external interface for a later batch to consume; this is the only batch.

## Cards

### Card 1: Align 4b/4c/4d's `_plan_validate.run` kwarg-count prose and enumeration with Phase: Plan's 8-kwarg call

- **Context:** none
- **Edits:**
  - `plugins/mill/skills/mill-plan/SKILL.md`
- **Creates:** none
- **Deletes:** none
- **Moves:** none
- **Requirements:**
  Make three isolated text substitutions in `plugins/mill/skills/mill-plan/SKILL.md`, each confined to its own sentence — no other prose in the file changes.

  1. In step 4b's full-validate-gate sentence, replace the phrase `the identical 7 keyword arguments (\`root\`, \`git_root\`, \`wiki_root\`, \`skip_checks=plan_skip_checks\`, \`parent_branch\`, \`max_cards_per_batch\`, \`max_batch_context_tokens\`) that Phase: Plan's own self-validate call already uses` with `the identical 8 keyword arguments (\`root\`, \`git_root\`, \`wiki_root\`, \`skip_checks=plan_skip_checks\`, \`parent_branch\`, \`max_cards_per_batch\`, \`max_batch_context_tokens\`, \`done_gate\`) that Phase: Plan's own self-validate call already uses`.

  2. In step 4c's full-validate-gate sentence, replace the phrase `the same 7 kwargs (\`root\`, \`git_root\`, \`wiki_root\`, \`skip_checks=plan_skip_checks\`, \`parent_branch\`, \`max_cards_per_batch\`, \`max_batch_context_tokens\`)` with `the same 8 kwargs (\`root\`, \`git_root\`, \`wiki_root\`, \`skip_checks=plan_skip_checks\`, \`parent_branch\`, \`max_cards_per_batch\`, \`max_batch_context_tokens\`, \`done_gate\`)`.

  3. In step 4d's full-validate-gate sentence, replace the phrase `call \`_plan_validate.run\` with the same 7 kwargs, apply Step 1.5's mechanical-fix table` with `call \`_plan_validate.run\` with the same 8 kwargs, apply Step 1.5's mechanical-fix table`.

  Do not touch Phase: Plan's own self-validate prose (the "same eight keyword arguments" sentence) or its fenced `_plan_validate.run(...)` code block — both are already correct and are the source of truth these three substitutions match against. Do not touch any other occurrence of the word "kwargs" or "keyword arguments" elsewhere in the file.

  After editing, grep the file for the literal strings `7 keyword arguments` and `same 7 kwargs` — both must return zero matches — and grep for `done_gate` scoped to these three sites plus Phase: Plan's own site — all four must now name it.
- **Commit:** `docs(mill-plan): align 4b/4c/4d re-validate kwarg enumeration with Phase: Plan's 8-kwarg call`

## Batch Tests

Pure prose edit inside `SKILL.md`; no runnable test exercises this file's narrative text, so `verify: null`. Verification is manual text inspection, performed as the card's own last Requirements step: after editing, `grep -n "7 keyword arguments\|same 7 kwargs" plugins/mill/skills/mill-plan/SKILL.md` must return no lines, and the three edited sentences (4b, 4c, 4d) must each read "8"/"eight" and list `done_gate` exactly as Phase: Plan's line 251 does.
