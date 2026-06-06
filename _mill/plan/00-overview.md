# Plan: Fix infrastructure bugs across merge, wiki-daemon, config, plan, and cleanup

```yaml
task: "Fix infrastructure bugs across merge, wiki-daemon, config, plan, and cleanup"
slug: mill-infra-bug-fixes
approved: true
started: "20260606-190000"
parent: main
root: ""
verify: null
```

## Batch Index

_The fenced yaml block below is the authoritative DAG mill-go reads to
schedule batches. Every batch lives at `NN-<batch-slug>.md` in this
directory and is mirrored as one entry here. All batches touch disjoint
files and are independent (`depends-on: []`), so mill-go may run them in
any order / in parallel._

```yaml
batches:
  - number: 1
    name: wiki-client-retry
    file: 01-wiki-client-retry.md
    depends-on: []
    verify: PYTHONPATH= uv run --project plugins/mill python plugins/mill/unit_tests/run-all.py --only test-wiki-client-retry.py
  - number: 2
    name: review-backend
    file: 02-review-backend.md
    depends-on: []
    verify: PYTHONPATH= uv run --project plugins/mill python plugins/mill/unit_tests/run-all.py --only test-review-common.py test-review-plan-flow.py
  - number: 3
    name: plan-verify-language-aware
    file: 03-plan-verify-language-aware.md
    depends-on: []
    verify: PYTHONPATH= uv run --project plugins/mill python plugins/mill/unit_tests/run-all.py --only test-plan-validate.py
  - number: 4
    name: cleanup-robustness
    file: 04-cleanup-robustness.md
    depends-on: []
    verify: PYTHONPATH= uv run --project plugins/mill python plugins/mill/unit_tests/run-all.py --only test-cleanup.py test-worktree.py
  - number: 5
    name: implementer-correctness
    file: 05-implementer-correctness.md
    depends-on: []
    verify: PYTHONPATH= uv run --project plugins/mill python plugins/mill/unit_tests/run-all.py --only test-cleanliness.py test-millpy-implement.py test-implementer-common.py
  - number: 6
    name: psmux-dispatch
    file: 06-psmux-dispatch.md
    depends-on: []
    verify: PYTHONPATH= uv run --project plugins/mill python plugins/mill/unit_tests/run-all.py --only test-claude-sub.py test-llm-claude.py
  - number: 7
    name: cache-preflight
    file: 07-cache-preflight.md
    depends-on: []
    verify: PYTHONPATH= uv run --project plugins/mill python plugins/mill/unit_tests/run-all.py --only test-preflight.py
  - number: 8
    name: merge-in-verify-gate
    file: 08-merge-in-verify-gate.md
    depends-on: []
    verify: PYTHONPATH= uv run --project plugins/mill python plugins/mill/unit_tests/run-all.py --only test-merge-in-subagent.py
```

## Shared Decisions

### Decision: ASCII-only script output

- **Decision:** Every `print()` / `_log()` / stderr message added or changed
  must be ASCII-only (`--` not the em dash, `->` not the arrow). Windows
  cp1252 stdout crashes on non-ASCII.
- **Rationale:** Project convention (CLAUDE.md); a non-ASCII byte in a
  message crashes the very script the fix is meant to harden.
- **Applies to:** all batches

### Decision: test conventions

- **Decision:** Unit tests live in `plugins/mill/unit_tests/test-<name>.py`,
  use in-memory / tempfile fixtures, and never invoke real git, real LLMs,
  or real sockets. Monkeypatch the boundary (e.g. `subprocess.run`,
  `_connect_send_recv`, process enumeration) rather than exercising it. Run
  via `run-all.py --only <files>`. New test files are auto-discovered by
  `run-all.py`.
- **Rationale:** Matches the existing suite; keeps `verify:` fast and
  deterministic.
- **Applies to:** all batches

### Decision: testability via pure helpers

- **Decision:** When a fix involves a side-effecting boundary that is hard
  to unit-test (process killing, socket retry, formatter drift), extract the
  decision logic into a pure function that takes its inputs as arguments
  (e.g. an injected process-record list, or porcelain lines) so it can be
  unit-tested without the side effect. The side-effecting caller wires the
  default real source.
- **Rationale:** Lets the behavior be pinned by a unit test per the test
  conventions above without real OS calls.
- **Applies to:** cleanup-robustness, implementer-correctness, psmux-dispatch,
  wiki-client-retry

### Decision: fix at call site, keep helper APIs clean

- **Decision:** Correct wrong behavior at the call site / in the targeted
  function; do not add kw-only guards or runtime type checks to "catch"
  misuse. All path resolution stays through `_paths.py`.
- **Rationale:** Project convention; runtime guards rot and hide the real bug.
- **Applies to:** all batches

### Decision: Windows-first correctness

- **Decision:** Each fix must behave on Windows: cp1252 stdout, junction
  symlinks, `WinError` socket codes (10054/10061), and the CreateProcess
  command-line length limit.
- **Rationale:** The hub runs on Windows; every reported bug surfaced there.
- **Applies to:** all batches

## All Files Touched

- `CLAUDE.md`
- `plugins/mill/scripts/_cleanliness.py`
- `plugins/mill/scripts/_implementer_common.py`
- `plugins/mill/scripts/_llm_claude.py`
- `plugins/mill/scripts/_plan_validate.py`
- `plugins/mill/scripts/_preflight.py`
- `plugins/mill/scripts/_review_common.py`
- `plugins/mill/scripts/_review_plan.py`
- `plugins/mill/scripts/_worktree.py`
- `plugins/mill/scripts/millpy-claude-sub.py`
- `plugins/mill/scripts/millpy-cleanup.py`
- `plugins/mill/scripts/millpy-implement.py`
- `plugins/mill/scripts/millpy-merge-in-subagent.py`
- `plugins/mill/scripts/wiki/_client.py`
- `plugins/mill/skills/mill-go/SKILL.md`
- `plugins/mill/skills/mill-merge/SKILL.md`
- `plugins/mill/skills/mill-plan/SKILL.md`
- `plugins/mill/templates/implementer-brief.md`
- `plugins/mill/templates/mill-config.yaml`
- `plugins/mill/templates/review-output.schema.md`
- `plugins/mill/unit_tests/test-claude-sub.py`
- `plugins/mill/unit_tests/test-cleanliness.py`
- `plugins/mill/unit_tests/test-cleanup.py`
- `plugins/mill/unit_tests/test-implementer-common.py`
- `plugins/mill/unit_tests/test-llm-claude.py`
- `plugins/mill/unit_tests/test-merge-in-subagent.py`
- `plugins/mill/unit_tests/test-millpy-implement.py`
- `plugins/mill/unit_tests/test-plan-validate.py`
- `plugins/mill/unit_tests/test-preflight.py`
- `plugins/mill/unit_tests/test-review-common.py`
- `plugins/mill/unit_tests/test-review-plan-flow.py`
- `plugins/mill/unit_tests/test-wiki-client-retry.py`
- `plugins/mill/unit_tests/test-worktree.py`
