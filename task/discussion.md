# Discussion: Drop active.slug.md marker

```yaml
task: Drop active.slug.md marker
slug: drop-active-marker
status: discussing
parent: main
```

## Problem

The per-worktree file `.millhouse/active.slug.md` is the current authoritative "this is a mill-managed worktree" signal. Every downstream skill (`mill-start`, `mill-plan`, `mill-go`, `mill-merge`, `mill-merge-in`, `mill-claim`, `mill-cleanup`, `mill-color`, `mill-vscode`, `mill-terminal`, `mill-autofix`) reads it on entry; mill-spawn / mill-claim write it; mill-merge / mill-cleanup / mill-autofix delete it. The marker is gitignored local state — it does not propagate across clones, and it is the file that breaks first when spawn fails between worktree creation and the marker write call.

The marker's data is fully derivable from two sources that already exist:

| Field | Derivable from |
|---|---|
| `slug` | `git branch --show-current` with `spawn.branch_prefix` stripped |
| `branch` | `git branch --show-current` |
| `task_title` | the task entry in `wiki/Home.md` for that slug |
| `spawned_at` | (no production consumer — drop) |

The only non-derivable signal is the marker's *existence* — "is this a mill task worktree?". Branch-name + Home.md lookup gives an equivalent answer. Risk of false positive (a hand-created branch happening to match a slug already in Home.md) is negligible — it requires deliberate effort and the existing slug-to-branch invariant from spawn keeps the namespace coherent.

The cascade is large but mechanical: ~14 production files, ~12 test files, 8 SKILL.md files. The work is all replacements with no new architecture.

## Scope

**In:**

- Delete `plugins/mill/scripts/_active.py` entirely (`read_slug`, `read_all`, `write`, `ActiveError`, `_MARKER_NAME`).
- Add a new helper module `plugins/mill/scripts/_marker.py` exposing:
  - `slug_from_branch(git_root: Path, wiki_path: Path, cfg: dict) -> str` — current branch with `spawn.branch_prefix` stripped, validated against Home.md `[active]`. Raises `MarkerError` on mismatch / detached HEAD.
  - `task_data(git_root: Path, wiki_path: Path, cfg: dict) -> dict` — returns `{"slug": str, "branch": str, "task_title": str}`. `task_title` from Home.md task entry.
  - `MarkerError` exception type.
