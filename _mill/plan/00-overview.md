# Plan: Misc infra/wiki/PR/self-hosting reliability bugs

```yaml
task: "Misc infra/wiki/PR/self-hosting reliability bugs"
slug: mill-infra-reliability-misc-r2
approved: false
started: "20260921-152342"
parent: main
root: ""
verify: null
discussion_sha: ebd681d8062b4a7945e7395e5346790577b39cae
```

## Batch Index

```yaml
batches:
  - number: 1
    name: wiki-daemon-reliability
    file: 01-wiki-daemon-reliability.md
    depends-on: []
    verify: PYTHONPATH= uv run --project plugins/mill python plugins/mill/unit_tests/run-all.py --only test-wiki-health-check.py test-wiki-sync.py test-wiki-daemon.py
  - number: 2
    name: pr-state-and-cache-freshness
    file: 02-pr-state-and-cache-freshness.md
    depends-on: []
    verify: PYTHONPATH= uv run --project plugins/mill python plugins/mill/unit_tests/run-all.py --only test-pr-state.py test-cleanup.py
  - number: 3
    name: merge-in-verify-field-fix
    file: 03-merge-in-verify-field-fix.md
    depends-on: []
    verify: PYTHONPATH= uv run --project plugins/mill python plugins/mill/unit_tests/test-millpy-merge-in-subagent.py
  - number: 4
    name: baseline-lazy-preflight
    file: 04-baseline-lazy-preflight.md
    depends-on: []
    verify: PYTHONPATH= uv run --project plugins/mill python plugins/mill/unit_tests/run-all.py --only test-status.py test-verify-baseline.py test-implementer-common.py test-millpy-implement.py
  - number: 5
    name: review-duration-derivation
    file: 05-review-duration-derivation.md
    depends-on: []
    verify: PYTHONPATH= uv run --project plugins/mill python plugins/mill/unit_tests/run-all.py --only test-agent-dispatch.py test-review-common.py
  - number: 6
    name: handoff-skill-doc-fix
    file: 06-handoff-skill-doc-fix.md
    depends-on: []
    verify: null
  - number: 7
    name: csharp-build-node-reuse
    file: 07-csharp-build-node-reuse.md
    depends-on: []
    verify: null
  - number: 8
    name: skill-cross-reference-fix
    file: 08-skill-cross-reference-fix.md
    depends-on: []
    verify: null
```

## Shared Decisions

### Decision: eight independent batches, no cross-batch dependencies

- **Decision:** Each batch fixes one (or, for batches 2, closely related) source GitHub issue named
  in `_mill/discussion.md`. No batch's `Edits:`/`Creates:` set overlaps another's, and no batch's
  design depends on another batch's output, so every batch is a DAG root (`depends-on: []`).
- **Rationale:** the ten source issues (#1107, #1106, #1105, #1103, #1102, #1097, #1095, #1094,
  #1092, #1077) share no code path — grouping by root cause, not by arbitrary sequencing, keeps each
  batch small and independently reviewable, and lets mill-go execute them in any order (or in
  parallel, if a future orchestrator variant supports it) with no risk of a `parallel-modifies-overlap`
  validator conflict.
- **Applies to:** all batches.

### Decision: test convention

- **Decision:** Every code-touching batch extends an existing unit-test file in
  `plugins/mill/unit_tests/` rather than creating a new one, using that file's own existing harness
  convention (either the `main()`/`ok()`/`fail()` free-function harness, e.g.
  `test-wiki-health-check.py`, or `unittest.TestCase`, e.g. `test-millpy-merge-in-subagent.py`).
  Verify commands run only the touched file(s) via `uv run --project plugins/mill python
  plugins/mill/unit_tests/<file>.py` or `run-all.py --only <file1> <file2>` for a batch touching more
  than one test file, never the unbounded suite.
- **Rationale:** matches this repo's own `## Testing` conventions (`plugins/mill/unit_tests/test-<name>.py`,
  in-memory/tempfile fixtures, no real git/LLM except where a file already uses real git fixtures,
  e.g. `test-wiki-health-check.py`, `test-wiki-sync.py`) and keeps each batch's verify scope proportional
  to its diff.
- **Applies to:** batches 1-5 (batches 6-8 are pure documentation/skill-text edits with no runnable
  surface — see each batch's own `## Batch Tests`).

### Decision: doc-only batches use `verify: null`

- **Decision:** Batches 6, 7, and 8 edit only `SKILL.md`/`CLAUDE.md` prose. Their frontmatter
  `verify:` is `null`.
- **Rationale:** there is no runnable surface to verify; `## Batch Tests` in each states the
  alternative check (a self-review read-through or a `grep` self-check), matching this project's
  established pattern for documentation-only plan batches.
- **Applies to:** batches 6, 7, 8.

## All Files Touched

- `CLAUDE.md`
- `plugins/csharp/skills/csharp-build/SKILL.md`
- `plugins/mill/scripts/_agent_dispatch.py`
- `plugins/mill/scripts/_implementer_common.py`
- `plugins/mill/scripts/_pr_state.py`
- `plugins/mill/scripts/_status.py`
- `plugins/mill/scripts/_verify_baseline.py`
- `plugins/mill/scripts/millpy-cleanup.py`
- `plugins/mill/scripts/millpy-implement.py`
- `plugins/mill/scripts/millpy-merge-in-subagent.py`
- `plugins/mill/scripts/millpy-review-code.py`
- `plugins/mill/scripts/millpy-review-discussion.py`
- `plugins/mill/scripts/millpy-review-plan.py`
- `plugins/mill/scripts/wiki/_client.py`
- `plugins/mill/scripts/wiki/_server.py`
- `plugins/mill/scripts/wiki/_sync.py`
- `plugins/mill/skills/handoff/SKILL.md`
- `plugins/mill/skills/mill-go-base/SKILL.md`
- `plugins/mill/skills/mill-merge/SKILL.md`
- `plugins/mill/skills/mill-plan/SKILL.md`
- `plugins/mill/skills/mill-start/SKILL.md`
- `plugins/mill/unit_tests/test-agent-dispatch.py`
- `plugins/mill/unit_tests/test-cleanup.py`
- `plugins/mill/unit_tests/test-implementer-common.py`
- `plugins/mill/unit_tests/test-millpy-implement.py`
- `plugins/mill/unit_tests/test-millpy-merge-in-subagent.py`
- `plugins/mill/unit_tests/test-pr-state.py`
- `plugins/mill/unit_tests/test-review-common.py`
- `plugins/mill/unit_tests/test-status.py`
- `plugins/mill/unit_tests/test-verify-baseline.py`
- `plugins/mill/unit_tests/test-wiki-daemon.py`
- `plugins/mill/unit_tests/test-wiki-health-check.py`
- `plugins/mill/unit_tests/test-wiki-sync.py`
