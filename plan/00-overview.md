# Plan: review-subsystem-fixes — Review subsystem: deleted-refs + execution infrastructure

```yaml
task: 'review-subsystem-fixes — Review subsystem: deleted-refs + execution infrastructure'
slug: review-subsystem-fixes
approved: true
started: 20260504-122950
parent: main
root: ""
verify: null
```

## Batch Index

```yaml
batches:
  - name: content-helpers
    file: 01-content-helpers.md
    depends-on: []
    verify: uv run --project "${CLAUDE_PLUGIN_ROOT}" python "${CLAUDE_PLUGIN_ROOT}/unit_tests/run-all.py"
  - name: subprocess-tree-kill
    file: 02-subprocess-tree-kill.md
    depends-on: []
    verify: uv run --project "${CLAUDE_PLUGIN_ROOT}" python "${CLAUDE_PLUGIN_ROOT}/unit_tests/run-all.py"
  - name: llm-rate-limit
    file: 03-llm-rate-limit.md
    depends-on: []
    verify: uv run --project "${CLAUDE_PLUGIN_ROOT}" python "${CLAUDE_PLUGIN_ROOT}/unit_tests/run-all.py"
  - name: review-plan-integration
    file: 04-review-plan-integration.md
    depends-on: [content-helpers]
    verify: uv run --project "${CLAUDE_PLUGIN_ROOT}" python "${CLAUDE_PLUGIN_ROOT}/unit_tests/run-all.py"
  - name: review-code-integration
    file: 05-review-code-integration.md
    depends-on: [content-helpers, review-plan-integration]
    verify: uv run --project "${CLAUDE_PLUGIN_ROOT}" python "${CLAUDE_PLUGIN_ROOT}/unit_tests/run-all.py"
  - name: cli-error-prefix
    file: 06-cli-error-prefix.md
    depends-on: [content-helpers]
    verify: uv run --project "${CLAUDE_PLUGIN_ROOT}" python "${CLAUDE_PLUGIN_ROOT}/unit_tests/run-all.py"
  - name: plan-validate-deletes
    file: 07-plan-validate-deletes.md
    depends-on: [content-helpers]
    verify: uv run --project "${CLAUDE_PLUGIN_ROOT}" python "${CLAUDE_PLUGIN_ROOT}/unit_tests/run-all.py"
  - name: mill-plan-skill-step45
    file: 08-mill-plan-skill-step45.md
    depends-on: [review-plan-integration]
    verify: null
```

## Shared Decisions

### Decision: tests-shape

- **Decision:** Tests live in `plugins/mill/unit_tests/` as `test-<name>.py` (one file per helper or backend module). All fixtures are in-memory or use `tempfile`. No real LLM, no real git mutation outside tempfile-backed fixtures. Run via `uv run --project "${CLAUDE_PLUGIN_ROOT}" python "${CLAUDE_PLUGIN_ROOT}/unit_tests/run-all.py"`.
- **Rationale:** Existing project convention (per CLAUDE.md). Keeps the suite fast, deterministic, and runnable on every commit.
- **Applies to:** all batches.

### Decision: tdd-first-helpers

- **Decision:** TDD-first for `compute_deletes_union` (Card 2), the `resolve_ref_paths` extension with `deletes_union` (Card 3), `detect_resume_round` (Card 5), and `_scan_rate_limit` (Card 11). Write the failing test first, then the implementation. The other cards may add tests in the same card or in a dedicated test card after the implementation lands.
- **Rationale:** These four have pure, isolated input/output surfaces. Locking the contract via tests first keeps the implementations small.
- **Applies to:** content-helpers, llm-rate-limit.

### Decision: subprocess-contract-preserved

- **Decision:** The `_subprocess_util.run` public contract is preserved across the rewrite: same `subprocess.CompletedProcess[str]` return type, same `subprocess.TimeoutExpired` exception on timeout, same `[subprocess] spawn argv=... timeout=...` and `[subprocess] exit code=... duration=...s` (or `exit code=timeout duration=...s`) breadcrumb format on stderr.
- **Rationale:** Every mill script depends on this surface. Smoke tests grep the breadcrumbs. Changing the contract would cascade into unrelated work.
- **Applies to:** subprocess-tree-kill.

### Decision: stdlib-only-subprocess-kill