- Drop `_spawn_core.write_active_marker` (and its call sites in `millpy-spawn.py:230` and `millpy-claim.py:300`).
- Rewrite `_spawn_core.discover_active_worktrees`. New signature: `discover_active_worktrees(worktrees_dir: Path, home_tasks: list[_tasks_md.Task]) -> list[tuple[Path, str, str]]`. Body: scan `<wts>/<dir>` → `git -C <dir> branch --show-current` → strip prefix → match against `home_tasks` (any phase, not just `[active]`). Caller pre-loads and parses Home.md; helper does no I/O for the wiki.
- Update callers `millpy-cleanup.py`, `millpy-vscode.py`, `millpy-terminal.py` to pass `home_tasks` to `discover_active_worktrees`. mill-cleanup already has it; vscode/terminal load `wiki_path = _paths.resolve_wiki_path(git_root)` then `home_tasks = _tasks_md.parse((wiki_path / "Home.md").read_text())` before the call.
- Retain `_paths.ActiveWorktreeSlugMismatch` and `_paths.ActiveWorktreeNotFound`. The slug-comparison branch in `resolve_active_worktree` is preserved — it now compares the requested slug against the slug derived from `git -C <wts/slug-dir> branch --show-current` instead of the marker file. Tests at `test-paths.py:429,516` and `test-review-common.py:292-294` are adapted to set up a branch+Home.md mismatch state.
- Rewrite `_inplace.is_inplace` to `is_inplace(slug: str, git_root: Path, cfg: dict) -> bool` — branch-match check is implicit because slug derives from current branch.
- Rewrite `_paths.resolve_active_worktree` and `_paths.resolve_active_hub` to use the new `_marker` module instead of `_active.read_all` / `read_slug`.
- Rewrite `_review_common.find_active_slug` and `_review_common.load_task_title` to delegate to `_marker`. New signatures take `(git_root, wiki_path, cfg)` instead of `mill_dir`.
- Replace `_active.read_slug(Path(".millhouse"))` calls in `millpy-abandon.py`, `millpy-color.py`, `millpy-implement.py`, `millpy-implement-holistic.py`, `millpy-merge-in-subagent.py` with the new `_marker` API.
- Rewrite `millpy-cleanup.py`'s "must run from hub" check (line 471), in-place mode resolver (line 246), and inline marker-delete (line 362) to use the new module / drop the marker delete.
- Update 8 SKILL.md files to reference `_marker` API and drop `active.slug.md` mentions: `mill-go`, `mill-plan`, `mill-merge`, `mill-merge-in`, `mill-start`, `mill-claim`, `mill-terminal`, `mill-autofix`.
- Drop the `rm -f .millhouse/active.slug.md` line from `mill-autofix/SKILL.md` Phase 3.6.
- Drop the "Also remove `<git_root>/.millhouse/active.slug.md`" line from `mill-merge/SKILL.md` Step 8.
- Add new `plugins/mill/unit_tests/test-marker.py` covering: branch+Home.md happy path, branch not in Home.md, branch with mismatched prefix, detached HEAD, non-`[active]` task, `task_data` returns title from Home.md.
- Update existing unit tests that wrote markers (`test-cleanup.py`, `test-spawn-core.py`, `test-paths.py`, `test-review-common.py`, `test-millpy-vscode.py`, `test-millpy-terminal.py`, `test-millpy-spawn.py`, `test-millpy-claim.py`, `test-abandon.py`, `test-millpy-merge-in-subagent.py`, `test-review-discussion-flow.py`, `test-review-plan-flow.py`, `test-review-code-flow.py`) — replace `_active.write` with the new `_make_task_worktree` helper.
- Delete `plugins/mill/unit_tests/test-active.py` — it imports `_active` directly and exists only to test that module's IO contract; coverage is subsumed by the new `test-marker.py`.
- Update `plugins/mill/unit_tests/test-inplace.py` — every test passes `active_data: dict` to the old `is_inplace(active_data, git_root, cfg)` signature. Rewrite each test to pass `slug: str` to the new `is_inplace(slug, git_root, cfg)`. Test setup uses `_make_task_worktree` so `<wts>/<slug>/` presence/absence drives the in-place vs worktree branch.
- Update patch targets in `plugins/mill/unit_tests/test-millpy-color.py`, `test-millpy-implement.py`, `test-millpy-implement-holistic.py` — they currently patch `mill_color._active`, `millpy_implement._active`, `millpy_implement_holistic._active`. After production imports change, patch `mill_color._marker`, `millpy_implement._marker`, `millpy_implement_holistic._marker` (or whatever symbol the production code imports — verify per file).
- Add a shared test helper `_make_task_worktree(tmp, slug, title, *, branch_prefix="", phase="active") -> tuple[Path, Path]` that initializes a real git repo, creates the task branch, writes `.scratch`/Home.md fixtures, and returns `(worktree_path, wiki_path)`.
- Delete `_spawn_core.write_active_marker` and its docstring entry.
- Delete `_active.py` once all imports are gone.

**Out:**

- No replacement marker file. No bootstrap stub at `.millhouse/active.slug.md` for any reason. The `<worktree_root>/.millhouse/config.local.yaml` stub for `hub_relative_path` is unrelated and stays.
- No active.slug.md cleanup pass for existing worktrees in the user's clones — leftover marker files are harmless cruft (gitignored, never read by the new code, removed by mill-merge / mill-cleanup when the worktree is removed). No migration script.
- No change to `task/status.md` schema, `_status.py` API, Home.md structure, the `[active]` phase semantics, or `wiki/active/<slug>/` directory.
- No change to mill-spawn ordering; `write_initial_status` continues to be the last write of the spawn flow. The new orphan-detection robustness comes from branch+Home.md, not from re-ordering writes.
- No change to `wiki/active/<slug>/task.md` (still written by spawn for wiki-side discoverability).
- No fallback to `task/status.md` as a secondary signal. Branch+Home.md is the single source of truth.

## Decisions

