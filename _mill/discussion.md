# Discussion: Audit and clean up stale V2 references

```yaml
task: Audit and clean up stale V2 references
slug: stale-v2-references-audit
status: discussing
parent: main
```

## Problem

The wiki migration from V2 (Home.md as source of truth, `_wiki.py` + `_tasks_md.py` helper modules) to V3 (TinyDB daemon, `wiki._client` TCP API, Home.md auto-rendered) is functionally complete in Python scripts, but 13 SKILL.md files still instruct Claude to call `_wiki.sync_pull`, `_wiki.wiki_lock`, `_wiki.write_commit_push`, `_tasks_md.parse`, `_tasks_md.set_phase_at` etc. Both `_wiki.py` and `_tasks_md.py` no longer exist in the repository. Any skill invocation that follows the stale instructions gets `ModuleNotFoundError` on the first wiki operation.

Three Python source files also carry stale "v2" comments (no logic impact, but confusing). One integration test comment mentions "v2 shape".

## Scope

**In:**
- All 13 SKILL.md files under `plugins/mill/skills/` that reference `_wiki.` or `_tasks_md.`
- Stale "v2" comments in 3 Python scripts (`millpy-add.py`, `millpy-spawn.py`, `_worktree.py`)
- Stale "v2 shape" comment in `integration_tests/test-plan-assets.py`
- mill-setup Phase 6 ("Initialise or normalise Home.md") — full architectural rethink (see Decisions)
- mill-autofix — full rewrite of Home.md read/write logic to use `_client`

**Out:**
- Functional V3 bug fixes (tracked in `wiki-v3-followups`)
- Removing or renaming existing CLI scripts (`millpy-*.py`)
- Changes to `wiki/_client.py`, `wiki/_server.py`, or any other Python implementation file
- Adding new CLI wrapper scripts for wiki operations
- Changing the daemon's TCP protocol or wire format

## Decisions

### wiki-access-pattern-in-skills

- **Decision:** SKILL.md pseudocode uses inline Python `_client` calls via `"$MILL_PYTHON" -c "from wiki import _client; ..."` for wiki operations that have no existing `millpy-*.py` CLI entry point.
- **Rationale:** The Python client is a thin TCP wrapper; the daemon carries all the heavy work (TinyDB, git push, rendering). Python startup (~100–200ms) is negligible compared to V2 where Python did everything. Pattern is consistent with existing millpy scripts. Avoids adding new CLI wrappers just to keep SKILL.md "clean".
- **Rejected:** Raw TCP + curl (requires SKILL.md to read port from `.wiki-daemon.json`, no auto-start, more fragile). Thin CLI wrappers (unnecessary complexity, same cost as inline Python).

### no-sync-pull

- **Decision:** Delete all `_wiki.sync_pull(...)` calls from SKILL.md. No replacement.
- **Rationale:** The V3 daemon pushes to the wiki remote on every mutation and pulls on startup. There is no "stale local clone" problem to solve. A sync_pull call would fail with `ModuleNotFoundError` anyway.
- **Rejected:** Replacing with `_client.health_check(wiki_path)` as a proxy — unnecessary; daemon auto-starts on first real call.

### no-wiki-lock

- **Decision:** Delete all `with _wiki.wiki_lock(wiki_path, slug):` blocks from SKILL.md. No replacement.
- **Rationale:** The daemon serializes all writes internally. For multi-step atomic operations, use `_client.merge_tasks(wiki_path, remove_slugs=[...], upsert={...}, set_phase=(...))`.
- **Rejected:** Replacing with a client-side lock — the daemon's serialization makes it redundant.

### write-commit-push-replacement

- **Decision:** Replace `_wiki.write_commit_push(wiki_path, paths, msg, slug=...)` with the appropriate `_client` mutation: `_client.set_phase(wiki_path, slug, phase)`, `_client.upsert_task(wiki_path, slug, ...)`, or `_client.merge_tasks(...)` depending on context.
- **Rationale:** `_wiki.write_commit_push` wrote raw files and committed; the daemon owns that now.
- **Rejected:** git commit + push from SKILL.md for wiki files — daemon owns the wiki repo's git state.

### mill-setup-phase6-deletion

- **Decision:** Delete mill-setup Phase 6 ("Initialise or normalise Home.md") and Phase 6a ("Initialise `_Sidebar.md` via `_sidebar.regenerate()`") entirely. Replace both with a single `_client.list_tasks_brief(wiki_path)` call (goes through `_ensure_daemon`, triggering auto-start + initial render of both Home.md and _Sidebar.md).
- **Rationale:** Phase 6 seeded Home.md from a template (V2 pattern). Phase 6a called `_sidebar.regenerate()` (also V2 module, now gone). In V3, both files are auto-rendered by the daemon from `tasks.json`. `_client.health_check` does NOT trigger auto-start (it returns False if `.wiki-daemon.json` is absent); `list_tasks_brief` goes through `_ensure_daemon` and is the correct trigger. The "v2 shape" probe (`# Tasks` first-line check) is meaningless in V3.
- **Rejected:** Using `_client.health_check` as the startup trigger — confirmed by source inspection that `health_check` bypasses `_ensure_daemon` and returns `False` on fresh install instead of spawning the daemon.

