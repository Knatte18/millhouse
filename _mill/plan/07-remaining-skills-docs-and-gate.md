# Batch: remaining-skills-docs-and-gate

```yaml
task: Remove batch review (plan-review.batch / code-review.batch)
batch: remaining-skills-docs-and-gate
number: 7
cards: 3
verify: PYTHONPATH= uv run --project plugins/mill python plugins/mill/unit_tests/run-all.py
depends-on: [6]
```

## Batch Scope

Removes the last references to per-batch review from `mill-plan/SKILL.md`, `mill-go2/SKILL.md` and `doc/backlog.md`, then runs the discussion's final grep gate and the full unit suite as the task's acceptance check.
`doc/turn-reduction-audit.md` is a point-in-time audit report and is deliberately left unedited.
`SKILLS.md` needs no regeneration: no changed skill's `description:` mentions batch review.

## Cards

### Card 20: Drop per-batch plan review from mill-plan/SKILL.md

- **Context:**
  - `plugins/mill/scripts/millpy-review-plan.py`
- **Edits:**
  - `plugins/mill/skills/mill-plan/SKILL.md`
- **Creates:** none
- **Deletes:** none
- **Moves:** none
- **Requirements:**
  In `plugins/mill/skills/mill-plan/SKILL.md`, grep for `--holistic-only|--no-holistic|plan-review\.batch|per-batch|RE_BATCH|batch plan review|batch review` and fix every hit that refers to per-batch *plan review* (hits about plan batches, per-batch `verify:`, per-batch files or per-batch frontmatter are unrelated and stay):
  - Phase: Plan Review step 2's Agent-mode dispatch: `<args> = --holistic-only`, plus one `--skip-check <name>` per entry → `<args>` is one `--skip-check <name>` per entry in `plan_skip_checks` (empty when `plan_skip_checks` is empty).
  - The same change at step 3.5's ERROR-only-aggregate retry Agent-mode dispatch ("exactly as step 2's dispatch above").
  - Delete the two sentences "Because plan batch review is disabled in this hub (`roles.plan-review.batch.reviewer: null`), the agent-mode branch targets the holistic scope only." and "If per-batch plan review is ever enabled, the SKILL loops the three-step flow once per enabled scope."
  - The cost-line sentence: drop the parenthetical about a per-batch scope printing one line per scope; keep "with `<type> = plan` and `<scope> = holistic`".
  - Delete the subprocess branch's scope-flag paragraph (`--holistic-only` / `--no-holistic` / "Default — both run per the `roles.plan-review.batch.reviewer` and `roles.plan-review.holistic.reviewer` config keys" / "Append the flag to the inner ... invocation when needed"); keep the following sentence about appending `--skip-check <name>`.
  - The `--revise` namespacing paragraph: "`RE_SIMPLE`/`RE_BATCH` (the fixed-shape filename regexes `discover_round` matches against)" → "`RE_SIMPLE` (the fixed-shape filename regex `discover_round` matches against)" (a text-only edit, no file read needed).
- **Commit:** `docs(mill-plan): drop per-batch plan review wording and --holistic-only`

### Card 21: Narrow mill-go2 fixer scope wording and the backlog config slot

- **Context:**
  - `plugins/mill/skills/mill-go-base/SKILL.md`
- **Edits:**
  - `plugins/mill/skills/mill-go2/SKILL.md`
  - `doc/backlog.md`
- **Creates:** none
- **Deletes:** none
- **Moves:** none
- **Requirements:**
  In `plugins/mill/skills/mill-go2/SKILL.md`, in the fixer fork-fallback paragraph, change "`{scope}` is the batch name, or `holistic`." to "`{scope}` is `holistic`."
  Leave the implementer fork-fallback text (`{batch_name}`, "Cold fallback, once per batch") unchanged: it is about plan batches.
  Check the frontmatter `description:`; it says "the first fixer dispatch per scope/round", which stays correct.

  In `doc/backlog.md`, in the "Config wiring" line of the cluster-reviewer entry, change `review.<type>.{reviewer|batch|holistic}` to `review.<type>.{reviewer|holistic}`.
- **Commit:** `docs: drop the per-batch fixer scope and backlog config slot`

### Card 22: Final grep gate

- **Context:**
  - `_mill/discussion.md`
  - `plugins/mill/scripts/_config.py`
  - `plugins/mill/unit_tests/test-config.py`
  - `plugins/mill/scripts/millpy-review-summary.py`
- **Edits:** none
- **Creates:** none
- **Deletes:** none
- **Moves:** none
- **Requirements:**
  Run from the worktree root:

  ```
  git grep -n -E "plan-review\.batch|code-review\.batch|BATCH_REVIEWER|review-(plan|code)-batch|fixer-batch-brief|rename_detect_pct|diff_scope_threshold|--holistic-only|--no-holistic|--batch-name|RE_BATCH|detect_resume_round|bulk_files_with_diff|_moves_check"
  ```

  Every hit must fall in one of these allowed places:
  - `doc/turn-reduction-audit.md` (an allowed grep location only, no file read needed);
  - anything under `_mill/`;
  - `RENAMED_KEY_HINTS` entries in `plugins/mill/scripts/_config.py`;
  - `plugins/mill/unit_tests/test-config.py`'s stale-key and template/`ENV_REGISTRY` absence tests, and synthetic fixture templates in that file;
  - `plugins/mill/scripts/millpy-review-summary.py`'s own `_RE_BATCH` (the pattern `RE_BATCH` matches it; it is kept on purpose; no file read needed).

  Any other hit is a straggler from an earlier card: report `stuck_type: logic` naming each file and line, and do not edit files in this card.
- **Commit:** none

## Batch Tests

`verify:` runs the whole unit suite unscoped.
Justification: the discussion's Testing section makes a green full suite the task's acceptance bar, and this task deletes shared helpers (`RE_BATCH`, `detect_resume_round`, `bulk_files_with_diff`, `_moves_check.py`) and templates that any test module could import or render; batches 1–6 each ran only their own scoped tests.
The full suite runs in well under a minute.
Card 22's grep gate covers text references that no test exercises.
