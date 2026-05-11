# Discussion: 45 (A) — Machine-level config layer

```yaml
task: 45 (A) — Machine-level config layer
slug: machine-level-config
status: discussing
parent: main
```

## Problem

mill's config currently has two layers: `wiki/config.yaml` (shared across machines, git-tracked) and `<worktree>/.millhouse/config.local.yaml` (gitignored, per-worktree, seeded from a template by mill-setup/mill-spawn). The "local" file is per-worktree, not per-machine — switching reviewer mode (e.g. `cluster-gemini` on Gaming-PC vs `sonnet` on NORCE-PC) means editing every worktree's `config.local.yaml` on that machine, and editing every newly-spawned worktree afterwards.

A true per-machine layer at `~/.millhouse/config.machine.yaml` is read once and applies to all current and future worktrees on that machine. Since `$HOME` lies outside every git repo, the file is naturally untracked without any gitignore work, and never copied between worktrees — every worktree reads the same absolute path.

## Scope

**In:**
- `_config.load_config` (lenient variant) reads `~/.millhouse/config.machine.yaml` and deep-merges it between `wiki/config.yaml` and `<worktree>/.millhouse/config.local.yaml`.
- `_review_common.load_config` (strict variant used by review/abandon/implement CLIs) does the same read + merge so reviewer overrides at machine level actually apply.
- Shared helper `_machine.machine_config_path() -> Path` and `_machine.load_layer(target_cfg) -> dict` so both `load_config` callers go through one place. Lives in new `_machine.py` (sibling to `_config.py`).
- New mill-setup Phase 4.95: read-only report on whether `~/.millhouse/config.machine.yaml` exists and parses; never creates, never prompts.
- Comment block in `templates/config.local.yaml` pointing readers at the machine layer.
- Unit tests in `unit_tests/test-config.py`: machine present + merged, machine absent (graceful skip), machine overrides wiki, worktree overrides machine.

**Out:**
- Renaming `<worktree>/.millhouse/config.local.yaml` → `config.worktree.yaml`. Symmetric and clearer, but scope creep across every script, skill, and template. Tracked as a follow-up.
- Interactive prompts in mill-setup. `--auto` mode and non-interactive flows must work; reading an existing file is enough.
- Migration tooling. Missing file = layer falls away; existing setups keep working unchanged.
- Schema validation. The file is gitignored personal preference; same lenient deep-merge as `config.local.yaml`.
- Cross-machine sync. By design — a machine-pinned file rejects sync.
- Anything that hardcodes `$HOME` for testing. Tests use `monkeypatch`/temp dir + a parameterised `home_dir` arg on the helpers (see Testing).

## Decisions

### File location and name

- **Decision:** `~/.millhouse/config.machine.yaml`. Resolved at runtime via `Path.home() / ".millhouse" / "config.machine.yaml"`.
- **Rationale:** `$HOME/.millhouse/` is outside every git repo, so the file is automatically untracked without explicit gitignore work. The `.machine.yaml` suffix pairs visually with the existing per-worktree `.local.yaml` while making the scope distinction explicit in filename.
- **Rejected:**
  - `~/.millhouse/config.yaml` — collides on bare filename with `wiki/config.yaml`; confusing when reading code or grep'ing for "which config".
  - `~/.config/millhouse/config.yaml` (XDG) — Windows is the primary target; XDG is alien there and adds path-resolution branching for no operator benefit.
  - `~/.millhouse/machine.yaml` (no `config.` prefix) — loses the symmetry with `config.local.yaml`.

### Merge order

- **Decision:** `wiki/config.yaml` → `~/.millhouse/config.machine.yaml` → `<worktree>/.millhouse/config.local.yaml` (stub) → `<hub-subpath>/.millhouse/config.local.yaml` (real, when `hub_relative_path != "."`).
- **Rationale:** Natural specificity from broadest to narrowest scope. Wiki applies to everyone, machine applies to all-worktrees-on-this-host, worktree applies to one checkout. Each layer overrides the previous on key conflicts via `deep_merge`.
- **Rejected:** "Machine wins everywhere" (machine layer applied last) — defeats the point of per-worktree overrides, which exist precisely for worktree-specific tweaks (e.g. a probe worktree experimenting with a different reviewer).

### Both `load_config` helpers updated

