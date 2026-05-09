# Batch: foundations

```yaml
task: 34 (A) — Config schema cleanup + reviewer registry
batch: foundations
number: 1
cards: 4
verify: uv run --project plugins/mill python plugins/mill/unit_tests/run-all.py
depends-on: []
```

## Batch Scope

This batch introduces the new resolver helper and the new reviewer dispatcher alongside the existing reviewer modules. No consumer is rewired; no schema is flipped; no test fixture changes shape. The intent is to land the new code with its own tests passing while every existing test continues to pass against the old schema. Batch 2 then atomically flips the world to use these helpers.

External interface batch 2 will consume:

- `_reviewers.load(wiki_root: Path) -> dict[str, dict]`
- `_reviewers.resolve(registry: dict, name: str) -> dict`
- `_reviewers.resolve_role(cfg: dict, registry: dict, role: str, scope: str) -> dict | None`
- `_reviewers.validate_role_refs(cfg: dict, registry: dict) -> None`
- `_reviewers.ReviewerError` (Exception subclass)
- `_reviewer_single.run(spec: dict, prompt_text: str, *, session_id: str | None = None, resume: bool = False, timeout: int | None = None) -> tuple[str, str]`

Batch-local decisions:

- The `test_stub` carve-out is implemented in BOTH `_reviewers.resolve` and `_reviewer_single.run`. Resolve returns the synthetic spec without consulting the registry; run forwards to `_reviewer_test_stub.run` without doing any provider import. Either layer alone covers the test surface; both are present for symmetry.
- `_reviewers.load` reads `wiki_root / "reviewers.yaml"` exactly. No local overlay, no merge with other files.
- All test fixtures introduced in this batch use the NEW schema shapes (cfg with `roles:`; registries shaped per the new spec). The existing fixtures in `test-review-*-flow.py` etc. remain on the old shape until batch 2 migrates them.

## Cards

### Card 1: Create `_reviewers.py` resolver helper

- **Context:**
  - `task/discussion.md`
  - `plugins/mill/scripts/_review_common.py`
  - `plugins/mill/scripts/_paths.py`
- **Edits:** none
- **Creates:**
  - `plugins/mill/scripts/_reviewers.py`
- **Deletes:** none
- **Requirements:**
  Create a new module `_reviewers.py` in the flat scripts dir. The module exposes:
  - `class ReviewerError(Exception)` — raised on every validation/resolution failure.
  - `_NAME_REGEX = re.compile(r"^[a-z0-9_-]+$")` — module-level regex.
  - `load(wiki_root: Path) -> dict[str, dict]`: reads `wiki_root / "reviewers.yaml"` via `yaml.safe_load`. Raises `ReviewerError(f"Missing registry at {path}")` if the file is absent. Validates structure: every entry has `type` in `{"single", "cluster"}`; every name matches `_NAME_REGEX`; for `type: single` requires `provider` (string) and `model` (string); `effort` is optional (string or null); `tooluse` is optional (bool, default false); for `type: cluster` requires both `workers: { use: <name>, count: <positive int> }` and `handler: { use: <name> }`. Detect duplicate top-level keys by reading the file as text and parsing with a custom yaml loader that overrides `construct_mapping` to flag duplicates (or by comparing `len(yaml.safe_load(text))` against the count of top-level `^[a-z0-9_-]+:` lines). After per-entry validation, walk every cluster's `workers.use` and `handler.use`: each must reference a name present in the registry AND that name's `type` must equal `"single"` (no nested clusters). Then run a generic cycle-detection DFS over `use:` edges (defensive — given the no-nested-cluster rule, no cycle should be reachable, but the check guards against future relaxation). Returns the validated raw registry dict (name → entry dict). Raises `ReviewerError` listing every problem in a single message.
  - `resolve(registry: dict, name: str) -> dict`: special case — if `name == "test_stub"`, return `{"type": "single", "provider": "test_stub", "tooluse": False}` immediately without consulting the registry. Otherwise look up `name` in registry; raise `ReviewerError(f"Unknown reviewer: {name!r}")` if missing. Defensive type guard: if the looked-up entry's `type` is not in `{"single", "cluster"}`, raise `ReviewerError(f"Unknown reviewer type: {spec['type']!r}")` (this guard is unreachable if `load` validated correctly, but protects direct callers that bypass `load`). For `type: single`: return a copy of the entry with `tooluse` defaulted to `False` if absent. For `type: cluster`: return a copy of the entry with `workers.use` and `handler.use` replaced by the fully-resolved single-spec dicts (recursive `resolve` call on each `use:` value, but since cluster `use:` only references singles by load-time validation, recursion is bounded at depth 1).
  - `resolve_role(cfg: dict, registry: dict, role: str, scope: str) -> dict | None`: reads `cfg["roles"][role][scope]`. If the subsection is missing, raise `ReviewerError(f"Missing roles.{role}.{scope} in config")`. Read `reviewer` and `rounds`. If `reviewer is None` OR `rounds == 0`, return `None`. Otherwise call `resolve(registry, reviewer)` and return the result.
  - `validate_role_refs(cfg: dict, registry: dict) -> None`: walks every (role, scope) pair across `cfg["roles"]` where the subsection has a `reviewer` key. For each non-null `reviewer` name, attempt `resolve(registry, name)`. Collect all `ReviewerError` messages; if non-empty, raise a single `ReviewerError` whose message lists every (role, scope, name) → error.
  Module docstring documents the public API per the discussion's "_reviewers.py API" section. Use `yaml` from PyYAML and `importlib`/`re` from stdlib. No other imports from the millhouse codebase.
