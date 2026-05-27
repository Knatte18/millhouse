# Discussion: Sub-project repo (hub_relative_path) support

```yaml
task: Sub-project repo (hub_relative_path) support
slug: hub-relative-path-support
status: discussing
parent: main
```

## Problem

mill's config is **layered**: the plugin-bundled `templates/mill-config.yaml` is the always-present base, and `<hub>/mill-config.yaml` plus `<worktree>/.millhouse/config.local.yaml` are optional overlays. `hub_relative_path` (set in `config.local.yaml`) tells mill that the hub lives at a subfolder of the worktree's git checkout — used when mill is installed inside an existing repo rather than being its own repo.

Many call sites silently assume `hub == git_root`. The assumption is invisible in the typical millhouse setup (where hub *does* equal git_root by coincidence) but breaks in sub-project layouts. The bugs split into five surfaces:

1. **Config loaders called with wrong conceptual path.** `_config.load_config(repo_root, worktree_root)` and `_review_common.load_config(repo_root, mill_dir)` both expect the **hub** path as their first arg. Callers pass `git_root` instead. When `git_root != hub`, the loader looks for `<git_root>/mill-config.yaml` (not there), skips the hub overlay layer, and silently returns template defaults — the caller's hub-level config edits appear to have no effect. Some SKILL.md docs even document the first arg as `wiki_path`, which makes the bug doubly invisible.

2. **`millpy-claim.py` / `millpy-spawn.py` precheck wrappers**. Both wrap the loader with a `_strict_load_config` that requires `<repo_root>/mill-config.yaml` to exist. With the swapped first arg the precheck always fails in sub-project layouts. The wrappers are also wrong on principle — the layering model treats the hub overlay as optional, so requiring the file at all is incorrect.

3. **`mill-go` step 4.5 worktree_root**. The SKILL.md sets `worktree_root = _paths.resolve_git_root()`. In sub-project layouts this is the outer repo, not the hub subfolder where `_mill/` lives, so every subsequent `_paths.resolve_task_path` call fails.

4. **`millpy-review-code` resolve_ref_paths**. The function resolves plan-Context entries against `project_root = Path.cwd()` (= the hub). Plan files written by `mill-plan` use **git-root-relative** paths like `lib/avm/...` (the convention for files outside the hub but inside the repo). In sub-project layouts these always miss under `project_root`, and the holistic code review errors out before it starts.

5. **SKILL.md docs**. mill-start/mill-plan/mill-merge-in/mill-go all reference the wrong first-arg name (`wiki_path`) for `_config.load_config` / `_review_common.load_config`. Each occurrence propagates the same bug class to anyone who copies the documented form.

Why now: `hub_relative_path` support was wired into `_paths.py` (resolve_hub_relative_path / resolve_active_hub) but the rest of the codebase hasn't been audited against the layering model. No integration test exercises a sub-project layout, so the gap surfaces only when real users hit it. The current cluster of issues (#359, #369, #370, #375, #379, #380, #381) all originate from the same hub-vs-git_root confusion.

## Scope

