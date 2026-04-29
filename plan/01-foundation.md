# Batch: foundation

```yaml
task: 11 — par-C — Container layout overhaul + cwd-as-hub everywhere + gitignore-split
batch: foundation
cards: 5
verify: python plugins/mill/unit_tests/run-all.py
depends-on: []
```

## Batch Scope

This batch lands the pure-function library layer that every later batch depends on: the new `_sibling.py` rule (mill + codeguide twin), three `_paths.py` helpers (`resolve_hub_relative_path`, `resolve_active_worktree`, updated `resolve_worktrees_dir` fallback), and the `_gitignore.py` rewrite (entry split into `GLOB_ENTRIES` / `ANCHORED_ENTRIES`, new `upsert_split` function). All five cards are TDD: tests land in the same commit as the implementation. No script that imports any of these helpers is touched here — every consumer change is staged for batches 02 onward, where the new shapes get wired into running code. The external interface this batch produces is the new helper signatures themselves; later batches consume them. No batch-local decisions diverge from the shared decisions in `00-overview.md`.

## Cards

### Card 1: `_sibling.py` new container-form rule + codeguide twin

- **Reads:**
  - `plugins/mill/scripts/_sibling.py`
  - `plugins/codeguide/scripts/_sibling.py`
  - `plugins/mill/unit_tests/test-sibling.py`
  - `wiki/active/container-restructure/discussion.md`
- **Modifies:**
  - `plugins/mill/scripts/_sibling.py`
  - `plugins/codeguide/scripts/_sibling.py`
  - `plugins/mill/unit_tests/test-sibling.py`
- **Creates:** none
- **Requirements:** Replace the old `repo_root.name == "hub"` conditional with the container-form rule from discussion.md `## Decisions → hub-form-detection`. Function body becomes: parent = repo_root.parent; if parent.name == "wts": return parent.parent / role; else return parent / f"{repo_root.name}.{role}". Update the docstring's "Hub-form vs prefix-form" section to "Container-form vs prefix-form" with the new diagram. Apply the SAME function-body change to the codeguide twin at `plugins/codeguide/scripts/_sibling.py`; the only allowed difference between the two files is plugin-specific docstring wording. Verification helpers in test-sibling.py drop the old hub-form cases (which now fall through to prefix-form) and add: container-form cases (`<container>/wts/millhouse` resolves wiki/codeguide/wts to `<container>/wiki`, `<container>/codeguide`, `<container>/wts`); prefix-form cases unchanged; new explicit case showing that `<container>/hub` no longer resolves to bare `<container>/wiki` (intentional regression). Add a test that opens both `_sibling.py` files, strips docstrings and module-name lines, and asserts the remaining lines are byte-equal — this is the identical-twin invariant.
- **Commit:** `feat(sibling): switch from name=='hub' to parent.name=='wts' for container-form`

### Card 2: `_paths.resolve_hub_relative_path` helper

- **Reads:**
  - `plugins/mill/scripts/_paths.py`
  - `plugins/mill/unit_tests/test-paths.py`
  - `wiki/active/container-restructure/discussion.md`
- **Modifies:**
  - `plugins/mill/scripts/_paths.py`
  - `plugins/mill/unit_tests/test-paths.py`
- **Creates:** none
- **Requirements:** Add `resolve_hub_relative_path(worktree_root: Path, hub_subpath: str) -> Path`. Behaviour: `hub_subpath == "."` returns `worktree_root` unchanged; non-dot relative subpath returns `worktree_root / <subpath>`; absolute `hub_subpath` raises a `ValueError` with a message naming the offending value; trailing slash on `hub_subpath` is normalised away. Add the helper to `__all__`. Docstring follows the existing style in `_paths.py`. Tests cover all four cases plus a sanity case where the subpath contains nested directories. The helper does not read the filesystem — it is a pure path-join operation. The `hub_subpath` value comes from `.millhouse/config.local.yaml` `hub_relative_path:`; reading that file is the caller's job, not this function's.
- **Commit:** `feat(paths): add resolve_hub_relative_path helper for cwd-as-hub`

### Card 3: `_paths.resolve_active_worktree` helper

- **Reads:**
  - `plugins/mill/scripts/_paths.py`
  - `plugins/mill/scripts/_active.py`
  - `plugins/mill/unit_tests/test-paths.py`
  - `wiki/active/container-restructure/discussion.md`
- **Modifies:**
  - `plugins/mill/scripts/_paths.py`
  - `plugins/mill/unit_tests/test-paths.py`
