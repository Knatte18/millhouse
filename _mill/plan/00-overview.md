# Plan: mill-setup/wiki/docs/build-env: misc small bugs, round 3

```yaml
task: 'mill-setup/wiki/docs/build-env: misc small bugs, round 3'
slug: mill-setup-wiki-doc-misc-r3
approved: true
started: '20260923-103951'
parent: main
root: ""
verify: null
discussion_sha: c469861f3beea704662c011b4dfc920de7769700
```

## Batch Index

```yaml
batches:
  - number: 1
    name: mill-triage-title-escape
    file: 01-mill-triage-title-escape.md
    depends-on: []
    verify: null
  - number: 2
    name: handoff-draft-order
    file: 02-handoff-draft-order.md
    depends-on: []
    verify: null
  - number: 3
    name: claude-settings-denylist
    file: 03-claude-settings-denylist.md
    depends-on: []
    verify: PYTHONPATH= uv run --project plugins/mill python plugins/mill/unit_tests/test-claude-settings.py
  - number: 4
    name: golangci-lint-sandbox-fallback
    file: 04-golangci-lint-sandbox-fallback.md
    depends-on: []
    verify: null
```

## Shared Decisions

### Decision: independent-batches

- **Decision:** Each batch fixes one of five unrelated bugs from `discussion.md`'s `## Decisions` > `bundling`. All four batches (#1113, #1138, #1127, #1111) have `depends-on: []` — zero file overlap between them, so mill-go may execute them in any order, including in parallel if the executor ever supports it.
- **Rationale:** matches `discussion.md`'s own bundling decision: one plan batch per bug, no DAG dependencies.
- **Applies to:** all batches.

### Decision: 1112-descoped

- **Decision:** `#1112` (wiki-access guard hook false-positive) is descoped from this plan — no batch implements it. Per `discussion.md`'s `1112-investigation-in-plan` Decision, locating the hook was part of this plan's own investigation scope, with an explicit fallback to document-and-defer if it couldn't be found. Re-confirmed at Phase: Plan time: no `hooks` key exists in any of this repo's six plugin manifests (`plugins/*/.claude-plugin/plugin.json`), no `hooks.json` file exists anywhere under `plugins/`, `.claude/settings.json` at the worktree root is `{}`, and `~/.claude/settings.json` has no `hooks` key. No `settings.local.json` exists anywhere searched. The guard hook issue #1112 describes could not be located anywhere in this repository's or this machine's current Claude Code configuration.
- **Rationale:** a fix cannot be written against code/config that isn't found; inventing a stub hook or guessing at a location would risk masking the real one if it exists elsewhere (a different machine, a harness-internal mechanism not exposed via `hooks.json`, or the issue's bug having already been resolved by removing the offending hook entirely). Recording the investigation trail here — rather than silently dropping #1112 — means a future session that reproduces the false positive live has a documented list of what was already checked and ruled out, so it doesn't repeat the same dead-end search.
- **Applies to:** all batches (informational — no batch acts on this decision).
- **Follow-up:** if the guard hook is reproduced live again (see issue #1112's two repro cases), a fresh task should locate it via the actual blocking event (harness debug output, or a differently-scoped settings file this search didn't check) rather than re-running this same static search.

## All Files Touched

- `plugins/golang/skills/golang-build/SKILL.md`
- `plugins/mill/scripts/_claude_settings.py`
- `plugins/mill/skills/handoff/SKILL.md`
- `plugins/mill/skills/mill-setup/SKILL.md`
- `plugins/mill/skills/mill-triage-to-tasks/SKILL.md`
- `plugins/mill/unit_tests/test-claude-settings.py`