- **Decision:** Both `_config.load_config(wiki_path, worktree_root)` (lenient — returns `{}` on missing wiki config) and `_review_common.load_config(wiki_root, mill_dir)` (strict — raises `ReviewError` on missing wiki config) read the machine layer.
- **Rationale:** The task summary mentions only `_config.load_config`, but `_review_common.load_config` is the variant called by `millpy-review-discussion.py`, `millpy-review-plan.py`, `millpy-review-code.py`, `millpy-abandon.py`, `millpy-implement.py`, `millpy-implement-holistic.py`, `millpy-merge-in-subagent.py`, `millpy-validate-plan.py`. Skipping it would mean machine-level reviewer overrides silently don't apply to the very callers reviewer overrides are most useful for. That defeats the task.
- **Rejected:**
  - Update only `_config.load_config` — surface coverage too narrow.
  - Unify the two helpers in this task — meaningful refactor (signature divergence, strict vs lenient contract, callers in two import patterns). Out of scope; tracked as a follow-up bug if motivation surfaces.

### Shared helper module `_machine.py`

- **Decision:** New `plugins/mill/scripts/_machine.py` exposing:
  - `machine_config_path(home_dir: Path | None = None) -> Path` — returns `(home_dir or Path.home()) / ".millhouse" / "config.machine.yaml"`. `home_dir` arg exists for tests; production callers pass nothing.
  - `load_layer(home_dir: Path | None = None) -> dict` — reads + yaml-parses the file when present; returns `{}` when absent. No exceptions raised on FileNotFoundError; lets YAMLError propagate (malformed file is a user-fixable problem and silently skipping it would hide the error). Importing yaml is local to the function (lazy) — currently a top-level import in `_config.py`, so just match.
  - `MISSING`, `PRESENT`, `MALFORMED` constants and `probe(home_dir) -> (status, detail)` for mill-setup's Phase 4.95 readout. Status is one of the three constants; `detail` is the parsed dict, an error message, or `None`.
- **Rationale:** Two helpers (`_config.load_config`, `_review_common.load_config`) need identical read+merge logic. Single source of truth via `_machine.load_layer`. Keeping it in its own module avoids growing `_config.py` (already mixed responsibilities: stub-aware load + wiki-overrides setter + deep-merge) and avoids growing `_review_common.py` (already 900+ lines).
- **Rejected:** Inline the read in both load_config functions. Two copies of yaml-parse + path-resolve + missing-file branch is brittle; the third caller (Phase 4.95) would need a third copy.

### mill-setup Phase 4.95 — report-only

- **Decision:** New Phase 4.95 between 4.9 (seed `hub_relative_path` in `config.local.yaml`) and Phase 5 (seed `config.local.yaml`). Calls `_machine.probe(home_dir=Path.home())` and prints one line:
  - `MISSING`: `~/.millhouse/config.machine.yaml: not present (optional — create to set machine-wide overrides; see <template-path> for keys)`
  - `PRESENT`: `~/.millhouse/config.machine.yaml: loaded ({N} top-level keys: {key1}, {key2}, ...)`
  - `MALFORMED`: `~/.millhouse/config.machine.yaml: present but parse failed ({error}); fix or remove the file`
- **Rationale:** Surfaces the new layer in setup output so operators discover it without ceremony. Never creates the file (avoids touching `$HOME` filesystem during mill-setup, which runs scoped to the container). Never prompts (keeps mill-setup `--auto`-friendly).
- **Rejected:**
  - Interactive prompt asking the user to seed the file — breaks non-interactive flows; the file is gitignored personal taste, not setup-blocking.
  - Always create an empty stub — clutters `$HOME` for users who never want machine overrides; turns a "missing file = skip" branch into "empty file = skip" which is the same outcome with more state.
  - Skip Phase 4.95 entirely — discoverability suffers; operators don't realize the layer exists.

### `hub_relative_path` at machine level

- **Decision:** Allowed by the YAML schema (no whitelist) but semantically meaningless. `_paths.resolve_active_hub` and `_paths.resolve_active_worktree` read `hub_relative_path` from the resolved worktree's own `.millhouse/config.local.yaml`, not from the merged cfg dict, so a machine-level value is ignored.
- **Rationale:** `hub_relative_path` answers "where in this worktree is the hub" — by definition worktree-shape, not machine-shape. Filtering it out at the machine layer would require schema knowledge and add code; the existing lookup pattern already ignores it. No code change needed.
- **Rejected:** Strip `hub_relative_path` from the machine layer with a warning — gratuitous; the value silently doesn't apply anywhere it matters.

