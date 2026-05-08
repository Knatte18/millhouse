# Plan: 32 (A) — Bug-fix batch 2

```yaml
task: 32 (A) — Bug-fix batch 2
slug: mill-misc-fixes-2
approved: true
started: 20260508-134632
parent: main
root: ""
verify: python plugins/mill/unit_tests/run-all.py
```

## Batch Index

```yaml
batches:
  - number: 1
    name: script-fixes
    file: 01-script-fixes.md
    depends-on: []
    verify: python plugins/mill/unit_tests/run-all.py
  - number: 2
    name: gh-issues
    file: 02-gh-issues.md
    depends-on: []
    verify: python plugins/mill/unit_tests/run-all.py
  - number: 3
    name: docs
    file: 03-docs.md
    depends-on: []
    verify: null
```

## Shared Decisions

### Decision: test-pattern-mock-subprocess

- **Decision:** Every new or modified unit-test fixture mocks `_subprocess_util.run` (or the local `subprocess.run` reference inside the module under test) instead of invoking real `git` or `gh`. The exception is `test-spawn-core.py`, which already invokes real `git` against a tempdir-bare-remote pattern (`_make_wiki` at `test-spawn-core.py:81-135`) — extend the same pattern when adding origin-remote setup for the spawn test fixture.
- **Rationale:** Existing tests mock at the subprocess boundary (`test-gh-issues.py` patches `_gh_issues._subprocess_util.run`). Keeping that pattern uniform avoids real-network/real-git flakiness and matches CLAUDE.md `## Repo layout pointers` rule "no real git, no real LLM" for unit tests. `test-spawn-core.py` is a deliberate exception because it asserts on real-git side-effects (commit log entries).
- **Applies to:** all batches

### Decision: commit-message-conventional

- **Decision:** Every card's `Commit:` line uses Conventional Commits with one of: `fix`, `feat`, `refactor`, `test`, `docs`. The scope in parentheses names the affected module or skill (e.g., `fix(holistic-implement)`, `docs(mill-plan)`).
- **Rationale:** Matches the repo's existing commit-log style (see `git log --oneline plugins/mill/`). Keeps the squash-merge message readable when mill-merge collapses 11 cards into one parent-branch commit.
- **Applies to:** all batches

### Decision: no-comments-or-docstrings

- **Decision:** Code edits do not add new explanatory comments or docstrings unless removing one would leave a non-obvious WHY. Existing comments stay in place; small bug fixes do not justify rewriting surrounding documentation.
- **Rationale:** Matches the global "no comments" guideline in the agent system prompt and the repo's existing helper style. The plan's bugs are mechanical; commentary would be noise.
- **Applies to:** Batches 1, 2 (Batch 3 is doc-only, prose lives in the documents themselves).

### Decision: backward-compatible-default-for-detect-repo

- **Decision:** `_gh_issues.detect_repo(git_root: Path | None = None)` keeps `None` as a working default — when `None`, fall back to `_paths.resolve_git_root()` and parse `git -C <git_root> remote get-url origin`. The `gh repo view` lookup is removed entirely. The two in-tree call sites MUST pass `git_root=` explicitly per the discussion's `detect-repo-explicit-git-root` Decision; the default is a safety-net for any future caller, not a recommended pattern.
- **Rationale:** Removing `gh repo view` is the load-bearing fix. The default-`None` keeps the helper signature non-breaking while making the explicit param the documented contract for callers (enforced via SKILL.md updates in Batch 2, Cards 8 and 9).
- **Applies to:** Batch 2

## All Files Touched

- `CLAUDE.md`
- `plugins/mill/scripts/_gh_issues.py`
- `plugins/mill/scripts/_plan_validate.py`
- `plugins/mill/scripts/_spawn_core.py`
- `plugins/mill/scripts/millpy-builder-lock.py`
- `plugins/mill/scripts/millpy-implement-holistic.py`
- `plugins/mill/skills/mill-autofix/SKILL.md`
- `plugins/mill/skills/mill-ghissues-to-tasks/SKILL.md`
- `plugins/mill/skills/mill-plan/SKILL.md`
- `plugins/mill/unit_tests/test-gh-issues.py`
- `plugins/mill/unit_tests/test-millpy-implement-holistic.py`
- `plugins/mill/unit_tests/test-plan-validate.py`
- `plugins/mill/unit_tests/test-spawn-core.py`