- **Decision:** No new dependencies. The tree-kill path uses stdlib only: `subprocess.Popen` with `start_new_session=True` on POSIX, `subprocess.run(["taskkill", "/T", "/F", "/PID", str(proc.pid)])` on Windows, `os.killpg(os.getpgid(proc.pid), signal.SIGKILL)` on POSIX, `_GRACE_SECONDS = 5` constant.
- **Rationale:** `psutil` and `pywin32` would solve the same problem with extra surface area. The stdlib path is enough.
- **Applies to:** subprocess-tree-kill.

### Decision: reviewer-timeout-kwarg

- **Decision:** Every reviewer module's `run()` function gains a keyword-only parameter `timeout: int | None = None`. When None, the inner `_llm_claude.run_*` default applies (no kwarg propagated). When set, the value is forwarded to the LLM provider. The test stub captures `timeout` in the kwargs dict so backend tests can assert the right value flows through.
- **Rationale:** Today the per-batch and holistic paths share one hard-coded LLM-provider default; the wiki's `bulk_timeout` is silently ignored. To plumb `holistic_timeout` (and to make `bulk_timeout` actually take effect) the reviewer signature has to extend.
- **Applies to:** content-helpers, review-plan-integration, review-code-integration.

### Decision: deletes-section-from-raw-strings

- **Decision:** `build_deletes_section(deletes_tokens: list[str])` accepts raw token strings (not resolved `Path` objects), so pending-future deletes that aren't on disk yet still surface to the reviewer. Output: `## Intentionally deleted (N=<count>)\n\n- <token-1>\n- <token-2>\n...`. No trailing newline. Empty list returns the empty string so callers can splice unconditionally.
- **Rationale:** A delete declared in batch 02 of a not-yet-implemented plan resolves to a string in `deletes_union` but has no `Path` (the file may not exist yet, or may be created and deleted across batches). Strings preserve the planner's declared form and avoid path-resolution edge cases.
- **Applies to:** content-helpers, review-plan-integration, review-code-integration.

### Decision: commit-message-style

- **Decision:** Conventional Commits. `feat(<scope>): <summary>` for new behaviour, `fix(<scope>): <summary>` for bug fixes, `test(<scope>): <summary>` for test-only commits, `chore(<scope>): <summary>` for config / build-ish changes, `docs(<scope>): <summary>` for prose-only edits. Scope is the affected module/skill (e.g. `review-common`, `subprocess`, `llm-claude`, `review-plan`, `review-code`, `review-cli`, `plan-validate`, `mill-plan`, `wiki`, `plan-batch`, `reviewers`).
- **Rationale:** Existing repo convention; keeps `git log` greppable.
- **Applies to:** all batches.

### Decision: deletes-field-on-cards-this-plan

- **Decision:** Every card in this plan declares `**Deletes:** none` on its own bullet line, even though no card actually deletes a file. Once the `plan-validate-deletes` batch (B07) lands, `_REQUIRED_CARD_FIELDS` includes `Deletes` — declaring it now keeps the plan validator-stable if anything re-validates the plan during or after mill-go execution.
- **Rationale:** Cheap, harmless future-proofing. The pre-B07 validator ignores the field; the post-B07 validator requires it.
- **Applies to:** all batches.

## All Files Touched

- `plugins/mill/scripts/_llm_claude.py`
- `plugins/mill/scripts/_plan_validate.py`
- `plugins/mill/scripts/_review_cli.py`
- `plugins/mill/scripts/_review_code.py`
- `plugins/mill/scripts/_review_common.py`
- `plugins/mill/scripts/_review_plan.py`
- `plugins/mill/scripts/_reviewer_sonnetmax.py`
- `plugins/mill/scripts/_reviewer_sonnetmax_tool.py`
- `plugins/mill/scripts/_reviewer_test_stub.py`
- `plugins/mill/scripts/_subprocess_util.py`
- `plugins/mill/scripts/millpy-review-code.py`
- `plugins/mill/scripts/millpy-review-discussion.py`
- `plugins/mill/scripts/millpy-review-plan.py`
- `plugins/mill/skills/mill-plan/SKILL.md`
- `plugins/mill/templates/plan-batch.md`
- `plugins/mill/unit_tests/test-llm-claude.py`
- `plugins/mill/unit_tests/test-plan-validate.py`
- `plugins/mill/unit_tests/test-review-cli.py`
- `plugins/mill/unit_tests/test-review-code-flow.py`
- `plugins/mill/unit_tests/test-review-common.py`
- `plugins/mill/unit_tests/test-review-plan-flow.py`
- `plugins/mill/unit_tests/test-reviewer-modules.py`
- `plugins/mill/unit_tests/test-subprocess-util.py`
- `wiki/config.yaml`