### mill-autofix-full-rewrite

- **Decision:** Rewrite mill-autofix's Home.md read/slug-enumeration/write logic to use `_client.list_tasks_brief(wiki_path)` for reads and `_client.upsert_task(wiki_path, slug, ...)` for writes.
- **Rationale:** mill-autofix currently reads Home.md to enumerate existing slugs (via `_TASK_HEADING_RE`) and calls `_tasks_md.parse(home_text)` to list tasks. Both operations now map directly to `_client.list_tasks_brief(wiki_path)` which returns `[{id, slug, title, group, brief, status, has_proposal}]`. Write-back via `_wiki.write_commit_push` is replaced by `_client.upsert_task`.
- **Rejected:** Partial rewrite leaving structural Home.md approach with TODO markers — the stale instructions would still mislead implementers.

### tasks-md-parse-replacement

- **Decision:** Replace every `_tasks_md.parse(home_text)` pattern with `_client.list_tasks_brief(wiki_path)`. Note the field rename: V2 Task objects used `.phase`; V3 dicts use `["status"]`.
- **Rationale:** Direct equivalence per the cheatsheet. Also eliminates the need to first read Home.md text.
- **Rejected:** None; this is a mechanical swap.

### set-phase-replacement

- **Decision:** Replace `_tasks_md.set_phase_at(home_path, slug, phase)` and `_tasks_md.set_phase(home_text, slug, phase)` patterns with `_client.set_phase(wiki_path, slug, phase)`.
- **Rationale:** Direct equivalence. `set_phase` accepts slug or numeric id.
- **Rejected:** None.

### board-discipline-note

- **Decision:** Update "Board discipline" footers in skills to say: "Wiki mutations go through `_client` calls; the daemon serializes all writes and pushes automatically. For multi-step atomic operations use `_client.merge_tasks`."
- **Rationale:** Every skill with a "Board discipline" section still says "Home.md writes go through `_wiki.write_commit_push` (acquires the wiki lock internally)." This is the wrong mental model for V3.
- **Rejected:** None.

### fix-stale-code-comments

- **Decision:** Fix stale "v2" comments in `millpy-add.py`, `millpy-spawn.py`, `_worktree.py`, and `integration_tests/test-plan-assets.py`.
- **Rationale:** Comments describe V2 behavior that no longer applies; they mislead future contributors.
- **Rejected:** Skipping — minimal effort to fix, risk of confusion is real.

## Technical context

### V3 wiki client API (canonical reference)

Full cheatsheet at `.scratch/v3-wiki-cheatsheet.md`. Key operations:

```python
from wiki import _client

# Read
tasks = _client.list_tasks_brief(wiki_path)   # list of {id, slug, title, group, brief, status, has_proposal}
task  = _client.get_task(wiki_path, id_or_slug) # dict or None

# Mutate
_client.set_phase(wiki_path, id_or_slug, phase)           # phase=None clears
_client.upsert_task(wiki_path, slug, *, title=..., brief=..., body=..., group=..., status=...)
_client.merge_tasks(wiki_path, remove_slugs=[...], upsert={...}, set_phase=(slug, phase))

# Daemon
_client.health_check(wiki_path)  # -> bool; does NOT auto-start (probe only)
_client.rerender(wiki_path)
```

V2→V3 field rename: `task["phase"]` → `task["status"]`.

Daemon auto-starts on first `_client` call. No sync_pull, no wiki lock needed.

### Affected SKILL.md files and their change profile

**Simple API swaps (delete sync_pull, replace write_commit_push/set_phase_at):**
- `mill-plan/SKILL.md` — 2 hits: delete `_wiki.sync_pull` call + signature line
- `mill-start/SKILL.md` — 3 hits: delete `_wiki.sync_pull`, update Board discipline footer
- `mill-merge-in/SKILL.md` — 1 hit: delete `_wiki.sync_pull`
- `mill-resume/SKILL.md` — 4 hits: delete `_wiki.sync_pull` references (Entry + error table), update WikiPushError note
- `workflow/SKILL.md` — 1 hit: update Board discipline line

**Medium complexity (phase-set + write-commit-push + lock removal):**
- `mill-go/SKILL.md` — 11 hits: delete sync_pull; replace `_wiki.health_check(hub_root)` + `except _wiki.WikiHealthError` try/except blocks (lines 115–116 and 338–339) with `if not _client.health_check(wiki_path): <error handling>` conditionals; delete wiki_lock + write_commit_push; replace set_phase_at with `_client.set_phase`; update Board discipline
- `mill-finalize/SKILL.md` — 8 hits: delete sync_pull, replace wiki_lock + write_commit_push + set_phase_at with `_client.set_phase` + `_client.merge_tasks`
- `mill-fold/SKILL.md` — 4 hits: remove `_tasks_md.LOCKED_FOLD_PHASES` reference — replace with the hardcoded inline set `{"active", "ready-to-merge", "pr-pending"}` (same pattern as mill-ghissues-to-tasks); update write_commit_push
- `mill-merge/SKILL.md` — 10 hits: delete sync_pull, replace two wiki_lock + write_commit_push + set_phase blocks with `_client.set_phase`, update Board discipline
- `mill-groom/SKILL.md` — 7 hits: delete sync_pull, replace `_tasks_md.parse()` with `_client.list_tasks_brief`, replace write_commit_push

