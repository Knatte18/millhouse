# Discussion: 57 (A) — Move config.yaml and agents.yaml from wiki to hub worktree

```yaml
task: 57 (A) — Move config.yaml and agents.yaml from wiki to hub worktree
slug: config-move-to-hub
status: discussing
parent: main
```

## Problem

The wiki repo (`<container>/wiki/`) is a separate git remote that mill scripts
pull and push on virtually every operation. Today it owns two files that are
*configuration*, not *task state*: `wiki/config.yaml` (shared hub settings) and
`wiki/agents.yaml` (the model/reviewer catalogue). This conflates two
lifecycles:

- Task state changes constantly (Home.md is rewritten by every spawn, claim,
  fold, merge, abandon, groom). Concurrent machines pull-rebase-push the wiki
  many times per hour; merge conflicts are routine and handled by the wiki
  lock.
- Config schema and the agent catalogue change rarely, but they ALSO need to
  be predictable across worktrees on the same machine and the same commit.
  Today, machine A can land a config change into the wiki while machine B is
  mid-task; machine B's next pull silently swaps the rules out from under
  an in-flight `mill-go` run.

In addition, `config.yaml`'s schema has been edited several times since the
v2 rewrite started, and existing config files break silently on plugin
upgrade — there is no validation of unknown keys. The example operators have
hit: `pipeline.implementer` was renamed to `roles.implementer`, and old
configs continue to load `cfg["pipeline"]["implementer"]` as `None` with no
warning.

The fix is to move both files out of the wiki repo. The shared, repo-wide
config becomes a tracked file at the hub-repo root (`mill-config.yaml`),
committed to main like any other source file. The agent catalogue becomes
plugin-owned — the plugin's template is the source of truth; per-machine
overrides go in `.millhouse/agents.local.yaml`. Both load paths gain a
declarative overlay model and unknown-key validation against the plugin
template.

**Why now:** parallel-machine task runs (`/mill-go` on two laptops, or one
laptop running `/mill-autofix` in the background while the operator hand-runs
another) are now the norm, not the exception. Each new concurrent runner
multiplies the wiki-write surface, and the wiki lock cannot protect against
two machines committing legitimate but conflicting config edits on top of
each other. Plugin upgrades have also started moving faster, surfacing the
silent-schema-rot problem.

## Scope

**In:**

- New tracked file `mill-config.yaml` at the hub repo root, committed to the
  main branch.
- Three-layer overlay in `_config.load_config` and `_review_common.load_config`:
  plugin template -> `mill-config.yaml` -> `.millhouse/config.local.yaml`.
  The current per-user machine layer (`~/.millhouse/config.machine.yaml`)
  is **removed** as part of this task (see Decision: Overlay precedence
  below). The `_machine.load_layer()` call sites are deleted; the
  `plugins/mill/templates/config.machine.yaml` template is deleted; the
  `_machine.py` helper is deleted if it has no remaining callers.
- Final env-var override pass applied on top of the three-layer overlay,
  scoped to a small named registry of reviewer/implementer selection
  keys (see Decision: Env-var overrides). Only the keys in the registry
  are env-overridable; arbitrary config keys are not. The env layer is
  applied inside both `_config.load_config` and
  `_review_common.load_config` after the deep merge completes.
- Two-layer overlay in `_reviewers.load`: plugin template
  (`${CLAUDE_PLUGIN_ROOT}/templates/mill-agents.yaml`) ->
  `.millhouse/agents.local.yaml`. New signature
  `_reviewers.load(hub_dir: Path) -> dict[str, dict]` -- replaces
  `_reviewers.load(wiki_root: Path)`. The 9 existing callers
  (`millpy-implement.py`, `millpy-implement-holistic.py`,
  `millpy-review-discussion.py`, `millpy-review-plan.py`,
  `millpy-review-code.py`, `_review_discussion.py`, `_review_code.py`,
  `_review_plan.py`, `millpy-merge-in-subagent.py`) are updated to pass
  `hub_dir` instead of `wiki_root` -- parallel to the `load_config`
  callsite migration. The implementer should re-grep
  `_reviewers.load(` at the start of the migration batch to get the
  authoritative call list.
- Unknown-key validation against the plugin template; warns on stderr, does
  not fail.
- New helper `_paths.resolve_mill_config_path(repo_root) -> Path`.
- New module `_autonomous.py` with `is_autonomous(hub_dir)`,
  `set_autonomous(hub_dir)`, `clear_autonomous(hub_dir)` — backed by the
  presence of `.millhouse/autonomous.flag`.
- Removal of the `pipeline.autonomous_mode` key from the config schema
  (plugin template + wiki template + `.millhouse/config.local.yaml` template
  block).
- New mill-setup migration phase (call it Phase 3.2b) that, on every re-run:
    1. If `wiki/config.yaml` exists AND `mill-config.yaml` does not exist at
       the hub root → copy contents to `mill-config.yaml` and `git add` it
       (no commit; operator commits manually).
    2. If `wiki/config.yaml` exists AND `mill-config.yaml` already exists →
       skip the copy (operator already committed) but still delete the wiki
       file and push wiki.
    3. If `wiki/agents.yaml` exists → diff against
       `${CLAUDE_PLUGIN_ROOT}/templates/mill-agents.yaml`. Identical → delete
       wiki file and push. Different → stderr warning telling the operator
       what unique entries exist and to copy them into
       `.millhouse/agents.local.yaml` before re-running; do NOT delete.
