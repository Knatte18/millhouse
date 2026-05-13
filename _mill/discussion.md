# Discussion: Add status_md to paths config + refactor 14 callsites

```yaml
task: (A) — Add status_md to paths config + refactor 14 callsites
slug: status-md-in-paths-config
status: discussing
parent: main
```

## Problem

`wiki/config.yaml` declares `paths.discussion_file`, `paths.plan_dir`, and `paths.reviews_dir` but is missing `paths.status_md`. Roughly 14 Python scripts in `plugins/mill/scripts/` reach for the status file. Some go through the centralised `_paths.resolve_task_path(worktree, "_mill/status.md")` helper (which carries a `_mill/` -> `task/` compat fallback for in-flight worktrees), but several call sites still build the path locally with hardcoded segments. Two of them — `millpy-inspect.py:77` and `millpy-status.py:49` — build `wt_path / "status.md"` (missing the `_mill/` segment entirely), which is why `millpy-inspect` currently reports `(no active tasks)` even when the worktree on disk holds a valid `_mill/status.md`. `_review_code.py:220` calls `resolve_path("status.md", slug)`, which is not what `resolve_path` does at all — that signature is `(role, repo_root)`.

The post-rename world (task 33) means `_mill/` is the canonical location, but already-active worktrees from before the rename still hold their state under `task/`. Until every active worktree is drained, every status read must transparently fall back to `task/status.md`. This is the same compat shape `_paths.resolve_task_path` already implements for `discussion.md`, `plan/`, `reviews/`.

**Why now:** `millpy-inspect` is broken for the operator (silent "no active tasks" while tasks exist); the broken `_review_code.py:220` call is a latent bug waiting on the first code-review run that hits its per-batch diff-scope branch; and the config schema is internally inconsistent — three of the four task-state paths are declared, the fourth isn't.

## Scope

**In:**

- Add `status_md: _mill/status.md` to the `paths:` block of `wiki/config.yaml`.
- Mirror the same key into `plugins/mill/templates/wiki-config.yaml` (the seed copied by `mill-setup` into new hubs).
- Add `_paths.status_path(worktree_root, cfg)` helper that reads `cfg["paths"]["status_md"]` and delegates to `_paths.resolve_task_path` so the `_mill/` -> `task/` compat fallback is preserved.
- Refactor all call sites that build the status path locally — including the two bug sites (`millpy-inspect.py:77`, `millpy-status.py:49`) and the broken `_review_code.py:220` — to call `_paths.status_path` instead.
- Leave existing correct call sites alone if they already use `_paths.resolve_task_path(worktree, "_mill/status.md")` — that helper continues to work — but migrate them to `status_path` for uniformity in the same pass.
- Unit-test the new helper: returns the configured path when it exists; falls back to `task/status.md` when only the legacy file exists; returns the configured path (non-existent) when neither exists; raises a clear error when `cfg` lacks `paths.status_md`.

**Out:**

- Do **not** drop the `task/` compat fallback. That is a separate, later task once every in-flight worktree has either merged or had its state migrated.
- Do **not** migrate any on-disk `task/status.md` files to `_mill/status.md`. The compat fallback covers them in place; rewriting active state mid-flight is out of scope.
- Do **not** touch `millpy-migrate-layout.py`. That script's job is reading the *old* layout to produce the new one; its `slug_dir / "status.md"` reads target a historical structure and would break if rewired through the new helper.
- Do **not** broaden the helper to also handle `discussion.md`, `plan/`, `reviews/`. Those already work through `_paths.resolve_task_path(worktree, cfg_relative_path)` driven by the existing `paths.*` keys. A symmetric `discussion_path`/`plan_dir_path`/`reviews_dir_path` family is appealing but adds scope without solving a known bug — defer.
- Do **not** change the new wiki/config.yaml schema in a way that requires a backwards-compat-rollout layer (see Home.md banner). Adding a brand-new key with no readers in the old code path is a pure addition — old code doesn't need it; new code reads it. This task is safe to merge in one go.

## Decisions

### Helper signature

