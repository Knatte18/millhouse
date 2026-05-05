# Plan: 6 — mill-go SKILL.md prose + lock-API + lock-coverage + Builder-oppførsel

```yaml
task: 6 — mill-go SKILL.md prose + lock-API + lock-coverage + Builder-oppførsel
slug: mill-go-fixes
approved: true
started: 20260504-121302
parent: main
root: ""
verify: uv run --project "plugins/mill" python "plugins/mill/unit_tests/run-all.py"
```

## Batch Index

```yaml
batches:
  - name: wiki-lock-unification
    file: 01-wiki-lock-unification.md
    depends-on: []
    verify: uv run --project "plugins/mill" python "plugins/mill/unit_tests/run-all.py"
  - name: helper-api-additions
    file: 02-helper-api-additions.md
    depends-on: []
    verify: uv run --project "plugins/mill" python "plugins/mill/unit_tests/run-all.py"
  - name: validate-plan-typeerror
    file: 03-validate-plan-typeerror.md
    depends-on: []
    verify: uv run --project "plugins/mill" python "plugins/mill/unit_tests/run-all.py"
  - name: mill-go-skill-rewrite
    file: 04-mill-go-skill-rewrite.md
    depends-on: [wiki-lock-unification, helper-api-additions]
    verify: null
  - name: mill-plan-start-resume-prose
    file: 05-mill-plan-start-resume-prose.md
    depends-on: [wiki-lock-unification]
    verify: null
  - name: workflow-anti-patterns
    file: 06-workflow-anti-patterns.md
    depends-on: [wiki-lock-unification]
    verify: null
```

## Shared Decisions

### Decision: lock-API contract — helpers own the lock, plus `wiki_lock` context manager

- **Decision:** `_wiki.sync_pull(wiki_path, *, slug)` and `_wiki.write_commit_push(wiki_path, paths, msg, *, slug)` acquire and release the wiki advisory lock internally. A new `_wiki.wiki_lock(wiki_path, slug)` context manager exists for callers that need a multi-operation locked window (the canonical case is the Handoff Home.md flip: read text → `_tasks_md.set_phase_at` → `write_commit_push`). When `wiki_lock` already holds the lock for this PID, the inner acquire in `sync_pull` / `write_commit_push` is a no-op (re-entrancy via a module-level `_held_locks: dict[Path, int]` counter). Stale-self-lock detection: `_acquire` finds a lockfile whose holder slug matches the caller's `slug` → reclaim immediately (overwrite + warn) instead of waiting for the timeout. The old public `_wiki.acquire_lock` / `_wiki.release_lock` symbols are removed; their work moves to module-private `_acquire` / `_release` helpers used only by `sync_pull`, `write_commit_push`, and `wiki_lock`.
- **Rationale:** Subsumes #27 (asymmetric signatures), #82 (stale lock on uncaught exception), and the 2026-04-28 wiki-concurrency bug (`Cannot fast-forward to multiple branches`) in one move. Callers stop touching the lock API directly, so the asymmetric-signature trap disappears. `try/finally` inside helpers and `__exit__` inside the context manager both release on the exception path. Stale-self-lock detection turns the existing 30s wait into immediate reclaim when the prior holder is the same task that crashed without releasing.
- **Applies to:** all batches (B01 implements; B04, B05, B06 reference the new API in SKILL.md prose; B02 unaffected).

### Decision: task-state path invariants — local commits, no push

- **Decision:** Every mutation of `status.md`, `reviews/<file>`, and `plan/<file>` in mill-go (and in mill-plan, mill-start) is committed via `git -C <worktree> add <path> && git -C <worktree> commit -m "..."` on the task branch. No push from per-card commits. mill-merge handles the push at task end. `_wiki.write_commit_push` is reserved for shared wiki files (Home.md, _Sidebar.md) only.
- **Rationale:** Restores the CLAUDE.md "Path invariants" rule that working state lives at the worktree root on the task branch, not in the wiki. mill-resume on another machine fetches the task branch from origin (`git fetch origin <branch>`) — push from per-card commits is a recovery-path optimisation, not a correctness requirement.
- **Applies to:** B04 (mill-go SKILL.md), B05 (mill-plan SKILL.md step 1.5).

### Decision: implementer-brief and template HTML comments

