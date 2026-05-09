# Discussion: 34 (A) — Config schema cleanup + reviewer registry

```yaml
task: 34 (A) — Config schema cleanup + reviewer registry
slug: config-schema-refactor
status: discussing
parent: main
```

## Problem

`wiki/config.yaml` has accumulated rot in the `review:` umbrella, and the `_reviewer_*.py` module layout is starting to combinatorially explode.

The review schema has four concrete defects:

1. `review.code.holistic_effort: max` is redundant with the reviewer name `sonnetmax` — both encode "max effort".
2. `review.code.self_fix_rounds` lives under `review:` but is an *implementer* parameter (consumed by `millpy-implement.py` and `millpy-implement-holistic.py`, never by any review backend).
3. `review.code` is asymmetric to `review.plan`: code uses `holistic: true/false` + `per_batch: false` flags + separate `holistic_rounds` / `holistic_effort`; plan uses `batch:` / `holistic:` reviewer slots. There is no way to set a different holistic reviewer for code.
4. `review.discussion.holistic` was originally `sonnetmax` (bulk mode). Bulk-mode discussion review is useless — the bulk only contains `discussion.md`, no source — already partially fixed by commit a337579 (now `sonnetmax_tool`); the schema must formalise the requirement.

The reviewer-module layout couples model + effort + mode in the file name (`_reviewer_sonnetmax.py`, `_reviewer_sonnetmax_tool.py`). Adding an effort variant means a new file. Adding a provider means more files. The combinatorial explosion is starting now (gemini-reviewer is queued in task 31, cluster-reviewer in task 13).

**Why now:** task 31 (gemini-reviewer) is blocked by this. If task 31 lands first under the old schema it will spawn another N×M files and lock in the asymmetry. After task 34 lands, task 31 reduces to "add `_llm_gemini.py` + registry entries" — one file, no new reviewer modules.

## Scope

**In:**

- New file `wiki/reviewers.yaml` — the reviewer registry (named single + cluster definitions).
- Rewrite `wiki/config.yaml` — replace `review:` umbrella with `roles:` (`discussion-review`, `plan-review`, `code-review`, `implementer`); each role has symmetric `batch:`/`holistic:` `{rounds, reviewer}` subsections per scope; `self_fix_rounds` moves to `roles.implementer`; `diff_scope_threshold` moves to `roles.code-review`.
- Rewrite `plugins/mill/templates/wiki-config.yaml` — fresh-setup default mirroring the new live schema.
- New `plugins/mill/templates/reviewers.yaml` — fresh-setup default registry; minimal entries (`sonnetmax`, `sonnetmedium`, `sonnetmax_tool`).
- New helper `plugins/mill/scripts/_reviewers.py` — registry loader, name resolver, role-aware lookup, cross-validation against `cfg.roles.*`.
- New reviewer module `plugins/mill/scripts/_reviewer_single.py` — replaces `_reviewer_sonnetmax.py` and `_reviewer_sonnetmax_tool.py`; takes a resolved spec, dispatches to the right `_llm_<provider>` module.
- Delete `plugins/mill/scripts/_reviewer_sonnetmax.py` and `_reviewer_sonnetmax_tool.py` in the same commit that introduces `_reviewer_single.py` and rewires consumers.
- Rewire all readers: `_review_discussion.py`, `_review_plan.py`, `_review_code.py`, `millpy-implement.py`, `millpy-implement-holistic.py` — read `cfg.roles.*` instead of `cfg.review.*`; resolve reviewer names via `_reviewers.py`.
- Update unit tests: rewrite cfg-builder fixtures across `test-review-code-flow.py`, `test-review-plan-flow.py`, `test-review-discussion-flow.py`, `test-review-cli.py`, `test-review-common.py`, `test-llm-claude.py`, `test-millpy-implement.py`, `test-millpy-implement-holistic.py`, `test-reviewer-modules.py`. Add new `test-reviewers.py` for the resolver.
- Update skill docs that reference old config keys: `mill-go/SKILL.md`, `mill-plan/SKILL.md`, `mill-start/SKILL.md`, plus any other matches under `plugins/mill/skills/**/*.md`.
- Add a startup warning in `_review_common.load_config` when the `.millhouse/config.local.yaml` overlay carries a stale top-level `review:` key.

**Out:**

