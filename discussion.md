# Discussion: 22 (A) — SKILL.md round-2 fixes

```yaml
task: 22 (A) — SKILL.md round-2 fixes
slug: skill-md-fixes-2
status: discussing
parent: main
```

## Problem

Two issues in `mill-plan`'s SKILL.md were filed during the `disable-per-batch-reviews` and `wiki-enhance` task runs (issues #164 and #169). Both concern step 1.5 of the Plan Review phase, which runs the plan validator as a pre-LLM gate:

1. The mechanical-fix table has no row for the `wiki-config-mutation` validator check. When a batch modifies `wiki/config.yaml`, the validator emits this check with the message "use --skip-validate if a bootstrap card is present" — but mill-plan has no documented procedure for handling it, forcing the planner to reason outside the table.

2. The SKILL.md states "As of today, mill-plan never passes `--skip-validate`" — which directly contradicts the validator's own message recommending `--skip-validate` for this exact scenario.

A third issue (#163, `resolve_git_root` and `sync_pull` signature errors in mill-start/mill-go) was already fixed by task 17(A) (`82546d8`). No work remains for it.

## Scope

**In:**
- Add a `wiki-config-mutation` row to the step-1.5 fix table in `plugins/mill/skills/mill-plan/SKILL.md`.
- Update the "mill-plan never passes --skip-validate" sentence in the same file to reflect the new row.

**Out:**
- `_plan_validate.py` — no changes to validator logic or error messages.
- `mill-start/SKILL.md` — no changes needed (issue C is closed).
- `mill-go/SKILL.md` — not affected.
- Any other file.

## Decisions

### wiki-config-mutation row: conditions for --skip-validate

- **Decision:** The row allows `--skip-validate` under two conditions: (a) a bootstrap card is present (a card whose body explains why the config.yaml change is safe mid-flight for the currently-shipping task), or (b) the modified keys are provably unused — defined as key *removal or rename* where zero grep hits across `scripts/` and `skills/` confirm no existing code references them. If neither holds, the instruction is to halt.
- **Rationale:** The validator message names condition (a). Issue #169 adds condition (b) for the dead-key-removal case, where the risk cited by the validator (self-applying layout change) is not present. Condition (b) is explicitly scoped to removal/rename: for key *addition* (where consuming code is also being added in the same plan), grep hits are zero before deployment, making the condition trivially — and incorrectly — satisfied. Key addition requires condition (a) or a halt.
- **Rejected:** Allowing `--skip-validate` unconditionally whenever `wiki-config-mutation` fires — too permissive, would mask real self-applying layout risks.

### wiki-config-mutation row: "fix" is invoking --skip-validate, not editing plan files

- **Decision:** The row describes an invocation change (add `--skip-validate` to the CLI re-run), not a plan file edit. The batch intentionally modifies `wiki/config.yaml`; there is nothing to correct in the plan itself.
- **Rationale:** All other fix-table rows correct plan files. This one cannot because the plan is structurally correct — only the validator's false-positive needs to be bypassed. The distinction must be explicit so mill-plan doesn't try to edit config.yaml references out of the plan.
- **Rejected:** Removing `wiki/config.yaml` from the batch's `Modifies:` list — that would make the plan inaccurate.

### wiki-config-mutation + other errors in same pass

- **Decision:** If `wiki-config-mutation` appears alongside other fixable errors, fix all the other errors per their rows first, then re-run with `--skip-validate`. The `--skip-validate` flag bypasses all validator checks on the re-run, so other fixed errors are not re-validated — that is acceptable since they were already mechanically corrected.
- **Rationale:** `--skip-validate` is all-or-nothing; there is no per-check skip. Fixing other errors first ensures no regressions slip through.
- **Rejected:** Halting when multiple error types are present — unnecessarily conservative.

### Justification documentation: commit message

- **Decision:** When mill-plan decides to use `--skip-validate` for `wiki-config-mutation`, it documents the justification (which condition was met and the grep evidence) in the validator-fix commit message.
- **Rationale:** The validator-fix pass has no fixer report file (that is only written during LLM review step 4c). The commit message is the natural audit trail for this decision.
- **Rejected:** Writing a separate note file — adds a new file type that nothing else reads.

### "never passes --skip-validate" sentence update

- **Decision:** Replace "As of today, mill-plan never passes `--skip-validate`." with "mill-plan passes `--skip-validate` only when the fix table instructs it — see the `wiki-config-mutation` row."
- **Rationale:** The current sentence flatly contradicts the new `wiki-config-mutation` row. The replacement is precise: it allows `--skip-validate` only via the table, not ad hoc.
- **Rejected:** Deleting the sentence entirely — the clarification that `--skip-validate` is not a general escape hatch is worth keeping.

## Technical context

- **Affected file:** `plugins/mill/skills/mill-plan/SKILL.md` — specifically the step-1.5 section (lines ~74–94 in the current version).
- **Fix table location:** The table is in the "Step 1.5: pre-review validator gate" subsection of Phase: Plan Review. Existing rows cover `non-existent-path`, `card-missing-field`, `card-numbering`, `depends-on-unknown`, `parallel-modifies-overlap`, `reads-not-backtick-path`, `all-files-touched-mismatch`, `missing-overview`, `batch-index-parse`. The new row is appended after `all-files-touched-mismatch` (before the two structural-halt rows).
- **Validator check definition:** `_plan_validate.py:620 — _check_wiki_config_mutation`. Fires when `wiki/config.yaml` appears in any batch's `Modifies:` or `Creates:`. Error message: "use --skip-validate if a bootstrap card is present". The check has no `card` field (it's batch-level).
- **--skip-validate flag:** `millpy-review-plan.py:49` — action store_true. When set, bypasses the entire `_plan_validate.run()` call and proceeds directly to the LLM reviewer.
- **Bootstrap card definition:** from `review-plan-holistic.md:30` — "an explicit bootstrap step for the currently-shipping task" that explains why the config.yaml change is safe mid-flight. A task running under the old layout cannot safely migrate its own state mid-flight.
- **Issue C already closed:** Task 17(A) commit `82546d8` fixed `resolve_git_root(Path.cwd())` → `resolve_git_root()` in mill-start, mill-plan, and mill-go. The `sync_pull` slug kwarg has been in the code since task 6. No changes needed.

## Testing

This task is a documentation-only change — no new Python code and no changes to existing Python helpers. There is nothing to unit-test or integration-test.

Manual verification: after the edit, read the changed SKILL.md and confirm:
1. The fix table has a `wiki-config-mutation` row that matches the decisions above.
2. The "never passes --skip-validate" sentence is updated.
3. No other text in the file was inadvertently modified.

## Q&A log

- **Q:** Is issue C (#163, resolve_git_root + sync_pull signatures) still open? **A:** No — fixed by task 17(A). No work needed.
- **Q:** Should the table row cover both "bootstrap card present" and "provably unused keys"? **A:** Yes, both conditions. Condition (b) is scoped to key removal/rename only; key addition always requires condition (a).
- **Q:** Where to document the --skip-validate justification? **A:** Validator-fix commit message (no fixer report exists at that stage).
- **Q:** If wiki-config-mutation co-occurs with other fixable errors, what to do? **A:** Fix the others first per their rows, then re-run with --skip-validate.
- **Q:** Is this scope limited to mill-plan SKILL.md only? **A:** Yes — no validator code changes, no other SKILL.md files.