- Rename `plugins/mill/templates/wiki-config.yaml` → `mill-config.yaml`.
- New `plugins/mill/templates/mill-agents.yaml` (the current full
  `wiki/agents.yaml` contents, owned by plugin).
- Rename `plugins/mill/templates/reviewers.yaml` → folded into
  `mill-agents.yaml` (the existing 19-line example file is redundant once
  the canonical catalogue is plugin-owned).
- All 17 callsites that pass `wiki_path` into `load_config` updated to pass
  `repo_root` (or whatever the new signature needs).
- Fallback in both `load_config` implementations: if `mill-config.yaml` is
  absent at `repo_root` but `wiki/config.yaml` is present, read the wiki
  file and emit a one-line stderr warning. This is for in-flight task
  branches that predate the migration.
- New unit tests in `plugins/mill/unit_tests/test-config.py` and
  `test-paths.py`; new integration test in
  `plugins/mill/integration_tests/test-migration.py` that runs a fixture
  hub through the migration phase.
- Update of CLAUDE.md `## Constraints` and `## Path invariants` sections to
  reflect that config is no longer in the wiki.

**Out:**

- No unification of the two `load_config` implementations (lenient `_config`
  vs. strict `_review_common`). Existing split is preserved — both get the
  new overlay logic, neither gets merged with the other.
- No JSON-Schema file. Validation derives from the plugin template's keyset.
- No deep type-validation of leaf values. Validation is structural
  (key paths only).
- No automatic mill-setup commit on the main branch. Operator commits the
  generated `mill-config.yaml` themselves.
- No deletion of the in-process `wiki/agents.yaml` if it differs from the
  template — operator decides.
- No new behaviour around `autonomous_mode` from the consuming side.
  The `.flag` file API is added and the schema key is removed from
  templates in this task, but the existing SKILL.md callers
  (mill-autofix writes the key; mill-go and mill-plan read it) keep
  working through the intermediate state because mill-autofix
  continues to write the key into `.millhouse/config.local.yaml` and
  unknown-key validation is warn-only. The follow-up task (see
  Technical Context) migrates the three skills to the flag-file API.
  This task does NOT touch the three SKILL.md files; their migration
  is explicitly out of scope here.
- No changes to `.scratch/` semantics, junction layout, or wiki-lock logic.
- No changes to how `Home.md` is written or where it lives.
- No removal of the `_reviewers.load` agents.yaml → reviewers.yaml fallback
  in load-layer code; the fallback stays for one release cycle so existing
  hubs that haven't run mill-setup still work.

## Decisions

### File location: `mill-config.yaml` at repo root

- **Decision:** Tracked repo-root file named `mill-config.yaml`, sitting
  alongside `.gitignore`, `CLAUDE.md`, `pyproject.toml`.
- **Rationale:** Matches existing repo-rooted config files; no carve-out in
  `.gitignore` required. The `mill-` prefix scopes the name to this tool
  without nesting it in a folder.
- **Rejected:** `.millhouse/config.yaml` (would require a `.gitignore`
  carve-out for a single tracked file inside an otherwise-gitignored dir —
  fragile and confusing); `config/mill.yaml` (extra folder for one file).

### No tracked repo file for agents

- **Decision:** The agent catalogue is plugin property. Source of truth lives
  at `${CLAUDE_PLUGIN_ROOT}/templates/mill-agents.yaml`. Per-machine
  overrides land in `.millhouse/agents.local.yaml`.
- **Rationale:** Adding a model name to the catalogue is a plugin-level
  change, not a per-repo change. Tracking it in each repo means N copies of
  the same list and no upgrade story.
- **Rejected:** Tracked `mill-agents.yaml` in repo root (would force every
  repo to ship the catalogue and break the "plugin upgrade adds new agents
  automatically" property); plugin-only with no local overlay (per-machine
  model swap is a real operator need).

### `.millhouse/autonomous.flag` for ephemeral autonomous-mode state

- **Decision:** Presence of `.millhouse/autonomous.flag` (a zero-byte file)
  means autonomous mode is on. `pipeline.autonomous_mode` is removed from
  the config schema entirely.
- **Rationale:** Autonomous mode is session-state, not config. Putting it in
  config caused (in the v1 codebase) a class of bugs where mill-autofix
  crashed mid-run and left autonomous_mode=true in the committed config,
  silently changing the behaviour of the operator's next manual run. A flag
  file in `.millhouse/` (gitignored, per-worktree) is impossible to commit
  by accident and self-cleans on `mill-cleanup` of the worktree.