- `_reviewer_cluster.py` runtime — deferred to task 13 (cluster-reviewer). This task defines the cluster *schema* and the resolver's cluster validation, but no `_reviewer_cluster.py` file is created. When a resolved cluster spec is dispatched, the dispatcher raises `ReviewerError("cluster dispatch not yet implemented; see task 13")`.
- `_llm_gemini.py` — task 31's job. The proposal example references gemini reviewers (`g25flash`, `g25flash_lo`, `g25flash-x3-sonnetmax`), but these are not part of the fresh-setup template default.
- Implementer registry. `_implementer_sonnet.py` stays as-is, imported directly by `millpy-implement.py`. `roles.implementer:` carries `self_fix_rounds` only; no `reviewer:` slot, no registry lookup. A future task can lift implementer into the registry if a second implementer arrives.
- A normalized cross-provider effort vocabulary. `effort:` values pass verbatim from registry to `_llm_<provider>` module; the provider rejects unknown values with its own error.
- Backwards-compatibility shim. The old `review:` umbrella keys are removed in the same commit that adds `roles:`; no dual-read period. The wiki is single-operator and migrates atomically.

## Decisions

### Two-layer architecture (LLM-provider vs. reviewer strategy)

- Decision: Reviewer modules become *strategy patterns*, not model wrappers. Two reviewer files are enough for the foreseeable future: `_reviewer_single.py` (one LLM call) and the future `_reviewer_cluster.py` (N workers + handler). LLM-provider knowledge is centralised in one file per provider (`_llm_claude.py`, future `_llm_gemini.py`), each exposing `run_bulk()` and `run_tool_use()` and accepting `model=` / `effort=` arguments.
- Rationale: Decouples model+effort+mode combinatorics from the reviewer-module count. Adding a new effort = registry entry. Adding a new provider = one new `_llm_*.py`. No `_reviewer_sonnetmedium.py`, no `_reviewer_sonnetmax_tool.py` — those collapse into a single file driven by spec.
- Rejected: Keep one reviewer module per (model, effort, mode) combination. Already linear in files; explodes once gemini and cluster land.

### Reviewer registry — `wiki/reviewers.yaml`

- Decision: A new sibling file to `wiki/config.yaml` holding named reviewer definitions. Each entry has `type: single | cluster`. `single` requires `provider` (which `_llm_*.py` to import), `model`, `effort`, optional `tooluse: true|false` (default false). `cluster` requires `workers: { use: <name>, count: <n> }` and `handler: { use: <name> }`. Cluster `workers.use` and `handler.use` must resolve to `single` entries — no nested clusters.
- Rationale: Reviewer specs are referenced by many roles and edited rarely; separating them from the role-config shrinks `config.yaml` to a one-screen summary. The registry is the single source of truth for reviewer behaviour.
- Rejected: Keep specs inline at each `roles.<role>.<scope>.reviewer` site. Triples duplication when one reviewer is reused.
- Rejected: Allow nested clusters (cluster `use:` resolving to another cluster). YAGNI — cycle detection adds complexity nobody has asked for.

### Roles section replaces `review:` umbrella

- Decision: `wiki/config.yaml` exposes `roles:` instead of `review:`. Role keys are `discussion-review`, `plan-review`, `code-review`, `implementer`. Review roles each have `batch:` and/or `holistic:` subsections; each subsection is `{rounds: <int>, reviewer: <name|null>}`. `code-review` carries `diff_scope_threshold` at role level (artefact-bulking concern, not reviewer concern). `implementer` carries `self_fix_rounds` at role level (no `reviewer:` slot).
- Rationale: Symmetric vocabulary across discussion / plan / code. Skip semantics are uniform: `rounds: 0` OR `reviewer: null` → skip the scope. The boolean `holistic: true/false` and `per_batch: true/false` flags die — presence of a non-null reviewer enables the scope.
- Rejected: Keep `review.<type>` umbrella with renamed leaf keys. Doesn't fix the asymmetry between code and plan.
- Rejected: Add an explicit `enabled: true|false` per scope. Redundant with the null-reviewer sentinel.

### `tooluse:` lives on the spec, not the reviewer module

- Decision: The `MODE = "bulk" | "tool-use"` module-level constant on `_reviewer_*.py` is no longer used by the dispatcher. The backend reads `spec.tooluse` and decides prompt shape (bulk inlines file content; tool-use lists paths). `_reviewer_single.run(spec, prompt_text, ...)` reads `spec.tooluse` to dispatch to `_llm_<provider>.run_bulk` or `run_tool_use`. `_reviewer_test_stub.py` retains its `MODE = "bulk"` for test compatibility but the new dispatch path consults the spec.
- Rationale: A single `_reviewer_single.py` cannot have a static `MODE` because mode varies per registered name. Pushing the decision to the spec layer eliminates the constant.
- Rejected: Compute `MODE` dynamically per call. Awkward; the spec already carries the answer.

### `effort:` is fully owned by the registry entry — no call-site override

- Decision: Today `_review_code.py` reads `cfg.review.code.holistic_effort` and passes it to `reviewer.run(..., effort=...)` to override the per-batch reviewer's default. Under the registry, `effort:` is part of the named reviewer. To pick a different effort for holistic vs. batch, define a different reviewer (e.g. `sonnetmedium`) and reference it under `roles.code-review.holistic.reviewer`. The `effort=` keyword on `_reviewer_single.run` and downstream goes away.
- Rationale: One source of truth per reviewer behaviour. The "override per call" knob is exactly the asymmetry the proposal is trying to delete.
- Rejected: Keep a `roles.<role>.<scope>.effort` overlay. Re-introduces asymmetry; makes effort live in two places.