**In:**
- Fix every wrong callsite of `_config.load_config` so the first arg is the hub root (= `_paths.resolve_hub_path()`, which returns `cwd.resolve()` and is the project convention for the hub directory).
- Fix every wrong callsite of `_review_common.load_config` analogously.
- Rename the first positional arg from `repo_root` to `hub_root` in `_config.load_config`, `_review_common.load_config`, and `_paths.resolve_mill_config_path`. Pure naming + docstring change; positional signature is otherwise untouched.
- Delete `_strict_load_config` in `millpy-claim.py` and the `_load_config` wrapper in `millpy-spawn.py`. Callers invoke `_config.load_config(resolve_hub_path(), resolve_hub_path())` directly.
- In `mill-go` SKILL.md step 4.5: replace `worktree_root = _paths.resolve_git_root()` with `worktree_root = _paths.resolve_active_hub(container_path, slug, cfg=cfg, git_root=git_root)` where `container_path = _paths.resolve_container_path(git_root)`. Also update step 3 to use the hub for `_review_common.load_config`'s first arg.
- Add a `git_root: Path | None = None` keyword arg to `_review_common.resolve_ref_paths`. When a candidate under `project_root` does not exist and the raw token is not in `creates_union` or `deletes_union`, try `git_root / raw` before raising. Routing precedence: `wiki/` prefix → wiki_root (unchanged); else `project_root / root / raw` if exists; else `git_root / raw` if exists; else suppression by creates/deletes union; else raise. Verified callsites to update (3 sites total): `_review_code.py:254`, `_review_plan.py:134`, `_review_plan.py:470`.
- Add the same `git_root: Path | None = None` keyword arg to `_review_common.resolve_existing_paths`, with identical fallback semantics — when the candidate under `project_root` does not exist, try `git_root / raw` before silently dropping. Symmetric with `resolve_ref_paths`. Without this, sub-project layouts silently drop git-root-relative `lib/...` paths from the bulk and reviewers see an incomplete context. Verified callsites to update (6 sites total): `_review_code.py:274`, `_review_code.py:374`, `_review_plan.py:140`, `_review_plan.py:205`, `_review_plan.py:476`, `_review_plan.py:544`.
- Fix the four SKILL.md docs: `mill-start/SKILL.md:49`, `mill-plan/SKILL.md:19`, `mill-merge-in/SKILL.md:56`, `mill-go/SKILL.md:25` — change documented first arg from `wiki_path` to `hub_root` and update the signature annotation. Also fix the undefined `repo_root` reference in `mill-finalize/SKILL.md:15` (uses the variable name without ever defining it).
- Add one integration test (`plugins/mill/integration_tests/test-hub-relative-path.py`) that constructs a sub-project fixture and asserts `millpy-spawn --dry-run` + asset-level checks (status.md path resolution, `.millhouse/config.local.yaml` stub contains `hub_relative_path:`, junctions land at the hub subfolder).
- Extend unit tests:
  - `test-config.py`: add a sub-project fixture case for `_config.load_config` confirming hub-overlay merges correctly when hub != git_root.
  - `test-review-common.py`: add a sub-project case for `load_config`, plus tests for `resolve_ref_paths` `git_root` fallback semantics (hit, miss, precedence with creates/deletes union and `wiki/` prefix).
  - `test-paths.py`: confirm `resolve_active_hub` is exercised against a fixture with `hub_relative_path != "."`.

**Out:**
- Any behaviour change in `_config.load_config` beyond the doc-only first-arg rename. The function stays positional (no kw-only), stays lenient (template alone is valid), and has no runtime guard for misuse — fix the bug at every callsite, never in the helper. (See feedback-memory `fix-misuse-at-callsite-not-api`.)
- Refactor of the `mill-claim` / `mill-spawn` config-loading paths beyond deleting the wrappers and calling the loader directly.
- LLM-driven end-to-end integration test. The path-resolution failure modes are observable at asset-level; full E2E with real reviewers is out of scope and expensive.
- Changes to `_client.health_check` / wiki-daemon health logic. Issue #380's `_wiki.health_check(hub_root)` no longer exists — the current `_client.health_check(wiki_path)` takes wiki_path only and is layout-agnostic. No work needed.
- Removing or changing `hub_relative_path` semantics. The mechanism in `_paths.py` is correct; we are aligning the rest of the codebase to it.
- Adding new config keys, new `pipeline.*` flags, or new env-var bindings.
- Renaming the `_review_common.load_config` second arg `mill_dir` — its meaning is correct; only the first arg is wrong-named.

## Decisions

### Fix at callsite, not at API

