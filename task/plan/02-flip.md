# Batch: flip

```yaml
task: 34 (A) — Config schema cleanup + reviewer registry
batch: flip
number: 2
cards: 10
verify: uv run --project plugins/mill python plugins/mill/unit_tests/run-all.py
depends-on: [1]
```

## Batch Scope

This batch atomically flips the world from the old `review:` umbrella to the new `roles:` schema. All consumers, all test fixtures, the live `wiki/config.yaml`, the fresh-setup templates, and the deletion of the now-unused `_reviewer_sonnetmax*` files happen in lockstep. After this batch, the unit-test suite passes against the new schema and no consumer reads any `review.*` key.

This is a wiki-config-mutation batch (it modifies `wiki/config.yaml`). Card 5 is the bootstrap card — it documents why the live config flip is safe mid-flight. Justification: every consumer of the affected keys is rewired in this same batch (cards 7–12), so by the time `verify` runs the consumers and the schema agree on shape. There is no version of the code that runs against the new schema with old consumer expectations or vice versa. The reviewer should accept `--skip-check wiki-config-mutation` at validator-fix time.

Batch-local decisions:

- The live wiki edit (`wiki/config.yaml` rewrite + `wiki/reviewers.yaml` create) goes through `_wiki.write_commit_push` so the wiki-side commit is locked, pushed, and propagates to other clones. Inline edits to wiki files via `Edit`/`Write` would skip the lock and the push; do NOT use them. The implementer reads `_wiki.py` to understand `write_commit_push`'s signature.
- All test fixtures across the eight affected `test-*.py` files migrate to the new shape in this batch. Adopt the helpers from card 3 (`_test_cfg.make_minimal_cfg`, `_test_registry.make_minimal_registry`) wherever they reduce boilerplate; otherwise rewrite the cfg dict literal in place. Do not leave any test file with a `cfg["review"][...]` reference.
- After card 14 deletes the old reviewer modules, no test or production code may import `_reviewer_sonnetmax` or `_reviewer_sonnetmax_tool`. Verify with a project-wide grep before commit.

## Cards

### Card 5: Live wiki schema flip — `wiki/config.yaml` and `wiki/reviewers.yaml`

- **Context:**
  - `task/discussion.md`
  - `plugins/mill/scripts/_wiki.py`
  - `plugins/mill/scripts/_paths.py`
- **Edits:**
  - `wiki/config.yaml`
- **Creates:**
  - `wiki/reviewers.yaml`