- **Decision:** `_paths.status_path(worktree_root: Path, cfg: dict) -> Path`. Reads `cfg["paths"]["status_md"]` (required, raises `KeyError` if absent — fail loud), then delegates to `_paths.resolve_task_path(worktree_root, cfg_value)` for the existence-checked `_mill/` -> `task/` fallback.
- **Rationale:** Mirrors the existing `_paths.resolve_task_path` shape exactly (one helper, two args, returns `Path`). Reading from `cfg` rather than hardcoding `"_mill/status.md"` keeps the config the single source of truth — a hub that wanted to relocate `status.md` (unlikely but supported by the same `paths:` mechanism that exists for the other three files) only edits `wiki/config.yaml`. Required `KeyError` rather than silent default-fallback because we are explicitly adding the key to every hub's config in this same task; if it's missing in a hub after this lands, something is wrong and we want a loud failure, not a silent half-migration.
- **Rejected:**
  - `status_path(worktree_root)` (no cfg, hardcoded `"_mill/status.md"`): Defeats the purpose of adding the config key. The whole task is "stop hardcoding paths".
  - `status_path(worktree_root, cfg=None)` with default `_mill/status.md` when cfg is None: Adds a non-obvious behaviour difference between "called with cfg" and "called without". Every existing call site has cfg in scope.
  - Reading cfg internally inside the helper (e.g. via `_config.load_config`): Forces a redundant config re-read in scripts that already have cfg loaded. The two call-site categories (`mill-go` per-batch, `mill-status`/`mill-inspect` top-level) both already pass cfg around.

### Compat-fallback ownership

- **Decision:** Compat fallback (`_mill/` -> `task/`) stays inside `_paths.resolve_task_path`. `_paths.status_path` does no fallback logic of its own — it just feeds `cfg["paths"]["status_md"]` into `resolve_task_path` and returns the result.
- **Rationale:** Single owner for the fallback rule. The `[compat]` stderr warning already lives in `resolve_task_path` and gets emitted once per call when the fallback triggers — preserving that behaviour for free.
- **Rejected:** Duplicate the fallback logic inside `status_path`. No reason to fork the rule.

### Where the helper lives

- **Decision:** Add `status_path` to `_paths.py`. Export from `__all__`.
- **Rationale:** Co-located with `resolve_task_path`, `resolve_wiki_path`, `resolve_active_worktree`. The "single home for path resolution" docstring on `_paths.py` is the explicit invariant.
- **Rejected:** Add to `_status.py`. Would invert the dependency (`_paths` would need to call into `_status` later if any other path helpers were added), and breaks the file's "Render + mutate status.md" scope.

### Bug fix scope at the broken call sites

- **Decision:** Fix `millpy-inspect.py:77` and `millpy-status.py:49` (currently `wt_path / "status.md"`) by routing through `_paths.status_path(wt_path, cfg)`. Fix `_review_code.py:220` (currently `resolve_path("status.md", slug)`) by routing through `_paths.status_path(project_root, cfg)` — both `project_root` and `cfg` are already in scope at that call site.
- **Rationale:** The bugs are within the task's stated scope (the third sentence of the Home.md description names `millpy-inspect` explicitly). Fixing them as part of the refactor means the user sees `mill-inspect` come back to life when this task ships.
- **Rejected:** Leave the inspect/status bugs as-is and only add the helper. The helper would exist but its first benefit would land in a follow-up task — wasteful.

### Test approach

- **Decision:** Unit tests in `plugins/mill/unit_tests/test-paths-status.py` (new file). Use `tempfile.TemporaryDirectory` to materialise both layout shapes (`_mill/status.md` present, `task/status.md` present, neither present). Stub `cfg` to a plain dict — no `_config.load_config` call. No regression test for the refactored call sites themselves; they are simple substitutions and exercising them would require a full mill setup fixture.
- **Rationale:** TDD candidate: write the four behaviour cases first, then implement the helper to satisfy them. The helper is small enough that test parity with `resolve_task_path` is realistic.
- **Rejected:** Integration test invoking real `mill-inspect`. Out of scope — that's `integration_tests/`, slower, and adds nothing the unit test doesn't cover for this specific helper.

## Technical context

**Files touched (estimate; mill-plan finalises):**

