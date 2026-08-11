# Plan: mill-go2: fork-based implementer dispatch

```yaml
task: 'mill-go2: fork-based implementer dispatch'
slug: mill-go2-fork-implementer
approved: false
started: '2026-08-11T13:57:18Z'
parent: main
root: ""
verify: PYTHONPATH= uv run --project plugins/mill python plugins/mill/unit_tests/run-all.py --only test-status.py test-mill-go-variants.py test-skill-helper-drift.py test-guards.py
```

## Batch Index

_The fenced yaml block below is the authoritative DAG mill-go reads to schedule batches.
Every batch lives at `NN-<batch-slug>.md` in this directory and is mirrored as one entry here._

```yaml
batches:
  - number: 1
    name: status-fork-fallback-helper
    file: 01-status-fork-fallback-helper.md
    depends-on: []
    verify: PYTHONPATH= uv run --project plugins/mill python plugins/mill/unit_tests/test-status.py
  - number: 2
    name: mill-go2-implementer-override
    file: 02-mill-go2-implementer-override.md
    depends-on: [1]
    verify: PYTHONPATH= uv run --project plugins/mill python plugins/mill/unit_tests/test-mill-go-variants.py
```

## Shared Decisions

### Decision: batch-2-depends-on-batch-1-via-the-drift-guard

- **Decision:** batch 2 depends on batch 1 even though no batch-2 file imports `_status`.
- **Rationale:** `plugins/mill/unit_tests/test-skill-helper-drift.py` scans every mill `SKILL.md` for the pattern `_<module>.<fn>(` and fails when the reference does not resolve to a real shipped function in `plugins/mill/scripts`. Batch 2's override text names `_status.append_fork_fallback_log(...)`, so that function must already exist when batch 2 lands or the module-wide verify goes red. This is a hard ordering constraint, not a stylistic one.
- **Applies to:** all batches

### Decision: tests-first inside each batch

- **Decision:** in both batches the test card is numbered before the implementation card(s), so the implementer writes the assertion first and then makes it pass.
- **Rationale:** the discussion names `append_fork_fallback_log` the genuine TDD candidate, and the variant-contract assertions are the only executable verification the SKILL.md edits have at all. `verify:` runs once per implementer round, not per card, so an intermediate red commit inside a batch is expected and is resolved before the batch's own verify gate.
- **Applies to:** all batches

### Decision: no fork spike card

- **Decision:** the plan schedules no card that dispatches a live fork to confirm its `agentId` / `<task-notification>` shapes, even though discussion Decision `fork-dispatch-shape` allows one.
- **Rationale:** a mill implementer's declared tool grant is `Read, Edit, Write, Bash, Grep, Glob, Skill` (`plugins/mill/agents/mill-implementer.md`) — it holds no `Agent` tool, so it structurally cannot dispatch a fork. The assumption is instead recorded as an explicit inference in the variant file (card 4) and listed below as a manual PoC observation. Faking it as an assertion would be worse than naming it.
- **Applies to:** mill-go2-implementer-override

### Decision: verify scoping and the module-wide gate

- **Decision:** each batch's own `verify:` names exactly the one test file that batch edits. The cross-file regression coverage — `test-skill-helper-drift.py` (drift guard over the new `_status` reference) and `test-guards.py` (no-wiki-cwd scan over the edited SKILL files) — lives in the overview's module-wide `verify:` instead.
- **Rationale:** `_plan_validate.py`'s `verify-unrelated-test-file` check flags any `--only` token in a *batch* verify that the batch does not itself touch and that is unchanged versus the parent branch, which both guard files are. The module-wide `verify:` is not subject to that check and runs at every batch boundary, so the coverage is kept without tripping the validator. Unbounded `run-all.py` is not used anywhere — `verify-full-suite` rejects it and the full 116-file suite is minutes long.
- **Applies to:** all batches

### Decision: literals the tests and the SKILL files must agree on

- **Decision:** card 3's assertions and cards 4-5's edits are written against one fixed literal set. Changing any of these means changing both sides in the same batch.
  - `subagent_type: "fork"` — present in `mill-go2/SKILL.md`, absent from `mill-go/SKILL.md`.
  - `not the orchestrator` — the de-briefing's stable substring.
  - `fork-fallback` — the cold-fallback marker's stable substring.
  - `unclaimed` — the token recording that fixer, reviewer, and merge-in keep the default dispatch.
  - `(none)` — must remain the first non-blank line of `mill-go`'s `## Dispatch overrides` and of `mill-go2`'s `## Driver preamble`.
  - `**Why not fork?**` and `parent's tools` — must survive verbatim in `mill-go-base/SKILL.md`.
- **Rationale:** the discussion's Testing section asks for assertions on stable substrings rather than whole paragraphs, so wording can be tuned without churning the test. Fixing the set in one place keeps the two batches honest about what "stable" means.
- **Applies to:** mill-go2-implementer-override

### Decision: banned literals in variant files

- **Decision:** no text written into `plugins/mill/skills/mill-go2/SKILL.md` may contain `## Agent-mode dispatch`, `## Holistic code review`, `## Execute`, `You are the **Builder**`, `"mill-go: `, `_notify.notify("mill-go.`, or `[mill-go]`, and the whole file must stay under 4096 bytes.
- **Rationale:** `_check_variants_carry_no_machinery` and `_check_parameterization_lock` in `test-mill-go-variants.py` already enforce every one of these, and the cap is the scaffold's own regression guard against re-inlining base machinery into a variant. Prose referring to the base's dispatch pattern must therefore omit the `## ` prefix, and every commit/notify string must use the `<VARIANT_LABEL>` form.
- **Applies to:** mill-go2-implementer-override

### Decision: manual PoC observations, not assertions

- **Decision:** three outcomes are recorded here as things a real `/mill-go2` run observes, and are deliberately not encoded as tests: (1) that a forked implementer completes a batch at all; (2) that the cold fallback fires on a dead fork; (3) that the de-briefing stops the fork from acting on inherited driver instructions. A fourth is the load-bearing inference: that a fork returns an `agentId` and delivers a completion `<task-notification>` in the same shapes a cold agent does.
- **Rationale:** these are the experiment's actual subject matter. An assertion over SKILL.md prose would assert that the instruction is written, not that it works, and would read as coverage it does not provide.
- **Applies to:** all batches

## All Files Touched

- `plugins/mill/scripts/_status.py`
- `plugins/mill/skills/mill-go-base/SKILL.md`
- `plugins/mill/skills/mill-go2/SKILL.md`
- `plugins/mill/unit_tests/test-mill-go-variants.py`
- `plugins/mill/unit_tests/test-status.py`
