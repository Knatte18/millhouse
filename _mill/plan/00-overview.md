# Plan: Fix agent-pipeline reliability gaps in finalize/success contract

```yaml
task: Fix agent-pipeline reliability gaps in finalize/success contract
slug: agent-pipeline-reliability
approved: true
started: 20260609-131228
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
    name: "Core fix: emit_prepare + millpy-fix.py"
    file: 01-core-fix.md
    depends-on: []
    verify: PYTHONPATH= uv run --project plugins/mill python plugins/mill/unit_tests/test-implementer-common.py
  - number: 2
    name: "Review CLI finalize: drop prepare() re-invocation"
    file: 02-review-cli-finalize.md
    depends-on: []
    verify: PYTHONPATH= uv run --project plugins/mill python plugins/mill/unit_tests/run-all.py --only test-review-code-flow.py test-review-plan-flow.py test-review-discussion-flow.py
  - number: 3
    name: "SKILL.md updates: Agent-mode dispatch pattern"
    file: 03-skill-updates.md
    depends-on: [1, 2]
    verify: null
  - number: 4
    name: "Unit tests: fix-finalize and review-finalize"
    file: 04-unit-tests.md
    depends-on: [1, 2]
    verify: PYTHONPATH= uv run --project plugins/mill python plugins/mill/unit_tests/run-all.py --only test-fix-finalize.py test-review-finalize.py
```

## Shared Decisions

_Cross-cutting decisions every batch inherits._

### Decision: start_sha-via-cli-arg

- **Decision:** `start_sha` crosses the prepare->finalize boundary as a `--start-sha` CLI argument added to `millpy-fix.py`. The prepare stage captures `start_sha` via `git rev-parse HEAD` after the pre-commit, includes it in the prepare envelope JSON, and mill-go passes it to the finalize call.
- **Rationale:** Explicit contract — no hidden sidecar files, no status.md schema changes. Consistent with existing pattern of passing prepare envelope fields as finalize args.
- **Applies to:** batch 1 (code), batch 3 (docs), batch 4 (tests)

### Decision: session_id-via-cli-arg-for-fix-finalize

- **Decision:** `session_id` in `millpy-fix.py` finalize stage comes exclusively from `--session-id` CLI arg (from the prepare envelope), not from a fresh `uuid.uuid4()` call. The local `uuid.uuid4()` at the top of `main()` is retained for prepare and full stages only.
- **Rationale:** Prevents the inferred-success path from emitting a wrong session_id. No cost to implement alongside Gap A.
- **Applies to:** batch 1 (code), batch 3 (docs), batch 4 (tests)

### Decision: round-via-cli-arg-for-review-finalize

- **Decision:** All three review CLIs (`millpy-review-code.py`, `millpy-review-plan.py`, `millpy-review-discussion.py`) accept a new `--round` CLI arg in the finalize stage. The finalize branch uses `args.round` directly and derives `reviews_dir` via `_review_common.resolve_path(cfg["paths"]["reviews_dir"], slug)`. The `prepare()` call is removed from the finalize branch entirely.
- **Rationale:** Eliminates double-config-load and fragile round re-derivation. `round` is already authoritative in the prepare envelope.
- **Applies to:** batch 2 (code), batch 3 (docs), batch 4 (tests)

### Decision: reviews_dir-via-resolve_path

- **Decision:** In review CLI finalize stages, `reviews_dir` is derived via `_review_common.resolve_path(cfg["paths"]["reviews_dir"], slug)`, not `_paths.resolve_task_path`. The former applies slug substitution and resolves against the active hub root, matching what `prepare()` returns.
- **Rationale:** Exact match with what prepare() derives; no slug-substitution gap.
- **Applies to:** batch 2 (code)

### Decision: no-backend-changes

- **Decision:** The backend `finalize()` functions in `_review_code.py`, `_review_plan.py`, and `_review_discussion.py` are NOT changed. They already accept `round_n` and `reviews_dir` as parameters.
- **Rationale:** The only fix is WHERE the CLI gets those values.
- **Applies to:** all batches

## All Files Touched

- `plugins/mill/scripts/_implementer_common.py`
- `plugins/mill/scripts/millpy-fix.py`
- `plugins/mill/scripts/millpy-review-code.py`
- `plugins/mill/scripts/millpy-review-discussion.py`
- `plugins/mill/scripts/millpy-review-plan.py`
- `plugins/mill/skills/mill-go/SKILL.md`
- `plugins/mill/skills/mill-start/SKILL.md`
- `plugins/mill/unit_tests/test-fix-finalize.py`
- `plugins/mill/unit_tests/test-review-finalize.py`
