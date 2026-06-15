# Batch: fold-guard-allowlist

```yaml
task: "Fix mill-ghissues-to-tasks to refuse fold-ins into done and deferred tasks"
batch: "fold-guard-allowlist"
number: 1
cards: 6
verify: PYTHONPATH= uv run --project plugins/mill python plugins/mill/unit_tests/run-all.py --only test-fold.py
depends-on: []
```

## Batch Scope

This batch flips the fold guard from a frozen-phase denylist to an unclaimed-only
allowlist and propagates the change to every doc/code surface. It is one batch
because the change is a single semantic unit: the guard predicate in
`millpy-fold.py`, the constant removal it depends on, the test suite that pins
the new behavior, and the four documentation surfaces (two fold SKILLs, the
script docstring, and `CLAUDE.md`) that must all state the identical rule. The
external contract this batch establishes is the predicate **foldable iff
`status is None AND not deferred`** and the reason-bearing refusal message; the
`mill-ghissues-to-tasks` skill consumes that same predicate inline. All
batch-local work inherits the four `## Shared Decisions` in the overview without
deviation.

## Cards

### Card 1: Remove LOCKED_FOLD_PHASES constant from the wiki package

- **Context:**
  - `plugins/mill/scripts/millpy-fold.py`
- **Edits:**
  - `plugins/mill/scripts/wiki/__init__.py`
- **Creates:** none
- **Deletes:** none
- **Requirements:** Delete the `LOCKED_FOLD_PHASES = ("active", "ready-to-merge", "pr-pending")` assignment and its preceding `# Locked fold phases ...` comment (lines ~21-22) from `plugins/mill/scripts/wiki/__init__.py`. No other symbol in this module references the constant. Its two importers (`millpy-fold.py`, `test-fold.py`) drop the import in cards 2 and 3 of this same batch.
- **Commit:** `refactor(wiki): remove LOCKED_FOLD_PHASES constant`

### Card 2: Replace the fold guard with the unclaimed-only allowlist and rewrite the docstring

- **Context:**
  - `plugins/mill/scripts/wiki/_render.py`
  - `plugins/mill/scripts/wiki/_parse.py`
- **Edits:**
  - `plugins/mill/scripts/millpy-fold.py`
- **Creates:** none
- **Deletes:** none
- **Requirements:** Three edits to `plugins/mill/scripts/millpy-fold.py`. (1) Drop the constant from the import: change `from wiki import _client as wiki, LOCKED_FOLD_PHASES` (line ~39) to `from wiki import _client as wiki`. (2) Replace the guard block (lines ~97-102) that reads `phase = target_task["status"]` / `if phase in LOCKED_FOLD_PHASES:` with the allowlist: read `status = target_task.get("status")` and `deferred = target_task.get("deferred", False)`, then `if status is not None or deferred:` raise `SystemExit` with the reason-bearing message per the "refusal message names the blocking state" Shared Decision (name the concrete `status` value, or `'deferred'` when `status is None` and `deferred` is True). The guard must stay BEFORE the `--issue` `fetch_one` call and before any `upsert_task` (it already is). (3) Rewrite the module docstring (lines ~10-17): replace the "Phases that reject fold operations" / `LOCKED_FOLD_PHASES` block and the "phase-guard" wording in the operation-order line (~line 11) to describe the unclaimed-only allowlist. The token `LOCKED_FOLD_PHASES` and the "plan frozen" rationale must not survive anywhere in the module. The close-comment-string docstring block (~lines 19-21) is unchanged.
- **Commit:** `fix(fold): refuse fold into any non-unclaimed task (allowlist)`

### Card 3: Update test-fold.py to pin the allowlist behavior

- **Context:**
  - `plugins/mill/scripts/millpy-fold.py`
- **Edits:**
  - `plugins/mill/unit_tests/test-fold.py`
- **Creates:** none
- **Deletes:** none
- **Requirements:** Update `plugins/mill/unit_tests/test-fold.py`. (1) Remove `LOCKED_FOLD_PHASES` from the import at line ~21, leaving `from wiki import _client as wiki, WikiPushError`. (2) Delete the `LOCKED_FOLD_PHASES` value-assertion block (lines ~176-184). (3) Invert the "done phase accepts fold" test (lines ~411-434): assert `millpy_fold.main(["done-task", "--scope", "done fold"])` raises `SystemExit` and `post_home == pre_home`; relabel PASS/FAIL strings to "done phase refused". (4) Invert the "abandoned phase accepts fold" test (lines ~436-459) identically -> "abandoned phase refused". (5) Add new cases reusing the existing `_setup_tempfile_wiki` + `_patch_resolve_paths` + `--scope` pattern: (a) `status=None` unclaimed backlog -> fold ACCEPTED (`rc == 0`, bullet present in Home.md); (b) `status="blocked"` -> refused, Home.md unchanged; (c) a task seeded with `deferred=True` and `status=None` -> refused, Home.md unchanged; (d) `--issue` path against a refused target (e.g. `status="done"`) using `_make_fake_fetch_one` + `_make_fake_close_with_comment` injected via `millpy_fold.main(..., _fetch_one=, _close_with_comment=)` -> raises `SystemExit` AND the captured close-calls list is empty (guard precedes the GH close). (6) Register every new test function in the `main()` runner's execution/call list so each new case actually runs and contributes to the exit code.
- **Commit:** `test(fold): assert allowlist guard refuses claimed/terminal/deferred targets`

