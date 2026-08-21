# Plan: mill-go2: fork-based dispatch reliability, shared-skill preloading, and catalog accuracy

```yaml
task: "mill-go2: fork-based dispatch reliability, shared-skill preloading, and catalog accuracy"
slug: mill-go2-fork-dispatch-reliability
approved: true
started: "20260821-090547"
parent: main
root: ""
verify: null
```

## Batch Index

```yaml
batches:
  - number: 1
    name: fork-dispatch-reliability-fixes
    file: 01-fork-dispatch-reliability-fixes.md
    depends-on: []
    verify: PYTHONPATH= uv run --project plugins/mill python plugins/mill/unit_tests/run-all.py
```

## Shared Decisions

### Decision: single-file scope

- **Decision:** every card in this plan edits `plugins/mill/skills/mill-go2/SKILL.md`, with one post-approval scope extension to `plugins/mill/unit_tests/test-mill-go-variants.py` (see batch 1's `## Scope Extension (post-approval)`) — this task is a prompt/frontmatter change to one variant skill's dispatch-override text, per `_mill/discussion.md`'s Scope section, plus the follow-on test update that change required.
- **Rationale:** `_mill/discussion.md`'s four implementation Decisions (de-briefing text for both roles, logic/verify self-resolve re-fire dispatches cold, shared-skill preload scope, catalog description) all resolve to edits inside `mill-go2/SKILL.md`'s existing `## Dispatch overrides` and `## Driver preamble` sections, or its frontmatter — none require changes to `mill-go-base/SKILL.md` (see discussion's "shared-skill preload scope" Decision, which explicitly rejects placing the preload there) or to any Python helper (see discussion's Technical context: "No Python helper changes are anticipated"). Mid-implementation, `test-mill-go-variants.py` was found to directly exercise `mill-go2/SKILL.md`'s content (a byte-size ceiling and a `## Driver preamble` placeholder assertion), so it required a matching update — documented as a scope extension in batch 1 rather than anticipated up front.
- **Applies to:** all batches (there is only one).

### Decision: verify is full-suite regression guard, not scoped

- **Decision:** the batch's `verify:` runs the entire unit-test suite (`run-all.py`, unbounded) rather than a scoped `--only` subset.
- **Rationale:** per `_mill/discussion.md`'s Testing section, this task edits only `SKILL.md` prose — no unit test in `plugins/mill/unit_tests/` exercises that file's content directly, so there is no natural scoped subset to target with `--only`. The full suite serves purely as a regression guard (confirms these edits don't accidentally corrupt anything a test does cover, e.g. if a script parses `SKILL.md` frontmatter). This is the `verify-full-suite` skip-check escape hatch's documented justification case.
- **Applies to:** all batches (there is only one).

## All Files Touched

- `plugins/mill/skills/mill-go2/SKILL.md`
- `plugins/mill/unit_tests/test-mill-go-variants.py` (post-approval scope extension — see batch 1's `## Scope Extension (post-approval)`)