### Skip semantics: `rounds: 0` OR `reviewer: null` → skip

- Decision: Either sentinel disables the scope. `roles.code-review.batch: {rounds: 0, reviewer: <whatever>}` skips per-batch code review; `roles.plan-review.batch: {rounds: 3, reviewer: null}` skips per-batch plan review (already valid today). Both forms are accepted; backends never look at one without the other.
- Rationale: Two skip sentinels are tolerated because they express different operator intents (turn off vs. not configured). Backends treat them identically.
- Rejected: Allow only `reviewer: null` for skip. Forces operators to keep stale `rounds:` values when temporarily disabling.

### Eager validation on first load

- Decision: `_reviewers.load(wiki_root) -> dict` loads `wiki/reviewers.yaml`, validates structure (`type ∈ {single, cluster}`, required fields per type, name regex `[a-z0-9_-]+`, no duplicate names, all `use:` references resolve, no cycles, cluster `use:` only references `type: single`). Raises `ReviewerError` with a clear message on any failure. The API scripts call `_reviewers.load` once and pass the registry around.
- Rationale: Operator typos surface immediately, not only when the bad reviewer is selected. Cheap; the registry is small.
- Rejected: Lazy validation. Hides typos until that role fires.

### Cross-validation: every named reviewer in `cfg.roles.*` must exist

- Decision: After `_reviewers.load` and `_review_common.load_config` both succeed, the API scripts call `_reviewers.validate_role_refs(cfg, registry)` which walks `cfg.roles.<role>.<scope>.reviewer` for every (role, scope) pair and confirms each non-null name resolves in the registry. Crashes with a list of all missing names so the operator fixes them in one pass.
- Rationale: A typo in `roles.code-review.batch.reviewer: sonentmax` should fail at startup, not when code review fires three days later.
- Rejected: Defer per-role validation until the role is invoked. Same anti-pattern as Q23 option 2.

### Provider → LLM module mapping is convention-based

- Decision: `_reviewer_single.run` reads `spec.provider` (e.g. `"claude"`) and imports `_llm_claude` via `importlib.import_module(f"_llm_{spec['provider']}")`. Mirrors today's `load_reviewer` pattern. Unknown provider raises `ReviewerError("unknown provider: ...")`.
- Rationale: Adding a provider = one new file, no edits to the resolver. Self-documenting.
- Rejected: Hard-coded dispatch table. Adds an edit step per new provider.

### Effort values pass verbatim to the LLM provider

- Decision: `_reviewer_single` does not enumerate or translate effort values. `spec.effort` is forwarded as-is to `_llm_<provider>.run_bulk(..., effort=...)`. The provider module raises if the value is unknown to its CLI.
- Rationale: Providers have different effort vocabularies (claude `max/medium/low/none`, gemini may differ). Centralising a normalized scale forces a translation table per provider that nobody has asked for.
- Rejected: Normalized vocabulary translated by each `_llm_*.py`. Premature.

### `_reviewer_single.run` takes the spec

- Decision: Signature is `_reviewer_single.run(spec: dict, prompt_text: str, *, session_id: str | None = None, resume: bool = False, timeout: int | None = None) -> tuple[str, str]`. `effort` and `tooluse` come from `spec`. Backends always call through `_reviewer_single.run`; they never import `_llm_*` directly.
- Rationale: Spec is the unit. Treating reviewer modules as strategies means the strategy gets the full spec.
- Rejected: Flatten spec into kwargs (`run(prompt_text, *, model, effort, tooluse, ...)`). Loses the framing; backends start passing `spec["model"]` etc. piecewise.

### Cluster dispatch raises until task 13 lands

- Decision: No `_reviewer_cluster.py` file is created in this task. The dispatcher inside `_reviewer_single.run` (or a small wrapper at the resolver layer) detects `spec.type == "cluster"` and raises `ReviewerError("cluster dispatch not yet implemented; see task 13")`. The schema and resolver fully support clusters; only the runtime is deferred.
- Rationale: Locking the schema before task 13 starts means task 13 only writes runtime. Avoids a stub `_reviewer_cluster.py` that masquerades as real code.
- Rejected: Stub file with `NotImplementedError`. Adds a placeholder that exists only to be opened.

### Atomic rewrite of live `wiki/config.yaml` + `wiki/reviewers.yaml`