- **Deletes:** none
- **Requirements:**
  Bootstrap card for the schema flip. Modify the LIVE wiki via `_wiki.write_commit_push(wiki_path, paths, msg, slug=...)` — never via raw `Edit` or `Write` directly on the wiki path. Use a single `with _wiki.wiki_lock(wiki_path, slug=...)` block (or one combined `write_commit_push` call) so both files land in one wiki commit. Resolve `wiki_path` via `_paths.resolve_wiki_path(_paths.resolve_git_root())` exactly as other consumers do.
  Final `wiki/config.yaml` shape:
  - Preserve every top-level key currently in the file: `repo`, `junctions`, `hardlinks`, `spawn`, `git` (commented section if present), `paths`, `pipeline`, `notify`, `groom`, `merge`. Their content is unchanged.
  - Replace the entire `review:` block with a `roles:` block:
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
    ```
  - Keep the `llm:` section flat with all four timeout keys: `bulk_timeout: 900`, `holistic_timeout: 1800`, `tool_use_timeout: 900`, `implementer_timeout: 3600`. Match the values currently in the live file.
  - Update the `Layer 02: file-path templates` comment block above `paths:` to remove the obsolete `<SLUG>` token note (since the live file's `paths:` already does not use `<SLUG>`).
  Final `wiki/reviewers.yaml` content (live file): three single-spec entries:
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
  Top-of-file comment block on `wiki/reviewers.yaml` documents that this is the registry consumed by `_reviewers.py`, that names match `[a-z0-9_-]+`, and that `type:` is `single` or `cluster`. The wiki commit message is `mill-go: refactor config schema (task 34)`.
- **Commit:** `feat(schema): flip live wiki/config.yaml to roles + add wiki/reviewers.yaml`

### Card 6: Fresh-setup template defaults

- **Context:**
  - `task/discussion.md`
  - `wiki/config.yaml`
  - `wiki/reviewers.yaml`
- **Edits:**
  - `plugins/mill/templates/wiki-config.yaml`
- **Creates:**
  - `plugins/mill/templates/reviewers.yaml`
- **Deletes:** none
- **Requirements:**
  Rewrite `plugins/mill/templates/wiki-config.yaml` so the `review:` block is replaced by the same `roles:` block as the live file (card 5), with adjusted defaults appropriate for fresh setups: `roles.discussion-review.holistic.reviewer: sonnetmax_tool` and `rounds: 2`; `roles.plan-review.batch: {rounds: 3, reviewer: sonnetmax}`; `roles.plan-review.holistic: {rounds: 3, reviewer: sonnetmax}`; `roles.code-review.batch: {rounds: 3, reviewer: sonnetmax}`; `roles.code-review.holistic: {rounds: 1, reviewer: sonnetmax}`; `roles.code-review.diff_scope_threshold: 0.25`; `roles.implementer.self_fix_rounds: 2`. Update the `llm:` block to include `holistic_timeout: 1800` (the existing template lacks it). Preserve all other top-level keys (repo, junctions, hardlinks, spawn, git comment block, paths, pipeline, notify, groom, merge) unchanged. The header comment at the top of the file mentions the new `roles:` shape.
  Create `plugins/mill/templates/reviewers.yaml` containing three single-spec entries (same shape as the live `wiki/reviewers.yaml` from card 5: `sonnetmax`, `sonnetmax_tool`, `sonnetmedium`). Top-of-file comment notes this is a fresh-setup default copied to `wiki/reviewers.yaml` by mill-setup.
- **Commit:** `feat(templates): mirror new schema in wiki-config.yaml + add reviewers.yaml`

### Card 7: Rewire `_review_common.py` — drop `load_reviewer`, add overlay warning

- **Context:**
  - `task/discussion.md`
  - `plugins/mill/scripts/_reviewers.py`
- **Edits:**
  - `plugins/mill/scripts/_review_common.py`
- **Creates:** none
- **Deletes:** none
- **Requirements:**
  - Delete the `load_reviewer(name)` function (currently at the bottom of the module). Remove its docstring entry from the module-level public-API listing at the top of the file. The replacement is `_reviewers.resolve` and `_reviewer_single.run` — backends import those directly.
  - Modify `load_config(wiki_root, mill_dir)`: after the deep-merge succeeds, check `local_cfg.get("review")` (top-level key on the OVERLAY dict, not the merged dict). If present and truthy, write a one-line stderr warning naming the overlay path (`local_path`) and the orphaned keys (sorted list of `local_cfg["review"].keys()`). Do not crash. The merged cfg is returned unchanged. The check uses the overlay loaded inside `load_config` — capture `local_cfg` BEFORE the deep-merge call so the overlay's top-level keys are still inspectable. The warning writes to `sys.stderr` via `print(..., file=sys.stderr)`.
  - The `aggregate_verdict` and other helpers in `_review_common.py` are untouched.
- **Commit:** `refactor(review): drop load_reviewer; warn on stale review: overlay`

### Card 8: Rewire `_review_discussion.py`

- **Context:**
  - `task/discussion.md`
  - `plugins/mill/scripts/_reviewers.py`
  - `plugins/mill/scripts/_reviewer_single.py`
  - `plugins/mill/scripts/_review_common.py`
- **Edits:**
  - `plugins/mill/scripts/_review_discussion.py`
- **Creates:** none
- **Deletes:** none
- **Requirements:**
  Rewire `run(cfg, slug, mill_dir, project_root, *, max_rounds=None)` to read from the new schema. Concretely:
  - Replace `max_rounds = ... cfg["review"]["discussion"]["rounds"]` with `cfg["roles"]["discussion-review"]["holistic"]["rounds"]`.
  - Replace `reviewer_name = cfg["review"]["discussion"]["holistic"]` with `reviewer_name = cfg["roles"]["discussion-review"]["holistic"]["reviewer"]`. If `reviewer_name is None`, raise `ReviewError(f"discussion-review holistic reviewer is null; nothing to do")`.
  - Replace `reviewer = load_reviewer(reviewer_name)` with: load the registry once via `_reviewers.load(_paths.resolve_wiki_path(_paths.resolve_git_root()))`, then `spec = _reviewers.resolve(registry, reviewer_name)`. Reads of `reviewer.MODE` (lines 72, 75) become `mode = "tool-use" if spec.get("tooluse") else "bulk"`; build_tool_rule(mode); `if mode == "tool-use": ... else: ...`.
  - Replace `reviewer.run(prompt_text)` with `_reviewer_single.run(spec, prompt_text)`.
  - Imports: drop `from _review_common import ... load_reviewer ...` and add `_reviewers` and `_reviewer_single` imports as needed. Drop the `from _llm_claude import LLMError` only if still unused; LLMError is still raised by `_reviewer_single.run` indirectly via the LLM provider, so keep it for the `except LLMError` block.
- **Commit:** `refactor(review): wire _review_discussion to roles + registry`

### Card 9: Rewire `_review_plan.py`

- **Context:**
  - `task/discussion.md`
  - `plugins/mill/scripts/_reviewers.py`
  - `plugins/mill/scripts/_reviewer_single.py`
  - `plugins/mill/scripts/_review_common.py`
- **Edits:**
  - `plugins/mill/scripts/_review_plan.py`
- **Creates:** none
- **Deletes:** none
- **Requirements:**
  Rewire `run(cfg, slug, mill_dir, wiki_root, project_root, *, max_rounds=None, holistic_only=False, no_holistic=False)` and the helper `_review_one_batch(...)` to read from the new schema:
  - The single `max_rounds = cfg["review"]["plan"]["rounds"]` is split. Per-batch `_review_one_batch` reads `batch_max_rounds = cfg["roles"]["plan-review"]["batch"]["rounds"]` for its round-cap check (line 124). The holistic round-cap check (line 433) reads `cfg["roles"]["plan-review"]["holistic"]["rounds"]`. The signature parameter `max_rounds` continues to act as a CLI override; when set, it CLAMPS BOTH (each scope's effective max becomes `min(scope_rounds, max_rounds)` if max_rounds is not None, else `scope_rounds`).
  - Replace `cfg["review"]["plan"]["batch"]` with `cfg["roles"]["plan-review"]["batch"]["reviewer"]` and `cfg["review"]["plan"]["holistic"]` with `cfg["roles"]["plan-review"]["holistic"]["reviewer"]`. Skip semantics — `reviewer is None OR rounds == 0` — applies to both scopes.
  - Replace `load_reviewer(name)` calls with `_reviewers.load(...)` once at the top of `run`, then `spec = _reviewers.resolve(registry, reviewer_name)`. Pass the per-scope spec into `_review_one_batch` instead of the reviewer module. Inside `_review_one_batch`, replace `batch_reviewer.MODE` (lines 145, 150) with `("tool-use" if spec.get("tooluse") else "bulk")`. Same for the holistic block (lines 457, 461).
  - Replace `batch_reviewer.run(prompt_text, timeout=...)` and `holistic_reviewer.run(prompt_text, timeout=...)` with `_reviewer_single.run(spec, prompt_text, timeout=...)`. Keep the resume retry calls (`session_id=..., resume=True, timeout=...`) intact — `_reviewer_single.run` forwards those.
  - Imports: drop `load_reviewer`; add `_reviewers` + `_reviewer_single`.
  - Remove `cfg["review"]["plan"].get("holistic") is None` checks at line 316 — they become `cfg["roles"]["plan-review"]["holistic"]["reviewer"] is None`.
- **Commit:** `refactor(review): wire _review_plan to roles + registry`

### Card 10: Rewire `_review_code.py`

- **Context:**
  - `task/discussion.md`
  - `plugins/mill/scripts/_reviewers.py`
  - `plugins/mill/scripts/_reviewer_single.py`
  - `plugins/mill/scripts/_review_common.py`
- **Edits:**
  - `plugins/mill/scripts/_review_code.py`
- **Creates:** none
- **Deletes:** none
- **Requirements:**
  Rewire `run(cfg, slug, mill_dir, wiki_root, project_root, *, max_rounds=None, batch_name=None, extra_files=None)`:
  - Replace `max_rounds = ... cfg["review"]["code"]["rounds"]` with: when `batch_name is not None`, read `cfg["roles"]["code-review"]["batch"]["rounds"]`; when `batch_name is None`, read `cfg["roles"]["code-review"]["holistic"]["rounds"]`. The `max_rounds` parameter clamps per the same rule as `_review_plan` (single CLI override clamps both scopes; backend picks the right scope based on `batch_name`).
  - Delete `holistic_effort` reads (line 258). The reviewer's effort is now encoded in the registry entry; no per-call override exists. Remove the `effort=holistic_effort` kwargs at lines 287 and 324.
  - Replace `cfg["review"]["code"]["reviewer"]` (line 257) with: when `batch_name is not None`, `cfg["roles"]["code-review"]["batch"]["reviewer"]`; when `batch_name is None`, `cfg["roles"]["code-review"]["holistic"]["reviewer"]`. Skip semantics applies (null reviewer means the call should not have been made — raise `ReviewError` with a clear message because the orchestrator should have skipped).
  - Replace `load_reviewer(reviewer_name)` with `_reviewers.load(...)` at the top of `run`, then `spec = _reviewers.resolve(registry, reviewer_name)`. Reads of `reviewer.MODE` (lines 263, 265) become `("tool-use" if spec.get("tooluse") else "bulk")`. Replace `reviewer.run(prompt_text, timeout=timeout, effort=holistic_effort)` (line 287) and the resume retry call (line 324) with `_reviewer_single.run(spec, prompt_text, timeout=timeout)`.
  - Replace `cfg["review"]["code"].get("diff_scope_threshold", 0.25)` (line 204) with `cfg["roles"]["code-review"].get("diff_scope_threshold", 0.25)`.
  - Imports: drop `load_reviewer`; add `_reviewers` + `_reviewer_single`.
- **Commit:** `refactor(review): wire _review_code to roles + registry`

### Card 11: Rewire `millpy-implement.py` and `millpy-implement-holistic.py`

- **Context:**
  - `task/discussion.md`
- **Edits:**
  - `plugins/mill/scripts/millpy-implement.py`
  - `plugins/mill/scripts/millpy-implement-holistic.py`
- **Creates:** none
- **Deletes:** none
- **Requirements:**
  In both scripts, replace `cfg.get("review", {}).get("code", {}).get("self_fix_rounds", 2)` with `cfg.get("roles", {}).get("implementer", {}).get("self_fix_rounds", 2)`. Currently this assignment lives at `millpy-implement.py:97` and `millpy-implement-holistic.py:81`. The `SELF_FIX_ROUNDS` template token is unaffected; only its source key changes.
- **Commit:** `refactor(implementer): read self_fix_rounds from roles.implementer`

### Card 12: Rewire `millpy-review-discussion.py`, `millpy-review-plan.py`, `millpy-review-code.py`

- **Context:**
  - `task/discussion.md`
  - `plugins/mill/scripts/_reviewers.py`
  - `plugins/mill/scripts/_review_common.py`
- **Edits:**
  - `plugins/mill/scripts/millpy-review-discussion.py`
  - `plugins/mill/scripts/millpy-review-plan.py`
  - `plugins/mill/scripts/millpy-review-code.py`
- **Creates:** none
- **Deletes:** none
- **Requirements:**
  - In each of the three CLIs, after `cfg = _review_common.load_config(...)` succeeds, load the registry: `registry = _reviewers.load(wiki_path)`. Then call `_reviewers.validate_role_refs(cfg, registry)`. If it raises, print `str(exc)` to stderr and `return 1` (or the script's existing error-exit pattern).
  - Update `--max-rounds` argparse `help` text:
    - `millpy-review-discussion.py`: `Override roles.discussion-review.holistic.rounds for this invocation. Default: use config value.` (currently references `review.discussion.rounds`).
    - `millpy-review-plan.py`: `Override roles.plan-review.batch.rounds and roles.plan-review.holistic.rounds (clamps both) for this invocation. Default: use config values.` (currently references `review.plan.rounds`).
    - `millpy-review-code.py`: `Override roles.code-review.batch.rounds and roles.code-review.holistic.rounds (clamps both) for this invocation. Default: use config values.` (currently references `review.code.rounds`).
  - Update the module-level docstring `--max-rounds <N>` line in each CLI to match the help text.
  - Confirm that the existing CLI handing of `--max-rounds` flows into the backend's `max_rounds` parameter unchanged. The backends now apply the clamp internally per cards 9 and 10.
- **Commit:** `refactor(review-cli): validate role refs at startup; update --max-rounds help`

### Card 13: Migrate test fixtures across all affected `test-*.py`

- **Context:**
  - `task/discussion.md`
  - `plugins/mill/unit_tests/_test_cfg.py`
  - `plugins/mill/unit_tests/_test_registry.py`
- **Edits:**
  - `plugins/mill/unit_tests/test-review-discussion-flow.py`
  - `plugins/mill/unit_tests/test-review-plan-flow.py`
  - `plugins/mill/unit_tests/test-review-code-flow.py`
  - `plugins/mill/unit_tests/test-review-cli.py`
  - `plugins/mill/unit_tests/test-review-common.py`
  - `plugins/mill/unit_tests/test-llm-claude.py`
  - `plugins/mill/unit_tests/test-millpy-implement.py`
  - `plugins/mill/unit_tests/test-millpy-implement-holistic.py`
- **Creates:** none
- **Deletes:** none
- **Requirements:**
  Rewrite every cfg-builder fixture inside the listed test files to the new schema. The mechanical conversion table:
  - `cfg["review"]["discussion"]["rounds"]` → `cfg["roles"]["discussion-review"]["holistic"]["rounds"]`.
  - `cfg["review"]["discussion"]["holistic"]` → `cfg["roles"]["discussion-review"]["holistic"]["reviewer"]`.
  - `cfg["review"]["plan"]["rounds"]` → both `cfg["roles"]["plan-review"]["batch"]["rounds"]` and `cfg["roles"]["plan-review"]["holistic"]["rounds"]` (use the same int).
  - `cfg["review"]["plan"]["batch"]` → `cfg["roles"]["plan-review"]["batch"]["reviewer"]`.
  - `cfg["review"]["plan"]["holistic"]` → `cfg["roles"]["plan-review"]["holistic"]["reviewer"]`.
  - `cfg["review"]["code"]["rounds"]` → both `cfg["roles"]["code-review"]["batch"]["rounds"]` and `cfg["roles"]["code-review"]["holistic"]["rounds"]`.
  - `cfg["review"]["code"]["reviewer"]` → both `cfg["roles"]["code-review"]["batch"]["reviewer"]` and `cfg["roles"]["code-review"]["holistic"]["reviewer"]` (same name).
  - `cfg["review"]["code"]["self_fix_rounds"]` → `cfg["roles"]["implementer"]["self_fix_rounds"]`.
  - `cfg["review"]["code"]["diff_scope_threshold"]` → `cfg["roles"]["code-review"]["diff_scope_threshold"]`.
  - Delete every `cfg["review"]["code"]["holistic"]` boolean and every `cfg["review"]["code"]["per_batch"]` boolean — replace with the appropriate scope's `reviewer: null` for skip semantics. Tests that previously asserted `holistic: true` behaviour now set `cfg["roles"]["code-review"]["holistic"]["reviewer"] = "test_stub"`; tests that asserted `holistic: false` set `reviewer: null`.
  - Delete every `cfg["review"]["code"]["holistic_rounds"]` reference — its value moves into `cfg["roles"]["code-review"]["holistic"]["rounds"]`.
  - Delete every `cfg["review"]["code"]["holistic_effort"]` reference — it has no replacement. `test-review-code-flow.py` test 14a asserted `holistic_effort='medium'` propagation; rewrite the test to instead seed two registry entries (`sonnetmax` for batch with `effort: max`, `sonnetmedium` for holistic with `effort: medium`), wire `cfg.roles.code-review.batch.reviewer = "sonnetmax"` and `holistic.reviewer = "sonnetmedium"`, and assert via the `_reviewer_test_stub` captured kwargs that the holistic and per-batch calls saw different `model` or `effort` values resolved through the registry. Test 14b's "per-batch passes effort=None" assertion becomes redundant and should be deleted; the new contract is that effort always comes from the resolved spec.
  - Inline yaml fragments (e.g. `test-millpy-implement.py:85` writing `"review:\n  code:\n    self_fix_rounds: 2\n"` as text) flip to `"roles:\n  implementer:\n    self_fix_rounds: 2\n"`.
  - Where a fixture builds a multi-key cfg dict from scratch, prefer importing `make_minimal_cfg` from `_test_cfg` and applying overrides; this keeps each test's intent readable. Inline cfg dicts that exist solely to demonstrate one schema shape can be simplified accordingly.
  - Tests that previously imported `from _review_common import load_reviewer` (e.g. via flow setups that look up the test stub) must change to import `_reviewers` and call `_reviewers.resolve(registry, "test_stub")` to obtain the stub spec, then pass the spec into the backend through whatever wiring the flow tests use. The `_reviewer_test_stub.seed(...)` and `_reviewer_test_stub.captured_prompts()` calls remain unchanged.
  - After rewiring, no test file may contain any `cfg["review"]` reference. Verify with grep.
- **Commit:** `test(review): migrate fixtures to roles + registry schema`

### Card 14: Delete `_reviewer_sonnetmax*.py` and `test-reviewer-modules.py`

- **Context:**
  - `task/discussion.md`
- **Edits:** none
- **Creates:** none
- **Deletes:**
  - `plugins/mill/scripts/_reviewer_sonnetmax.py`
  - `plugins/mill/scripts/_reviewer_sonnetmax_tool.py`
  - `plugins/mill/unit_tests/test-reviewer-modules.py`
- **Requirements:**
  Remove the three files. Search the project for any remaining import or reference to `_reviewer_sonnetmax`, `_reviewer_sonnetmax_tool`, or `test-reviewer-modules`; the search must be empty before commit. Remove the corresponding entry from `plugins/mill/unit_tests/run-all.py` (the runner's discovery list/loop) so it does not try to invoke the deleted test module — adopt whatever the runner's existing pattern is.
- **Commit:** `chore(review): remove _reviewer_sonnetmax* and test-reviewer-modules`

## Batch Tests

`verify: uv run --project plugins/mill python plugins/mill/unit_tests/run-all.py`. After this batch, the full unit-test suite passes against the new schema. Tests expected to be exercised heavily by the verify run: `test-reviewers.py`, `test-reviewer-single.py`, `test-review-discussion-flow.py`, `test-review-plan-flow.py`, `test-review-code-flow.py`, `test-review-common.py`, `test-review-cli.py`, `test-llm-claude.py`, `test-millpy-implement.py`, `test-millpy-implement-holistic.py`. The deleted `test-reviewer-modules.py` must NOT be invoked. A grep for `cfg\["review"\]` across `plugins/mill/` returns zero matches.
