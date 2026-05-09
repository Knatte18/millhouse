# Discussion: 35 (A) — Centralize path resolution across all three modes

```yaml
task: 35 (A) — Centralize path resolution across all three modes
slug: mill-path-resolution-audit
status: discussing
parent: main
```

## Problem

An external user running `mill@2.0.0` against a hub clone (`NORCE-DrillingAndWells`, slug `backward-temp-energy-conservation`) hit `_paths.ActiveWorktreeNotFound` on `/mill-start`'s Phase: Discussion Review. They had run `/mill-claim`, which is intentionally in-place — it does not create a `<container>/wts/<slug>/` directory; it checks out the task branch in the hub itself and writes `.millhouse/active.slug.md` there. Subsequent review scripts then resolve the active worktree via `_paths.resolve_active_worktree(container, slug)`, which is hardcoded to return `container / "wts" / slug`. That directory does not exist for in-place tasks, so the review crashes.

Investigation during 2026-05-08 revealed mill supports three orthogonal modes whose path resolution is scattered:

| Mode | Worktree root | Hub dir |
|---|---|---|
| 1. Worktree (default) | `<container>/wts/<slug>/` | same |
| 1 + sub-dir hub | `<container>/wts/<slug>/` | `<wt>/<hub_relative_path>/` |
| 2. In-place | `<git_root>/` | same |
| 2 + sub-dir hub | `<git_root>/` | `<root>/<hub_relative_path>/` |

The hardcoded `container / "wts" / slug` only handles row 1. Rows 2 and 4 break loudly (`ActiveWorktreeNotFound`); row 3 (in-place, hub_rel=".") would also break the review path the same way. Row 2 (worktree + sub-dir hub) breaks differently — the path is found but `task/` files are looked up at the git root instead of the hub, missing them.