### Source of truth: branch + Home.md lookup

- Decision: New helpers in `_marker.py` derive `slug`, `branch`, `task_title` from `git branch --show-current` (with `spawn.branch_prefix` stripped) plus the matching task entry in `wiki/Home.md`.
- Rationale: Robust during the spawn-failure window between `claim_in_wiki` (Home.md `[active]` is committed early) and `write_initial_status` (status.md is the last write). If spawn dies in that window, branch+Home.md still detects the worktree; status.md wouldn't.
- Rejected: `task/status.md` as the SoT (simpler — no config load, no prefix strip — but fragile mid-spawn-failure: status.md doesn't exist yet at that point). Hybrid (status.md preferred, branch+Home.md fallback — doubles code paths for no real win).

### Module placement: new `_marker.py`

- Decision: New module `plugins/mill/scripts/_marker.py`. `_active.py` is deleted entirely.
- Rationale: Keeps `_paths.py` focused on path resolution; semantic continuity (the file used to be a "marker", the helper retains the name with new internals); fresh module name signals new behavior so callers don't assume legacy semantics.
- Rejected: Add helpers to `_paths.py` (turns `_paths.py` into a grab-bag); add to `_spawn_core.py` (wrong coupling — reads happen far from spawn flow); rewrite `_active.py` in place (the old name implies a file that no longer exists, misleading future readers).

### Drop `spawned_at` field

- Decision: Drop entirely. No production code reads it.
- Rationale: Only tests roundtrip it, and those tests will be rewritten anyway. The new derivation can't synthesize `spawned_at` from branch+Home.md, and `git log <branch> --format=%aI --reverse | head -1` would add a git call for zero consumer benefit.
- Rejected: Derive from initial-commit timestamp via `git log` — adds cost, no callers.

### `task_data()` return shape: `{slug, branch, task_title}`

- Decision: Return exactly the fields current consumers need: `slug` (from current branch), `branch` (current branch), `task_title` (from Home.md).
- Rationale: Exact replacement for the consumed subset of `_active.read_all`. Adding `parent` would be redundant — every caller that needs `parent` already goes through `_status.read_parent_branch(status_path)`.
- Rejected: Include `parent` from Home.md or status.md (no consumer); split into slug-only + title-only helpers (creates two call sites where one suffices).

### `is_inplace` simplified to `(slug, git_root, cfg)`

- Decision: New signature `is_inplace(slug: str, git_root: Path, cfg: dict) -> bool`. No `branch` parameter.
- Rationale: With branch+Home.md as the SoT, the slug already derives from the current branch by definition — the existing branch-match check inside `is_inplace` becomes tautological. The function reduces to: "is `<container>/wts/<slug>/` absent?".
- Rejected: Keep `is_inplace(slug, branch, ...)` and re-fetch current branch for symmetry — adds a git call for no semantic benefit.

### Strict `[active]` requirement for per-slug reads

- Decision: `slug_from_branch` and `task_data` raise `MarkerError` when the resolved slug is in Home.md but not `[active]` (e.g. `[done]`, `[abandoned]`, no marker).
- Rationale: Matches current marker semantics ("this is a *live* mill task"). `[done]`/`[abandoned]` worktrees are mid-cleanup; mill-merge / mill-cleanup already have the slug in scope from the entry-step read that succeeded earlier in the run.
- Rejected: Accept any phase (broader detection but loses the "live task" guarantee, masks operator errors); accept any phase only for some callers (per-caller flags create a confusing API surface).

### `discover_active_worktrees` accepts any phase

- Decision: Function accepts any slug present in Home.md regardless of phase marker.
- Rationale: mill-cleanup uses this function to *find* worktrees that need sweeping, including `[done]`/`[abandoned]` ones. Strict `[active]` would hide exactly the worktrees cleanup is meant to remove.
- Rejected: Strict `[active]` (cleanup couldn't find done/abandoned worktrees); skip Home.md entirely / include any worktree directory (too permissive — captures orphans, which we already report separately).

### branch_prefix handling: strict strip-prefix

- Decision: Load config, take `spawn.branch_prefix`, strip it from the current branch. When prefix is non-empty and branch doesn't start with it, raise `MarkerError`.
- Rationale: Matches the existing spawn invariant — every task branch is created with the configured prefix. Strict matching surfaces operator errors loudly; greedy fallback would mask drift.
- Rejected: Greedy try-with-then-without-prefix (works without config but risks ambiguity); search Home.md slugs for a branch suffix (most flexible, easiest to misfire when slugs overlap).

### Detached HEAD / non-task branch halt

- Decision: When `git branch --show-current` returns empty (detached) or returns a branch whose stripped slug is not in Home.md, raise `MarkerError`. Callers halt with a clear message.
- Rationale: Same outcome as today's "marker missing" error — invalid state, not silently-OK.
- Rejected: Allow branch=`""` and treat as "not mill-managed" silently — masks operator errors.

### `mill-cleanup`'s "must run from hub" check via branch detection

- Decision: Replace `if (Path.cwd() / ".millhouse" / "active.slug.md").exists(): error` with: get current branch via `git branch --show-current`, check if stripped slug exists in Home.md as `[active]`, error if so.
- Rationale: Same semantics as today — if you're on a task branch, you're in a worktree, not the hub. Branch+Home.md preserves the existing guard.
- Rejected: Path-based detection (`Path.cwd().parent.name == "wts"` — works without Home.md but fails when hub_relative_path puts the cwd in a sub-dir); drop the check (silent foot-gun).

### Retain `ActiveWorktreeSlugMismatch` and `ActiveWorktreeNotFound`

- Decision: Both exception types in `_paths.py.__all__` survive the rewrite. `resolve_active_worktree` still raises `ActiveWorktreeSlugMismatch` when `<container>/wts/<slug>/` exists but the slug derived from its current branch differs from the requested slug.
- Rationale: The semantics are valid post-rewrite — "the worktree dir at this path is on a different task than the one you asked for" is a real condition that should surface as a typed exception, not silently convert into a generic `MarkerError`. Callers already catch these types; tests already cover them. Changing only the *triggering check* (branch-derived vs marker-derived) keeps the public exception surface stable.
- Rejected: Drop `ActiveWorktreeSlugMismatch` and let `MarkerError` propagate (narrows semantics — "marker error" and "slug mismatch" are different conditions; call sites currently catching `ActiveWorktreeSlugMismatch` would need updates); drop the slug-mismatch detection branch entirely (silent foot-gun: returning a worktree on the wrong branch is a bug that should surface).

### `discover_active_worktrees` signature change: add `home_tasks` parameter

- Decision: New signature `discover_active_worktrees(worktrees_dir: Path, home_tasks: list[_tasks_md.Task]) -> list[tuple[Path, str, str]]`. Caller pre-loads and parses Home.md; helper does no wiki I/O.
- Rationale: The new body needs Home.md for branch-slug-to-task lookup. Resolving `wiki_path` inside the helper from `worktrees_dir` would couple it to a layout assumption (container-form: `worktrees_dir.parent.parent`) that breaks in prefix-form repos. mill-cleanup already has `home_tasks` in scope; mill-vscode and mill-terminal load it once at startup — a single `Home.md` read per invocation is negligible.
- Rejected: Internal `wiki_path` resolution via `worktrees_dir.parent.parent` (couples helper to container-form layout); pass `wiki_path: Path` and load+parse inside the helper (helper still does I/O, marginally less pure).

### Test fixture: `_make_task_worktree` helper

- Decision: New shared helper `_make_task_worktree(tmp, slug, title, *, branch_prefix="", phase="active")` that initializes a real git repo, creates a task branch, writes a minimal Home.md with the slug at the requested phase, and returns `(worktree_path, wiki_path)`.
- Rationale: Most existing tests already create temp git repos; this consolidates the boilerplate in one helper. Tests then exercise the real branch+Home.md path the new code follows in production.
- Rejected: Mock `_marker.task_data()` directly per test (couples tests to internal API; hides bugs in the actual derivation logic); mixed strategy (different patterns per test type — adds cognitive load).

### Update SKILL.md docs in this task

- Decision: Update all 8 SKILL.md files in this PR. Replace `_active.read_slug(Path(".millhouse"))` calls and remove `active.slug.md` prose mentions.
- Rationale: Keeps docs and code in lockstep. Skill instructions are user-facing — defer-to-follow-up risks confusion if a skill runs against the new code with stale docs.
- Rejected: Defer (out-of-sync docs); update only the inline calls (partial fix is worse than full).

### Leftover marker files: leave as cruft

- Decision: Existing `.millhouse/active.slug.md` files in the user's working clones stay where they are. No migration script.
- Rationale: They are gitignored, never read by the new code, and removed when their worktree is removed by mill-merge / mill-cleanup. The cleanup-burden of writing a migration helper exceeds the cost of the dead bytes.
- Rejected: One-shot cleanup pass in mill-cleanup (over-engineered for a non-issue); refuse to operate when stale markers found (over-restrictive).

## Technical context

**Module map (callers / writers of the marker today):**

| File | Today's call | New replacement |
|---|---|---|
| `plugins/mill/scripts/_active.py` | the module itself | DELETE |
| `plugins/mill/scripts/_inplace.py:32-71` | `is_inplace(active_data, git_root, cfg)` | `is_inplace(slug, git_root, cfg)` — drop `active_data["branch"]` check; single absence test for `<wts>/<slug>/` |
| `plugins/mill/scripts/_spawn_core.py:152-202` | `discover_active_worktrees(worktrees_dir)` reads stub + `_active.read_all(hub_mill_dir)` | new signature: `discover_active_worktrees(worktrees_dir: Path, home_tasks: list[_tasks_md.Task])`. Per-dir `git -C <dir> branch --show-current`, strip `spawn.branch_prefix`, match against `home_tasks` (a `Task` whose slug equals the stripped value, regardless of phase). Helper does no Home.md I/O; caller passes pre-parsed tasks. `hub_relative_path` stub-read for sub-dir hubs preserved. |
| `plugins/mill/scripts/_spawn_core.py:653-679` | `write_active_marker(...)` | DELETE; remove call sites in `millpy-spawn.py:230` and `millpy-claim.py:300` |
| `plugins/mill/scripts/_paths.py:295,307` | `_active.read_all(hub_dir/".millhouse")`, `_active.read_slug(worktree/".millhouse")` | `_marker.task_data(git_root, wiki_path, cfg)` and `_marker.slug_from_branch(...)` |
| `plugins/mill/scripts/_review_common.py:118-140` | `find_active_slug(mill_dir)`, `load_task_title(mill_dir, slug)` | `find_active_slug(git_root, wiki_path, cfg)`, `load_task_title(git_root, wiki_path, cfg, slug)` — keep `slug` arg as the fallback when Home.md entry is missing |
| `plugins/mill/scripts/millpy-abandon.py:40,45` | file-exists guard + `_active.read_slug` | `_marker.slug_from_branch(...)`; halt on `MarkerError` |
| `plugins/mill/scripts/millpy-claim.py:300` | `_spawn_core.write_active_marker(...)` | DELETE the call (slug is already derivable from branch+Home.md after `claim_in_wiki`) |
| `plugins/mill/scripts/millpy-cleanup.py:113,246,362,471` | multi-call cluster (read_all, marker-delete, hub-check) | branch+Home.md detection; drop the `marker_path.unlink()`; rewrite the hub-check to use branch detection |
| `plugins/mill/scripts/millpy-color.py:97` | `_active.read_slug` | `_marker.slug_from_branch(...)`, fall back to None on `MarkerError` (current code already swallows `ActiveError`) |
| `plugins/mill/scripts/millpy-implement.py:87`, `millpy-implement-holistic.py:72` | `_active.read_slug(mill_dir)` | `_marker.slug_from_branch(...)` |
| `plugins/mill/scripts/millpy-merge-in-subagent.py:84` | `_active.read_slug(mill_dir)` (existence check) | `_marker.slug_from_branch(...)`; halt on `MarkerError` |
| `plugins/mill/scripts/millpy-spawn.py:230` | `_spawn_core.write_active_marker(...)` | DELETE |
| `plugins/mill/scripts/millpy-vscode.py`, `millpy-terminal.py` | `discover_active_worktrees(worktrees_dir)` | signature changed — caller now resolves wiki, parses Home.md tasks, passes them in: `home_tasks = _tasks_md.parse((wiki_path / "Home.md").read_text(encoding="utf-8"))`. `wiki_path` resolved via `_paths.resolve_wiki_path(_paths.resolve_git_root())`. |
| `plugins/mill/scripts/millpy-cleanup.py` (line 480 area) | `discover_active_worktrees(container_path / "wts")` | signature changed AND call must be reordered: the existing `home_tasks` parse is at line 484, *after* the `discover_active_worktrees` call at line 480. Hoist the `home_text = (wiki_path / "Home.md").read_text("utf-8")` + `home_tasks = _tasks_md.parse(home_text)` block to *before* the `discover_active_worktrees` call, then pass `home_tasks` in. |

**Config dependency (new):** `_marker` must load config to read `spawn.branch_prefix`. `_review_common.load_config(wiki_path, mill_dir)` already exists — but the `mill_dir` argument is now obsolete because `.millhouse/config.local.yaml` lives at hub root, not the marker's mill_dir. Pass `git_root` (the worktree root) and resolve via `_paths.resolve_hub_path()`. Most callers already load config before resolving the slug, so they can pass the cfg dict in directly — the new `_marker` API takes `cfg` as a param to avoid re-loading.

**Home.md parser:** `_tasks_md.parse(home_text)` already returns `list[Task]` with `slug`, `phase`, `title`, `has_proposal` — no parser change needed. `Task.phase` is one of `"active"`, `"done"`, `"abandoned"`, `"s"`, or `None`.

**Critical edge case — multiple worktrees can share a parent worktree's branch namespace.** `discover_active_worktrees` runs `git -C <dir> branch --show-current` per dir. When the dir is a stale orphan (no branch checkout, e.g. corrupted by half-removed git worktree), the call returns empty. Treat empty branch as "skip silently" — same as today's "marker missing → continue" semantics.

**Critical sequence — spawn write order is unchanged.** The proposal motivation ("the file we hit when spawn failed before write_active_marker") is *resolved by the deletion itself* — there's no marker to fail on. We do not need to move `write_initial_status` earlier or re-order `claim_in_wiki`. Spawn flow is:

1. `claim_in_wiki` — Home.md `[active]` (this is what makes branch+Home.md work after this point)
2. `_worktree.create` — branch checkout
3. `_spawn_core.write_wiki_active_task_md`, junctions, vscode, etc.
4. `write_initial_status` — `task/status.md` committed and pushed.

After step 1+2, branch+Home.md gives a complete answer. If spawn fails between steps 2 and 4, the worktree is in a half-built state — but it's *detectable* as a mill task worktree, which is the property we lost with the marker file.

**No changes to `_paths.resolve_hub_path` / `resolve_git_root` / `resolve_wiki_path` / `resolve_container_path`.** The marker drop is invisible to those.

**`_paths.resolve_active_worktree(container, slug, *, cfg, git_root)`:** currently calls `_active.read_all(hub_dir / ".millhouse")` to check if the cwd's hub matches `slug` for in-place detection. Replacement: call `_marker.slug_from_branch(git_root, wiki_path, cfg)` and compare to `slug`; if equal AND `<wts>/<slug>/` is absent → in-place hit. Wiki path is needed; fetch via `_paths.resolve_wiki_path(git_root)`.

**`_paths.resolve_active_hub(...)`:** same delegation pattern; ride on `resolve_active_worktree`'s rewrite.

**`mill-merge` Step 8 in-place mode marker delete (line 222 of SKILL.md):** the line `Also remove <git_root>/.millhouse/active.slug.md` becomes a no-op once the marker is gone. Drop the line; the surrounding `git checkout <parent_branch>` + `git branch -D "$CHILD_BRANCH"` already restore the worktree to its non-task state per the new detection (branch is no longer a task branch).

**`mill-autofix` Phase 3.6 (line 400 of SKILL.md):** `rm -f .millhouse/active.slug.md` becomes a no-op. Drop the line. The Home.md `[active]` reset is intentionally NOT done here — the surrounding flow's note "the wiki active/<slug>/ directory and the [active] marker in Home.md are left as-is" stays correct.

## Constraints

- `${CLAUDE_PLUGIN_ROOT}` invariants from CLAUDE.md still apply — no hardcoded `plugins/mill/` paths in SKILL.md updates.
- Junctions are IDE/terminal convenience only — no junction reads/writes change in this task.
- Working state lives in `task/` on the task branch — `task/status.md` is unchanged; only the *additional* `.millhouse/active.slug.md` marker is dropped.
- All Home.md writes go through `_wiki.write_commit_push` — this task adds Home.md *reads* but does not introduce new write paths.
- New `_marker.py` follows the flat-Python convention: top-level helpers, `_*.py` naming, smoke-test-free body.

## Testing

**TDD candidates** (write failing test first, then implement):

- `_marker.slug_from_branch` happy path (branch with prefix, slug in Home.md as `[active]`).
- `_marker.slug_from_branch` raises `MarkerError` on detached HEAD.
- `_marker.slug_from_branch` raises `MarkerError` when stripped-slug is not in Home.md.
- `_marker.slug_from_branch` raises `MarkerError` when slug is in Home.md but phase is `[done]`/`[abandoned]`/no-marker.
- `_marker.slug_from_branch` raises `MarkerError` when branch doesn't start with non-empty `spawn.branch_prefix`.
- `_marker.slug_from_branch` happy path with empty `spawn.branch_prefix` (branch == slug).
- `_marker.task_data` returns `{slug, branch, task_title}` with title from Home.md task entry.
- `_inplace.is_inplace(slug, git_root, cfg)` returns False when `<wts>/<slug>/` exists.
- `_inplace.is_inplace(slug, git_root, cfg)` returns True when `<wts>/<slug>/` is absent.
- `_paths.resolve_active_worktree` raises `ActiveWorktreeSlugMismatch` when `<wts>/<slug>/` exists but its branch's stripped-slug differs from the requested slug.
- `_paths.resolve_active_worktree` raises `ActiveWorktreeNotFound` when neither in-place mode nor a worktree dir applies.
- `discover_active_worktrees` accepts `home_tasks` parameter and returns entries only for branches whose stripped-slug appears in the passed task list.

**Coverage scenarios** (must be exercised somewhere in the suite):

- `discover_active_worktrees` returns a `[done]` slug (must include — cleanup needs it).
- `discover_active_worktrees` returns an `[abandoned]` slug (same reason).
- `discover_active_worktrees` skips a sub-dir whose branch is not in Home.md.
- `discover_active_worktrees` skips a sub-dir with detached HEAD.
- `discover_active_worktrees` honors `hub_relative_path` stub (existing test pattern).
- `mill-cleanup` "must run from hub" check fails when current branch is a task slug.
- `mill-cleanup`'s `_apply_inplace_record` no longer attempts to unlink the marker file.
- `mill-merge` in-place teardown does not reference the marker.
- `_paths.resolve_active_worktree` in-place hit returns `git_root`.
- `_paths.resolve_active_worktree` worktree mode returns `<container>/wts/<slug>`.
- `_review_common.load_task_title` falls back to `slug` when the Home.md entry is missing the title (defensive).

**Test helper:** `plugins/mill/unit_tests/_test_helpers.py` (new or extend existing) exports `_make_task_worktree(tmp, slug, title, *, branch_prefix="", phase="active") -> tuple[Path, Path]`. Returns `(worktree_path, wiki_path)`. Internal: creates a temp git repo at `worktree_path`, checks out a fresh branch named `f"{branch_prefix}{slug}"`, writes a minimal `wiki/Home.md` with one task entry at the requested phase, parses-and-validates the file. Tests that need multi-task Home.md state can write additional entries via `_tasks_md.append_entry` after the helper returns.

**Existing tests to retire:** every test currently calling `_active.write(...)`. Either replace the call with `_make_task_worktree(...)` (when the test exercises a real worktree flow) or delete the test (when it was purely testing the marker module's IO contract — those have no remaining surface). `plugins/mill/unit_tests/test-active.py` is deleted entirely — it tests `_active.write/read_slug/read_all` directly; the new `test-marker.py` covers the equivalent surface for `_marker`.

**Tests with patch targets that break:** `test-millpy-color.py`, `test-millpy-implement.py`, `test-millpy-implement-holistic.py` use `mock.patch("<script>._active")` patterns. After the production-side `import _active` is replaced with `import _marker`, the patch path becomes `<script>._marker`. Update each patch target.

**Tests that pass `active_data` dicts:** `test-inplace.py` constructs `active_data = {"slug": ..., "branch": ...}` and passes to `is_inplace`. Rewrite to pass `slug: str` directly (matches the new signature). Add `<wts>/<slug>/` directory in setup to drive the worktree-mode branch and omit it to drive the in-place branch.

**Integration test:** extend `integration_tests/test-spawn.py` to assert that `discover_active_worktrees` returns the new worktree even though no `active.slug.md` was written. Drop the `marker_path.exists()` assertions at lines 200-205.

## Q&A log

- **Q:** Source of truth — branch+Home.md or `task/status.md`? **A:** Branch+Home.md — robust during the spawn-failure window between Home.md `[active]` write and `task/status.md` commit.
- **Q:** Delete `_active.py` or rewrite in place? **A:** Delete entirely; new helpers go in `_marker.py`.
- **Q:** New module name? **A:** `_marker.py` for semantic continuity.
- **Q:** Drop `spawned_at`? **A:** Yes — no production consumer.
- **Q:** `is_inplace` signature? **A:** `(slug, git_root, cfg)` — drop the `branch` parameter; check is reduced to "is `<wts>/<slug>/` absent?".
- **Q:** `task_data` return shape? **A:** `{slug, branch, task_title}` — exact replacement for consumed subset.
- **Q:** Strict `[active]` for per-slug reads? **A:** Yes — matches today's marker semantics. `discover_active_worktrees` is the exception (accepts any phase) so cleanup can sweep done/abandoned.
- **Q:** branch_prefix handling? **A:** Strict — raise `MarkerError` if non-empty prefix doesn't match.
- **Q:** Detached HEAD / non-task branch? **A:** Halt with `MarkerError`.
- **Q:** mill-cleanup's "must run from hub" check? **A:** Replace with branch-name detection — if current branch's stripped slug is in Home.md as `[active]`, error.
- **Q:** Existing marker files in the user's clones? **A:** Leave as cruft; no migration script. Removed when their worktree is removed.
- **Q:** SKILL.md updates in this task? **A:** Yes — all 8 affected files updated in the same PR.
- **Q:** mill-autofix Phase 3.6 marker-rm line? **A:** Delete the line entirely.
- **Q:** mill-merge Step 8 marker-rm line? **A:** Delete the line entirely.
- **Q:** Test fixture pattern? **A:** Shared `_make_task_worktree` helper that builds real git+Home.md state.
- **Q:** Test scope? **A:** New `test-marker.py` + update existing tests + integration-test assertion update.
- **Q:** `config.local.yaml` stub at worktree root for `hub_relative_path`? **A:** Out of scope — different concern (hub-subpath discovery), not the active marker.
- **Q:** Fate of `_paths.ActiveWorktreeSlugMismatch` and `ActiveWorktreeNotFound`? **A:** Both retained. The slug-comparison branch in `resolve_active_worktree` keeps raising `ActiveWorktreeSlugMismatch`; only the triggering check changes (branch-derived slug instead of marker-derived). Existing tests adapted, not deleted.
- **Q:** How does `discover_active_worktrees` get Home.md without coupling to a layout assumption? **A:** It doesn't — the signature is changed to accept `home_tasks: list[Task]` from the caller. mill-cleanup has it in scope; mill-vscode / mill-terminal each load+parse Home.md once before the call.
- **Q:** mill-cleanup call-site reorder needed? **A:** Yes — the existing `home_tasks` parse at line 484 is *after* the `discover_active_worktrees` call at line 480. Hoist the Home.md read/parse pair above the discover call.
- **Q:** Test files missed in the initial sweep? **A:** Five additional files: `test-active.py` (delete), `test-inplace.py` (rewrite for new `is_inplace(slug, ...)`), `test-millpy-color.py` / `test-millpy-implement.py` / `test-millpy-implement-holistic.py` (update `mock.patch("<script>._active")` → `._marker`).
