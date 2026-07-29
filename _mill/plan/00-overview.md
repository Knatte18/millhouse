# Plan: Review dispatch: no per-round reviewer override, and reviewer_model echoes the dispatch flag instead of the model that ran

```yaml
task: 'Review dispatch: no per-round reviewer override, and reviewer_model echoes the dispatch flag instead of the model that ran'
slug: mill-review-dispatch-attribution-gaps
approved: false
started: 20260729-072603
parent: main
root: ""
verify: null
```

## Batch Index

_The fenced yaml block below is the authoritative DAG mill-go reads to
schedule batches. Every batch lives at `NN-<batch-slug>.md` in this
directory and is mirrored as one entry here._

```yaml
batches:
  - number: 1
    name: reviewer-override-helper
    file: 01-reviewer-override-helper.md
    depends-on: []
    verify: PYTHONPATH= uv run --project plugins/mill python plugins/mill/unit_tests/test-reviewers.py
  - number: 2
    name: discussion-review-cli
    file: 02-discussion-review-cli.md
    depends-on: [1]
    verify: PYTHONPATH= uv run --project plugins/mill python plugins/mill/unit_tests/run-all.py --only test-review-discussion-flow.py test-review-prepare-envelope.py test-review-cli-error-envelope.py
  - number: 3
    name: plan-review-cli
    file: 03-plan-review-cli.md
    depends-on: [1]
    verify: PYTHONPATH= uv run --project plugins/mill python plugins/mill/unit_tests/run-all.py --only test-review-plan-flow.py test-review-prepare-envelope.py test-review-cli-error-envelope.py
  - number: 4
    name: reviewer-self-id-templates
    file: 04-reviewer-self-id-templates.md
    depends-on: []
    verify: PYTHONPATH= uv run --project plugins/mill python plugins/mill/unit_tests/test-review-templates.py
  - number: 5
    name: unit-tests-discussion
    file: 05-unit-tests-discussion.md
    depends-on: [1, 2]
    verify: PYTHONPATH= uv run --project plugins/mill python plugins/mill/unit_tests/run-all.py --only test-reviewers.py test-review-discussion-flow.py
  - number: 6
    name: unit-tests-plan
    file: 06-unit-tests-plan.md
    depends-on: [1, 3, 4]
    verify: PYTHONPATH= uv run --project plugins/mill python plugins/mill/unit_tests/run-all.py --only test-review-plan-flow.py test-review-common.py
```

## Shared Decisions

_Cross-cutting decisions every batch inherits: naming conventions,
error-handling posture, test frameworks, style/lint constraints. One
subsection per decision. Batch-local decisions live in each batch file._

### Decision: exception-conversion at the resolution site

- **Decision:** Every one of the four `reviewer_override` resolution sites (`_review_discussion.py`'s `prepare()` and `run()`; `_review_plan.py`'s `prepare()` holistic branch and `run()` holistic branch) wraps its call into the new `_reviewers.resolve_reviewer_override(...)` helper in `try: ... except _reviewers.ReviewerError as exc: raise ReviewError(str(exc)) from exc`. Never rely on a CLI's outer `except Exception` catch-all to perform this conversion — `millpy-review-discussion.py`'s `--stage prepare`/`--stage full` blocks catch only `except ReviewError` (no catch-all), so an unconverted `ReviewerError` would crash with a raw traceback instead of the JSON `ERROR` envelope; `millpy-review-plan.py`'s equivalent blocks do have a broader `except Exception` catch-all, but it prefixes a different message ("unhandled review error: ...") than the clean, registry-native error text this task's tests assert on, so relying on it would make the two CLIs behave inconsistently with each other for the same kind of failure.
- **Rationale:** `_reviewers.resolve()` raises `_reviewers.ReviewerError` (a class with no relationship to `_review_common.ReviewError` — both extend `Exception` directly), so nothing converts it automatically. Converting once, at each resolution call site, guarantees both CLIs emit the same `verdict: ERROR` JSON envelope shape for an unknown/invalid `--reviewer` value regardless of which CLI's outer exception handling happens to be broader.
- **Applies to:** discussion-review-cli, plan-review-cli, unit-tests-discussion, unit-tests-plan

### Decision: `--reviewer` bypasses a `reviewer: null` disablement, not a `rounds: 0` disablement

