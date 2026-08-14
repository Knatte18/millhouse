Both conflict hunks in `plugins/mill/skills/mill-plan/SKILL.md` have been resolved and the file staged.

- Lines 68-74 (Entry step 4 phase table): combined both sides' disjoint edits — kept `main`'s widened `phase: discussing` row condition (`, or matching ^discussion-fix-r\d+$`, an unrelated #821 fix) together with HEAD's new `phase: blocked` row (the direct surface-`blocked_reason`-and-halt text implementing this task's #852 design, per discussion.md).
- Lines 365-372 (Step 1.5 fix table): combined both sides — kept HEAD's corrected `verify-excludes-edited-tagged-test` remedy (the `&&`-chained-invocation fix for #853) together with `main`'s three additional, unrelated fix-table rows (`verify-malformed-cwd`, `verify-mixed-cwd`, `verify-full-suite`), which are cross-referenced elsewhere in the file (e.g. the `verify-full-suite` skip-check escape hatch at line ~261) and are not duplicates.

File staged via `git -C /home/knatte/Code/millhouse/wts/mill-plan-step6-and-fixtable-bugs add plugins/mill/skills/mill-plan/SKILL.md`. No `git merge --continue` was run.

{"status":"success"}