- Decision: every misuse of `_config.load_config` and `_review_common.load_config` is fixed at the offending callsite. Helpers stay positional, no kw-only retrofits, no runtime guards for caller mistakes, no stderr warnings on a missing hub overlay.
- Rationale: defensive APIs encourage sloppy callers. The mistake happens at the call site; the fix lives there. Internal Python helpers are not a system boundary and do not need to police their inputs. This is the explicit operator stance for this codebase (saved as feedback-memory `fix-misuse-at-callsite-not-api`).
- Rejected: keyword-only first-arg enforcement (would raise `TypeError` on positional swap — still treats misuse as the helper's concern); runtime guard that probes `<hub_root>/mill-config.yaml` existence (re-encodes "hub == X" assumptions the layering model deliberately avoids); stderr warning when no overlay is present (template-only is a valid configuration, not a deserves-a-warning state); splitting into strict + lenient variants (every caller is conceptually lenient).

### Rename first arg to `hub_root` (doc-only)

- Decision: rename the first positional arg of `_config.load_config`, `_review_common.load_config`, and `_paths.resolve_mill_config_path` from `repo_root` to `hub_root`. Update docstrings, type-hint comments, and SKILL.md signature annotations. No behavioural change; no kw-only enforcement.
- Rationale: `repo_root` is ambiguous in a project where multiple roots exist (git_root, wiki_path, hub_root). `hub_root` names the conceptual role and matches `_paths.resolve_hub_path()`. The rename is a pure clarity improvement; positional call sites continue to work as long as they pass the right value.
- Rejected: keeping `repo_root` (perpetuates the naming confusion); renaming the second arg too (`worktree_root` and `mill_dir` are both correctly named for their semantics).

### Drop the strict-wrapper precheck in `millpy-claim` / `millpy-spawn`

- Decision: delete `_strict_load_config` in `millpy-claim.py` and the `_load_config` wrapper in `millpy-spawn.py`. Replace each invocation with a direct call `_config.load_config(resolve_hub_path(), resolve_hub_path())` (claim is in-place: hub == worktree) or `_config.load_config(resolve_hub_path(), resolve_hub_path())` (spawn pre-creates the worktree later; the loader does not consume `worktree_root` for spawn-time decisions).
- Rationale: the precheck enforces `<repo_root>/mill-config.yaml` must exist. Per the layering model the hub overlay is optional — template-only is a valid setup. The precheck rejects valid configurations. Calling the loader directly preserves the correct lenient behaviour.
- Rejected: keep wrapper but fix the arg (passes `resolve_hub_path()` instead of `git_root`) — preserves the wrongly-strict precheck; replace with a `load_config_strict` helper — adds a strict variant we do not need.

### `mill-go` `worktree_root` via `resolve_active_hub`

- Decision: in `mill-go` SKILL.md step 4.5, replace `worktree_root = _paths.resolve_git_root()` with:
  ```python
  git_root      = _paths.resolve_git_root()
  container_path = _paths.resolve_container_path(git_root)
  worktree_root  = _paths.resolve_active_hub(container_path, slug, cfg=cfg, git_root=git_root)
  ```
  `slug` is in scope from step 1; `cfg` from step 3. The same path resolution applies to step 3's load_config call (already correct in code via the script but the SKILL.md prose example is wrong).
- Rationale: `resolve_active_hub` is the canonical helper for this question. It applies the two-tier `hub_relative_path` lookup (caller's cfg first, then the worktree's own stub) and handles both in-place mode (hub == git_root) and worktree mode (hub == `<git_root>/<sub>`). No path arithmetic at the call site.
- Rejected: inline `_paths.resolve_git_root() / cfg.get('hub_relative_path', '.')` (duplicates the two-tier resolution logic and misses the stub-override case); new mill-go-specific helper (`resolve_active_hub` already exists for this purpose).

### `resolve_ref_paths` gains a `git_root` fallback

- Decision: extend the signature to `resolve_ref_paths(raw_paths, project_root, root, *, creates_union=None, deletes_union=None, wiki_root=None, git_root=None, caller_label="resolve_ref_paths")`. When the candidate under `project_root / root / raw` does not exist on disk and the raw token is not in `creates_union` or `deletes_union`:
  - If `git_root` is provided and `git_root / raw` exists, return that.
  - Else raise `ReviewError`.
  Routing precedence:
  1. `wiki/`-prefix → `wiki_root` (unchanged).
  2. `project_root / root / raw` if on disk.
  3. `git_root / raw` if on disk (new fallback).
  4. Suppression via creates/deletes union (unchanged).
  5. `ReviewError` (unchanged).
- Update the callers verified in the Technical Context tables below (3 `resolve_ref_paths` sites + 6 `resolve_existing_paths` sites) to pass `git_root=_paths.resolve_git_root()`. `millpy-review-code.py` / `millpy-review-plan.py` resolve and pass `git_root` from their main entries through `_review_code.run` / `_review_plan.run`.
- Rationale: plan files written by `mill-plan` use git-root-relative paths like `lib/avm/...` for files outside the hub but inside the repo (a common pattern in monorepos). The fallback keeps plans portable across both layouts without forcing mill-plan to canonicalise differently per layout. Symmetric with the existing `wiki/`-prefix routing.
- Rejected: making `mill-plan` rewrite Context paths to project-relative (`../../lib/...`) when `hub_relative_path != "."` — less permissive, breaks hand-edited plans, complicates plan-review (relative paths obscure intent); adding a `git_root:` frontmatter field — over-engineered; replacing the hard-fail with a silent-skip — defeats #41's intent.

### Integration test: structural, no LLM

- Decision: add `plugins/mill/integration_tests/test-hub-relative-path.py`. It builds a hub-in-subfolder fixture under `.scratch/`:
  - outer repo root: `<container>/wts/<outer>/`
  - hub: `<container>/wts/<outer>/projects/sub/`
  - hub `mill-config.yaml` lives at the hub
  - `<outer>/.millhouse/config.local.yaml` declares `hub_relative_path: projects/sub`
- The test runs `millpy-spawn --dry-run --slug <fixture-slug>` from the hub and asserts:
  - the dry-run output reports the resolved status.md path under the hub subfolder, not the outer git_root;
  - a follow-up assert simulates the mill-go step 4.5 derivation: `resolve_active_hub(container, slug, cfg=cfg, git_root=git_root)` returns the hub subfolder;
  - `resolve_ref_paths` with a `lib/...` raw under the same fixture (and `git_root` provided) resolves to the outer-repo file, not raising.
- The test does not invoke claude/sonnet or any LLM-driven path. It exercises the path-resolution surface that broke in every reported issue.
- Rationale: every reported failure is a path-resolution bug; LLM execution is irrelevant to the surface under test. Existing integration tests (`test-spawn.py`, `test-cleanup.py`) follow the same dry-run + asset-asserts shape.
- Rejected: full E2E with real claude (out of scope, expensive, not informative for path bugs); unit-tests-only (misses the cross-script wiring that `_paths.resolve_active_hub` enables).

## Technical context

### Affected files and current state

- `plugins/mill/scripts/_config.py:147` — `load_config(repo_root, worktree_root)`. The hub-overlay merge starts at line 161 (`_paths.resolve_mill_config_path(repo_root)`). Currently raises `FileNotFoundError` when the hub-overlay file is missing — that raise must be removed or guarded, since per the layering model a missing overlay is valid. (Re-verify this is still the case at implementation time — the raise is the strict-form behaviour that the operator-level layering principle contradicts.)
- `plugins/mill/scripts/_paths.py:441` — `resolve_mill_config_path(repo_root)`. Rename arg only.
- `plugins/mill/scripts/_paths.py:145` — `resolve_hub_path(cwd=None)`. Returns `cwd.resolve()`. Used by every fixed callsite as the hub root.
- `plugins/mill/scripts/_paths.py:342` — `resolve_active_hub(container_path, slug, *, cfg, git_root)`. Already implements the two-tier `hub_relative_path` lookup. mill-go's step 4.5 starts using this.
- `plugins/mill/scripts/_review_common.py:1206` — `load_config(repo_root, mill_dir)`. Same rename as `_config.load_config`.
- `plugins/mill/scripts/_review_common.py:552` — `resolve_ref_paths(...)`. New `git_root` kwarg.

### `_config.load_config` callsites to fix

All currently pass `git_root` (or in two cases the resolved git_root path) as the first positional. After the fix each passes the hub root (`resolve_hub_path()`).

| File | Line | Current | Replace with |
|---|---|---|---|
| `millpy-bg.py` | 142 | `_config.load_config(Path(git_root), Path(git_root))` | `_config.load_config(_paths.resolve_hub_path(), Path(git_root))` (second arg stays the launcher's git_root view for worktree resolution) |
| `millpy-claim.py` | 168 (via `_strict_load_config`) | `_strict_load_config(git_root, resolve_hub_path())` | direct `_config.load_config(resolve_hub_path(), resolve_hub_path())` after deleting the wrapper |
| `millpy-claude-sub.py` | 159 | `_config.load_config(git_root, git_root)` | `_config.load_config(_paths.resolve_hub_path(), _paths.resolve_hub_path())` |
| `millpy-cleanup.py` | 600 | `_load_config(git_root, git_root)` | `_load_config(_paths.resolve_hub_path(), git_root)` (worktree_root stays as the cleanup-target's git_root) |
| `millpy-color.py` | 90 | `_load_config(git_root, resolve_hub_path())` | `_load_config(resolve_hub_path(), resolve_hub_path())` |
| `millpy-inspect.py` | 47 | `_config.load_config(git_root, git_root)` | `_config.load_config(_paths.resolve_hub_path(), _paths.resolve_hub_path())` |
| `millpy-spawn.py` | 111 (via `_load_config`) | `_load_config(git_root, resolve_hub_path())` | direct `_config.load_config(resolve_hub_path(), resolve_hub_path())` after deleting the wrapper |
| `millpy-status.py` | 26 | `_config.load_config(git_root, git_root)` | `_config.load_config(_paths.resolve_hub_path(), _paths.resolve_hub_path())` |
| `millpy-terminal.py` | 56 | `_load_config(git_root, git_root)` | `_load_config(_paths.resolve_hub_path(), _paths.resolve_hub_path())` |
| `millpy-vscode.py` | 183 | `_load_config(git_root, git_root)` | `_load_config(_paths.resolve_hub_path(), _paths.resolve_hub_path())` |
| `_llm_claude.py` | 99 | `_config.load_config(git_root, git_root)` | `_config.load_config(_paths.resolve_hub_path(), _paths.resolve_hub_path())` |

Verification rule for the implementer: for each callsite, ask "what does this loader need — config values for the hub the user is operating on (use `resolve_hub_path()`) or for a specific worktree the script is targeting?" The second arg is `worktree_root` because the loader reads `<worktree_root>/.millhouse/config.local.yaml`. In most scripts the worktree being operated on is the current cwd (hub == worktree). For `millpy-cleanup.py` the worktree may differ from cwd when cleaning a different task — keep the existing `git_root` for that second arg.

### `_review_common.load_config` callsites to fix

| File | Line | Current | Replace with |
|---|---|---|---|
| `millpy-review-code.py` | 76 | `load_config(project_root, mill_dir)` where `project_root = Path.cwd()` | `load_config(_paths.resolve_hub_path(), mill_dir)` (conceptually identical; uses the canonical helper) |
| `millpy-review-discussion.py` | 50 | `load_config(hub_dir, mill_dir)` | already correct; no change |
| `millpy-review-plan.py` | 86 | `load_config(project_root, mill_dir)` | same as review-code |
| `millpy-validate-plan.py` | 44 | `load_config(repo_root, mill_dir)` where `repo_root = resolve_git_root()` | `load_config(_paths.resolve_hub_path(), mill_dir)` |

The first arg should be `_paths.resolve_hub_path()` in every case. `mill_dir` stays as `<worktree>/.millhouse` resolved via the script's own logic.

### Strict-wrapper deletions

- `millpy-claim.py:56–66` — delete `_strict_load_config`. Update call at line 168.
- `millpy-spawn.py:57–67` — delete `_load_config`. Update import on line 46 (drop the alias) and call at line 111.

After deletion the call sites become a single `_config.load_config(resolve_hub_path(), resolve_hub_path())` invocation. The import-alias `_load_config_lenient` in `millpy-spawn.py` becomes unnecessary; import `load_config as _load_config` (or use unaliased import) consistent with the other scripts.

### `_config.load_config` raise-removal

`_config.py` currently raises `FileNotFoundError` when `<hub_root>/mill-config.yaml` is missing. Per the layering principle the hub overlay is optional — template-only is a valid configuration. The raise must be removed; instead, when the file is missing, skip the hub-overlay merge step (continue with template + local overlays). Implementer must remove the raise and add a no-op path. Unit test `test-config.py` must add a case where no hub overlay is present and confirm template defaults are returned without raising.

### `resolve_ref_paths` and `resolve_existing_paths` signature change

Update `_review_common.resolve_ref_paths` to:

```python
def resolve_ref_paths(
    raw_paths: list[str],
    project_root: Path,
    root: str | None,
    *,
    creates_union: set[str] | None = None,
    deletes_union: set[str] | None = None,
    wiki_root: Path | None = None,
    git_root: Path | None = None,           # NEW
    caller_label: str = "resolve_ref_paths",
) -> list[Path]:
```

Fallback logic inside the per-raw loop:

```python
if candidate.exists():
    resolved.append(candidate)
    continue
# Fallback: try git_root for git-root-relative paths.
if git_root is not None:
    gr_candidate = git_root / raw
    if gr_candidate.exists():
        resolved.append(gr_candidate)
        continue
# Suppression via creates/deletes union (existing logic).
if raw in creates or raw in deletes:
    continue
raise ReviewError(...)
```

The wiki/-prefix branch is untouched. The fallback applies to non-wiki, non-existing-under-project paths.

Apply the **same** kwarg + same fallback to `_review_common.resolve_existing_paths`:

```python
def resolve_existing_paths(
    raw_paths: list[str],
    project_root: Path,
    root: str | None,
    *,
    wiki_root: Path | None = None,
    git_root: Path | None = None,           # NEW
) -> list[Path]:
```

With identical wiki/ → project_root → git_root precedence. The function still silently drops paths that exist nowhere — that behaviour is unchanged. The fallback only adds the git_root attempt before the silent drop.

Verified callsites to update (audited by grep against the current source tree, not inferred):

**`resolve_ref_paths` (3 sites):**
- `_review_code.py:254` — inside `_review_code.run()`; add `git_root=git_root` to call and to `run()`'s signature.
- `_review_plan.py:134` — inside batch-card resolution; same treatment.
- `_review_plan.py:470` — inside holistic plan-review path; same treatment.

**`resolve_existing_paths` (6 sites):**
- `_review_code.py:274` — ancestors-on-disk for the batch under review.
- `_review_code.py:374` — missing-paths reconciliation step.
- `_review_plan.py:140` — batch-card ancestor expansion.
- `_review_plan.py:205` — batch-card missing-path resolution.
- `_review_plan.py:476` — holistic all-creates-on-disk expansion.
- `_review_plan.py:544` — holistic missing-path resolution.

For each callsite, the implementer threads `git_root` from the caller's main entry (`millpy-review-code.py`, `millpy-review-plan.py`) down through the `_review_code.run` / `_review_plan.run` signatures and into the callsite. `millpy-review-discussion.py` does not call either function — no change needed.

Source-of-truth verification: implementer must re-grep `resolve_ref_paths` and `resolve_existing_paths` in `_review_code.py` and `_review_plan.py` at implementation time and assert the count matches (3 and 6 respectively). If counts diverge, the codebase has shifted since this discussion was written — pause and update the plan rather than guessing.

### `mill-go` SKILL.md edits

Locations to edit:
- Step 3 (line 25): change `_review_common.load_config(_paths.resolve_git_root(), Path(".millhouse"))` to `_review_common.load_config(_paths.resolve_hub_path(), _paths.resolve_hub_path() / ".millhouse")`.
- Step 4.5 (lines 38–47): replace the `worktree_root` derivation per the Decision above. Add `slug` capture (already at step 1) into step 4.5 as a precondition note.

### `mill-finalize` SKILL.md fix

Step 2 currently reads `cfg = _config.load_config(repo_root, git_root)` where `repo_root` is never defined in step 1 — the prose is internally inconsistent. Fix to `cfg = _config.load_config(_paths.resolve_hub_path(), git_root)` and update the signature annotation on the next line to use `hub_root` instead of `repo_root`.

### Other SKILL.md edits

- `mill-start/SKILL.md:49` — change signature comment from `(wiki_path: Path, worktree_root: Path)` to `(hub_root: Path, worktree_root: Path)`.
- `mill-plan/SKILL.md:19` — same.
- `mill-merge-in/SKILL.md:56` — change `cfg = _config.load_config(wiki_path, git_root)` to `cfg = _config.load_config(_paths.resolve_hub_path(), git_root)`.

### Integration-test fixture sketch

Under `.scratch/test-hub-relative-path/<run-id>/`:

```
<container>/
  wts/
    outer-repo/                  ← outer git repo
      .git/
      lib/example.py             ← git-root-relative file for resolve_ref_paths test
      .millhouse/config.local.yaml  ← declares hub_relative_path: projects/sub
      projects/sub/               ← hub
        mill-config.yaml          ← hub overlay
        .millhouse/config.local.yaml  ← worktree-stub view
  wiki/
    Home.md                       ← one [s] task for spawn to pick up
    proposal-<slug>.md
```

Test steps (no LLM):
1. Construct the fixture via the `_setup_pair`-style helper used by `test-spawn.py`.
2. From `<container>/wts/outer-repo/projects/sub/` (the hub) run `millpy-spawn --dry-run --slug <slug>`. Assert exit 0 and that the printed status path lands under `<container>/wts/<slug>/projects/sub/_mill/status.md`.
3. Directly call `_paths.resolve_active_hub(container_path, slug, cfg=cfg, git_root=outer-worktree-git-root)` and assert the returned path is the worktree's hub subfolder.
4. Construct a fake plan-Context list `["lib/example.py"]`, call `resolve_ref_paths(..., project_root=hub_subfolder, git_root=outer-worktree-git-root)`, assert the returned path resolves to the outer repo's `lib/example.py`. Repeat with no `git_root` and assert `ReviewError`.

The fixture stays under `.scratch/` and is cleaned by the test's teardown (mirroring `test-spawn.py`).

### Helper sub-batches

For the implementer's planning:

- **Batch A — helper API (layering correctness):** `_config.load_config` rename + remove raise; `_review_common.load_config` rename; `_paths.resolve_mill_config_path` rename; add `resolve_ref_paths` `git_root` kwarg + fallback; add `resolve_existing_paths` `git_root` kwarg + fallback. Update unit tests `test-config.py`, `test-review-common.py`, `test-paths.py`.
- **Batch B — callsite fixes:** all 11 `_config.load_config` callers; all 4 `_review_common.load_config` callers; delete `_strict_load_config` / `_load_config` wrappers in claim/spawn. Thread `git_root` through `_review_code.run` and `_review_plan.run` to the 3 verified `resolve_ref_paths` callsites and the 6 verified `resolve_existing_paths` callsites.
- **Batch C — SKILL.md docs + mill-go path:** edit mill-start, mill-plan, mill-merge-in, mill-go, mill-finalize SKILL.md per the Decisions. Adjust mill-go step 4.5 prose to use `resolve_active_hub`.
- **Batch D — integration test:** new `test-hub-relative-path.py`.

Batches B and C depend on A. Batch D depends on B+C being green.

## Constraints

From `CLAUDE.md` and project conventions:

- **All path resolution through `_paths.py`.** Callsite fixes must use `_paths.resolve_hub_path()`, `_paths.resolve_active_hub`, `_paths.resolve_container_path`, `_paths.resolve_git_root` — no inline path arithmetic.
- **`${CLAUDE_PLUGIN_ROOT}` for all intra-plugin Bash invocations** in any test or skill scripts touched.
- **Wiki mutations stay through `_client` / `_wiki` helpers** — irrelevant to this task (no wiki writes), but applies to the integration test if it ever needs to seed Home.md (use the daemon, not raw writes).
- **ASCII-only stdout from `print()` / `_log()`** — applies to any new print statements in fixed callsites or in the integration test.
- **No CONSTRAINTS.md** at the hub root — the operator-level "fix at callsite, not API" principle (saved as feedback-memory) supersedes any documentation that might suggest defensive APIs.
- **No new dependencies.** YAML loading is via the existing `yaml` import; subprocess via `_subprocess_util.run`; pygit2 only where already used.

## Testing

### Unit tests

- **`test-config.py`** — add:
  - `test_load_config_sub_project_hub_overlay`: fixture with `hub_root = <tmp>/projects/sub`, `<hub_root>/mill-config.yaml` declares non-default key, call `load_config(hub_root, worktree_root)`, assert overlay value wins over template.
  - `test_load_config_no_hub_overlay_returns_template`: fixture with no `<hub_root>/mill-config.yaml`, assert `load_config` returns the template defaults without raising. (Verifies the raise removal.)

- **`test-review-common.py`** — add:
  - Same sub-project case for `_review_common.load_config`.
  - `test_resolve_ref_paths_git_root_fallback_hit`: raw path missing under `project_root`, present under `git_root`, with `git_root=...` passed → returns `git_root / raw`.
  - `test_resolve_ref_paths_git_root_fallback_miss`: raw path missing both places, not in creates/deletes union, with `git_root=...` passed → raises `ReviewError`.
  - `test_resolve_ref_paths_no_git_root_kwarg`: existing callers that don't pass `git_root` → behaviour unchanged (current tests must still pass).
  - `test_resolve_ref_paths_creates_union_precedence`: raw in creates_union, not on disk under `project_root` or `git_root`, with `git_root` passed → suppressed (creates_union wins over fallback miss).
  - `test_resolve_ref_paths_wiki_prefix_unaffected`: `wiki/foo`-prefixed path → still routes to `wiki_root`, ignores `git_root`.
  - `test_resolve_existing_paths_git_root_fallback_hit`: same shape as the ref_paths variant — raw missing under `project_root`, present under `git_root`, with `git_root=...` → returns `git_root / raw`.
  - `test_resolve_existing_paths_git_root_fallback_miss`: raw missing both places → silently dropped (no raise; existing behaviour for missing-everywhere paths).
  - `test_resolve_existing_paths_no_git_root_kwarg`: existing callers that don't pass `git_root` → behaviour unchanged.

- **`test-paths.py`** — confirm an existing test exercises `resolve_active_hub` with `hub_relative_path != "."`; add one if not, mirroring the integration fixture shape but in-memory.

### Integration test

- **`test-hub-relative-path.py`** — single file in `plugins/mill/integration_tests/`. Build sub-project fixture, run `millpy-spawn --dry-run`, call `_paths.resolve_active_hub`, call `_review_common.resolve_ref_paths` with a fake plan-Context. Assert each path lands where the Decisions say it must. No LLM. Mirror `test-spawn.py`'s scratch-cleanup and `_run` helper.

### Test gating

The new integration test is added to `plugins/mill/integration_tests/`. It is not automatically run by `run-all.py` (that script is for unit tests). It runs via direct invocation (`PYTHONPATH=plugins/mill/scripts "$MILL_PYTHON" plugins/mill/integration_tests/test-hub-relative-path.py`). Add this to the verify section of the relevant plan batch.

### TDD candidates

- `resolve_ref_paths` `git_root` fallback: TDD candidate. Write the unit tests first, watch them fail, add the kwarg + fallback, watch them pass.
- `_config.load_config` raise removal: TDD candidate. Write the no-hub-overlay test, watch it raise, remove the raise, watch it pass.
- Callsite fixes are mechanical refactors (no behaviour change in the typical layout) — covered by the integration test, not TDD candidates individually.

## Q&A log

- **Q:** Should `_config.load_config` add a runtime guard or kw-only enforcement to reject wrong calls? **A:** No. Fix every wrong callsite; helpers stay clean. Defensive APIs encourage sloppy callers and produce bad code.
- **Q:** Is `<hub_root>/mill-config.yaml` required to exist for `_config.load_config` to succeed? **A:** No. Plugin template is the always-present base; hub overlay is optional. The current `FileNotFoundError` raise must be removed.
- **Q:** Does the hub equal `git_root`? **A:** No, not by definition. The hub is the user's cwd by convention (`resolve_hub_path()` returns `cwd.resolve()`). In typical millhouse setups `hub == git_root` coincidentally; in sub-project layouts `hub == <git_root>/<sub>`. Code must not assume the coincidence.
- **Q:** Should `_review_common.load_config` get the same callsite-audit treatment as `_config.load_config`? **A:** Yes — same fix, every wrong callsite repaired.
- **Q:** What replaces `_strict_load_config` / `_load_config` wrappers in `millpy-claim` / `millpy-spawn`? **A:** Delete them. Callers invoke `_config.load_config(resolve_hub_path(), resolve_hub_path())` directly.
- **Q:** How should `mill-go` step 4.5 derive `worktree_root` in sub-project layouts? **A:** Use `_paths.resolve_active_hub(container_path, slug, cfg=cfg, git_root=git_root)`.
- **Q:** Strategy for `resolve_ref_paths` failing on git-root-relative paths in sub-projects? **A:** Add a `git_root` kwarg; fall back to `git_root / raw` when the candidate under `project_root` does not exist and the raw is not in creates/deletes union. Symmetric with `wiki/` prefix routing.
- **Q:** Integration test scope? **A:** Structural, asset-level assertions only, no LLM. Mirror `test-spawn.py`'s shape.
- **Q:** Rename the first positional arg from `repo_root` to `hub_root`? **A:** Yes — pure doc/naming improvement, no behavioural change, no kw-only enforcement.
- **Q:** Should `mill-finalize` SKILL.md's undefined `repo_root` variable be fixed in this task? **A:** Yes — it's a parallel doc bug in the same family; small enough to fold in.
- **Q (round 1 gap):** How many `resolve_ref_paths` callsites are there, and should `resolve_existing_paths` get the same fallback? **A:** 3 `resolve_ref_paths` callsites verified (`_review_code.py:254`, `_review_plan.py:134`, `_review_plan.py:470`). `_review_discussion.py` has none. Yes — `resolve_existing_paths` gets the same `git_root` kwarg + fallback for symmetry; 6 callsites verified (`_review_code.py:274, :374`, `_review_plan.py:140, :205, :476, :544`).