- Decision: One commit on the task branch (committed via `_wiki.write_commit_push`) rewrites `wiki/config.yaml` to the new schema and creates `wiki/reviewers.yaml`. After mill-merge lands the task, the new schema is live for every clone on next pull. No deprecation cycle, no dual-read period.
- Rationale: Single-operator wiki. Running both schemas in parallel adds complexity for nobody.
- Rejected: Stage new files alongside old, deprecate later. Pure churn.

### Migration warning on stale `.millhouse/config.local.yaml`

- Decision: When `_review_common.load_config` deep-merges `.millhouse/config.local.yaml`, scan the overlay's top-level keys for `review:`. If present, write a stderr warning naming the file path and the orphaned keys. Do not crash — the merged config is still valid because the new schema has no `review:` section, so the orphan branch is harmless.
- Rationale: One warning per process launch is a cheap nudge to delete the stale overlay. Crashing the user's tooling over an orphaned key is too aggressive.
- Rejected: Crash on overlay containing `review:`. Annoying for sessions that rerun for unrelated reasons.

### `_reviewer_test_stub.py` resolves via a hard-coded special case

- Decision: `_reviewers.resolve(registry, name)` checks `name == "test_stub"` first and returns a synthetic spec without consulting the registry. Tests don't need to write a fixture `reviewers.yaml`. Document the special case in the resolver's docstring so the carve-out is explicit.
- Rationale: Tests across `test-review-*-flow.py` already use `load_reviewer("test_stub")`; preserving a zero-config path keeps the test surface unchanged.
- Rejected: Per-test fixture `reviewers.yaml`. Adds setup boilerplate everywhere.
- Rejected: Fall back to direct `_reviewer_<name>` import when the name is missing from the registry. Hides typos; same anti-pattern as today's `load_reviewer` fallback.

### Reviewer-name regex: `[a-z0-9_-]+`

- Decision: Allow lowercase letters, digits, underscore, hyphen. Both `sonnetmax_tool` and `g25flash-x3-sonnetmax` are valid. Reject capitals, dots, slashes, spaces. Validate at load time.
- Rationale: Both styles already appear in the proposal; forcing one breaks examples.
- Rejected: Allow only one style. Cleaner but breaks examples.

### `holistic_timeout` and `implementer_timeout` stay flat under `llm:`

- Decision: All four timeouts (`bulk_timeout`, `tool_use_timeout`, `holistic_timeout`, `implementer_timeout`) live at `llm:` top level. Backends read them as-is (`cfg["llm"]["holistic_timeout"]` etc.). The `roles:` section does not own timeouts.
- Rationale: Timeouts are LLM-provider concerns (rate-limit, cold-cache headroom) bound to the call mode, not the role. The proposal's `llm:` example understated this section.
- Rejected: Move `holistic_timeout` to `roles.<role>.holistic.timeout` and `implementer_timeout` to `roles.implementer.timeout`. Pushes provider concerns into role configuration.

## Technical context

### Files that read the old `review.*` keys (must rewire)

- `plugins/mill/scripts/_review_discussion.py`
  - `cfg["review"]["discussion"]["rounds"]` → `cfg["roles"]["discussion-review"]["holistic"]["rounds"]`
  - `cfg["review"]["discussion"]["holistic"]` (reviewer name) → `cfg["roles"]["discussion-review"]["holistic"]["reviewer"]`
- `plugins/mill/scripts/_review_plan.py`
  - `cfg["review"]["plan"]["rounds"]` is a single int that gates both per-batch and holistic in the current code. Under the new schema, batch and holistic each have their own `rounds`. Backend reads:
    - `cfg["roles"]["plan-review"]["batch"]["rounds"]` for the per-batch path (`_review_one_batch` round cap, `_review_plan.run` round-discovery loop).
    - `cfg["roles"]["plan-review"]["holistic"]["rounds"]` for the holistic path (round-cap check before holistic invoke).
  - `cfg["review"]["plan"]["batch"]` → `cfg["roles"]["plan-review"]["batch"]["reviewer"]`
  - `cfg["review"]["plan"]["holistic"]` → `cfg["roles"]["plan-review"]["holistic"]["reviewer"]`
- `plugins/mill/scripts/_review_code.py`
  - `cfg["review"]["code"]["rounds"]` → `cfg["roles"]["code-review"]["batch"]["rounds"]` for per-batch invocations (when `batch_name is not None`); `cfg["roles"]["code-review"]["holistic"]["rounds"]` for holistic (when `batch_name is None`).
  - `cfg["review"]["code"]["reviewer"]` → split: per-batch uses `cfg["roles"]["code-review"]["batch"]["reviewer"]`; holistic uses `cfg["roles"]["code-review"]["holistic"]["reviewer"]`. The single `reviewer:` slot disappears entirely.
  - `cfg["review"]["code"]["holistic_effort"]` is removed; effort is encoded in the holistic reviewer entry.
  - `cfg["review"]["code"]["diff_scope_threshold"]` → `cfg["roles"]["code-review"]["diff_scope_threshold"]`.