**High complexity (structural rewrites):**
- `mill-setup/SKILL.md` — six changes: (a) Phase 3: replace `import _wiki; result = _wiki.clone_or_init(...)` with `import _setup; result = _setup.clone_or_init(...)` (function moved to `_setup.py`); (b) Phase 3 line 31 scripts listing: remove `_wiki.py` from the `${CLAUDE_PLUGIN_ROOT}/scripts/` directory listing; (c) Phase 6: delete entirely (Home.md is daemon-rendered); (d) Phase 6a: delete `_sidebar.regenerate(...)` call and `_wiki.write_commit_push(["_Sidebar.md"], ...)` — replace the entire phase with a single `_client.list_tasks_brief(wiki_path)` call that triggers daemon startup + initial render; (e) update Phase 5 verification list to remove the "Home.md starts with `# Tasks`" check; (f) update description line to remove "seeds ... Home.md"
- `mill-ghissues-to-tasks/SKILL.md` — 5 hits: replace `_tasks_md.parse()` with `_client.list_tasks_brief`, replace `_tasks_md.append_to_body` pattern with `_client.upsert_task(..., body=...)`, replace `_tasks_md.LOCKED_FOLD_PHASES` with locked-phase inline list (the constant is gone; use hardcoded set `{"active", "ready-to-merge", "pr-pending"}`), replace write_commit_push
- `mill-autofix/SKILL.md` — two changes: (a) Phase 1b: replace Home.md text reading + `_TASK_HEADING_RE` slug extraction with `_client.list_tasks_brief(wiki_path)` to get existing slugs; (b) Step 2 error-handling path (lines 202–212): replace `_tasks_md.parse(home_text)` lookup with `_client.list_tasks_brief(wiki_path)`. The `millpy-add.py` subprocess call in Step 2 stays — it already uses V3 `_client.upsert_task` internally.

### LOCKED_FOLD_PHASES

`_tasks_md.LOCKED_FOLD_PHASES` was a tuple of phase strings you cannot fold into. The module is gone. Its value was `("active", "ready-to-merge", "pr-pending")`. SKILL.md files referencing it should inline this set directly or note it as a policy check.

### Stale code comment locations

| File | Line | Current text | Fix |
|---|---|---|---|
| `plugins/mill/scripts/millpy-add.py` | 43 | `"""Reject anything that is not a valid v2 task slug."""` | Remove "v2" → `"""Reject anything that is not a valid task slug."""` |
| `plugins/mill/scripts/millpy-spawn.py` | 238–240 | Comment describes V2's Home.md limitation | Delete the V2-specific explanation; keep the functional note |
| `plugins/mill/scripts/_worktree.py` | 86 | `in dst are overwritten — v2's contract is that mill-spawn owns` | Remove "v2's contract" → `mill-spawn owns` |
| `plugins/mill/integration_tests/test-plan-assets.py` | 16 | mentions "v2 shape" in comment | Remove "v2 shape" reference |

## Testing

No unit tests cover SKILL.md content. Verification is:

1. After all edits, `grep -r "_wiki\." plugins/mill/skills/` must return zero hits.
2. After all edits, `grep -r "_tasks_md\." plugins/mill/skills/` must return zero hits.
3. After all edits, `grep -rn "v2 shape\|v2's contract\|valid v2 task\|v2's Home" plugins/mill/scripts/ plugins/mill/integration_tests/` must return zero hits.

These three grep checks are the acceptance criteria. The auto-report mechanism handles surfacing any runtime failures discovered during subsequent skill invocations.

## Q&A log

- **Q:** Should SKILL.md pseudocode use raw TCP + curl, thin CLI wrappers, or inline Python `_client` calls for wiki operations? **A:** Inline Python `_client`. The daemon carries the heavy work; Python startup for a thin TCP client call is ~100–200ms — negligible. Pattern is consistent with existing millpy scripts. No new wrappers needed.
- **Q:** What replaces mill-setup Phase 6 (Home.md init / v2-shape gate)? **A:** Delete Phase 6 and Phase 6a entirely. Replace Phase 6a with `_client.list_tasks_brief(wiki_path)` — this goes through `_ensure_daemon`, triggering auto-start + initial render of both Home.md and _Sidebar.md. `health_check` must NOT be used here: it bypasses `_ensure_daemon` and returns False on a fresh install instead of spawning the daemon.
- **Q:** Should mill-autofix be fully rewritten or marked TODO? **A:** Full rewrite. Partial rewrites with TODO markers still mislead implementers.
- **Q:** Fix stale code comments in Python scripts? **A:** Yes, fix all of them.
- **Q:** Prioritise hot-path skills or do all 13? **A:** All 13 in one pass.
- **Q:** Formal skill tests? **A:** No. Auto-report handles surfacing runtime failures.