### Schema — full, not whitelisted

- **Decision:** Any key valid at the wiki or worktree layer is valid at the machine layer. No allowlist, no schema check.
- **Rationale:** Same lenient deep-merge contract as `config.local.yaml`. Schema validation is out of scope for the broader mill config (no validator exists for any of the three layers today); imposing it on the new layer alone is inconsistent.
- **Rejected:** Whitelist `roles` + `review` only — the obvious operator use case is reviewer overrides, but tomorrow's use case might be `notifications`, `spawn`, or `pipeline`. Restricting now and lifting later is just churn.

### Template comment block

- **Decision:** Add a paragraph to `plugins/mill/templates/config.local.yaml` (top of file, near the existing "partial overlay" intro) explaining the three layers and pointing at `~/.millhouse/config.machine.yaml`. Plus a one-line YAML comment in the new file's template documenting its purpose (see next decision on template).
- **Rationale:** Worktree's `config.local.yaml` is the file operators see and edit most often; a 3-line note there is the highest-leverage documentation point. Discoverable via the existing mill-setup seed step.
- **Rejected:** Document only in `_config.py` docstring or a SKILL.md note — neither surfaces during day-to-day editing.

### Machine-config template

- **Decision:** Add `plugins/mill/templates/config.machine.yaml` (commented examples + header explaining the file is per-machine and gitignored-by-virtue-of-location). mill-setup Phase 4.95 prints the template path in its `MISSING` message so operators can copy it manually if they want.
- **Rationale:** Symmetric to the existing `templates/config.local.yaml`. Discoverable. Doesn't auto-create the file.
- **Rejected:** No template — operators have to guess valid keys; defeats the discoverability point.

### Testing strategy

- **Decision:** Add four cases in `plugins/mill/unit_tests/test-config.py`:
  1. Machine config present + non-conflicting key — merged into result.
  2. Machine config absent — function returns successfully with no machine keys; no exception.
  3. Machine config overrides wiki — same key in both; machine wins.
  4. Worktree `config.local.yaml` overrides machine — same key in both; worktree wins.
- Add three cases in a new `plugins/mill/unit_tests/test-machine.py` for `_machine` directly: `machine_config_path` returns the right path; `load_layer` returns `{}` when file missing; `load_layer` returns dict when file present; `probe` returns `MALFORMED` for invalid YAML.
- Tests inject `home_dir` via the helper's optional arg pointing at a `tempfile.TemporaryDirectory()`. No real `$HOME` writes.
- Existing six `test-config.py` cases continue to pass unchanged (machine layer absent in those tempdirs).
- **Rationale:** Covers every branch of the new merge step and every status of the new helper. Existing tests prove backwards compatibility.
- **Rejected:** Minimal two cases (present + absent) — leaves the override-direction branches untested, which are the load-bearing semantics of "third layer."

### `_review_common.load_config` signature unchanged

- **Decision:** `_review_common.load_config(wiki_root, mill_dir)` keeps its two-arg signature. The machine layer is read via `_machine.load_layer()` (no args) inserted between the wiki read and the `mill_dir / config.local.yaml` read.
- **Rationale:** Eighteen callers; adding a third arg means touching every call site. The machine config path is a constant function of `Path.home()`, so passing it through call sites adds nothing testable.
- **Rejected:** Add `home_dir: Path | None = None` as a kwarg — fine but unused everywhere except tests, which can monkeypatch `Path.home` if needed. The pattern of "implicit $HOME with monkeypatch in tests" matches typical Python conventions.

### Stale-keys warning placement

- **Decision:** `_review_common.load_config`'s existing "stale 'review:' keys" warning (printed when a local `config.local.yaml` has top-level `review:`) is **not** extended to the machine layer. Only worktree-level `config.local.yaml` gets the warning.
- **Rationale:** That warning exists for migration: the schema moved from `review:` to `roles:` and worktree configs that haven't migrated print noise. The machine layer is new; no migration to nag about.
- **Rejected:** Run the same warning on the machine layer for symmetry — pointless noise on a fresh file.