- **Rejected:** State YAML file (overkill for a single boolean); env var
  (doesn't survive between subprocess invocations).

### Env-var overrides for reviewer/implementer selection

- **Decision:** Support a small, named registry of environment variables
  that override specific reviewer/implementer-selection keys. The env
  layer is the highest-precedence layer in the config overlay (applied
  after plugin/repo/local merge). The registry is hard-coded in a new
  helper `_config.apply_env_overrides(cfg) -> cfg`:
    - `MILL_DISCUSSION_REVIEWER` -> `roles.discussion-review.holistic.reviewer`
    - `MILL_PLAN_REVIEWER`       -> `roles.plan-review.holistic.reviewer`
    - `MILL_PLAN_BATCH_REVIEWER` -> `roles.plan-review.batch.reviewer`
    - `MILL_CODE_REVIEWER`       -> `roles.code-review.holistic.reviewer`
    - `MILL_CODE_BATCH_REVIEWER` -> `roles.code-review.batch.reviewer`
    - `MILL_IMPLEMENTER`         -> `roles.implementer.model`
  Empty-string or unset env var = no override. Any value is passed
  through verbatim as the reviewer/implementer name; if the name
  doesn't resolve in `_reviewers.load()` the existing strict-resolve
  error fires at use-time (no extra validation here -- the existing
  call path catches it).
- **Rationale:** Operators frequently want to swap a reviewer for one
  run without editing files ("try the new sonnet model on this PR's
  plan review"). Editing `.millhouse/config.local.yaml`, running, then
  reverting is friction operators today work around with one-off git
  stashes. A targeted env-var registry covers the realistic use cases
  with zero risk of typo'd keys landing in committed config, and the
  small fixed registry keeps the contract obvious. Arbitrary-key env
  overlay (e.g. `MILL_CONFIG__roles__plan__holistic__reviewer=...`) is
  more powerful but the path-encoding is unmemorable and the surface
  area is larger than the actual operator need.
- **Scope effects:**
    - New helper `_config.apply_env_overrides(cfg: dict) -> dict` --
      pure function, returns a new dict with the overrides applied.
    - Called as the final step of both `_config.load_config` and
      `_review_common.load_config`.
    - The env registry lives as a module-level constant in `_config.py`
      (single source of truth; `_review_common.load_config` imports it).
    - Document the registry in the header comment of
      `plugins/mill/templates/mill-config.yaml` so operators can
      discover the env vars from the same place they edit reviewer
      assignments.
    - Unit-tested in `plugins/mill/unit_tests/test-config.py`: each
      registry entry has a test that sets the env var via
      `monkeypatch.setenv`, calls `load_config`, asserts the override
      took effect, and asserts no other keys changed.
- **Out of scope:**
    - Env-var override of non-reviewer keys (timeouts, rounds, etc.).
      Not on the registry. If a use case appears, it can be added in
      a follow-up by extending the registry.
    - Generic `MILL_CONFIG__a__b__c=value` parsing. Rejected for
      legibility.
    - Env-var override of agents.yaml entries (model swaps inside the
      catalogue). Covered by `.millhouse/agents.local.yaml`.
- **Rejected:** Generic dotted-path env-var overlay (poor ergonomics);
  no env support at all (loses the realistic one-off-run use case);
  env-var pointing to a YAML override file (extra indirection without
  benefit when the targeted set of keys is small).

### Overlay precedence: plugin -> repo -> local (machine layer removed)

- **Decision:** Three layers, last wins. For config: plugin template
  (`${CLAUDE_PLUGIN_ROOT}/templates/mill-config.yaml`) ->
  `mill-config.yaml` at the hub repo root ->
  `.millhouse/config.local.yaml` (per-worktree). For agents: plugin
  template (`${CLAUDE_PLUGIN_ROOT}/templates/mill-agents.yaml`) ->
  `.millhouse/agents.local.yaml`. The current per-user machine layer
  (`~/.millhouse/config.machine.yaml`, loaded via `_machine.load_layer()`
  in `_config.py:66` and `_review_common.py:1036`) is **removed**.
- **Rationale:** Operator-wide-on-this-machine settings are an
  underused abstraction with no current consumers in production. The
  same settings that were valid candidates for the machine layer
  (e.g. longer LLM timeouts) are equally well-expressed as a
  per-worktree override in `.millhouse/config.local.yaml`, and that
  file is already where operators set their preferences in practice.
  Removing the layer simplifies the overlay model (one fewer place
  to look when a config value behaves unexpectedly) and reduces the
  surface area of the migration. Agents already have no machine
  layer; this brings config to parity.
- **Scope effects of the removal:**
    - Delete `_machine.load_layer()` callsites in `_config.py` and
      `_review_common.py`.
    - Delete `plugins/mill/skills/mill-setup/SKILL.md` Phase 4.95
      ("Probe machine-level config") entirely -- it imports `_machine`
      and prints a message referencing the to-be-deleted template; with
      no machine layer there is nothing to probe.
    - Update mill-setup's "Final summary" section to drop the
      machine-config bullet (currently at SKILL.md:516) and drop the
      "Machine config:" format block (currently at SKILL.md:553).
    - Delete `plugins/mill/scripts/_machine.py` (after the three
      removals above, no callers remain).
    - Delete `plugins/mill/unit_tests/test-machine.py`.
    - Delete `plugins/mill/templates/config.machine.yaml`.
    - Existing `~/.millhouse/config.machine.yaml` files on operator
      machines are **silently ignored** after the migration; mill
      does not delete them. An operator who relied on them must move
      the relevant keys into each hub's `.millhouse/config.local.yaml`.
      Document this in the migration log line emitted by mill-setup
      Phase 3.2b: "machine config layer removed -- if you previously
      kept overrides in ~/.millhouse/config.machine.yaml, move them
      into this hub's .millhouse/config.local.yaml".
    - The implementer should re-grep `_machine`, `machine.yaml`, and
      `machine_config` across the whole repo at the start of this
      batch to confirm no additional callers exist beyond the ones
      listed above. Any new caller is added to the deletion scope.
- **Rejected:** Keep the machine layer (drops a clean opportunity to
  simplify; the layer's value-per-complexity is low); repo-wins-over-local
  (would make per-machine experimentation impossible without committing);
  template-wins-over-repo (defeats the whole point of a tracked repo
  override).

### Overlay merge: deep for dicts, replace for lists

- **Decision:** Recursive merge of dicts; lists replaced wholesale at the
  level they appear.
- **Rationale:** Matches existing `_config.load_config` behaviour. Lists
  like `verify.skip_known_broken` are operator-owned; partial-merge of
  lists is unpredictable.
- **Rejected:** Element-wise list merge (surprising semantics); shallow
  merge only (forces operators to copy huge subtrees just to override one
  leaf).

### Unknown-key validation: warn, don't fail

- **Decision:** Unknown keys at any level produce a one-line stderr warning
  naming the key path; load succeeds.
- **Rationale:** Catches the realistic `pipeline.implementer` →
  `roles.implementer` rename case. Failing-fast on every old hub during
  plugin upgrade would be operator-hostile and stall background work.
- **Rejected:** Fail-fast (breaks live systems on plugin upgrade); silent
  (the rename bug remains invisible).

### Schema source of truth: plugin template's keyset

- **Decision:** Unknown-key validation walks the plugin template's keyset.
  Any key path present in the template is valid; any other key path
  produces the warning. Same for agents.
- **Rationale:** Template is already the canonical schema. A separate
  JSON-Schema file duplicates state and drifts.
- **Rejected:** Dedicated JSON-Schema file; Python allow-list.

### Validation depth: structural, all levels

- **Decision:** Validate every key path (`a.b.c.d`) recursively. Leaf
  values are not type-checked; only structure.
- **Rationale:** Catches the rename case. Type-checking leaves is
  overengineering for an internal config.
- **Rejected:** Top-level only (misses the rename case); full leaf
  type-validation (too strict for an internal tool).

### mill-setup runs the migration idempotently

- **Decision:** Migration phase runs on every mill-setup invocation;
  detects state and is a no-op when already migrated.
- **Rationale:** Operators run `/mill-setup` on every machine that touches
  a hub; idempotency means a re-run after migration is harmless.
- **Rejected:** Separate one-off `/mill-migrate-config` skill (extra
  invocation operators must remember); manual operator instruction (no
  automation = stragglers forever).

### Config migration is copy-then-stage, never commit

- **Decision:** Mill-setup copies `wiki/config.yaml` contents to
  `mill-config.yaml`, runs `git add mill-config.yaml`, then prints a
  notice that the operator must commit it. It DOES delete the wiki file
  and push wiki, since that's the wiki repo (mill-setup is already
  permitted to push wiki).
- **Rationale:** Mill-setup must never commit silently on the main branch.
  Wiki pushes are an established operation; main-branch commits are not.
- **Rejected:** Auto-commit on main (silent main-branch mutation); move
  rather than copy (operator must commit before re-running, breaking
  idempotency).

### Agents migration is diff-or-skip

- **Decision:** Mill-setup diffs `wiki/agents.yaml` against
  `${CLAUDE_PLUGIN_ROOT}/templates/mill-agents.yaml`. Identical → delete
  wiki file and push. Different → stderr warning listing the differences
  and skipping; operator must manually copy unique entries into
  `.millhouse/agents.local.yaml` before re-running.
- **Rationale:** Silently auto-merging unique entries into the local file
  hides a class of mistakes (operator typo'd an agent name and now it's
  permanently in their local config, divergent from plugin). Operator
  confirmation is the safety gate.
- **Rejected:** Always delete (loses unique entries); auto-merge into
  local (introduces hidden per-machine state).

### Both `load_config` implementations get the overlay

- **Decision:** Both `_config.load_config` and `_review_common.load_config`
  are updated to use the new three-layer overlay reading from `repo_root /
  "mill-config.yaml"`. The two implementations remain separate; lenient
  vs. strict behaviour preserved.
- **Rationale:** Unification is attractive but doubles the blast radius
  of this task. Existing split has reasons (lenient for admin scripts
  that run on partially-set-up hubs; strict for reviewers that must fail
  fast). Both need the new path resolution; keeping them split is the
  YAGNI choice.
- **Rejected:** Unify into one (out-of-scope refactor); update lenient
  only (leaves the review pipeline reading from the wiki).

### `_autonomous.py` for the flag-file API

- **Decision:** New module `plugins/mill/scripts/_autonomous.py` with three
  helpers: `is_autonomous(hub_dir) -> bool`, `set_autonomous(hub_dir)`,
  `clear_autonomous(hub_dir)`.
- **Rationale:** Matches existing module split (`_status.py`, `_marker.py`,
  `_wiki.py`). `_paths.py` is for path resolution, not state predicates.
  Future readers find the file by name.
- **Rejected:** Add to `_paths.py` (violates the file's single
  responsibility); inline the `.exists()` at each callsite (no callsites
  exist yet, but the API will get callers — best to start with a
  helper).

### New path helper `_paths.resolve_mill_config_path`

- **Decision:** Add `resolve_mill_config_path(repo_root: Path) -> Path`
  returning `repo_root / "mill-config.yaml"`.
- **Rationale:** Matches the CLAUDE.md invariant that all path resolution
  goes through `_paths.py`. Single-purpose helper is a one-liner with a
  clear name.
- **Rejected:** Inline (violates the invariant); tuple-return (premature
  generalisation).

### Template renames

- **Decision:** Rename `plugins/mill/templates/wiki-config.yaml` to
  `mill-config.yaml`. Add new `plugins/mill/templates/mill-agents.yaml`
  whose initial contents are exactly the current `wiki/agents.yaml`
  (12 agent entries). Delete `plugins/mill/templates/reviewers.yaml`
  (the 19-line example file).
- **Rationale:** Template file names should track the destination, not
  the historical source. `reviewers.yaml` is the old name for the same
  data; keeping it as an example file is dead weight once the canonical
  template exists.
- **Rejected:** Keep `wiki-config.yaml` name; keep `reviewers.yaml` as
  an example.

### Branch-fallback to wiki/config.yaml

- **Decision:** If `repo_root / "mill-config.yaml"` is missing but
  `wiki_path / "config.yaml"` exists, both `load_config` implementations
  fall back to the wiki file and emit a one-line stderr warning.
- **Rationale:** Task branches started before the migration must keep
  working until they merge or rebase main. The fallback is a few lines
  and avoids "rebase or break" UX. The warning makes the situation
  visible so the operator knows to rebase.
- **Rejected:** Hard failure (forces an unscheduled rebase in the
  middle of in-flight work); read from main branch's
  `mill-config.yaml` regardless (cross-branch read is surprising and
  hard to test).

### Both-files-present resolution

- **Decision:** When both `mill-config.yaml` AND `wiki/config.yaml` exist
  at load time, `mill-config.yaml` wins. Stderr warning that the wiki
  file is stale and should be removed via mill-setup.
- **Rationale:** This is a post-migration state where someone partially
  rolled back. Picking the new file is the right answer; the warning
  prompts cleanup.
- **Rejected:** Halt (breaks the run for a recoverable state); deep-merge
  the two (no sensible precedence).

### Single PR, atomic landing

- **Decision:** All changes — overlay, validation, migration phase,
  template renames, `autonomous_mode` removal, fallback, tests — land in
  one PR.
- **Rationale:** The overlay is meaningless without migration; migration
  is meaningless without the overlay. Splitting creates intermediate
  states where the wiki still has the file but production code expects
  the new path.
- **Rejected:** Two PRs (overlay + migration); three PRs (overlay,
  migration, `autonomous_mode`).

## Technical context

### Current config load path

`plugins/mill/scripts/_config.py:32-80` defines `load_config(wiki_path,
worktree_root) -> dict`, which deep-merges three layers today:

1. `wiki_path / "config.yaml"` (lenient; returns `{}` if missing)
2. `~/.millhouse/config.machine.yaml` (per-user, via `_machine.load_layer()`)
3. `worktree_root / ".millhouse/config.local.yaml"`

After this task, the wiki layer is replaced by two new layers (plugin
template + repo-root `mill-config.yaml`) and the machine layer is
removed, giving three layers in total: plugin -> repo -> local. The
`_machine.load_layer()` calls in `_config.py` and `_review_common.py`
go away; `_machine.py` itself is deleted if it has no remaining
callers; the `plugins/mill/templates/config.machine.yaml` template is
deleted.

A final env-var override pass runs after the three-layer merge. The
registry of env-var-to-key-path mappings is a module-level constant
in `_config.py` and lists six entries (one per reviewer-selection
key + implementer model). The pass is a pure function applied at the
end of `load_config`. Both load implementations import the same
registry so the env behaviour is identical for admin scripts and the
review pipeline.

`plugins/mill/scripts/_review_common.py:1017-1052` defines a parallel
`load_config(wiki_root, mill_dir) -> dict` with the same shape but
strict semantics: raises `ReviewError` if `wiki_root / "config.yaml"` is
missing. This is the reviewer-side variant.

The earlier exploration estimated 17 callsites total (9 lenient + 8
strict). That figure was conservative -- a fresh `grep -rn
'load_config(' plugins/mill/scripts/` is the authoritative source. The
implementer should run that grep at the start of the migration batch
and treat the resulting list (minus function definitions, docstrings,
and self-references inside `_config.py` / `_review_common.py`) as the
work-item. The expected order of magnitude is twenty-plus callsites;
do not trust the historical "17" number.

Every callsite first resolves the wiki path via
`_paths.resolve_wiki_path(git_root)`. The migration changes this:
callsites will need `repo_root` (i.e. the git toplevel), not
`wiki_path`. `_paths.resolve_git_root()` already returns `repo_root`;
`wiki_path` is no longer needed as a load-config input.

### Current agents load path

`plugins/mill/scripts/_reviewers.py:36-56` defines `load(wiki_root) -> dict[str, dict]`,
which reads `wiki_root / "agents.yaml"` with a fallback to
`wiki_root / "reviewers.yaml"` for backward compatibility. Performs
strict validation: duplicate keys, `[a-z0-9_-]+` name format, `type`
must be `single|cluster`, etc.

After migration, the primary source becomes
`${CLAUDE_PLUGIN_ROOT}/templates/mill-agents.yaml`. Overlay layer is
`.millhouse/agents.local.yaml`. The `agents.yaml` → `reviewers.yaml`
fallback stays at the load layer for one release (covers hubs that
haven't yet run mill-setup); the fallback target becomes
`wiki/agents.yaml` → `wiki/reviewers.yaml` (legacy) when the plugin
template is absent (which should not happen in normal installs but does
in tests).

### `autonomous_mode` callsites and intermediate state

`cfg["pipeline"]["autonomous_mode"]` has live callsites today, all in
skill markdown that runs inline Python:

- `plugins/mill/skills/mill-autofix/SKILL.md:124` -- inline Python that
  writes `cfg.setdefault("pipeline", {})["autonomous_mode"] = True` into
  `.millhouse/config.local.yaml` before launching an autonomous run, and
  restores it on every exit path (cleanup phase).
- `plugins/mill/skills/mill-go/SKILL.md:232` -- reads the deep-merged
  config to gate the "stuck" escalation prompt under autonomous mode.
- `plugins/mill/skills/mill-plan/SKILL.md:153` and `:155` -- reads the
  deep-merged config to gate non-progress and max-rounds blocked
  behaviour during plan generation.

None are Python source under `plugins/mill/scripts/`, but all are
active callsites the moment the skills run. The implementer should
re-grep `pipeline.autonomous_mode` and `autonomous_mode` across
`plugins/mill/` before starting the follow-up task to confirm no
additional callsites exist.

Removing the key from the plugin template / wiki template means:

1. mill-autofix continues to write the key into
   `.millhouse/config.local.yaml`. Unknown-key validation (warn-only)
   emits a stderr warning on subsequent loads but does not fail.
2. mill-go and mill-plan's reads return the value mill-autofix wrote,
   so autonomous mode keeps working through the intermediate state.
3. A follow-up task migrates mill-autofix to set
   `.millhouse/autonomous.flag` and mill-go **and mill-plan** to read
   it via the new `_autonomous.is_autonomous(hub_dir)` helper, after
   which the `pipeline.autonomous_mode` key becomes silent dead state
   in old local files (and the unknown-key warning prompts cleanup).
   The follow-up task scope MUST include all three skills (autofix +
   go + plan) so the migration cuts over atomically; missing any one
   produces a silent regression where the omitted skill stops
   honouring autonomous mode.

This intermediate state is intentional and functionally
non-breaking *because* unknown-key validation is warn-only, not
fail. The `.flag` file API ships in this task; the skill-side
migration ships in a follow-up so that this PR stays focused on
config plumbing and doesn't drag mill-autofix's exit-path logic
into scope.

### `_paths.py` surface

Existing helpers: `resolve_git_root`, `resolve_wiki_path`,
`resolve_container_path`, `resolve_short_name`,
`resolve_hub_relative_path`, `resolve_active_worktree`,
`resolve_active_hub`, `resolve_task_path`, `status_path`. Plus
exceptions `ActiveWorktreeNotFound`, `ActiveWorktreeSlugMismatch`.

Adding `resolve_mill_config_path(repo_root: Path) -> Path` is a
one-line helper. Export via `__all__`.

### mill-setup phases

Existing phase numbering (from the explore report):

- Phase 3.1 — Seed `wiki/config.yaml` from template
- Phase 4.7 — Generate `.millhouse/*.ps1` wrappers; set PYTHONPATH user env var
- Phase 4.9 — Write `hub_relative_path` to `.millhouse/config.local.yaml`
- Phase 5  — Seed `.millhouse/config.local.yaml` from template

Proposed new phase 3.2b sits between 3.1 (seed wiki) and 4.x (worktree
setup): it inspects the wiki for `config.yaml` and `agents.yaml`,
migrates if present, is a no-op otherwise. Phase 3.1 also changes:
"seed wiki/config.yaml from template" becomes "seed mill-config.yaml
in repo root from template, if missing".

Phase 3.1 does NOT halt when `wiki/config.yaml` still exists. The
both-files-exist case (interrupted-migration state: `mill-config.yaml`
already at the hub root AND `wiki/config.yaml` still present in the
wiki) is handled entirely by Phase 3.2b Case 2: skip the copy, retry
the wiki delete + push, idempotent on re-run. Phase 3.1 is purely a
seeder; it never inspects the wiki for legacy `config.yaml`. This
keeps Phase 3.1 single-purpose and avoids the unbreakable-halt cycle
that an early-phase halt would create on re-run.

### `.millhouse/` directory contents

In the current `config-move-to-hub` worktree: 1 config file
(`config.local.yaml`, 87 lines) + 11 PS1 wrappers (`millpy-*.ps1`).
The PS1 wrappers are regenerated by mill-setup Phase 4.7; the proposal
doesn't change Phase 4.7. The `autonomous.flag` lives next to these as
an ephemeral file.

### CLAUDE.md updates

The session-start CLAUDE.md has a `## Constraints` section that says
"The wiki holds only `Home.md` and `config.yaml`" (paraphrasing). That
sentence becomes "The wiki holds only `Home.md`" after migration.
There's also a `## Path invariants` section listing what the wiki
contains; it needs the same edit. The wiki/config.yaml header comment
documents the wiki contents — that file is being deleted, so no edit
needed there, but the new `mill-config.yaml` template should carry a
similar header documenting overlay precedence.

### Unknown-key validation implementation

Walk the merged-config dict alongside the merged-template dict. For
each path that exists in the merged-config but not in the template,
emit a stderr line: `[config] unknown key: <path> (in <source-file>)`.
"Source file" is the topmost overlay layer that introduced the key —
useful for the rename case (`pipeline.implementer` would be flagged as
coming from `mill-config.yaml` if the operator hadn't migrated their
override).

Tracking the source layer requires keeping per-layer dicts and walking
them in precedence order. An alternative is to compute the warning
against each layer independently and dedupe; either is fine.

## Constraints

- **No silent main-branch commits.** mill-setup may `git add` but never
  `git commit` to the main branch on the operator's behalf.
- **Idempotent mill-setup phases.** Re-running mill-setup after a
  partial run must complete cleanly. The migration phase detects state
  (which files exist) and acts accordingly.
- **ASCII-only stdout/stderr.** Per CLAUDE.md, all `print()` and
  `_log()` strings are ASCII. Warning text must use `--` and `->`,
  not em-dash or arrow glyph.
- **`${CLAUDE_PLUGIN_ROOT}` for plugin-internal paths.** The plugin
  template path is `${CLAUDE_PLUGIN_ROOT}/templates/mill-config.yaml`,
  not `plugins/mill/templates/mill-config.yaml`. External repos using
  mill as a plugin have no `plugins/mill/` source checkout.
- **Wiki access only through helpers.** Wiki mutations go through
  `_wiki.write_commit_push` or `git -C <wiki_path>`; no `cd` into the
  wiki. The migration's wiki-file delete must use
  `_wiki.write_commit_push` (passing `paths=["config.yaml"]` and a
  delete operation, or sequencing `git -C <wiki_path> rm config.yaml`
  inside a `_wiki.wiki_lock` block).
- **Junctions are read-only navigation.** `.wiki`, `.active`, etc.
  must not appear in any script path. Use `_paths.resolve_wiki_path`
  and the new `_paths.resolve_mill_config_path`.
- **`_review_common.load_config` is the strict variant.** It must keep
  raising on missing config; the only change is the source path.
- **Worktree-isolation rule.** This task runs in the
  `config-move-to-hub` worktree; no edits to the main worktree or
  other task worktrees.

## Testing

### Unit tests

- **`plugins/mill/unit_tests/test-config.py`** — extend with cases for
  the new overlay:
    - Three-layer merge with deep dicts (plugin -> repo -> local).
    - Machine layer is no longer consulted: existing
      `~/.millhouse/config.machine.yaml` files are ignored even if
      present.
    - Env-var override pass: each registry entry has a unit test that
      `monkeypatch.setenv`s the var, calls `load_config`, asserts the
      target key took the env value, asserts no other config keys
      changed. Plus a negative test: empty-string env value is treated
      as "no override".
    - List-replace semantics (`verify.skip_known_broken` overlay).
    - Unknown-key warning emitted to stderr; load still succeeds.
    - Removed-key (`pipeline.autonomous_mode`) in a local file → warning.
    - Fallback to `wiki/config.yaml` when `mill-config.yaml` absent —
      warning emitted; load succeeds with wiki contents.
    - Both-files-present → `mill-config.yaml` wins, warning emitted.
- **`plugins/mill/unit_tests/test-paths.py`** — extend with:
    - `resolve_mill_config_path` returns `repo_root / "mill-config.yaml"`.
- **`plugins/mill/unit_tests/test-autonomous.py`** — NEW:
    - `is_autonomous` returns `False` when flag absent.
    - `set_autonomous` creates the flag (zero-byte file).
    - `is_autonomous` returns `True` after set.
    - `clear_autonomous` deletes the flag; second clear is idempotent.
    - All paths derived from a `hub_dir` argument — no global state.
- **`plugins/mill/unit_tests/test-reviewers.py`** (existing or new) —
  extend with:
    - Two-layer overlay: plugin template + local.
    - Local file adds a new agent → both visible.
    - Local file overrides plugin agent's `model` → override wins.
    - Unknown-key warning on local file.

All unit tests use in-memory fixtures (`tmp_path` from pytest, or
hand-rolled `tempfile.TemporaryDirectory`). No real git, no real LLM,
no real wiki. Existing test conventions documented in CLAUDE.md
(`plugins/mill/unit_tests/`).

### Integration test

- **`plugins/mill/integration_tests/test-migration.py`** — NEW:
    - Build a fixture hub with a wiki repo (real git) containing
      `config.yaml` and `agents.yaml`.
    - Run the mill-setup migration phase as a subprocess.
    - Assert `mill-config.yaml` exists at the hub root, contents
      match wiki contents, `git status` shows it as staged.
    - Assert `wiki/config.yaml` has been removed (and the wiki has
      been pushed — verify on the bare remote).
    - Case A: `agents.yaml` identical to plugin template → wiki
      file deleted.
    - Case B: `agents.yaml` differs → stderr warning emitted; wiki
      file NOT deleted; exit code 0 (warning, not failure).
    - Re-run the migration → no-op (idempotency check). All assertions
      still hold.

Integration tests use real `git` (`.scratch/` fixtures). No real
`claude` invocation.

### TDD candidates

The overlay logic and the unknown-key validation are the most
TDD-friendly pieces: pure functions, no I/O beyond reading YAML, easy
to fixture. Write tests first for the merge precedence and the warning
output; implementation follows.

The mill-setup migration phase is harder to TDD because it touches a
real wiki repo — write the integration test alongside the implementation
rather than strictly before.

## Q&A log

- **Q:** Where does the tracked repo-root config file live? **A:** [auto-pick] `mill-config.yaml` at repo root. **Why:** Proposal-explicit; avoids `.gitignore` carve-outs.
- **Q:** Does `agents.yaml` get a tracked repo-root file too? **A:** [auto-pick] No tracked repo file; plugin template owns the catalogue. **Why:** Per-machine overlay only; agent catalogue is plugin property.
- **Q:** Where does `autonomous_mode` ephemeral state live? **A:** [auto-pick] `.millhouse/autonomous.flag`. **Why:** Simplest semantics; cleanup is `os.unlink`.
- **Q:** Config overlay precedence? **A:** [auto-pick] `plugin template -> mill-config.yaml -> .millhouse/config.local.yaml`. **Why:** Local must override everything; matches proposal §3.
- **Q:** Agents overlay precedence? **A:** [auto-pick] `plugin template -> .millhouse/agents.local.yaml`. **Why:** Per-machine model swap is a real need; full-replace breaks plugin upgrade ergonomics.
- **Q:** Merge granularity? **A:** [auto-pick] Deep merge for dicts; lists replaced wholesale. **Why:** Matches existing behaviour; predictable for `verify.skip_known_broken`-style lists.
- **Q:** Unknown-key strictness? **A:** [auto-pick] Warn on stderr; do not fail. **Why:** Failing-fast breaks every old hub on plugin upgrade.
- **Q:** Schema source of truth? **A:** [auto-pick] Plugin template's keyset. **Why:** Avoids drifting separate schema file.
- **Q:** Validation depth? **A:** [auto-pick] All key paths recursively; values not type-checked. **Why:** Catches `pipeline.implementer` rename case; full type-check is overkill.
- **Q:** Migration trigger? **A:** [auto-pick] Idempotent phase in mill-setup that runs on every re-run. **Why:** Operators run mill-setup on every machine; idempotency makes re-runs safe.
- **Q:** Config migration behaviour? **A:** [auto-pick] Copy contents to `mill-config.yaml`, `git add`, operator commits; delete wiki file and push. **Why:** No silent main-branch commits.
- **Q:** Agents migration behaviour? **A:** [auto-pick] Diff vs. plugin template; identical -> delete wiki file; different -> warn and skip. **Why:** Operator confirmation is the safety gate against silent local-state introduction.
- **Q:** Refactor scope for the two `load_config`s? **A:** [auto-pick] Both get the overlay; keep them split. **Why:** Unification is an attractive out-of-scope refactor; doubles the blast radius.
- **Q:** `autonomous_mode` removal scope? **A:** [auto-pick] Remove from schema, no code reads it today, replace with `.flag` file API. **Why:** No production callsites; safe to remove.
- **Q:** Flag helper location? **A:** [auto-pick] New `_autonomous.py` module. **Why:** Matches `_status.py`, `_marker.py` split.
- **Q:** New path-resolver helper? **A:** [auto-pick] `resolve_mill_config_path(repo_root)`. **Why:** Honours the "all path resolution goes through `_paths.py`" CLAUDE.md invariant.
- **Q:** Template renames? **A:** [auto-pick] `wiki-config.yaml` -> `mill-config.yaml`; new `mill-agents.yaml`; delete `reviewers.yaml`. **Why:** Templates named after destination, not source.
- **Q:** `reviewers.yaml` template fate? **A:** [auto-pick] Delete; replaced by `mill-agents.yaml`. **Why:** Dead weight once canonical catalogue exists.
- **Q:** Both `mill-config.yaml` and `wiki/config.yaml` mid-migration? **A:** [auto-pick] Skip copy, still delete wiki file. **Why:** Idempotency requirement.
- **Q:** In-flight branch predating migration? **A:** [auto-pick] Load-time fallback to `wiki/config.yaml` with stderr warning. **Why:** Avoids forced rebase mid-task.
- **Q:** Both files exist at load time? **A:** [auto-pick] `mill-config.yaml` wins; warn about stale wiki file. **Why:** Post-migration partial rollback; pick the new source, prompt cleanup.
- **Q:** Removed key in local file? **A:** [auto-pick] Treat as unknown-key warning. **Why:** Consistent overlay behaviour; covers `autonomous_mode` removal.
- **Q:** Test coverage scope? **A:** [auto-pick] Unit tests for overlay + path helpers; integration test for migration. **Why:** Overlay is the new behaviour and must be deterministic; migration touches wiki state and operator UX.
- **Q:** Test file locations? **A:** [auto-pick] Extend existing `test-config.py`/`test-paths.py`; new `test-migration.py` in integration_tests. **Why:** Matches existing test layout.
- **Q:** Rollout sequence for in-flight hubs? **A:** [auto-pick] Opt-in via `/mill-setup` re-run; load-time fallback keeps live tasks working. **Why:** Minimises disruption; hard-cut is operator-hostile.
- **Q:** PR strategy? **A:** [auto-pick] One PR, atomic landing. **Why:** Overlay and migration are interlocked; intermediate states are broken.
- **Q:** Should the per-user machine layer (`~/.millhouse/config.machine.yaml`) be preserved or removed? **A:** Operator override -- remove. **Why:** The machine layer has no production consumers; the same use-cases are served by `.millhouse/config.local.yaml`. Removing it simplifies the overlay (one fewer layer to reason about) and shrinks the surface of this migration. Operators who relied on it move their keys into per-hub `.millhouse/config.local.yaml`; mill-setup logs a one-line notice on first run.
- **Q:** Should env vars be able to override reviewer selection at run time? **A:** Operator addition -- yes, via a small named registry. **Why:** Operators frequently want to swap a reviewer for one run (`MILL_PLAN_REVIEWER=opushigh /mill-plan`) without editing files or committing. The registry is hard-coded and narrow (six entries covering each reviewer scope plus implementer model) so the contract is obvious and there is no risk of typo'd keys silently doing nothing. Empty/unset = no override. Applied as the highest-precedence layer after the three-layer overlay merge.