The fix is two centralized helpers in `_paths.py` plus a tight audit of the demonstrably-broken consumers and the legacy abandon path (issue #207).

## Scope

**In:**

- Refactor `_paths.resolve_active_worktree` to handle all four mode/sub-dir combinations via `_inplace.is_inplace`. Signature changes to `resolve_active_worktree(container, slug, *, cfg, git_root) -> Path`.
- Add new helper `resolve_active_hub(container, slug, *, cfg, git_root) -> Path` to `_paths.py`. Returns `resolve_active_worktree(...) / hub_relative_path`. Reads `hub_relative_path` from the resolved worktree's own `.millhouse/config.local.yaml`, not from the cfg the caller has open (works correctly across cross-worktree resolution).
- Switch `_review_common.resolve_path` from `resolve_active_worktree` to `resolve_active_hub`. The path templates in `wiki/config.yaml` (`task/discussion.md`, `task/plan/`, `task/reviews/`) live under the hub, not under the git checkout root.
- Refactor `millpy-cleanup.py:103-114` inline `hub_relative_path` resolution to call `resolve_hub_relative_path` directly (no slug-based lookup needed there — `wt_path` is already in hand).
- Fix `millpy-abandon.py` (issue #207): switch from `wiki_path / "active" / slug / "status.md"` to `resolve_active_hub(container, slug, ...) / "task" / "status.md"`. Switch the abandon-phase commit from the wiki to a `git -C <active_worktree> commit + push` on the task branch.
- Add unit tests in `plugins/mill/unit_tests/test-paths.py` covering both helpers across all four scenarios (M1, M1+sub, M2, M2+sub).
- Add a focused unit test for `_review_common.resolve_path` exercising the in-place branch — the original bug surface.
- Add or update a unit test for `millpy-abandon.py`'s status-path resolution.
- Update `CLAUDE.md` `## Path invariants` with one paragraph mandating both helpers and banning hardcoded `container / "wts" / slug` and inline `<wt> / hub_relative_path` constructions.
- Update `mill-claim/SKILL.md` with a short section calling out in-place semantics: no `<container>/wts/<slug>/` directory is created; the hub is the worktree; `task/` lives at `<hub>/task/` not `<git_root>/task/` when `hub_relative_path` is set.
- Read `mill-spawn/SKILL.md` and add a one-liner cross-reference to mill-claim if the worktree-vs-in-place split is not already called out.

**Out:**

- `discover_active_worktrees` callers (`millpy-cleanup.py:170,483`, `millpy-inspect.py:48`, `millpy-status.py:34`). They scan `<container>/wts/` for marker files; they don't take a slug and build a path. The hub itself sits at `<container>/wts/<repo>/` with its own active marker (in in-place mode), so enumeration finds it correctly. No change needed.
- `millpy-spawn.py` — the spawn site that creates `<container>/wts/<slug>/`. Spawn doesn't resolve an existing worktree; it creates one. Out of scope.
- `millpy-claim.py` — operates entirely on cwd via `resolve_hub_path()`. No slug→path lookup. Out of scope.
- Integration test for the full `mill-claim → mill-start → review-discussion` flow. The reported bug surface is the helper logic alone; the integration path would mostly retest spawn/claim mechanics already covered by their own unit tests, and would require a `claude`-stub or `--no-llm` mode that doesn't exist.
- Refactoring `wiki_active_dir = wiki_path / "active" / slug` in `millpy-cleanup.py:135-136`. That's transitional cleanup of pre-task-32 wiki state; legitimate as written.
- `millpy-merge.py` — does not exist. Merge logic is in the SKILL.md flow only. Nothing to audit.
- General consolidation of every `<container>/wts/...` reference in the codebase. The audit is tight: only sites that take a slug and build a path, plus the one inline duplication in cleanup we're touching anyway.

## Decisions

### helper-signatures

- Decision: `resolve_active_worktree(container, slug, *, cfg, git_root) -> Path` and `resolve_active_hub(container, slug, *, cfg, git_root) -> Path`. Both keyword-only after the positional `(container, slug)`.
- Rationale: `git_root` is required for `_inplace.is_inplace` (which checks the current branch and the worktree-dir absence). Passing it explicitly keeps the helper pure and testable. `cfg` is the deep-merged config; the caller already has it loaded. Symmetric with the existing `is_inplace(active_data, git_root, cfg)` shape.
- Rejected: a magic version that walks up from `Path.cwd()` (hard to test, hides cwd dependency); a richer `resolve_active_worktree(active_data, container, *, cfg, git_root)` that also takes `active_data` (most callers don't have it pre-loaded; the helper can read the marker itself when needed).

### helper-bodies

- Decision:
  ```python
  def resolve_active_worktree(container, slug, *, cfg, git_root) -> Path:
      """Top-level git checkout for the slug (for git-ops, branch ops)."""
      hub_dir = resolve_hub_relative_path(git_root, cfg.get("hub_relative_path", "."))
      active_data = _active.read_all(hub_dir / ".millhouse")
      if active_data["slug"] == slug and _inplace.is_inplace(active_data, git_root, cfg):
          return git_root
      worktree = container / "wts" / slug
      if not worktree.is_dir():
          raise ActiveWorktreeNotFound(...)
      marker_slug = _active.read_slug(worktree / ".millhouse")
      if marker_slug != slug:
          raise ActiveWorktreeSlugMismatch(...)
      return worktree

  def resolve_active_hub(container, slug, *, cfg, git_root) -> Path:
      """Where .millhouse/ and task/ live for the slug."""
      wt = resolve_active_worktree(container, slug, cfg=cfg, git_root=git_root)
      stub = wt / ".millhouse" / "config.local.yaml"
      hub_subpath = "."
      if stub.exists():
          hub_subpath = (yaml.safe_load(stub.read_text()) or {}).get("hub_relative_path", ".")
      return resolve_hub_relative_path(wt, hub_subpath)
  ```
- Rationale: `resolve_active_hub` reads `hub_relative_path` from the resolved worktree's own stub so it works for cross-worktree resolution. Reusing existing `_active.read_slug` / `_active.read_all` and `resolve_hub_relative_path` keeps the surface small.
- Rejected: passing `hub_subpath` from the caller (forces every call site to read the stub themselves; defeats centralization).

### in-place-detection-edge

- Decision: When the cwd's git_root has an active marker matching `slug`, treat it as in-place IF `_inplace.is_inplace` returns True. Otherwise fall through to the worktree-directory branch. The "worktree directory exists AND branch matches cwd" stale-worktree edge stays the responsibility of `_inplace.prompt_stale_worktree` for callers that care (mill-cleanup, mill-merge); `resolve_active_worktree` is non-interactive — when both modes look plausible, it picks worktree-mode (the directory exists, so we trust it).
- Rationale: Resolution must be non-interactive. The stale-worktree case is rare and is already handled by mill-cleanup with an explicit prompt; baking that prompt into the resolver would create unwanted UX coupling.
- Rejected: raising on ambiguity (forces every caller to handle a new exception); always preferring in-place when branch matches (would silently break worktree-mode tasks the user happens to be cd'd into).

### review-common-resolve-path

- Decision: `_review_common.resolve_path` switches to `resolve_active_hub`. Signature stays `resolve_path(path_tmpl, slug)` — internal change only. Reads cfg via `_review_common.load_config(...)` (already loaded by callers) and computes git_root via `_paths.resolve_git_root()`. Does not change behavior for existing M1 callers (where `git_root == container/wts/slug == hub`).
- Rationale: Path templates in `wiki/config.yaml` (`task/discussion.md`, `task/plan/`, `task/reviews/`) are hub-relative by design (spawn writes `worktree_path / "task" / "status.md"` where `worktree_path = resolve_hub_path()` = the hub dir, so `task/` ends up under the hub, not necessarily the git root).
- Rejected: leaving it on `resolve_active_worktree` (would break sub-dir hub configs forever); changing the signature to take cfg explicitly (every caller already calls `load_config` first; the helper can recompute).

### abandon-fix

- Decision: `millpy-abandon.py` reads `<active_hub>/task/status.md` via `resolve_active_hub`. The phase-append commit goes to the task branch via `git -C <active_worktree> commit + push`, not to the wiki.
- Rationale: After task-32, status.md lives on the task branch under `<hub>/task/`. Wiki-side state for the slug is `Home.md` only.
- Rejected: keeping the legacy wiki write as a fallback (no remaining consumers read from wiki/active/<slug>/status.md; the fallback is dead weight).

### audit-tightness

- Decision: Tight audit. Only fix the demonstrably broken slug→path sites (`_paths.resolve_active_worktree` itself, `_review_common.resolve_path`, `millpy-abandon.py`) plus the inline `hub_relative_path` duplication in `millpy-cleanup.py:103-114` since we're already touching the helper. `discover_active_worktrees` callers (cleanup/inspect/status) are out of scope — they enumerate, they don't path-construct from slug, and they work in all three modes today.
- Rationale: The proposal listed an aggressive sweep; the actual broken surface is small. YAGNI on the rest.
- Rejected: full sweep across every `<container>/wts/...` reference (would touch enumeration sites that aren't broken); deferring #207 to a separate task (the abandon fix shares the helper change and is cheap to bundle).

### docs-updates

- Decision: Tight doc updates. CLAUDE.md `## Path invariants` gets one paragraph mandating both helpers and banning inline `container / "wts" / slug` and `<wt> / hub_relative_path` constructions. `mill-claim/SKILL.md` gets a short in-place-mode callout. `mill-spawn/SKILL.md` gets at most a one-liner cross-reference (only if it currently doesn't mention the contrast with mill-claim).
- Rationale: One paragraph beats a worked example for a contract that's already self-evident from the docstrings. The mill-claim semantics aren't well documented today (per the proposal), so a focused section there is high-value.
- Rejected: full pedagogical CLAUDE.md rewrite with a four-mode worked example (overkill); side-by-side mill-claim vs. mill-spawn restructure (too much churn for a path-resolution task); skipping all doc updates (the contract needs a written home so future audit work has something to point at).

## Technical context

Files mill-plan needs to know:

- [plugins/mill/scripts/_paths.py](plugins/mill/scripts/_paths.py) — `resolve_active_worktree` lives at line 255; `resolve_hub_relative_path` at line 215. New `resolve_active_hub` goes here. `__all__` at line 74 needs the addition.
- [plugins/mill/scripts/_inplace.py](plugins/mill/scripts/_inplace.py) — `is_inplace(active_data, git_root, cfg)` at line 32. Already detects in-place via branch match + worktree-dir absence. `resolve_active_worktree` calls into it.
- [plugins/mill/scripts/_active.py](plugins/mill/scripts/_active.py) — `read_slug(mill_dir)` and `read_all(mill_dir)` are the marker readers.
- [plugins/mill/scripts/_review_common.py:155-184](plugins/mill/scripts/_review_common.py#L155-L184) — `resolve_path(path_tmpl, slug)` is the single switch site.
- [plugins/mill/scripts/millpy-abandon.py](plugins/mill/scripts/millpy-abandon.py) — line 53 has the legacy wiki-active-dir read; lines ~95-100 do the wiki commit. Both flip to task-branch.
- [plugins/mill/scripts/millpy-cleanup.py:103-114](plugins/mill/scripts/millpy-cleanup.py#L103-L114) — inline `hub_relative_path` duplication; replace with `resolve_hub_relative_path(wt_path, stub_data.get("hub_relative_path", "."))`.
- [plugins/mill/scripts/_config.py](plugins/mill/scripts/_config.py) — `load_config` already deep-merges wiki + local cfg, with stub-aware sub-dir hub handling. No change.
- [plugins/mill/unit_tests/test-paths.py](plugins/mill/unit_tests/test-paths.py) — existing tests for `resolve_active_worktree` (lines 359-408) need updating for the new signature; new tests for `resolve_active_hub` get added here.
- [plugins/mill/unit_tests/test-inplace.py](plugins/mill/unit_tests/test-inplace.py) — existing fixture style for in-place mode.
- [plugins/mill/skills/mill-claim/SKILL.md](plugins/mill/skills/mill-claim/SKILL.md) — in-place callout goes here.
- [plugins/mill/skills/mill-spawn/SKILL.md](plugins/mill/skills/mill-spawn/SKILL.md) — read first, edit only if needed.
- [CLAUDE.md](CLAUDE.md) — `## Path invariants` section gets one new paragraph.

Helpers to reuse:

- `_active.read_slug` / `_active.read_all` for marker lookups.
- `_paths.resolve_hub_relative_path` for `<wt>/<hub_subpath>` arithmetic.
- `_inplace.is_inplace` for in-place detection.
- `_paths.resolve_main_worktree_root` if needed inside `resolve_active_worktree` to find the hub of the current cwd.

Gotchas discovered during exploration:

- `cfg["hub_relative_path"]` lives in `<hub>/.millhouse/config.local.yaml` (gitignored), not in `wiki/config.yaml`. The deep-merged cfg the caller has open reflects the cwd's worktree, which may differ from the worktree being resolved. That's why `resolve_active_hub` reads the resolved worktree's own stub.
- `task/` files are written at `worktree_path / "task" / ...` where `worktree_path = resolve_hub_path() = Path.cwd().resolve()` (see `_spawn_core.write_initial_status` at line 718-741). When `hub_relative_path = "src/Models"`, the user's cwd is `<git_root>/src/Models`, so `task/` ends up at `<git_root>/src/Models/task/`. Git tracks it at the hub-relative path, not at the git root.
- `_inplace.is_inplace` returns False if the worktree directory exists, even if the branch matches cwd. That gives `resolve_active_worktree` a clean fallthrough: try in-place first; if in-place says no, look for the worktree dir.
- `_active.ActiveError` is raised by `read_slug` / `read_all` when the marker is missing or malformed. The helper should let this propagate (caller decides whether absence is an error).

## Constraints

No `CONSTRAINTS.md` at the hub root. Project conventions inherited from `CLAUDE.md`:

- All path resolution goes through `_paths.py` (`## Path invariants`). New helpers added there, not scattered into CLI scripts.
- Plugin scripts reference `${CLAUDE_PLUGIN_ROOT}`; no path in the helpers should hardcode `plugins/mill/...`.
- `_sibling.resolve_path` detects container-form via `repo_root.parent.name == "wts"`. Container-form is the only supported layout — the old hub-form is gone.
- Working state lives in `task/` on the task branch; the wiki holds only `Home.md` and `config.yaml`. `millpy-abandon.py`'s wiki-write is a violation of this invariant and is part of the fix.
- Junctions are IDE convenience; helpers must never read them. The new helpers use `<container>/wts/<slug>/` (real path) or `git_root` (resolved via `git rev-parse`), never via `.wiki` / `.active` junctions.

## Testing

Helper tests in [plugins/mill/unit_tests/test-paths.py](plugins/mill/unit_tests/test-paths.py).

Fixture style: `tempfile.mkdtemp` plus a small scaffolding helper that creates `<container>/wts/<repo>/.git/`, `<container>/wts/<repo>/.millhouse/active.slug.md`, and optionally `<container>/wts/<slug>/.millhouse/active.slug.md` per scenario. Mock `_subprocess_util.run` for `git rev-parse --abbrev-ref HEAD` so `_inplace.is_inplace` works without a real git repo. Matches existing test-paths.py style. No real `git init`.

TDD candidates (write tests first, watch them fail, then implement):

- `resolve_active_worktree` — new signature `(container, slug, *, cfg, git_root)`. Tests cover:
  - M1: container-form, hub_rel=".", `<container>/wts/<slug>/` exists with matching marker → returns that path.
  - M1+sub: container-form, hub_rel="src/Models", `<container>/wts/<slug>/` exists with stub declaring sub-dir hub → returns the worktree root (not the hub-subdir).
  - M2: in-place, hub_rel=".", branch on cwd matches active marker, no `<container>/wts/<slug>/` dir → returns git_root.
  - M2+sub: in-place + sub-dir hub, same as M2 → returns git_root.
  - Error: `<container>/wts/<slug>/` exists but marker slug differs → `ActiveWorktreeSlugMismatch`.
  - Error: neither in-place nor worktree-dir exists → `ActiveWorktreeNotFound`.
- `resolve_active_hub` — same four happy-path scenarios. Returns:
  - M1, M2: same as `resolve_active_worktree` (hub_rel=".").
  - M1+sub: `<container>/wts/<slug>/<hub_relative_path>`.
  - M2+sub: `<git_root>/<hub_relative_path>`.
  - Error path: propagates `ActiveWorktreeNotFound` / `ActiveWorktreeSlugMismatch` from the inner call.
- `_review_common.resolve_path` — focused test exercising the in-place branch. Scaffolds an in-place fixture, calls `resolve_path("task/discussion.md", slug)`, asserts the returned path is `<git_root>/task/discussion.md`. This is the original bug surface; the test must catch a regression.
- `millpy-abandon.py` — unit test for status-path resolution. Scaffolds a worktree-mode fixture with `<active_worktree>/task/status.md`, calls into the abandon flow with mocked git commit, asserts the path read matches and the commit target is the task branch (not the wiki). Existing abandon tests in [plugins/mill/unit_tests/test-abandon.py](plugins/mill/unit_tests/test-abandon.py) need updating to match.

Test runner: `python plugins/mill/unit_tests/run-all.py` from the worktree root. No real git, no real LLM. `tempfile` for filesystem fixtures.

No integration test. The bug surface is the helper logic; integration coverage would mostly retest spawn/claim mechanics already covered.

## Q&A log

- **Q:** Helper signatures? **A:** `resolve_active_worktree(container, slug, *, cfg, git_root)` and `resolve_active_hub(container, slug, *, cfg, git_root)`. Both keyword-only after `(container, slug)`. Symmetric with `_inplace.is_inplace`.
- **Q:** Where does `resolve_active_hub` read `hub_relative_path` from? **A:** From the resolved worktree's own `.millhouse/config.local.yaml`, not from the cfg the caller has open. Lets the helper work correctly when the resolved worktree differs from cwd.
- **Q:** Should `_review_common.resolve_path` switch to `resolve_active_hub`? **A:** Yes. The path templates (`task/discussion.md`, `task/plan/`, `task/reviews/`) live under the hub, not the git checkout root.
- **Q:** Audit scope? **A:** Tight. Fix `_paths.resolve_active_worktree`, switch `_review_common.resolve_path`, fix `millpy-abandon.py`, refactor inline duplication in `millpy-cleanup.py:103-114`. Leave `discover_active_worktrees` callers and `wiki_active_dir` cleanup transitional code alone.
- **Q:** Abandon — fix path read AND commit target? **A:** Both. Path reads from `<active_hub>/task/status.md`. Phase-append commits to the task branch via `git -C <active_worktree>`, not the wiki.
- **Q:** Test fixture style? **A:** `tempfile.mkdtemp` + scaffolding helper. Mock `git rev-parse --abbrev-ref HEAD` via `_subprocess_util.run`. No real git, no real LLM.
- **Q:** Integration test for the in-place mill-claim → mill-start → review flow? **A:** Skip. Covered well enough by unit tests on the helpers and `_review_common.resolve_path`.
- **Q:** TDD ordering? **A:** Tests first, helpers second, then refactor `_review_common.resolve_path` and `millpy-abandon.py` against the now-passing helpers.
- **Q:** Stale-worktree edge (worktree dir exists AND branch matches cwd)? **A:** `resolve_active_worktree` is non-interactive; it picks worktree-mode (directory exists, trust it). Stale-worktree handling stays in mill-cleanup/mill-merge with `_inplace.prompt_stale_worktree`.
- **Q:** CLAUDE.md update? **A:** One paragraph in `## Path invariants` mandating both helpers and banning inline `container / "wts" / slug` and `<wt> / hub_relative_path` constructions.
- **Q:** SKILL.md updates? **A:** mill-claim gets a short in-place-mode callout. mill-spawn gets a one-liner cross-reference only if it doesn't already mention the worktree-vs-in-place split.