- **Decision:** In all four resolution sites, resolving `reviewer_override` happens unconditionally BEFORE the existing `reviewer_name is None: raise ReviewError(...)` check (in `prepare()`) or equivalent — i.e. when `reviewer_override` is set, that null-check is never reached at all, so an explicit `--reviewer` forces a round to run even when config has `reviewer: null` for that role/scope. This mirrors the existing `--max-rounds`-vs-`rounds: 0` precedent already in the same functions. It does NOT also bypass a `rounds: 0` disablement — `rounds: 0` is checked independently (in `prepare()`'s `effective_max == 0` branch and in `run()`'s early-return stub), before any reviewer-name resolution runs, and `reviewer_override` never touches that check. Forcing a round on a `rounds: 0` scope still requires `--max-rounds` in addition to `--reviewer`.
- **Rationale:** An operator naming a reviewer on the command line is unambiguously asking for a round to run, the same way `--max-rounds 1` already overrides `rounds: 0`. The two disablements (`reviewer: null` and `rounds: 0`) are independent checks and this task's scope only touches the reviewer-name resolution, not the round-count gate.
- **Applies to:** discussion-review-cli, plan-review-cli

### Decision: large-prompt auto-switch is skipped, not merely re-targeted, when `reviewer_override` is set

- **Decision:** In all four call sites that invoke `maybe_switch_spec_for_large_prompt(...)` today (`_review_discussion.py`'s `prepare()` and `run()`; `_review_plan.py`'s `prepare()` holistic branch and `run()` holistic branch), wrap the existing call in `if reviewer_override is None:` so it is skipped entirely — not called at all — whenever an override is present. The resolved `spec`/`reviewer_name` from `reviewer_override` pass through untouched to prompt rendering and dispatch.
- **Rationale:** The large-prompt auto-switch exists to protect against a reviewer choking on an oversized prompt by silently swapping in a configured fallback. The entire point of `--reviewer` is a deliberate, informed operator choice to break a stalled review loop; letting an unrelated token-count heuristic silently revert that choice would defeat the override's purpose, especially since a stalled loop with a large discussion/plan is exactly the scenario where an operator is most likely to reach for `--reviewer` in the first place.
- **Applies to:** discussion-review-cli, plan-review-cli, unit-tests-discussion, unit-tests-plan

### Decision: `--reviewer` on `millpy-review-plan.py` affects holistic scope only

- **Decision:** `_review_plan.py`'s per-batch resolution (`prepare()`'s `if scope is not None:` branch and `run()`'s `batch_reviewer_name`/`batch_spec` resolution) is never touched by `reviewer_override`. The new `reviewer_override` parameter is accepted by `prepare()` regardless of `scope`, but is a documented no-op when `scope is not None` — no error, no warning, since the CLI's Agent-mode `--stage prepare` branch always calls `prepare(scope=None, ...)` (holistic) today and there is no live caller that would pass both a batch `scope` and `reviewer_override` together.
- **Rationale:** Agent-mode plan review dispatch only ever operates on holistic scope; batch scope has no Agent-mode dispatch path at all and is disabled by default (`roles.plan-review.batch.reviewer: null` in the shipped config). Extending the override to a scope with no live incident and no dispatch path would be speculative surface.
- **Applies to:** plan-review-cli, unit-tests-plan

### Decision: no orchestration-doc changes

- **Decision:** This plan does not touch `mill-go/SKILL.md`, `mill-start/SKILL.md`, or `mill-plan/SKILL.md`.
- **Rationale:** `--reviewer` is designed for direct, manual CLI invocation (the exact workaround the sourced incident used by hand, mid-loop) — not for wiring into the automated Agent-mode dispatch loop those files describe. Neither sourced issue (#725, #722) asks for orchestration-doc changes.
- **Applies to:** all batches

## All Files Touched

- `plugins/mill/scripts/_reviewers.py`
- `plugins/mill/scripts/_review_discussion.py`
- `plugins/mill/scripts/millpy-review-discussion.py`
- `plugins/mill/scripts/_review_plan.py`
- `plugins/mill/scripts/millpy-review-plan.py`
- `plugins/mill/templates/review-discussion.md`
- `plugins/mill/templates/review-plan-batch.md`
- `plugins/mill/templates/review-plan-holistic.md`
- `plugins/mill/templates/review-output.schema.md`
- `plugins/mill/unit_tests/test-reviewers.py`
- `plugins/mill/unit_tests/test-review-discussion-flow.py`
- `plugins/mill/unit_tests/test-review-plan-flow.py`
- `plugins/mill/unit_tests/test-review-common.py`
