# Plan: Fix nit-enforcement gate marker gaps, NIT-dispatch wording, implementer liveness probe, and Haiku false-completion

```yaml
task: Fix nit-enforcement gate marker gaps, NIT-dispatch wording, implementer liveness probe, and Haiku false-completion
slug: mill-go-nit-gate-and-dispatch-gaps
approved: false
started: 20260709-131351
parent: main
root: ""
verify: null
```

## Batch Index

```yaml
batches:
  - number: 1
    name: nits-only-envelope-threading
    file: 01-nits-only-envelope-threading.md
    depends-on: []
    verify: PYTHONPATH= uv run --project plugins/mill python plugins/mill/unit_tests/run-all.py --only test-implementer-common.py test-millpy-fix.py
  - number: 2
    name: mill-go-skill-prose-fixes
    file: 02-mill-go-skill-prose-fixes.md
    depends-on: [1]
    verify: null
  - number: 3
    name: implementer-brief-and-config-hardening
    file: 03-implementer-brief-and-config-hardening.md
    depends-on: []
    verify: PYTHONPATH= uv run --project plugins/mill python plugins/mill/unit_tests/run-all.py --only test-config.py
```

## Shared Decisions

### Decision: envelope-threading over prose-flag-lists for cross-process CLI state

- **Decision:** Where Agent-mode dispatch needs a value from the prepare stage to be visible again at the finalize stage (a separate CLI process invocation), thread it through the prepare-stage JSON envelope as an optional field (present only when truthy/non-null, omitted otherwise) — the same pattern already used for `start_sha`. Do not rely solely on a hand-maintained prose list of "flags to re-pass" without a corresponding envelope field backing it.
- **Rationale:** `argparse` state does not survive across separate process invocations. #619's root cause was exactly a hand-maintained flag-list omission (`--nits-only` was never added to the re-pass list). Envelope-threading makes the script side testable; the SKILL.md instruction to read the field and re-pass the flag remains prose (see the residual-risk note in `_mill/discussion.md`'s `nits-only-envelope-threading` Decision), but the *value* itself is no longer at risk of being silently dropped by process-boundary argparse reset.
- **Applies to:** batch 1 (introduces the `nits_only` envelope field), batch 2 (SKILL.md instruction that reads it).

### Decision: SKILL.md prose changes carry no automated test coverage

- **Decision:** Edits to `plugins/mill/skills/mill-go/SKILL.md` (orchestration prompts consumed by an LLM at runtime, not executed as code) are not backed by unit tests. Their correctness is established by careful, verbatim replacement text specified in the plan (this file's batch 2 cards) and by discussion/plan/code review rounds — never by `run-all.py`.
- **Rationale:** There is no Python entry point that parses or executes SKILL.md; it is read by a Claude session as instructions. Inventing a "prose linter" for this task would be scope creep beyond the five issues being fixed.
- **Applies to:** batch 2 (verify: null is intentional, not an oversight).

### Decision: reuse the existing START_SHA / `--grep` fallback for any new commit-range computation

- **Decision:** Any new instruction that needs to compute "commits made so far in this batch" (in an implementer-facing brief template) must reuse the exact fallback already documented in `implementer-brief.md`'s "Resume-after-incomplete" section: use `<START_SHA>` when non-empty, else derive the range start via `git -C <PROJECT_ROOT> log --grep="^mill-go: start batch" -n 1 --format=%H`. Do not invent a second, parallel way to find the batch-start commit.
- **Rationale:** `<START_SHA>` renders as an empty string on a normal (non-resume) first-pass dispatch — the common case. A card-count self-check that assumes a non-empty start ref would break on every first-pass batch dispatch, which is most of them.
- **Applies to:** batch 3 (implementer-brief.md card-count self-check).

## All Files Touched

- `plugins/mill/scripts/_implementer_common.py`
- `plugins/mill/scripts/millpy-fix.py`
- `plugins/mill/skills/mill-go/SKILL.md`
- `plugins/mill/templates/implementer-brief.md`
- `plugins/mill/unit_tests/test-config.py`
- `plugins/mill/unit_tests/test-implementer-common.py`
- `plugins/mill/unit_tests/test-millpy-fix.py`