## Technical context

### Files that change

- `plugins/mill/scripts/_machine.py` — new module. Public API: `machine_config_path(home_dir)`, `load_layer(home_dir)`, `probe(home_dir)`, plus `MISSING`/`PRESENT`/`MALFORMED` string constants. ~50 lines.
- `plugins/mill/scripts/_config.py` — `load_config` reads machine layer between wiki and stub layers. Update docstring (`Exports` section + `load_config` Args/Returns) to mention the new layer and merge order.
- `plugins/mill/scripts/_review_common.py` — `load_config` reads machine layer between wiki and local-override layers. Update docstring.
- `plugins/mill/templates/config.local.yaml` — add a 3-line header comment block describing the three layers and pointing at `~/.millhouse/config.machine.yaml`.
- `plugins/mill/templates/config.machine.yaml` — new file. Commented-out examples mirroring `config.local.yaml`'s format. Header explains the file is per-machine and lives in `$HOME/.millhouse/`.
- `plugins/mill/skills/mill-setup/SKILL.md` — new Phase 4.95 between 4.9 and 5. Phase 8 verify list gets one new line (machine-config probe ran; not "file must exist").
- `plugins/mill/unit_tests/test-config.py` — four new test functions for the machine merge cases. Register in `tests = [...]` list in `main()`.
- `plugins/mill/unit_tests/test-machine.py` — new file with three tests for `_machine` helpers.

### Files that don't change

- 18 callers of `load_config` — signatures unchanged.
- `_paths.py` — machine path doesn't go through `_paths.resolve_*`; it's a pure `Path.home()` function with no dependency on git context. Lives in `_machine.py` for symmetry with the load function.
- `mill-spawn`, `mill-claim`, `mill-color`, `mill-terminal`, `mill-vscode`, `mill-cleanup`, `mill-status`, `mill-inspect` — all call `_config.load_config` and pick up the new layer transparently.
- The review CLIs and abandon/implement/merge-in-subagent — all call `_review_common.load_config` and pick up the new layer transparently.
- `wiki/config.yaml` schema — unchanged.

### Existing `_config.load_config` flow (current)

Source: `plugins/mill/scripts/_config.py:28-68`.

```
cfg = {}
if wiki/config.yaml exists: cfg = wiki_cfg
stub_path = worktree_root / .millhouse / config.local.yaml
hub_subpath = "."
if stub_path exists:
    stub_data = yaml.load(stub_path)
    cfg = deep_merge(cfg, stub_data)
    hub_subpath = stub_data.get("hub_relative_path", ".")
if hub_subpath != ".":
    real_path = worktree_root / hub_subpath / .millhouse / config.local.yaml
    if real_path exists: cfg = deep_merge(cfg, yaml.load(real_path))
return cfg
```

### Updated flow

```
cfg = {}
if wiki/config.yaml exists: cfg = wiki_cfg
cfg = deep_merge(cfg, _machine.load_layer())  # NEW
stub_path = worktree_root / .millhouse / config.local.yaml
hub_subpath = "."
if stub_path exists: ... (unchanged)
if hub_subpath != ".": ... (unchanged)
return cfg
```

`_machine.load_layer()` returns `{}` on missing file, so the `deep_merge` call is always safe.

### Existing `_review_common.load_config` flow

Source: `plugins/mill/scripts/_review_common.py:942-972`.

```
shared_path = wiki_root / config.yaml  (REQUIRED — raises ReviewError on missing)
cfg = yaml.load(shared_path)
local_path = mill_dir / config.local.yaml
if local_path exists:
    local_cfg = yaml.load(local_path)
    # stale-keys warning
    cfg = _deep_merge(cfg, local_cfg)
return cfg
```

### Updated flow

```
shared_path = wiki_root / config.yaml  (REQUIRED — unchanged)
cfg = yaml.load(shared_path)
cfg = _deep_merge(cfg, _machine.load_layer())  # NEW
local_path = mill_dir / config.local.yaml
if local_path exists: ... (unchanged, including stale-keys warning)
return cfg
```

### Import direction

`_machine` imports nothing from `_config` or `_review_common`. `_config` imports `_machine.load_layer`. `_review_common` imports `_machine.load_layer`. No cycles.