- **Commit:** `feat(reviewers): add registry resolver _reviewers.py`

### Card 2: Create `_reviewer_single.py` dispatcher

- **Context:**
  - `task/discussion.md`
  - `plugins/mill/scripts/_llm_claude.py`
  - `plugins/mill/scripts/_reviewer_test_stub.py`
  - `plugins/mill/scripts/_reviewer_sonnetmax.py`
  - `plugins/mill/scripts/_reviewer_sonnetmax_tool.py`
  - `plugins/mill/scripts/_reviewers.py`
- **Edits:** none
- **Creates:**
  - `plugins/mill/scripts/_reviewer_single.py`
- **Deletes:** none
- **Requirements:**
  Create a new module `_reviewer_single.py` whose only public surface is `run`. Signature: `run(spec: dict, prompt_text: str, *, session_id: str | None = None, resume: bool = False, timeout: int | None = None) -> tuple[str, str]`. Behaviour:
  - If `spec["type"] == "cluster"`: import `_reviewers.ReviewerError` and raise `_reviewers.ReviewerError("cluster dispatch not yet implemented; see task 13")`.
  - If `spec.get("provider") == "test_stub"`: import `_reviewer_test_stub` and call `_reviewer_test_stub.run(prompt_text, session_id=session_id, resume=resume, timeout=timeout)`. Do not pass `effort` to the stub.
  - Otherwise: import `_llm_<spec["provider"]>` via `importlib.import_module(f"_llm_{spec['provider']}")`. Catch `ImportError` and reraise as `_reviewers.ReviewerError(f"Unknown provider: {spec['provider']!r}")`. Pick the function: `fn = llm.run_tool_use if spec.get("tooluse") else llm.run_bulk`. Build kwargs: `{"model": spec["model"], "effort": spec.get("effort"), "session_id": session_id, "resume": resume}`; include `"timeout": timeout` only when `timeout is not None`. Call `fn(prompt_text, **kwargs)` and return its result.
  Module docstring describes the spec contract and the dispatch logic. No `MODE` constant on this module.
- **Commit:** `feat(reviewers): add _reviewer_single dispatcher`

### Card 3: Create unit-test fixture helpers

- **Context:**
  - `task/discussion.md`
  - `plugins/mill/unit_tests/test-review-discussion-flow.py`
  - `plugins/mill/unit_tests/test-review-code-flow.py`
- **Edits:** none
- **Creates:**
  - `plugins/mill/unit_tests/_test_cfg.py`
  - `plugins/mill/unit_tests/_test_registry.py`
- **Deletes:** none
- **Requirements:**
  - `_test_cfg.py` exposes `make_minimal_cfg(**overrides) -> dict` returning a baseline cfg dict that uses the NEW schema shape: top-level `roles:` with `discussion-review` (`holistic: {rounds: 2, reviewer: "test_stub"}`), `plan-review` (`batch: {rounds: 3, reviewer: "test_stub"}` and `holistic: {rounds: 3, reviewer: "test_stub"}`), `code-review` (`batch: {rounds: 3, reviewer: "test_stub"}`, `holistic: {rounds: 1, reviewer: "test_stub"}`, `diff_scope_threshold: 0.25`), `implementer: {self_fix_rounds: 0}`. Top-level `paths:` (`discussion_file`, `plan_dir`, `reviews_dir`), `llm:` (`bulk_timeout: 600`, `tool_use_timeout: 900`, `holistic_timeout: 1800`, `implementer_timeout: 1800`), `pipeline:`, `notify:`, `groom:`, `merge:`, `repo:`, `spawn:` populated with sensible defaults that mirror the live `wiki/config.yaml` shape *after* the batch-2 flip. The `**overrides` kwargs deep-merge into the baseline (use a small inline `_deep_merge` helper or import the one from `_review_common`).
  - `_test_registry.py` exposes `make_minimal_registry(**overrides) -> dict` returning a baseline registry dict containing at minimum a `sonnetmax` single-spec (`{"type": "single", "provider": "claude", "model": "claude-sonnet-4-6", "effort": "max"}`) and a `sonnetmax_tool` single-spec (with `tooluse: true`). Overrides deep-merge.
  Both modules are pure data builders — no I/O, no subprocess calls. Top-level docstring on each describes the helper.