- **Decision:** `_render.render` strips a leading `<!-- ... -->` comment at the very start of any template before token substitution. Mid-template HTML comments are preserved verbatim. Templates may continue to ship with their leading documentation comment; callers do not need to strip it.
- **Rationale:** Saves ~600 tokens per implementer call (the implementer-brief's 22-line documentation header) and removes per-template strip duplication. Pattern reference: `_status._strip_leading_comment` in `_status.py`.
- **Applies to:** B02 (implementation), B04 (mill-go SKILL.md may reference the new behaviour in passing).

### Decision: implementer report `session_id` field — literal echo

- **Decision:** `implementer-brief.md`'s `## Report` section requires the `session_id` value to be the exact UUID passed via the implementer's `--session-id` flag. Implementers MUST echo it literally. mill-go does NOT validate the field; it continues to use the UUID it generated. The fix is the contract, not enforcement.
- **Rationale:** Across four sightings (#71, #89, #105 + earlier) implementers invented synthetic strings in this field. Today it is harmless (mill-go ignores), but the broken contract is a footgun for future code that round-trips the UUID. Cheap to fix in template; mill-go enforcement would be over-engineering.
- **Applies to:** B02 (template change only).

### Decision: implementer tool surface — add `Skill`

- **Decision:** `_llm_claude.run_implementer` passes `--allowedTools Read,Edit,Write,Bash,Grep,Glob,Skill`. The added `Skill` tool lets the implementer invoke `@git-commit` (and any other skills the brief instructs).
- **Rationale:** The implementer brief already instructs per-card commits via `@git-commit` so `git-commit`'s lint + `codeguide-update` runs. Without `Skill` that instruction is dead letter; the implementer falls back to raw `git commit` and codeguide drifts on every batch.
- **Applies to:** B02 (one-line change in `_llm_claude.py`).

### Decision: `${CLAUDE_PLUGIN_ROOT}` for intra-plugin paths in SKILL.md

- **Decision:** Every script invocation in SKILL.md prose uses `uv run --project "${CLAUDE_PLUGIN_ROOT}" "${CLAUDE_PLUGIN_ROOT}/scripts/<name>.py"`. Inline Python helpers use `uv run --project "${CLAUDE_PLUGIN_ROOT}" python -c "..."`. The exception is `mill-setup` which is the bootstrapper and uses `PYTHONPATH="${CLAUDE_PLUGIN_ROOT}/scripts"` inline.
- **Rationale:** External repos using mill as a plugin have no millhouse source checkout. Hard-coded `plugins/mill/...` paths would break those repos. CLAUDE.md flags this as load-bearing.
- **Applies to:** B04, B05, B06 (every SKILL.md edit must preserve this convention).

### Decision: testing — unit tests use `tempfile`/in-memory fixtures, no real git, no real LLM

- **Decision:** Unit tests added in B01, B02, B03 use `tempfile.TemporaryDirectory` for filesystem fixtures and patch `_subprocess_util.run` (or equivalent) instead of invoking real `git` / `claude`. Integration tests (live `git`, optionally live `claude`) live under `plugins/mill/integration_tests/`.
- **Rationale:** Existing convention per CLAUDE.md "Repo layout pointers". Keeps the unit-test suite fast and hermetic.
- **Applies to:** B01, B02, B03.

## All Files Touched

- `plugins/mill/integration_tests/test-bootstrap.ps1`
- `plugins/mill/integration_tests/test-merge.py`
- `plugins/mill/integration_tests/test-wiki-concurrency.py`
- `plugins/mill/scripts/_llm_claude.py`
- `plugins/mill/scripts/_render.py`
- `plugins/mill/scripts/_spawn_core.py`
- `plugins/mill/scripts/_tasks_md.py`
- `plugins/mill/scripts/_wiki.py`
- `plugins/mill/scripts/millpy-abandon.py`
- `plugins/mill/scripts/millpy-add.py`
- `plugins/mill/scripts/millpy-claim.py`
- `plugins/mill/scripts/millpy-cleanup.py`
- `plugins/mill/scripts/millpy-spawn.py`
- `plugins/mill/scripts/millpy-validate-plan.py`
- `plugins/mill/skills/mill-go/SKILL.md`
- `plugins/mill/skills/mill-merge/SKILL.md`
- `plugins/mill/skills/mill-plan/SKILL.md`
- `plugins/mill/skills/mill-resume/SKILL.md`
- `plugins/mill/skills/mill-start/SKILL.md`
- `plugins/mill/skills/workflow/SKILL.md`
- `plugins/mill/templates/implementer-brief.md`
- `plugins/mill/unit_tests/test-abandon.py`
- `plugins/mill/unit_tests/test-cleanup.py`
- `plugins/mill/unit_tests/test-llm-claude.py`
- `plugins/mill/unit_tests/test-millpy-claim.py`
- `plugins/mill/unit_tests/test-millpy-spawn.py`
- `plugins/mill/unit_tests/test-millpy-validate-plan.py`
- `plugins/mill/unit_tests/test-render.py`
- `plugins/mill/unit_tests/test-tasks-md.py`
- `plugins/mill/unit_tests/test-wiki.py`