### Card 4: Update mill-ghissues-to-tasks SKILL guard to the allowlist

- **Context:**
  - `plugins/mill/skills/mill-fold/SKILL.md`
  - `plugins/mill/scripts/millpy-fold.py`
- **Edits:**
  - `plugins/mill/skills/mill-ghissues-to-tasks/SKILL.md`
- **Creates:** none
- **Deletes:** none
- **Requirements:** Update `plugins/mill/skills/mill-ghissues-to-tasks/SKILL.md` so every fold-target guard states the unclaimed-only rule. (1) Step 3 (line ~59): replace the locked-set guard prose with "a fold target must be unclaimed (`status is None` and not `deferred`); any task with a concrete status or `deferred=True` is routed to a new task or skipped." (2) Step 5 inline re-check (lines ~99-113): replace `if task['status'] in {'active', 'ready-to-merge', 'pr-pending'}:` with `if task.get('status') is not None or task.get('deferred', False):`, convert the existing `task['status']` subscript to `task.get('status')`, and update the printed error string to the allowlist wording. (3) Rules section "Locked-phase guard" (line ~152): rewrite to the allowlist rule and delete the "`{active, ready-to-merge, pr-pending}` is the source of truth" sentences. (4) No stale `{active, ready-to-merge, pr-pending}` set may remain anywhere in the file. Keep the close-comment strings and fold-bullet format unchanged.
- **Commit:** `docs(ghissues-to-tasks): fold only into unclaimed tasks`

### Card 5: Update mill-fold SKILL guard docs to the allowlist

- **Context:**
  - `plugins/mill/scripts/millpy-fold.py`
- **Edits:**
  - `plugins/mill/skills/mill-fold/SKILL.md`
- **Creates:** none
- **Deletes:** none
- **Requirements:** Update `plugins/mill/skills/mill-fold/SKILL.md`. (1) Frontmatter `description:` (line 3): replace the "Hard-refuses locked-phase targets ([active], [ready-to-merge], [pr-pending])" wording with the unclaimed-only rule. (2) Body intro (line 8): replace the locked-phase explanation and the "The locked phase set is `{...}`" sentence with the allowlist rule. (3) "Locked-phase guard" section (lines ~41-49): retitle to an unclaimed-only guard and rewrite, updating the quoted error message to the new wording and removing the "`{active, ready-to-merge, pr-pending}` is the source of truth" sentence. (4) Example (c) (lines ~112-123): keep a refused-fold example but update the printed error text to the new message (target may remain `[active]`). (5) Error-handling table (lines ~127-132): update the "Cannot fold into ..." row message to the new wording. (6) No stale `{active, ready-to-merge, pr-pending}` set or "Plan is frozen" wording may remain.
- **Commit:** `docs(fold): document unclaimed-only fold guard`

### Card 6: Update CLAUDE.md fold constraint

- **Context:**
  - `plugins/mill/scripts/millpy-fold.py`
- **Edits:**
  - `CLAUDE.md`
- **Creates:** none
- **Deletes:** none
- **Requirements:** In `CLAUDE.md` (hub-root project file, line ~45 under `## Hard constraints`), replace the line "No fold into `[active]`/`[ready-to-merge]`/`[pr-pending]` tasks. Phase tuple at `_tasks_md.LOCKED_FOLD_PHASES`." with the allowlist rule and no constant pointer, e.g.: "**Fold only into unclaimed backlog tasks** (`status is None AND not deferred`). Claimed, terminal, blocked, or deferred tasks reject fold-ins -- guard inlined in `millpy-fold.py` and the two fold SKILLs." Wording must stay consistent with the refusal message (card 2) and the SKILL guard text (cards 4-5).
- **Commit:** `docs(claude-md): state unclaimed-only fold constraint`

## Batch Tests

`verify: PYTHONPATH= uv run --project plugins/mill python plugins/mill/unit_tests/run-all.py --only test-fold.py` runs the single affected test file, `test-fold.py`, which pins the guard behavior in `millpy-fold.py` (cards 1-3). Scope is intentionally a single file per the per-batch scoping default -- no other test imports the fold guard or the removed constant. The constant removal (card 1) is exercised indirectly: `test-fold.py` drops the `LOCKED_FOLD_PHASES` import (card 3), so any inconsistency between the removal and the test edits surfaces as an `ImportError` at collection time. The documentation cards (4, 5, 6) have no runnable surface and are validated by plan/code review against the Shared Decisions; correctness is "no stale `{active, ready-to-merge, pr-pending}` set or `LOCKED_FOLD_PHASES` token remains, and the allowlist rule is stated consistently across all four surfaces."