- `plugins/mill/scripts/millpy-implement.py` and `millpy-implement-holistic.py`
  - `cfg.get("review", {}).get("code", {}).get("self_fix_rounds", 2)` → `cfg.get("roles", {}).get("implementer", {}).get("self_fix_rounds", 2)`.
- `plugins/mill/scripts/millpy-review-discussion.py`, `millpy-review-plan.py`, `millpy-review-code.py`
  - These pass `cfg` to the backend; the `--max-rounds` help-text references must update (`Override review.X.rounds` → `Override roles.X-review.<scope>.rounds`).

### Files that load reviewer modules (must rewire to registry)

Today every backend calls `_review_common.load_reviewer(name)` which `importlib.import_module(f"_reviewer_{name}")`. Under the new schema, backends call `_reviewers.resolve(registry, name) -> spec` and then `_reviewer_single.run(spec, prompt_text, ...)`. `load_reviewer` is removed; its docstring/import is dropped from `_review_common.py`. Existing call sites:

- `_review_discussion.py:71`, `_review_code.py:259`, `_review_plan.py:324, 330`.

`reviewer.MODE` reads (currently 7 occurrences across `_review_discussion.py`, `_review_plan.py`, `_review_code.py`) become `spec["tooluse"]` reads. Helper `build_tool_rule(mode)` keeps its `"bulk" | "tool-use"` API but is fed by `"tool-use" if spec.get("tooluse") else "bulk"`.

### `_reviewers.py` API (new helper)

```python
# Public:
def load(wiki_root: Path) -> dict[str, dict]:
    """Load wiki/reviewers.yaml, validate structure, return name → raw spec."""

def resolve(registry: dict, name: str) -> dict:
    """Resolve a reviewer name to a fully-flattened spec.

    For type=single: returns the spec dict ({type, provider, model, effort,
    tooluse}) verbatim, defaulting tooluse=False if absent.
    For type=cluster: returns the cluster spec with workers/handler `use:`
    references replaced by their fully-resolved single-specs (count preserved).
    Raises ReviewerError on missing name, missing provider, etc.

    Special case: name == "test_stub" returns
    {"type": "single", "provider": "test_stub", "tooluse": False}
    without consulting the registry.
    """

def resolve_role(cfg: dict, registry: dict, role: str, scope: str) -> dict | None:
    """Read cfg.roles.<role>.<scope>.reviewer; resolve via registry.
    Returns None if reviewer is null or rounds is zero. Otherwise returns the
    resolved spec dict (single or cluster)."""

def validate_role_refs(cfg: dict, registry: dict) -> None:
    """Walk cfg.roles.<role>.<scope>.reviewer for every (role, scope) pair;
    confirm each non-null name resolves. Raises ReviewerError with all
    missing names listed in the message."""

class ReviewerError(Exception): ...
```

The module lives at `plugins/mill/scripts/_reviewers.py` (flat scripts dir, no submodule). It shares the cwd-based scripts-dir layout.

### `_reviewer_single.py` (new module, replaces `_reviewer_sonnetmax*.py`)

```python
# plugins/mill/scripts/_reviewer_single.py
import importlib

def run(spec: dict, prompt_text: str, *,
        session_id: str | None = None,
        resume: bool = False,
        timeout: int | None = None) -> tuple[str, str]:
    """Dispatch a single-reviewer call.

    spec is a fully-flattened single spec ({type: "single", provider, model,
    effort, tooluse}). Imports _llm_<spec.provider> and calls run_bulk or
    run_tool_use based on spec.tooluse. Forwards session_id/resume/timeout.

    Cluster dispatch is detected here for safety: spec.type == "cluster" raises
    ReviewerError("cluster dispatch not yet implemented; see task 13") even
    though resolve_role is expected to deliver flattened cluster specs only
    when task 13 ships its runtime.
    """
    if spec["type"] == "cluster":
        raise ReviewerError("cluster dispatch not yet implemented; see task 13")
    provider = spec["provider"]
    if provider == "test_stub":
        import _reviewer_test_stub as stub
        return stub.run(prompt_text, session_id=session_id, resume=resume, timeout=timeout)
    llm = importlib.import_module(f"_llm_{provider}")
    fn = llm.run_tool_use if spec.get("tooluse") else llm.run_bulk
    extra = {} if timeout is None else {"timeout": timeout}
    return fn(prompt_text, model=spec["model"], effort=spec.get("effort"),
              session_id=session_id, resume=resume, **extra)
```

### `wiki/config.yaml` shape after rewrite