- **Commit:** `test(fixtures): add _test_cfg and _test_registry helpers`

### Card 4: Tests for `_reviewers.py` and `_reviewer_single.py`

- **Context:**
  - `task/discussion.md`
  - `plugins/mill/unit_tests/test-reviewer-modules.py`
  - `plugins/mill/unit_tests/test-llm-claude.py`
  - `plugins/mill/unit_tests/_test_cfg.py`
  - `plugins/mill/unit_tests/_test_registry.py`
  - `plugins/mill/scripts/_reviewers.py`
  - `plugins/mill/scripts/_reviewer_single.py`
  - `plugins/mill/scripts/_reviewer_test_stub.py`
- **Edits:** none
- **Creates:**
  - `plugins/mill/unit_tests/test-reviewers.py`
  - `plugins/mill/unit_tests/test-reviewer-single.py`
- **Deletes:** none
- **Requirements:**
  - `test-reviewers.py` covers `_reviewers.load`, `_reviewers.resolve`, `_reviewers.resolve_role`, `_reviewers.validate_role_refs`. Subtests:
    1. `load` happy path on a temp wiki dir with a valid `reviewers.yaml` — registry round-trips.
    2. `load` raises on missing file.
    3. `load` raises on missing required field per type (`single` without `provider`; `cluster` without `workers`; `cluster` without `handler`; cluster `workers.count` non-positive).
    4. `load` raises on unknown `type`.
    5. `load` raises on invalid name regex (uppercase, dot, slash).
    6. `load` raises on duplicate name.
    7. `load` raises on cluster `use:` referencing a non-existent name.
    8. `load` raises on cluster `use:` referencing another cluster.
    9. `resolve` happy path for `single`.
    10. `resolve` happy path for `cluster` (workers/handler `use:` flatten to fully-resolved single-specs).
    11. `resolve` raises on missing name.
    12. `resolve("test_stub")` returns synthetic spec without consulting the registry.
    13. `resolve_role` reads `cfg.roles.<role>.<scope>.reviewer`; null reviewer returns `None`; `rounds: 0` returns `None`; valid name returns spec.
    14. `validate_role_refs` happy path; missing reference raises with all missing names listed.
  - `test-reviewer-single.py` covers `_reviewer_single.run`:
    1. Signature inspection via `inspect.signature` — parameters `spec, prompt_text, session_id, resume, timeout` (no `effort`).
    2. `spec.type == "cluster"` raises `ReviewerError`.
    3. `spec.provider == "test_stub"` forwards to `_reviewer_test_stub.run` and the captured prompt round-trips. Do NOT assert anything about `effort` or `model` in the captured stub kwargs — `_reviewer_single.run` deliberately does not forward `effort`/`model` to the test stub. The effort/model forwarding contract is asserted in subtests 4 and 5 below (where `_llm_claude.run_bulk` / `run_tool_use` is mocked).
    4. `spec.provider == "claude"` with `tooluse: false` calls `_llm_claude.run_bulk` with `model=spec["model"]`, `effort=spec["effort"]`. Use monkey-patching: replace `_llm_claude.run_bulk` with a recording stub, restore after.
    5. Same as 4 but with `tooluse: true` calls `_llm_claude.run_tool_use`.
    6. Unknown provider (e.g. `provider: gemini`) raises `ReviewerError` with `"Unknown provider"` substring.
  - `run-all.py` requires no source change: it discovers tests via `HERE.glob("test-*.py")` so the new files are picked up automatically.
- **Commit:** `test(reviewers): cover _reviewers and _reviewer_single`

## Batch Tests

`verify: uv run --project plugins/mill python plugins/mill/unit_tests/run-all.py`. The new test modules (`test-reviewers.py`, `test-reviewer-single.py`) must pass. Every existing test must continue to pass — this batch does not touch any consumer or schema. After this batch, `_reviewer_sonnetmax.py` and `_reviewer_sonnetmax_tool.py` still exist and are still imported by the existing backends.
