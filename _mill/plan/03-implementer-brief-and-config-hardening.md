# Batch: implementer-brief-and-config-hardening

```yaml
task: Fix nit-enforcement gate marker gaps, NIT-dispatch wording, implementer liveness probe, and Haiku false-completion
batch: implementer-brief-and-config-hardening
number: 3
cards: 1
verify: null
depends-on: []
```

## Batch Scope

The remaining open half of #616 (the config-default half is already fixed — `roles.implementer.model` already resolves to `sonnethigh`, and is already guarded by an existing, stricter regression test: `test_implementer_model_default_is_sonnethigh` in `plugins/mill/unit_tests/test-config.py:1201`, already registered in that file's `tests` list and asserting an exact `== "sonnethigh"` match against both the plugin template and the hub's own `mill-config.yaml` — plan-review round 1 confirmed this test already fully covers the regression-guard need this task originally set out to add, so no new test is written here; adding a second, weaker allowlist-based test would be pure duplication). This batch hardens `implementer-brief.md`'s final-report contract so the implementer's free-text chat summary states an honest card-count instead of an unqualified completion claim, independent of model tier. No dependency on batches 1/2 — different file, no shared context.

## Cards

### Card 10: Add a card-count self-check to the implementer's free-text summary (#616)

- **Context:** none
- **Edits:**
  - `plugins/mill/templates/implementer-brief.md`
- **Creates:** none
- **Deletes:** none
- **Moves:** none
- **Requirements:** In the `## Report` section, locate the existing "**Pre-report self-check (mandatory before emitting success JSON):**" paragraph. Its exact current text is:

  > **Pre-report self-check (mandatory before emitting success JSON):** Run `git -C <PROJECT_ROOT> status --porcelain --untracked-files=no`. If it shows ANY tracked in-scope modification, commit it via the `git-commit` skill (or report `stuck_type: logic`) -- never report `success` with an uncommitted tracked change. The finalize gate now mechanically rejects a success report when in-scope files are dirty, so an uncommitted change will demote your report to stuck regardless.

  Insert a new paragraph immediately after it (before the "Your last line of output (after all work and commits) MUST be a single JSON object:" sentence that follows):

  > **Card-count self-check (mandatory before writing your free-text turn summary):** Before stating anything about completion in your prose summary to the Builder/operator, count how many cards you actually committed versus how many the batch file declares. Determine the range start exactly as in "Resume-after-incomplete" above: use `<START_SHA>` when non-empty, else `git -C <PROJECT_ROOT> log --grep="^mill-go: start batch" -n 1 --format=%H`. Run `git -C <PROJECT_ROOT> log <range-start>..HEAD --oneline` and match commit subjects against the batch file's `## Cards` `Commit:` messages to get an exact count. Your free-text summary MUST state the real count honestly (e.g. "4 of 9 cards committed") — never write an unqualified "all complete"/"all done" claim without having actually verified the count this way. This applies regardless of which model is running this session: this check is what protects an operator who is only reading your chat summary from a false completion claim, independent of whatever the machine-readable JSON status line below says.

  Reuse the exact `<START_SHA>` / `--grep` fallback logic already described in this same file's "Resume-after-incomplete" paragraph (~line 52) — do not invent a different way to find the batch-start commit (per the overview's Shared Decision "reuse the existing START_SHA / `--grep` fallback for any new commit-range computation").
- **Commit:** `docs(implementer-brief): add card-count self-check to final report (#616)`

## Batch Tests

`verify: null` — `implementer-brief.md` is a prompt template with no runnable surface; its correctness is established by the exact insertion text specified above and by review, not by `run-all.py` (mirrors the overview's Shared Decision on SKILL.md prose, applied here to a template file for the same reason: no Python entry point executes it as code). No test file is touched by this batch — the config-default regression guard this task originally scoped in (#616 hardening) already exists as `test_implementer_model_default_is_sonnethigh`; this was discovered and verified during plan review round 1 (see `_mill/reviews/`), which is why this batch is a single card rather than the two originally planned.