```yaml
roles:
  discussion-review:
    holistic:
      rounds: 2
      reviewer: sonnetmax_tool

  plan-review:
    batch:
      rounds: 3
      reviewer: null
    holistic:
      rounds: 3
      reviewer: sonnetmax

  code-review:
    batch:
      rounds: 3
      reviewer: sonnetmax
    holistic:
      rounds: 1
      reviewer: sonnetmax
    diff_scope_threshold: 0.25

  implementer:
    self_fix_rounds: 2

llm:
  bulk_timeout: 900
  holistic_timeout: 1800
  tool_use_timeout: 900
  implementer_timeout: 3600
```

All other top-level keys in `wiki/config.yaml` (`repo`, `junctions`, `hardlinks`, `spawn`, `git`, `paths`, `pipeline`, `notify`, `groom`, `merge`) remain unchanged.

### `wiki/reviewers.yaml` shape (live)

```yaml
sonnetmax:
  type: single
  provider: claude
  model: claude-sonnet-4-6
  effort: max

sonnetmax_tool:
  type: single
  provider: claude
  model: claude-sonnet-4-6
  effort: max
  tooluse: true

sonnetmedium:
  type: single
  provider: claude
  model: claude-sonnet-4-6
  effort: medium
```

The fresh-setup template at `plugins/mill/templates/reviewers.yaml` ships these three entries only — no Gemini, no clusters.

### Skill docs that must be updated

`grep -rn "review\.\(code\|plan\|discussion\)\." plugins/mill/skills/` finds matches in:

- `plugins/mill/skills/mill-go/SKILL.md` (lines 19–23, 106, 112, 140, 164–166, 198 — references `review.code.rounds`, `review.code.self_fix_rounds`, `review.code.holistic`, `review.code.holistic_rounds`, `review.code.per_batch`).
- `plugins/mill/skills/mill-plan/SKILL.md` (lines 15, 78, 106 — references `review.plan.rounds`, `review.code.self_fix_rounds`, `review.plan.batch`/`holistic`).
- `plugins/mill/skills/mill-start/SKILL.md` (line 15 — references `review.discussion.rounds`).

Each match becomes the new key path. `mill-go/SKILL.md`'s sentence about `review.code.holistic: true` flips to "if `roles.code-review.holistic.reviewer` is non-null, run one holistic code review after all batches approve". `review.code.per_batch: false` becomes "if `roles.code-review.batch.reviewer` is null (or `rounds: 0`), skip per-batch code review for all batches".

`SCRIPTS.md` (auto-generated) regenerates from the new docstrings.

### Test surface

`grep -rn "review\.\(code\|plan\|discussion\)\." plugins/mill/unit_tests/` shows fixture cfg-builders inside:

- `test-review-code-flow.py` (cfg dicts at lines 295, 346, 475, 685; test 14a constructs `cfg["review"]["code"]["holistic_effort"]` to assert effort propagation).
- `test-review-plan-flow.py` (cfg dicts in setup helpers).
- `test-review-discussion-flow.py`, `test-review-cli.py`, `test-review-common.py`, `test-llm-claude.py`, `test-millpy-implement.py` (line 85 inline yaml + line 120 dict), `test-millpy-implement-holistic.py` (lines 90, 131).
- `test-reviewer-modules.py` — the entire test-file checks `_reviewer_sonnetmax`/`_reviewer_sonnetmax_tool`. After the deletion (Decision "Delete _reviewer_sonnetmax*.py"), the file's purpose disappears. Replace it with a thinner `test-reviewer-single.py` that asserts `_reviewer_single.run` signature (spec + prompt_text + session_id + resume + timeout, no `effort` kwarg) and imports the module.

Test 14a (`holistic_effort='medium'` propagation) is rewritten to assert that pointing `roles.code-review.holistic.reviewer` at a different reviewer name produces a different effort in the captured stub call. Test 14b (per-batch passes `effort=None`) becomes redundant — the spec carries effort, so per-batch always passes whatever is in `roles.code-review.batch.reviewer`'s spec.

Add a small fixture helper (e.g. `plugins/mill/unit_tests/_test_cfg.py`) returning a baseline cfg dict for the new schema, so tests don't repeat the boilerplate. Add a parallel `_test_registry.py` returning a baseline `{name: spec}` registry dict for `_reviewers.resolve` callers.

New `plugins/mill/unit_tests/test-reviewers.py` covers:

- `load`: valid registry round-trips; missing required field per type; unknown type; invalid name regex; duplicate name.
- `resolve`: single returns spec; cluster `use:` references flatten; missing `use:` target raises; cycle detection raises (`A.handler.use → B`, `B.handler.use → A`); recursive cluster (`A.workers.use → B` where B is also a cluster) raises.
- `resolve_role`: `reviewer: null` returns None; `rounds: 0` returns None; valid name resolves to spec.
- `validate_role_refs`: every named reviewer resolves → no error; one missing name → ReviewerError lists it; multiple missing → ReviewerError lists all of them.
- `test_stub` special case: `resolve(registry, "test_stub")` returns synthetic spec without consulting the registry.

