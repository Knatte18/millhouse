# Plan: Audit and clean up stale V2 references

```yaml
task: Audit and clean up stale V2 references
slug: stale-v2-references-audit
approved: false
started: 20260527-072704
parent: main
root: ""
verify: null
```

## Batch Index

```yaml
batches:
  - number: 1
    name: Simple skill fixes
    file: 01-simple-skills.md
    depends-on: []
    verify: "PYTHONPATH= bash -c \"! grep -lrq '_wiki[.]' plugins/mill/skills/mill-plan/SKILL.md plugins/mill/skills/mill-start/SKILL.md plugins/mill/skills/mill-merge-in/SKILL.md plugins/mill/skills/mill-resume/SKILL.md plugins/mill/skills/workflow/SKILL.md\""
  - number: 2
    name: Medium skill fixes
    file: 02-medium-skills.md
    depends-on: []
    verify: "PYTHONPATH= bash -c \"! grep -rq '_wiki[.]\\|_tasks_md[.]' plugins/mill/skills/mill-finalize/SKILL.md plugins/mill/skills/mill-fold/SKILL.md plugins/mill/skills/mill-merge/SKILL.md plugins/mill/skills/mill-groom/SKILL.md\""
  - number: 3
    name: mill-go skill fix
    file: 03-mill-go.md
    depends-on: []
    verify: "PYTHONPATH= bash -c \"! grep -q '_wiki[.]\\|_tasks_md[.]\\|WikiHealthError' plugins/mill/skills/mill-go/SKILL.md\""
  - number: 4
    name: High-complexity skill fixes
    file: 04-high-complex-skills.md
    depends-on: []
    verify: "PYTHONPATH= bash -c \"! grep -rq '_wiki[.]\\|_tasks_md[.]\\|_sidebar[.]' plugins/mill/skills/mill-setup/SKILL.md plugins/mill/skills/mill-ghissues-to-tasks/SKILL.md plugins/mill/skills/mill-autofix/SKILL.md\""
  - number: 5
    name: Python comment fixes
    file: 05-python-comments.md
    depends-on: [1, 2, 3, 4]
    verify: "PYTHONPATH= bash -c \"! grep -rq '_wiki[.]' plugins/mill/skills/ && ! grep -rq '_tasks_md[.]' plugins/mill/skills/ && ! grep -rqE 'v2 shape|v2.s contract|valid v2 task|v2.s Home' plugins/mill/scripts/ plugins/mill/integration_tests/\""
```

## Shared Decisions

### Decision: v2-api-deletions

- **Decision:** `_wiki.sync_pull`, `_wiki.wiki_lock`, and `_wiki.write_commit_push` references are deleted from all skills. No replacement for sync_pull (daemon handles freshness). wiki_lock is replaced by `_client.merge_tasks` where atomicity is needed. write_commit_push is replaced by the appropriate `_client` mutation.
- **Rationale:** Both `_wiki.py` and `_tasks_md.py` no longer exist. V3 wiki is daemon-backed; all mutations go through `wiki._client`.
- **Applies to:** all batches

### Decision: client-inline-python

- **Decision:** Wiki operations in SKILL.md pseudocode that have no existing `millpy-*.py` CLI use inline Python via `"$MILL_PYTHON" -c "from wiki import _client; ..."`.
- **Rationale:** `_client` is a thin TCP wrapper; Python startup (~100–200ms) is negligible. Pattern matches existing millpy scripts.
- **Applies to:** all batches

### Decision: tasks-md-replacement

- **Decision:** `_tasks_md.parse(home_text)` → `_client.list_tasks_brief(wiki_path)` (returns list of dicts with `"status"` not `"phase"`). `_tasks_md.set_phase_at(path, slug, phase)` → `_client.set_phase(wiki_path, slug, phase)`. `_tasks_md.LOCKED_FOLD_PHASES` → inline set `{"active", "ready-to-merge", "pr-pending"}`.
- **Rationale:** Direct equivalents per V3 cheatsheet.
- **Applies to:** batches 2, 4

### Decision: sidebar-auto-rendered

- **Decision:** All `_sidebar.regenerate(wiki_path)` calls are deleted. No replacement.
- **Rationale:** In V3, `_Sidebar.md` is auto-rendered by the daemon after every mutation. Any explicit call is obsolete and references a deleted module.
- **Applies to:** batches 1 (mill-resume Phase 10), 2 (mill-merge §8, mill-groom Step 2.1), 4 (mill-setup Phase 6a, mill-ghissues-to-tasks Step 3)

### Decision: board-discipline-v3

- **Decision:** Every "Board discipline" footer that says "Home.md writes go through `_wiki.write_commit_push`..." is replaced with: "Wiki mutations go through `_client` calls (`set_phase`, `upsert_task`, `merge_tasks`); the daemon serializes all writes and pushes automatically. For multi-step atomic operations use `_client.merge_tasks`."
- **Rationale:** The V2 mental model (lock → write → push) is wrong for V3.
- **Applies to:** batches 1, 2, 3

## All Files Touched

- `plugins/mill/integration_tests/test-plan-assets.py`
- `plugins/mill/scripts/_worktree.py`
- `plugins/mill/scripts/millpy-add.py`
- `plugins/mill/scripts/millpy-spawn.py`
- `plugins/mill/skills/mill-autofix/SKILL.md`
- `plugins/mill/skills/mill-finalize/SKILL.md`
- `plugins/mill/skills/mill-fold/SKILL.md`
- `plugins/mill/skills/mill-ghissues-to-tasks/SKILL.md`
- `plugins/mill/skills/mill-go/SKILL.md`
- `plugins/mill/skills/mill-groom/SKILL.md`
- `plugins/mill/skills/mill-merge-in/SKILL.md`
- `plugins/mill/skills/mill-merge/SKILL.md`
- `plugins/mill/skills/mill-plan/SKILL.md`
- `plugins/mill/skills/mill-resume/SKILL.md`
- `plugins/mill/skills/mill-setup/SKILL.md`
- `plugins/mill/skills/mill-start/SKILL.md`
- `plugins/mill/skills/workflow/SKILL.md`