### YAML behaviour for empty / whitespace-only file

`yaml.safe_load("") → None`. Existing pattern in both `load_config` functions is `yaml.safe_load(...) or {}`. `_machine.load_layer` follows the same pattern.

### Windows path semantics

`Path.home()` on Windows returns `C:\Users\<username>` (verified — this session is on Windows 11). The trailing `.millhouse` subdir is created lazily by the operator (mill-setup does NOT create it). `Path.exists()` returns False cleanly when the dir is missing; no special-casing needed.

## Constraints

- **CLAUDE.md `## Path invariants`**: "All path resolution goes through `_paths.py`." Strictly speaking, `_machine.machine_config_path()` is path resolution but it doesn't depend on git context, wiki context, or worktree context — it's a pure `Path.home()` derivation. Placing it in `_machine.py` (alongside the loader that uses it) is consistent with the existing convention where `_config.set_local_wiki_overrides` accepts a `cfg_path` argument and doesn't itself resolve any path. `_paths.py` collects (git context, config) → path translations; this helper is none of those.
- **CLAUDE.md `## Conventions worth carrying`**: "Plugin scripts reference `${CLAUDE_PLUGIN_ROOT}`, never the source repo." Not relevant here — the new code reads `$HOME` (user data) and `_paths.resolve_wiki_path` results, neither of which involve plugin paths.
- **Generated markdown uses fenced ```yaml for metadata, not `---` frontmatter** — applies to `templates/config.machine.yaml`'s top doc-comment header. Use a leading `#`-comment block (existing pattern in `templates/config.local.yaml`).
- **No emojis in files unless explicitly requested.** Documentation strings and template comments stay plain.
- **Wiki edits go through `_wiki.write_commit_push`** — n/a here (we don't write to the wiki; only to plugin source files and `task/` state).
- **Task-state writes (`status.md`, `discussion.md`) committed on the task branch** — applies during mill-start (writing this file).

## Testing

### Unit tests

#### `plugins/mill/unit_tests/test-config.py` — 4 new cases

Pattern: each test uses `tempfile.TemporaryDirectory()` for both `wiki/`, `wt_root`, and a fake `home_dir`. The fake home is passed via `monkeypatch.setattr(_machine, "_default_home", Path(tmp) / "fake_home")` OR via patching `Path.home`. **Decision for plan-time:** monkeypatch `Path.home` returning a tempdir; cleaner than threading a `home_dir` arg through `load_config` signatures.

Cases:
1. `test_load_config_machine_layer_present_merged` — wiki has `spawn.branch_prefix: feat`, machine has `roles.discussion-review.holistic.reviewer: cluster-gemini`. Result has both keys.
2. `test_load_config_machine_absent_graceful` — wiki present, no machine file, no worktree file. Result equals wiki cfg. No exception.
3. `test_load_config_machine_overrides_wiki` — wiki has `roles.discussion-review.holistic.reviewer: sonnet`, machine has `roles.discussion-review.holistic.reviewer: cluster-gemini`. Result has `cluster-gemini`.
4. `test_load_config_worktree_overrides_machine` — wiki + machine + worktree all set `roles.discussion-review.holistic.reviewer` to three different values (`sonnet`, `cluster-gemini`, `experimental`). Result has `experimental` (worktree wins).

Register all four in the `tests = [...]` list in `main()` in `test-config.py`.

#### `plugins/mill/unit_tests/test-machine.py` — new file, 4 cases

1. `test_machine_config_path_uses_home` — `machine_config_path(home_dir=Path("/fake"))` returns `Path("/fake/.millhouse/config.machine.yaml")`. Default `home_dir=None` returns a path under `Path.home()`.
2. `test_load_layer_missing_file_returns_empty` — `load_layer(home_dir=tmp)` when no file exists → `{}`.
3. `test_load_layer_present_returns_dict` — write valid YAML, `load_layer` returns the parsed dict.
4. `test_probe_three_states` — exercises `MISSING`, `PRESENT`, `MALFORMED` via three sub-cases. Malformed = write `: : :` or similar that breaks `safe_load`.

Run via `python plugins/mill/unit_tests/run-all.py`. Confirm green before mill-merge.

### Manual smoke test (operator runs after merge)

1. On the dev machine, write `~/.millhouse/config.machine.yaml` with `roles:\n  discussion-review:\n    holistic:\n      reviewer: null`.
2. Spawn a new test task with `/mill:mill-spawn` (or use an existing worktree).
3. Run `python -c "from _paths import resolve_git_root, resolve_wiki_path; from _config import load_config; print(load_config(resolve_wiki_path(resolve_git_root()), resolve_git_root())['roles']['discussion-review']['holistic']['reviewer'])"` — expect `None`.
4. Delete `~/.millhouse/config.machine.yaml`. Re-run the load — expect the wiki default reviewer back.

### TDD candidates

- `_machine.load_layer` — pure function over filesystem; test-first.
- `_machine.probe` — three-state status helper; test-first.
- The mill-setup Phase 4.95 line itself is a print statement in a skill, not Python — covered by inspection of mill-setup's run output, not a unit test.

## Q&A log

- **Q:** Where should the new file live? **A:** `~/.millhouse/config.machine.yaml`. **Why:** `$HOME/.millhouse/` is outside every repo so the file is automatically untracked; `.machine.yaml` pairs visually with the existing per-worktree `.local.yaml`; `config.machine.yaml` avoids the bare-name `config.yaml` collision with `wiki/config.yaml`.
- **Q:** Is `config.local.yaml` not already a "machine-local config"? **A:** It's gitignored (so not synced via git), but it's **per-worktree**, not per-machine — five worktrees on Gaming-PC means five `config.local.yaml` files, each requiring its own edit to change reviewer mode. The new `config.machine.yaml` is one file per machine, read by all worktrees.
- **Q:** Should `config.local.yaml` be renamed to `config.worktree.yaml` for symmetry? **A:** No, deferred to a follow-up task. **Why:** rename touches every script, skill, template, and docstring; out of scope for the merge-layer change.
- **Q:** Should `_review_common.load_config` be updated too, or only `_config.load_config`? **A:** Both updated via a shared `_machine.load_layer` helper. **Why:** review CLIs, abandon, implement, merge-in-subagent all go through `_review_common.load_config`; not updating it would mean machine-level reviewer overrides silently don't apply to the very callers reviewer overrides exist for.
- **Q:** Should mill-setup auto-create `~/.millhouse/config.machine.yaml` or prompt for it? **A:** Neither — new Phase 4.95 is read-only: probe the file, print one-line status (MISSING / PRESENT / MALFORMED), never create, never prompt. **Why:** keeps mill-setup `--auto`-friendly; missing file = layer falls away per the task's explicit wording; clutter-free for operators who never use machine overrides.
- **Q:** Should the machine layer support `hub_relative_path`? **A:** Schema allows it (no whitelist) but it's silently ignored. **Why:** `hub_relative_path` is read from the resolved worktree's own `.millhouse/config.local.yaml` by `_paths.resolve_active_hub`, not from the merged cfg dict — so a machine-level value never reaches a code path that uses it. No filter needed.
- **Q:** Should the schema be a whitelist (only `roles` + `review`)? **A:** No — full schema, same lenient deep-merge as `config.local.yaml`. **Why:** today reviewer is the obvious use, tomorrow it may be `notifications`, `spawn`, `pipeline`; restrict-and-lift is just churn.
- **Q:** Where does the new helper live? **A:** New file `plugins/mill/scripts/_machine.py` with `machine_config_path`, `load_layer`, `probe`. **Why:** two callers (`_config`, `_review_common`) plus mill-setup's Phase 4.95 need the same logic; single source of truth; `_config.py` and `_review_common.py` are already busy.
- **Q:** Where in mill-setup does Phase 4.95 sit? **A:** Between Phase 4.9 (seed `hub_relative_path`) and Phase 5 (seed `config.local.yaml`). **Why:** logically after all worktree-local config writes are done; before Phase 6 (`Home.md` init) which is wiki territory. Phase number 4.95 keeps the existing fractional convention.
- **Q:** How many test cases? **A:** Four merge-direction cases in `test-config.py` + four `_machine`-helper cases in a new `test-machine.py`. **Why:** every branch of the new merge step (present, absent, machine-wins-wiki, worktree-wins-machine) needs explicit coverage; helper tests cover the three probe states + the basic path/load contract.
