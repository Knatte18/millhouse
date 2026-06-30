# Plan: Fix mid-batch stop recovery and fixer false-success in agent-dispatch mode

```yaml
task: "Fix mid-batch stop recovery and fixer false-success in agent-dispatch mode"
slug: "mill-agent-dispatch-gaps"
approved: false
started: "20260630-051126"
parent: "main"
root: ""
verify: null
```

## Batch Index

_The fenced yaml block below is the authoritative DAG mill-go reads to schedule batches._

```yaml
batches:
  - number: 1
    name: finalize-incomplete-core
    file: 01-finalize-incomplete-core.md
    depends-on: []
    verify: PYTHONPATH= uv run --project plugins/mill python plugins/mill/unit_tests/test-implementer-common.py
  - number: 2
    name: resume-path-and-brief-token
    file: 02-resume-path-and-brief-token.md
    depends-on: [1]
    verify: PYTHONPATH= uv run --project plugins/mill python plugins/mill/unit_tests/run-all.py --only test-millpy-implement.py test-language-skills-directive.py
  - number: 3
    name: fixer-brief-commit-guard
    file: 03-fixer-brief-commit-guard.md
    depends-on: []
    verify: null
  - number: 4
    name: millgo-incomplete-routing
    file: 04-millgo-incomplete-routing.md
    depends-on: [1, 2]
    verify: null
```

## Shared Decisions

### Decision: `stuck_type: incomplete` is a new first-class classification

- **Decision:** Introduce `stuck_type: incomplete` distinct from `transient`/`verify`/`logic`/`infrastructure`. It means a batch is provably partial on a path where no trustworthy success report exists; the correct recovery is to finish the remaining work in/continuing the existing session, never retry-from-scratch and never accept as done. Its envelope carries `commit_sha` (current HEAD), `commits_made`, and `session_id`.
- **Rationale:** `transient` routes to retry-fresh (re-does committed cards) or skip-to-cleanliness (accepts partial work); neither matches a partial-batch stop. See discussion `incomplete-stuck-type`.
- **Applies to:** all batches.

### Decision: only the no-JSON inference paths get stricter completeness detection

- **Decision:** The explicit-`status: success` completeness GATE (`_batch_completeness_stuck` short-circuit when `verify_cmd` is set) stays unchanged — a passing verify remains conclusive when the agent affirmatively claimed success. Only the no-JSON inference paths gain a verify-ignoring completeness check. Separately, the `_reclassify_verify_failure` rename (`transient` -> `incomplete`) applies to ALL callers because it fires only on verify FAILURE.
- **Rationale:** Changing the explicit-success gate would falsely flag legitimate combined-commit batches. See discussion `completeness-check-on-no-json-path-ignores-verify` and `reclassify-rename-all-callers`.
- **Applies to:** finalize-incomplete-core.

### Decision: resume must preserve the original `start_sha`

- **Decision:** The `incomplete` recovery re-dispatches/resumes preserving the original batch `start_sha` (read from status.md), never re-capturing HEAD. A re-captured `start_sha` makes the completeness recount under-count a finished batch and loop `incomplete`. The warm-`SendMessage` agent path is inherently safe (bypasses prepare); the fallback and subprocess paths use a new start_sha-preserving resume path.
- **Rationale:** See discussion `start-sha-preserving-resume` and `false-positive-incomplete-is-safe`.
- **Applies to:** resume-path-and-brief-token, millgo-incomplete-routing.

### Decision: Python verify shape

- **Decision:** Every non-null `verify:` starts with the literal `PYTHONPATH= ` prefix (mill is a Python project). Template-only and markdown-only batches use `verify: null`.
- **Rationale:** Prevents the test subprocess inheriting the cache `PYTHONPATH` (CLAUDE.md / `verify-not-isolated`).
- **Applies to:** all batches.

## All Files Touched

- `plugins/mill/integration_tests/test-go-assets.py`
- `plugins/mill/scripts/_implementer_common.py`
- `plugins/mill/scripts/millpy-implement.py`
- `plugins/mill/skills/mill-go/SKILL.md`
- `plugins/mill/templates/fixer-batch-brief.md`
- `plugins/mill/templates/fixer-holistic-brief.md`
- `plugins/mill/templates/implementer-brief.md`
- `plugins/mill/unit_tests/test-implementer-common.py`
- `plugins/mill/unit_tests/test-language-skills-directive.py`
- `plugins/mill/unit_tests/test-millpy-implement.py`
