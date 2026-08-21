# Batch: config-caller-alignment

```yaml
task: 'mill-merge/merge-in: nested-layout config resolution, stale locks, and rollback-target bugs'
batch: config-caller-alignment
number: 4
cards: 4
verify: PYTHONPATH= uv run --project plugins/mill python plugins/mill/unit_tests/test-config.py
depends-on: []
```

## Batch Scope

Fixes `#900`: `_review_common.load_config` (used by `millpy-review-plan.py` and ~11 other call sites) always derives its merge-order `worktree_root` from `mill_dir.parent` (hub-anchored), so a nested-hub layout's git-root `config.local.yaml` stub is invisible to `millpy-review-plan.py`, while `mill-plan`/`mill-merge`'s own direct `_config.load_config` calls already pass `git_root` there and honor it — a silent divergence. The fix is additive and narrow (confirmed via source read during discussion that `_review_common.load_config`'s `mill_dir` parameter is also used independently for a stale-`review:`-key stderr peek, so its meaning cannot simply be reassigned): add an opt-in `git_root` keyword parameter to `_review_common.load_config`, pass it only from `millpy-review-plan.py`'s call site, and add a `_config.load_config`-level stderr warning — gated to nested layouts only (`worktree_root != hub_root`) — when a stub file carries unexpected keys. `~11` other `_review_common.load_config` call sites, and `_review_common.resolve_path`'s own internal `load_config` call, are unchanged (see Shared Decisions in `00-overview.md` and the rationale in `_mill/discussion.md`'s `config-local-yaml-caller-alignment` Decision for why `resolve_path`'s hub-anchored load is safe to leave as-is). Every fenced block below reproduces the source file's own byte-exact indentation (flush left, no extra indent from this card's own list nesting) — copy fence contents literally.

## Cards

### Card 7: `_config.load_config` — add gated stub-misuse warning

- **Context:** none
- **Edits:**
  - `plugins/mill/scripts/_config.py`
- **Creates:** none
- **Deletes:** none
- **Moves:** none
- **Requirements:** In `load_config`, find this exact text (the "4. Apply stub-aware local config logic" block):

```
    # 4. Apply stub-aware local config logic (preserved from existing code)
    stub_path = worktree_root / ".millhouse" / "config.local.yaml"
    hub_subpath = "."
    if stub_path.exists():
        stub_data = yaml.safe_load(stub_path.read_text(encoding="utf-8")) or {}
        cfg = deep_merge(cfg, stub_data)
        source_label = "config.local.yaml"
        hub_subpath = stub_data.get("hub_relative_path", ".")

    if hub_subpath != ".":
```

  Replace it with:

```
    # 4. Apply stub-aware local config logic (preserved from existing code)
    stub_path = worktree_root / ".millhouse" / "config.local.yaml"
    hub_subpath = "."
    if stub_path.exists():
        stub_data = yaml.safe_load(stub_path.read_text(encoding="utf-8")) or {}
        cfg = deep_merge(cfg, stub_data)
        source_label = "config.local.yaml"
        hub_subpath = stub_data.get("hub_relative_path", ".")

        if worktree_root != hub_root and "hub_relative_path" in stub_data:
            unexpected_keys = sorted(k for k in stub_data.keys() if k != "hub_relative_path")
            if unexpected_keys:
                print(
                    f"[config] warning: {stub_path} sets hub_relative_path but also carries "
                    f"unexpected top-level key(s) {unexpected_keys} -- in a nested-hub layout this "
                    f"file is meant to be a pointer stub; real overrides belong in the hub's own "
                    f".millhouse/config.local.yaml",
                    file=sys.stderr,
                )

    if hub_subpath != ".":
```

  `worktree_root` and `hub_root` are both already in scope as this function's own parameters at this point in the function body — no new imports needed (`sys` is already imported at module top). The gate is two conditions, both required: `worktree_root != hub_root` (the nested-hub case) AND `"hub_relative_path" in stub_data` (the stub genuinely declares itself a pointer to a hub elsewhere). Only when BOTH hold does an extra top-level key count as misuse — a stub that never declares `hub_relative_path` at all is not claiming to be a pointer, so it carries no such contradiction, and a stub carrying real overrides with no `hub_relative_path` key is exactly the pattern Card 9 (below) legitimizes for `_review_common.load_config`'s new `git_root` parameter — do NOT warn on that pattern; warn ONLY on a stub that sets `hub_relative_path` and ALSO carries other keys (mixing "pointer" and "real override" roles in one file, the actual misuse pattern `#900` observed). This gate never fires in the common flat/in-place layout where `worktree_root == hub_root` (confirmed via `plugins/mill/unit_tests/test-config.py`'s existing `test_load_config_local_override_wins`, which writes a `spawn:` block directly to that path with `hub_root == worktree_root`), and never fires on a pure git-root override-only stub (no `hub_relative_path` key) even in a nested layout.
- **Commit:** `feat(_config): warn on nested-hub config.local.yaml stub carrying unexpected keys (#900)`

### Card 8: `_review_common.load_config` — add opt-in `git_root` parameter

- **Context:** none
- **Edits:**
  - `plugins/mill/scripts/_review_common.py`
- **Creates:** none
- **Deletes:** none
- **Moves:** none
- **Requirements:** Three edits to the `load_config` function (starting at its `def` line, currently `def load_config(hub_root: Path, mill_dir: Path) -> dict:`).

  **Edit A — signature.** Find:

```
def load_config(hub_root: Path, mill_dir: Path) -> dict:
```

  Replace with:

```
def load_config(hub_root: Path, mill_dir: Path, *, git_root: Path | None = None) -> dict:
```

  **Edit B — docstring `Args:` section.** Find this exact text:

```
    Args:
        hub_root: Absolute path to the hub directory.
        mill_dir: Absolute path to the .millhouse directory.
```

  Replace it with:

```
    Args:
        hub_root: Absolute path to the hub directory.
        mill_dir: Absolute path to the .millhouse directory. Always used for the stale-
            ``review:``-key peek (``mill_dir / config.local.yaml``), regardless of ``git_root``.
        git_root: Optional. When provided, used instead of ``mill_dir.parent`` as the delegate's
            ``worktree_root`` argument (governing the merge-order stub/real config layers) --
            ``mill_dir.parent`` is always a hub-anchored path, while callers with a nested-hub
            layout (``hub_root != git_root``) may need the git-repository-root stub layer
            instead. When omitted (the default), behavior is unchanged from before this
            parameter existed.
```

  **Edit C — `worktree_root` derivation.** Find this exact line (immediately after the docstring's closing `"""`):

```
    worktree_root = mill_dir.parent
```

  Replace it with:

```
    worktree_root = git_root if git_root is not None else mill_dir.parent
```

  This single change is sufficient: `worktree_root` is used twice later in the function body (`resolve_repo_config_path(hub_root, worktree_root)` and `_core_load_config(hub_root, worktree_root)`) and both uses correctly pick up `git_root` when provided, without further edits. Do not change the separate, independent `local_path = mill_dir / "config.local.yaml"` line used for the stale-`review:`-key peek later in the function — that stays anchored to `mill_dir` regardless of `git_root`, per the docstring update above.
- **Commit:** `feat(_review_common): add opt-in git_root parameter to load_config, decoupled from mill_dir's other use (#900)`

### Card 9: `millpy-review-plan.py` — pass `git_root` at the one reported call site

- **Context:** none
- **Edits:**
  - `plugins/mill/scripts/millpy-review-plan.py`
- **Creates:** none
- **Deletes:** none
- **Moves:** none
- **Requirements:** Find this exact text:

```
        project_root = _paths.resolve_hub_path()
        git_root = _paths.resolve_git_root()
        mill_dir = project_root / ".millhouse"
        wiki_root = resolve_wiki_path(project_root)
        cfg = load_config(project_root, mill_dir)
```

  Replace it with:

```
        project_root = _paths.resolve_hub_path()
        git_root = _paths.resolve_git_root()
        mill_dir = project_root / ".millhouse"
        wiki_root = resolve_wiki_path(project_root)
        cfg = load_config(project_root, mill_dir, git_root=git_root)
```

  `git_root` is already bound in this exact block (the line immediately above) — no new resolution needed. This is the only call site this batch changes; do not touch any other `_review_common.load_config(...)` call site in this file or any other file (see `00-overview.md`'s Shared Decisions and `_mill/discussion.md`'s `config-local-yaml-caller-alignment` Decision for the full list of unchanged call sites and why).
- **Commit:** `fix(millpy-review-plan): pass git_root to load_config so nested-hub config.local.yaml overrides are honored (#900)`

### Card 10: unit tests for the gated warning and the new `git_root` parameter

- **Context:**
  - `plugins/mill/unit_tests/test-config.py`
- **Edits:**
  - `plugins/mill/unit_tests/test-config.py`
- **Creates:** none
- **Deletes:** none
- **Moves:** none
- **Requirements:** This file already imports `_config`, `_paths`, and `_review_common`, and already defines `_git_init`, `_write_yaml`, `_setup_plugin_template` helpers, and precedent tests `test_load_config_sub_project_hub_overlay` (nested layout fixture shape) and `test_load_config_local_override_wins` (flat-layout stub carrying a `spawn:` block) — read both in full before writing, and follow their exact fixture/patching style (`tempfile.TemporaryDirectory()`, `patch.object(_paths, "resolve_wiki_path", side_effect=SystemExit)`, `patch.object(_config, "resolve_plugin_template_path", return_value=...)`, `patch("sys.stderr", new=io.StringIO())` for stderr capture — `io` is already imported at module top). Also read `test_review_common_load_config_container_layout` for the exact `_review_common.load_config(hub_root=..., mill_dir=...)` keyword-argument call shape already in use.

  Add four new test functions, each ending with a `print("PASS ...")` line matching this file's existing style, and register all four in `main()`'s `tests = [...]` list (append after the existing `test_load_config_done_gate_key_present` entry):

  1. `test_load_config_stub_misuse_warning_nested_layout` — nested layout (`hub_root = tmp_path / "projects" / "sub"`, `worktree_root = tmp_path`, i.e. `hub_root != worktree_root`, mirroring `test_load_config_sub_project_hub_overlay`'s directory shape). Write a stub at `worktree_root / ".millhouse" / "config.local.yaml"` containing both `hub_relative_path: projects/sub` and an unrelated top-level key (e.g. `spawn:\n  branch_prefix: leaked\n`). Call `_config.load_config(hub_root, worktree_root)` with `sys.stderr` captured via `io.StringIO()`. Assert the captured stderr contains `str(stub_path)` and the literal substring `unexpected top-level key(s)` and `spawn` (the leaked key name).

  2. `test_load_config_stub_misuse_no_warning_flat_layout` — flat layout (`hub_root == worktree_root`, both `tmp_path / "hub"`, mirroring `test_load_config_local_override_wins`'s shape). Write a stub at that same path's `.millhouse/config.local.yaml` containing a multi-key block with no `hub_relative_path` key at all (e.g. just `spawn:\n  branch_prefix: local\n`, matching `test_load_config_local_override_wins`'s existing fixture content). Call `_config.load_config(hub_root, hub_root)` with stderr captured. Assert the captured stderr does NOT contain the literal substring `unexpected top-level key(s)` — the flat-layout case must never emit this warning, since layer 3 and layer 4 are the same legitimate real-config file there.

  3. `test_review_common_load_config_git_root_param` — nested layout: `hub_root = tmp_path / "hub"` (real config lives here), `git_root = tmp_path` (git-root stub lives here). Write `git_root / ".millhouse" / "config.local.yaml"` with `roles:\n  plan-review:\n    holistic:\n      reviewer: fablehigh\n` (an override value not present in the template, and deliberately no `hub_relative_path` key — this stub is a pure git-root override, the pattern Card 7's gate must NOT warn on). Call `_review_common.load_config(hub_root=hub_root, mill_dir=hub_root / ".millhouse", git_root=git_root)` with `sys.stderr` captured via `io.StringIO()` (use `_setup_plugin_template`/`patch.object` exactly as `test_review_common_load_config_container_layout` does). Assert the returned `cfg["roles"]["plan-review"]["holistic"]["reviewer"] == "fablehigh"` (the git-root stub's override was honored) AND assert the captured stderr does NOT contain the literal substring `unexpected top-level key(s)` (this is the exact scenario Card 7's `"hub_relative_path" in stub_data` gate condition exists to exempt — a plan-review round caught this as a real contradiction before this second assertion was added, so it must not regress). Then call the same function again WITHOUT `git_root` (`_review_common.load_config(hub_root=hub_root, mill_dir=hub_root / ".millhouse")`) and assert the returned value is NOT `"fablehigh"` (the git-root stub is invisible without the new parameter — this is the pre-existing, still-correct default behavior for every other unchanged call site) — this second assertion is the regression guard confirming the parameter is genuinely opt-in.

  4. `test_load_config_stub_misuse_no_warning_git_root_override_only` — nested layout, same directory shape as Test 1 (`hub_root = tmp_path / "projects" / "sub"`, `worktree_root = tmp_path`). Write a stub at `worktree_root / ".millhouse" / "config.local.yaml"` containing ONLY a real-override key and no `hub_relative_path` at all (e.g. `git:\n  base_branch: develop\n`). Call `_config.load_config(hub_root, worktree_root)` directly (not via `_review_common`) with stderr captured. Assert the captured stderr does NOT contain the literal substring `unexpected top-level key(s)` — confirms Card 7's gate distinguishes "stub declares `hub_relative_path` and also carries extra keys" (Test 1, warns) from "stub carries override keys but never claims to be a pointer" (this test, silent) at the `_config.load_config` level directly, independent of `_review_common`'s own wrapper behavior covered by Test 3.
- **Commit:** `test(_config, _review_common): cover gated stub-misuse warning and opt-in git_root parameter (#900)`

## Batch Tests

`verify: PYTHONPATH= uv run --project plugins/mill python plugins/mill/unit_tests/test-config.py` — covers Card 7's `_config.py` change directly and Card 8's `_review_common.load_config` change (this file already imports and exercises `_review_common.load_config`, and Card 10 adds direct coverage for the new `git_root` parameter). Card 9's `millpy-review-plan.py` one-line call-site change has no dedicated unit test of its own — `millpy-review-plan.py` is a CLI entrypoint exercised by `plugins/mill/integration_tests`, not `unit_tests`, and the change is a mechanical pass-through of an already-bound `git_root` variable into a parameter Card 10 already covers at the `_review_common.load_config` level; a dedicated CLI-level test would need to invoke the full `millpy-review-plan.py --stage prepare` flow (LLM dispatch, plan-dir fixtures) for a one-line change, which is disproportionate. Scoped to the one file this batch's testable surface lives in, per the "Verify command scope" convention.