- **Creates:** none
- **Requirements:** Add `resolve_active_worktree(container_path: Path, slug: str) -> Path`. Behaviour: returns `container_path / "wts" / slug` when that directory exists AND its `.millhouse/active.slug.md` parses (via `_active.read_slug`) to the same slug. Raises a typed `ActiveWorktreeNotFound` (subclass of `RuntimeError`, defined in this module) when the directory is absent. Raises a typed `ActiveWorktreeSlugMismatch` (also `RuntimeError`-subclass) when the marker exists but its slug differs from the requested slug. Both error classes are added to `__all__`. The function is the canonical answer to "given a slug, where does that worktree live on disk" — every cross-worktree consumer uses it. Tests use `tempfile.TemporaryDirectory()`-based fixtures to populate `<container>/wts/<slug>/.millhouse/active.slug.md` via `_active.write` and exercise: happy path, missing dir, marker-slug-mismatch.
- **Commit:** `feat(paths): add resolve_active_worktree helper`

### Card 4: `_paths.resolve_worktrees_dir` fallback + new `resolve_container_path` + test-paths.py fixture migration

- **Reads:**
  - `plugins/mill/scripts/_paths.py`
  - `plugins/mill/unit_tests/test-paths.py`
  - `plugins/mill/unit_tests/test-cleanup.py`
  - `plugins/mill/scripts/millpy-cleanup.py`
- **Modifies:**
  - `plugins/mill/scripts/_paths.py`
  - `plugins/mill/unit_tests/test-paths.py`
  - `plugins/mill/unit_tests/test-cleanup.py`
- **Creates:** none
- **Requirements:** Three-part change. (a) `_paths.resolve_worktrees_dir` fallback expression: change from `resolve_path("worktrees", main_root)` to `main_root.parent`. The override path (`cfg["spawn"]["worktrees_dir"]` template substitution) is unchanged. The fallback is calibrated for container-form (`<container>/wts/<repo>` → `main_root.parent` = `<container>/wts/`). Prefix-form clones must set `spawn.worktrees_dir:` explicitly — there is no longer an automatic prefix-form sibling fallback for worktrees. Drop the unused `from _sibling import resolve_path` import if `resolve_path` is no longer referenced elsewhere in `_paths.py` (it remains re-exported via `__all__`; keep the re-export). Update the docstring to reflect "main worktree's parent is the worktrees container; prefix-form requires `spawn.worktrees_dir:` override". (b) Add a NEW helper `resolve_container_path(git_root: Path) -> Path` to `_paths.py` and to `__all__`. Body: compute `main_root = resolve_main_worktree_root(git_root)`; if `main_root.parent.name == "wts"` return `main_root.parent.parent` (container-form: container is grandparent of main_root); else return `main_root.parent` (prefix-form: container is parent of main_root). This is the canonical answer to "what is the container directory" for any cross-worktree operation that needs to resolve `<container>/portals/`, `<container>/wts/`, or `<container>/wiki/`. Every consumer in batches 02–04 that currently derives the container ad-hoc (mill-spawn `_build_tokens`, mill-claim portal creation, `_review_common.resolve_path`, `millpy-status`/`list`/`inspect` discovery, `millpy-cleanup` portal removal) routes through this helper. Tests in test-paths.py: container-form fixture (`<tmp>/wts/<repo>` as main_root) → returns `<tmp>`; prefix-form fixture (`<tmp>/<repo>` as main_root) → returns `<tmp>`. Use `patch("_paths.resolve_main_worktree_root", return_value=fixture_main_root)` for the resolution. (c) test-paths.py fixture migration — the file extensively uses `tmp_path / "hub"` as the main_root for `resolve_wiki_path` and `resolve_worktrees_dir` tests. Under Card 1's new `_sibling.resolve_path` rule, those fixtures fall through to prefix-form (`tmp_path / "hub.wiki"`) and break the existing assertions. Switch every hub-form fixture in test-paths.py to container-form: replace `hub = tmp_path / "hub"` with `wts_dir = tmp_path / "wts"; wts_dir.mkdir(); main_root = wts_dir / "millhouse"; main_root.mkdir()` (or equivalent), so `parent.name == "wts"` evaluates True and the existing assertions (`tmp_path / "wiki"`, `tmp_path / "wts"`) hold. The walk-up tests (`resolve_wiki_path` from a child worktree) similarly use `tmp_path / "hub"` as the main root via `patch("_paths.resolve_main_worktree_root", return_value=...)` — change those fixtures to container-form too. The `resolve_worktrees_dir` container-form fallback test's expectation becomes `tmp_path / "wts"` (the parent of the main_root in container-form). The prefix-form `resolve_worktrees_dir` fallback test's expectation becomes `tmp_path` (`main_root.parent` for `tmp_path / "foo"`); update or DROP this test — if dropped, add a comment explaining that prefix-form fallback is intentionally minimal and prefix-form users must configure `spawn.worktrees_dir:` for a sensible default. Add a new test case asserting that the OLD hub-form fixture (`tmp_path / "hub"` as a bare child of an arbitrary tmp_path with `parent.name != "wts"`) now resolves to prefix-form (`tmp_path / "hub.wiki"`) — proving the intentional regression from discussion.md `## Decisions → hub-form-detection`.
- **Commit:** `feat(paths): worktrees_dir fallback + resolve_container_path; migrate test fixtures`