### Migration warning implementation

Inside `_review_common.load_config`, after the deep-merge succeeds, check `local_cfg.get("review")` (top-level key on the *overlay*, not the merged dict). If present and truthy, write a one-line stderr warning naming the path and the orphaned `review.*` keys. The warning is emitted once per process; subsequent calls to `load_config` re-emit (acceptable — the call is rare and the warning is cheap). The merged cfg is returned unchanged; the orphan branch sits at `cfg["review"]` but no consumer reads it.

### Atomic-commit boundary

The plan needs one batch (or two, if mill-plan splits "schema rewrite" from "consumer rewire") that does the schema flip in a single git commit:

- New: `wiki/reviewers.yaml`, `plugins/mill/templates/reviewers.yaml`, `plugins/mill/scripts/_reviewers.py`, `plugins/mill/scripts/_reviewer_single.py`, `plugins/mill/unit_tests/test-reviewers.py`, fixture helpers.
- Rewritten: `wiki/config.yaml`, `plugins/mill/templates/wiki-config.yaml`, `_review_discussion.py`, `_review_plan.py`, `_review_code.py`, `_review_common.py` (drop `load_reviewer` + add migration warning), `millpy-implement.py`, `millpy-implement-holistic.py`, every affected `test-*.py`, every `SKILL.md` with stale references.
- Deleted: `_reviewer_sonnetmax.py`, `_reviewer_sonnetmax_tool.py`, `test-reviewer-modules.py` (replaced by `test-reviewer-single.py`).

`_wiki.write_commit_push` handles the wiki-side commit; the script-side commit goes through normal `git -C <worktree>` calls. Both commits must land before any test re-runs against the new schema.

## Constraints