- `wiki/config.yaml` — add one line under `paths:`.
- `plugins/mill/templates/wiki-config.yaml` — mirror the same line.
- `plugins/mill/scripts/_paths.py` — add `status_path`; register in `__all__`; docstring entry under "Public API".
- `plugins/mill/scripts/millpy-inspect.py:77` — replace local `wt_path / "status.md"` with `_paths.status_path(wt_path, cfg)`. `cfg` is already loaded at `_collect`'s line 47.
- `plugins/mill/scripts/millpy-status.py:49` — same substitution. `cfg` is already loaded at `_build_rows`'s line 26.
- `plugins/mill/scripts/_review_code.py:220` — replace `resolve_path("status.md", slug)` with `_paths.status_path(project_root, cfg)`. Both vars are in scope. Also add `import _paths` to the import block (current imports pull `resolve_path` from `_review_common`, not `_paths` — the new call references a different module).
- `plugins/mill/scripts/_spawn_core.py:716,720` — replace `worktree_path / "_mill" / "status.md"` and `"_mill/status.md"` with `_paths.status_path(worktree_path, cfg)`. The function `write_initial_status` (signature at line 672) needs `cfg: dict` threaded in. Both of its callers — `millpy-spawn.py:240` and `millpy-claim.py:300` — must be updated to pass `cfg` through (in addition to the dry-run-print line updates already listed below for those two files).
- `plugins/mill/scripts/millpy-spawn.py:165` — dry-run print: replace `worktree_path / '_mill' / 'status.md'` with `_paths.status_path(worktree_path, cfg)`. (Same file also updates the `write_initial_status` call at line 240 per the `_spawn_core.py` entry above.)
- `plugins/mill/scripts/millpy-claim.py:216` — dry-run print: replace `resolve_hub_path() / '_mill' / 'status.md'` with `_paths.status_path(resolve_hub_path(), cfg)`. (Same file also updates the `write_initial_status` call at line 300 per the `_spawn_core.py` entry above.)
- `plugins/mill/scripts/millpy-abandon.py:58` — already uses `_paths.resolve_task_path(active_hub, "_mill/status.md")`; migrate to `_paths.status_path(active_hub, cfg)` for uniformity.
- `plugins/mill/scripts/millpy-cleanup.py:130,325,353` — already use `_paths.resolve_task_path`; migrate for uniformity.
- `plugins/mill/scripts/millpy-implement-holistic.py:77` — already uses `_paths.resolve_task_path`; migrate for uniformity.
- `plugins/mill/scripts/millpy-implement.py:93` — already uses `_paths.resolve_task_path`; migrate for uniformity.
- `plugins/mill/scripts/_parent_branch.py` — read-only docstring references to `status.md`; no functional change.
- `plugins/mill/scripts/_timestamp.py` — docstring reference only.

**`_review_code.py` cfg availability:** `_review_code.run_review` (the entry around line 175ish) is called with `cfg` in scope — confirm during planning by reading the function signature.

**Spawn cache mismatch (observed during exploration, NOT in scope):** The current worktree's spawn commit `d4f42f2` wrote `task/status.md` rather than `_mill/status.md`, even though `_spawn_core.py:716` in the source tree writes to `_mill/`. The cache venv (`${CLAUDE_PLUGIN_ROOT}/.venv`) is running pre-task-33 code on this machine. The new helper's `_mill/` -> `task/` fallback means this task's plan/code does not need to migrate that file — it's still readable in place. Operator should run `update-plugins.ps1` after this task merges so the cache catches up. Mention in self-report.

**Existing helper pattern to mirror (`_paths.resolve_task_path`, lines 441-453):**

```python
def resolve_task_path(worktree_root: Path, cfg_relative_path: str) -> Path:
    """Resolve config-relative path with _mill/->task/ fallback for in-flight worktrees."""
    target = worktree_root / cfg_relative_path
    if target.exists():
        return target
    if "_mill/" in cfg_relative_path:
        fallback_rel = cfg_relative_path.replace("_mill/", "task/", 1)
        fallback = worktree_root / fallback_rel
        if fallback.exists():
            import sys
            print(f"[compat] falling back to task/ for {cfg_relative_path!r}", file=sys.stderr)
            return fallback
    return target
```