### Card 5: `_gitignore.py` STANDARD_ENTRIES split + `upsert_split`

- **Reads:**
  - `plugins/mill/scripts/_gitignore.py`
  - `plugins/mill/unit_tests/test-gitignore-phase.py`
  - `wiki/active/container-restructure/discussion.md`
- **Modifies:**
  - `plugins/mill/scripts/_gitignore.py`
  - `plugins/mill/unit_tests/test-gitignore-phase.py`
- **Creates:** none
- **Requirements:** Replace `STANDARD_ENTRIES` with two module-level lists: `GLOB_ENTRIES = ["**/.millhouse/", "**/.scratch/", "**/wts/", "**/portals/"]` and `ANCHORED_ENTRIES = ["/.active", "/.others"]`. Note: the `**/worktrees/` entry is replaced by `**/wts/` and `**/portals/` is added; this is intentional and load-bearing for the new layout (see discussion.md `## Decisions → gitignore-split`). Change `render_block`'s signature to `render_block(glob_entries: list[str], anchored_entries: list[str] | None = None) -> str` — single function, two modes. When `anchored_entries is None`, the function preserves the legacy single-list behaviour: it accepts `glob_entries` as the legacy "hardlink_entries" list (positional name change is permitted but the call shape `render_block([...])` still works), prepends the `STANDARD_ENTRIES`-equivalent legacy entry list internally, and emits the legacy block layout. When `anchored_entries` is a list (possibly empty), the function emits the new combined block: `glob_entries` first (each line as-is from `GLOB_ENTRIES`), then `anchored_entries` second (each normalised to leading `/`). Both `upsert` and the new `upsert_split` call the same `render_block` with different arities. Add `upsert_split(repo_root_gitignore: Path, hub_gitignore: Path, glob_entries: list[str], anchored_entries: list[str]) -> tuple[bool, bool]`: when `repo_root_gitignore == hub_gitignore`, write a single combined block (glob + anchored together) to the shared path and return `(changed, False)` where `changed` reflects the file-write outcome; when they differ, write `glob_entries` only to `repo_root_gitignore` and `anchored_entries` only to `hub_gitignore`, returning `(repo_changed, hub_changed)`. Idempotent re-run on either path returns `(False, False)`. **Keep the legacy single-call `upsert(gitignore_path, hardlink_entries)` callable** — the live `mill-setup` SKILL.md Phase 4.5b still calls `upsert` until Card 19 (mill-setup SKILL.md update) replaces the call with `upsert_split`. Removing `upsert` here would break any `/mill-setup` invocation between this card landing and Card 19 landing. Card 19 explicitly removes `upsert` (and the legacy single-list code path inside `render_block`) atomically with the SKILL.md rewrite. Test-modification requirements: replace every `from _gitignore import STANDARD_ENTRIES` (and any references to `STANDARD_ENTRIES` symbol) in `test-gitignore-phase.py` with imports/references to `GLOB_ENTRIES + ANCHORED_ENTRIES` as appropriate for the test's intent. New test cases cover: same-path single-block write; different-path two-block write; idempotent re-run on each path; hardlink-list expansion (anchored entries get `/` prepended); preserved corrupt-marker `ValueError`; legacy `upsert` (single-arg `render_block` path) still passes its existing tests (no regression).
- **Commit:** `feat(gitignore): split STANDARD_ENTRIES into GLOB/ANCHORED and add upsert_split`

## Batch Tests

`verify: python plugins/mill/unit_tests/run-all.py` — runs every `test-*.py` under `plugins/mill/unit_tests/`. Pass criteria: zero failures. The new test cases land in `test-sibling.py`, `test-paths.py`, `test-gitignore-phase.py`. No new test files in this batch (the new `_setup.py` lands in batch 02 with its own `test-setup-hub-links.py`).