- **Plugin-installable paths (`${CLAUDE_PLUGIN_ROOT}`):** all new scripts (`_reviewers.py`, `_reviewer_single.py`) live under `plugins/mill/scripts/` and run from the plugin cache when invoked by external repos. Hard-coded `plugins/mill/...` paths are banned in any new code or template (per `CLAUDE.md`'s "Plugin scripts reference `${CLAUDE_PLUGIN_ROOT}`" rule).
- **Junctions are IDE convenience only.** `_reviewers.py` resolves `wiki/reviewers.yaml` via `_paths.resolve_wiki_path(git_root)`, never via `.wiki/`. Mirror the existing `load_config` pattern.
- **Working state stays on the task branch.** `task/discussion.md` (this file), `task/plan/`, `task/reviews/`, `task/status.md` are committed to `hanf/config-schema-refactor`. Nothing about this task touches the wiki except for `wiki/config.yaml` and `wiki/reviewers.yaml` (both are wiki-owned shared config).
- **Single-operator wiki, atomic migration.** No backwards-compatibility shim. The old `review:` keys do not coexist with `roles:` for any window.
- **YAGNI on cluster runtime, gemini provider, implementer registry.** Schema covers clusters; runtime ships in task 13. `_llm_gemini.py` ships in task 31. Implementer registry is not part of this scope.

No `CONSTRAINTS.md` exists at the project root.

## Testing

- **TDD candidate: `_reviewers.py`.** Write `test-reviewers.py` first; implement to green. Covers `load`, `resolve`, `resolve_role`, `validate_role_refs`, plus error cases (missing name, cycle, type mismatch, missing required field, invalid name regex, duplicate name, recursive cluster, `test_stub` special case).
- **TDD candidate: `_reviewer_single.py`.** Write `test-reviewer-single.py` first; assert `run` signature (`spec, prompt_text, *, session_id, resume, timeout`); use `_reviewer_test_stub` to verify the bulk-vs-tool-use branch; verify `spec.type == "cluster"` raises.
- **Backend rewrite: surgical edits to fixture cfg-builders.** Add `_test_cfg.make_minimal_cfg()` and `_test_registry.make_minimal_registry()` helpers. Convert each `test-review-*-flow.py` fixture in lockstep with the consumer's rewire. The flow tests' assertions about review behaviour should not change; only the cfg shape feeding them changes.
- **`millpy-implement` / `millpy-implement-holistic`:** update `test-millpy-implement.py` and `test-millpy-implement-holistic.py` cfg-yaml fragments and dict fixtures (`review.code.self_fix_rounds: 2` → `roles.implementer.self_fix_rounds: 2`).
- **End-to-end smoke after the rewrite:** run `python plugins/mill/unit_tests/run-all.py` from the task worktree. Every test must pass.
- **Migration-warning test:** add a focused test that writes a `.millhouse/config.local.yaml` containing `review: {}` and asserts `_review_common.load_config` emits the warning to stderr (capture via `capsys` or equivalent). Confirm the merged cfg is still well-formed.
- **Cross-validation test in `test-review-cli.py`:** assert that a registry missing a name referenced by `cfg.roles.*.<scope>.reviewer` causes the API script to exit non-zero with a clear stderr message.
- **Manual integration check:** after the schema flip lands, run `millpy-review-discussion.py` against the live wiki — it should resolve `roles.discussion-review.holistic.reviewer = sonnetmax_tool` via the new registry, dispatch `_llm_claude.run_tool_use`, and write a review file. Sanity check before mill-merge.

## Q&A log

- **Q:** Where does `holistic_timeout` live under the new schema? **A:** Stays flat under `llm:` alongside `bulk_timeout`, `tool_use_timeout`, `implementer_timeout`. Timeouts are LLM-provider concerns, not role concerns.
- **Q:** What replaces `cfg.review.code.holistic_effort`? **A:** Nothing. Effort is fully encoded in the named reviewer entry; pick a different reviewer name to get a different effort.
- **Q:** Does the resolver fully validate `type: cluster` entries even though dispatch is deferred? **A:** Yes — the schema is locked here; task 13 only writes runtime.
- **Q:** Can a cluster's `workers.use` or `handler.use` resolve to another cluster? **A:** No. Cluster `use:` resolves to `type: single` only. Cycle detection enforces it.
- **Q:** What characters are allowed in reviewer names? **A:** `[a-z0-9_-]+`. Both `sonnetmax_tool` and `g25flash-x3-sonnetmax` are valid.
- **Q:** Does `per_batch: false` survive in any form? **A:** No. `roles.<role>.<scope>.reviewer: null` (or `rounds: 0`) replaces it.
- **Q:** Does `holistic: true/false` survive? **A:** No. Presence of a non-null `holistic.reviewer` enables the scope.
- **Q:** Where does `diff_scope_threshold` live? **A:** `roles.code-review.diff_scope_threshold` (role level, applies to per-batch artefact bulking).
- **Q:** How does `_reviewer_test_stub.py` fit the registry? **A:** Hard-coded special case in `_reviewers.resolve` — `name == "test_stub"` returns a synthetic spec without consulting `reviewers.yaml`.
- **Q:** Does `MODE` survive on reviewer modules? **A:** No new uses; the dispatcher reads `spec.tooluse` instead. `_reviewer_test_stub.py` keeps its `MODE = "bulk"` for legacy callers.
- **Q:** Does `reviewers.yaml` accept a `.millhouse/reviewers.local.yaml` overlay? **A:** No. The registry is shared by definition.
- **Q:** What is `_reviewer_single.run`'s signature? **A:** `(spec, prompt_text, *, session_id=None, resume=False, timeout=None)`. No `effort` kwarg.
- **Q:** How does `_reviewer_single` find `_llm_<provider>`? **A:** `importlib.import_module(f"_llm_{spec['provider']}")`. Convention-based, no dispatch table.
- **Q:** What if registry validation fails? **A:** `_reviewers.load` raises `ReviewerError` eagerly with a clear error listing all problems.
- **Q:** What if `cfg.roles.X.reviewer: typo` references a missing registry entry? **A:** `_reviewers.validate_role_refs(cfg, registry)` (called at API-script startup) raises with all missing names listed.
- **Q:** Are effort values normalized across providers? **A:** No. Pass-through verbatim. Provider modules reject unknown values with their own errors.
- **Q:** Is `_implementer_sonnet.py` lifted into the registry? **A:** No — out of scope. `roles.implementer:` carries `self_fix_rounds` only; no `reviewer:` slot.
- **Q:** Atomic or staged migration of `wiki/config.yaml`? **A:** Atomic. One commit on the task branch rewrites both files together.
- **Q:** Are old reviewer files (`_reviewer_sonnetmax.py`, `_reviewer_sonnetmax_tool.py`) deleted in this task? **A:** Yes — same commit that introduces `_reviewer_single.py` and rewires consumers.
- **Q:** Does `_reviewer_cluster.py` exist as a stub? **A:** No file at all. The dispatcher raises `ReviewerError("cluster dispatch not yet implemented; see task 13")`.
- **Q:** Are skill docs (`mill-go/SKILL.md`, etc.) in scope? **A:** Yes — every match for `review\.\(code\|plan\|discussion\)\.` under `plugins/mill/skills/**/*.md` updates in lockstep.
- **Q:** Are test fixtures rewritten wholesale or shimmed? **A:** Wholesale rewrite. Add `_test_cfg.py` helpers to dedupe boilerplate.
- **Q:** What ships in `plugins/mill/templates/reviewers.yaml`? **A:** `sonnetmax`, `sonnetmedium`, `sonnetmax_tool`. No Gemini, no clusters.
- **Q:** Does the migration warn about stale `.millhouse/config.local.yaml` keys? **A:** Yes — stderr warning if the overlay's top-level `review:` key is present after the schema flip.