`status_path` is a one-line wrapper that reads cfg and forwards.

## Constraints

- **No new wiki-config schema break:** adding a brand-new key (`paths.status_md`) is a pure addition — no existing reader of `wiki/config.yaml` will fail. The Home.md banner about shared-resource schema changes does not apply (this is additive, not renaming/removing).
- **ASCII-only print/log strings** (CLAUDE.md `## Conventions worth carrying`). The `[compat]` stderr line in `resolve_task_path` is already ASCII; new helper emits no log lines of its own.
- **`${CLAUDE_PLUGIN_ROOT}` invariant:** no SKILL.md / template touched by this task references plugin-relative paths.
- **Junction discipline:** no junction reads; no junction writes; cwd stays in the task worktree.

## Testing

Test file: `plugins/mill/unit_tests/test-paths-status.py`.

**TDD candidate cases (write before implementing the helper):**

1. `cfg["paths"]["status_md"]` set and `_mill/status.md` exists -> returns `<wt>/_mill/status.md`.
2. `cfg["paths"]["status_md"]` set, `_mill/status.md` missing, `task/status.md` exists -> returns `<wt>/task/status.md` and emits `[compat]` to stderr.
3. `cfg["paths"]["status_md"]` set, neither file on disk -> returns the configured (non-existent) `<wt>/_mill/status.md` without warning.
4. `cfg` missing `paths` key -> raises `KeyError` with a message that names `paths.status_md`.
5. `cfg["paths"]` present but `status_md` key missing -> raises `KeyError` with the same message.

Use `tempfile.TemporaryDirectory()` for the worktree fixture. Use `capsys` to assert on the `[compat]` stderr line in case 2. No git, no real config load.

**Out of scope for unit tests:** the refactored call sites themselves (substitution-only, no new logic). If a call-site bug slipped through, it would surface during the next real spawn/inspect/review run, which is already part of the mill-go verify cycle.

## Q&A log

- **Q:** Should the helper accept `cfg` explicitly or read it internally? **A:** [auto-pick] Accept explicitly: `status_path(worktree_root, cfg)`. **Why:** Every call site already has cfg in scope; internal read forces a redundant disk hit and adds an import edge between `_paths` and `_config`.
- **Q:** Should the helper return a default `_mill/status.md` when cfg lacks `paths.status_md`, or raise? **A:** [auto-pick] Raise `KeyError`. **Why:** This task adds the key to every shipped config; absence after this lands is a real misconfiguration and should fail loud, not silently.
- **Q:** Should the compat fallback live in the new helper or in `resolve_task_path`? **A:** [auto-pick] Stay in `resolve_task_path`; `status_path` is a thin wrapper. **Why:** Single owner for the fallback rule keeps the `[compat]` warning in one place and avoids duplicating logic.
- **Q:** Should already-correct call sites (using `resolve_task_path(wt, "_mill/status.md")`) also migrate to `status_path`? **A:** [auto-pick] Yes, migrate them in the same pass. **Why:** Uniformity — one helper name for one concept. Mixed call sites invite drift on the next bug.
- **Q:** Should the on-disk `task/status.md` for the current worktree be migrated to `_mill/status.md` as part of this task? **A:** [auto-pick] No, leave it in place. **Why:** The compat fallback covers it. Rewriting active state mid-flight risks breaking the running task; the fallback is exactly what the migration window is for.
- **Q:** Should `discussion_file` / `plan_dir` / `reviews_dir` get symmetric helpers in the same task? **A:** [auto-pick] No, defer. **Why:** Those already work through `resolve_task_path` driven by their existing `paths.*` keys; no known bug. Adding three more helpers expands scope without solving a problem.
- **Q:** Should the spawn cache mismatch (the worktree's `task/status.md` from stale cached `_spawn_core`) be fixed in this task? **A:** [auto-pick] No, mention in self-report only. **Why:** Out of scope — that's an operator action (`update-plugins.ps1`), not a code fix. The compat fallback makes this task safe to land regardless.
