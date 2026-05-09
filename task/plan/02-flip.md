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
  Rewire `run` to read from the new schema. Concretely:
  - Extend the signature to accept `wiki_root: Path` as a keyword-only parameter, mirroring `_review_plan.run` and `_review_code.run`. New signature: `run(cfg, slug, mill_dir, wiki_root, project_root, *, max_rounds=None)` (positional after `mill_dir`). The CLI caller in `millpy-review-discussion.py` already resolves `wiki_root` and now passes it down (see card 12 for the CLI update).
  - Replace `max_rounds = ... cfg["review"]["discussion"]["rounds"]` with `cfg["roles"]["discussion-review"]["holistic"]["rounds"]`.
  - Replace `reviewer_name = cfg["review"]["discussion"]["holistic"]` with `reviewer_name = cfg["roles"]["discussion-review"]["holistic"]["reviewer"]`. If `reviewer_name is None`, raise `ReviewError("discussion-review holistic reviewer is null; nothing to do")`.
  - Replace `reviewer = load_reviewer(reviewer_name)` with: load the registry once via `registry = _reviewers.load(wiki_root)`, then `spec = _reviewers.resolve(registry, reviewer_name)`. Reads of `reviewer.MODE` (lines 72, 75) become `mode = "tool-use" if spec.get("tooluse") else "bulk"`; build_tool_rule(mode); `if mode == "tool-use": ... else: ...`.
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
  - The single `max_rounds = cfg["review"]["plan"]["rounds"]` is split. Per-batch `_review_one_batch` reads `batch_max_rounds = cfg["roles"]["plan-review"]["batch"]["rounds"]` for its round-cap check (line 124). The holistic round-cap check (line 433) reads `cfg["roles"]["plan-review"]["holistic"]["rounds"]`. The signature parameter `max_rounds` continues to act as a CLI override; when set, it OVERRIDES both scopes' caps for the invocation — each scope's effective max becomes `max_rounds` (NOT `min(scope_rounds, max_rounds)`). When `max_rounds is None`, each scope uses its configured value. This preserves the existing `mill-plan/SKILL.md:147` escape-hatch where `--max-rounds {N+1}` extends past the configured cap.
  - Replace `cfg["review"]["plan"]["batch"]` with `cfg["roles"]["plan-review"]["batch"]["reviewer"]` and `cfg["review"]["plan"]["holistic"]` with `cfg["roles"]["plan-review"]["holistic"]["reviewer"]`. Skip semantics — `reviewer is None OR rounds == 0` — applies to both scopes. Concretely: at line ~315, replace `if batch_reviewer_name is None:` with `if batch_reviewer_name is None or cfg["roles"]["plan-review"]["batch"]["rounds"] == 0:` so `holistic_only = True` triggers on either skip condition. Apply the symmetric check for the holistic scope at line ~328 / ~329: treat `cfg["roles"]["plan-review"]["holistic"]["reviewer"] is None or cfg["roles"]["plan-review"]["holistic"]["rounds"] == 0` as the "no holistic" condition that nulls `holistic_reviewer`.
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
  - Replace `max_rounds = ... cfg["review"]["code"]["rounds"]` with: when `batch_name is not None`, read `cfg["roles"]["code-review"]["batch"]["rounds"]`; when `batch_name is None`, read `cfg["roles"]["code-review"]["holistic"]["rounds"]`. The `max_rounds` parameter follows the same rule as `_review_plan`: when set, it OVERRIDES the picked scope's effective cap to `max_rounds` (NOT `min(scope_rounds, max_rounds)`); when `None`, the scope's configured value is used. The CLI always passes a single value; the backend chooses which scope it overrides via `batch_name`.
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
  - `millpy-review-discussion.py` additionally extends its call site for `_review_discussion.run` to pass `wiki_root` (already resolved at line 41 of the CLI as `wiki_root = resolve_wiki_path(project_root)`); the call becomes `run(cfg, slug, mill_dir, wiki_root, project_root, max_rounds=args.max_rounds)`. Card 8's new signature accepts `wiki_root` as a positional parameter after `mill_dir`.
  - Update `--max-rounds` argparse `help` text:
    - `millpy-review-discussion.py`: `Override roles.discussion-review.holistic.rounds for this invocation. Default: use config value.` (currently references `review.discussion.rounds`).
    - `millpy-review-plan.py`: `Override roles.plan-review.batch.rounds and roles.plan-review.holistic.rounds (overrides both scopes) for this invocation. Default: use config values.` (currently references `review.plan.rounds`).
    - `millpy-review-code.py`: `Override roles.code-review.batch.rounds and roles.code-review.holistic.rounds (overrides the active scope) for this invocation. Default: use config values.` (currently references `review.code.rounds`).
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
  - Delete every `cfg["review"]["code"]["holistic_effort"]` reference — it has no replacement. **Delete `test-review-code-flow.py` tests 14a and 14b entirely** (do not attempt to migrate them). Rationale: those tests asserted `effort` propagation through the test stub's captured kwargs, but `_reviewer_single.run` deliberately does NOT forward `effort` to the test stub (per card 2). The effort/model forwarding contract is now covered by `test-reviewer-single.py` subtests 4 and 5 (introduced in card 4), which mock `_llm_claude.run_bulk` / `run_tool_use` and assert `effort=spec["effort"]` is forwarded to the LLM provider — coverage is preserved at the correct boundary.
  - Inline yaml fragments (e.g. `test-millpy-implement.py:85` writing `"review:\n  code:\n    self_fix_rounds: 2\n"` as text) flip to `"roles:\n  implementer:\n    self_fix_rounds: 2\n"`.
  - Where a fixture builds a multi-key cfg dict from scratch, prefer importing `make_minimal_cfg` from `_test_cfg` and applying overrides; this keeps each test's intent readable. Inline cfg dicts that exist solely to demonstrate one schema shape can be simplified accordingly.
  - Tests that previously imported `from _review_common import load_reviewer` (e.g. via flow setups that look up the test stub) must change to import `_reviewers` and call `_reviewers.resolve(registry, "test_stub")` to obtain the stub spec, then pass the spec into the backend through whatever wiring the flow tests use. The `_reviewer_test_stub.seed(...)` and `_reviewer_test_stub.captured_prompts()` calls remain unchanged.
  - After rewiring, no test file may contain any `cfg["review"]` reference. Verify with grep.
  - **`test-llm-claude.py` is NOT in this card's Edits** — it tests `_llm_claude` in isolation with no cfg-building fixtures and contains no `cfg["review"]` references. No migration needed there.
  - **`test-review-cli.py` migration scope:** the file currently tests only `print_error`; it has no `cfg["review"]` references either. The migration adds a NEW test for cross-validation per discussion.md's Testing section: "assert that a registry missing a name referenced by `cfg.roles.*.<scope>.reviewer` causes the API script to exit non-zero with a clear stderr message". Build a fixture with a wiki containing valid `config.yaml` (new schema) but a `reviewers.yaml` that omits at least one reviewer name referenced by `roles.<role>.<scope>.reviewer`; invoke the CLI module via `subprocess.run(...)` (or by calling `main([...])` and capturing stderr); assert exit code 1 AND a stderr containing the missing name and the path. One CLI is enough — `millpy-review-discussion.py` is the simplest target.
  - **Migration-warning test in `test-review-common.py`:** add a new test function (or extend an existing one) that constructs a `mill_dir` with a `config.local.yaml` containing a top-level `review:` key (e.g. `{"review": {"code": {"rounds": 1}}}`), calls `_review_common.load_config(wiki_root, mill_dir)` with a valid wiki-side config, and asserts `sys.stderr` (captured via `contextlib.redirect_stderr` to a `StringIO`) contains a non-empty warning string that mentions both the overlay path and the orphaned key `review`. The merged cfg returned by `load_config` is otherwise usable for downstream code; do NOT assert anything about the presence/absence of `cfg["review"]` — the deep-merge leaves `cfg["review"]` as a harmless orphan branch and that is intended behaviour per card 7's spec. Use a `tempfile.TemporaryDirectory` for the wiki + mill dirs.
  - **`load_reviewer` test removal in `test-review-common.py`:** delete the `load_reviewer` import line at line ~98 and the test block at lines ~476–482 that asserts `load_reviewer("nonexistent_xyz_abc")` raises `ReviewError`. Card 7 removes `load_reviewer` from `_review_common`; leaving the import causes an `ImportError` at module-load time. The equivalent coverage (unknown-reviewer-name raises `ReviewerError`) is provided by `test-reviewers.py` subtest 11 (introduced in card 4).
  - **Discussion-run call-site updates:** Card 8 changes `_review_discussion.run`'s signature to `run(cfg, slug, mill_dir, wiki_root, project_root, *, max_rounds=None)`. Every existing `discussion_run(cfg, SLUG, mill_dir, project_root)` call inside `test-review-discussion-flow.py` must be updated to `discussion_run(cfg, SLUG, mill_dir, wiki_root, project_root)` where `wiki_root` is the path passed to `_test_registry.write_to(wiki_root)`. Without this update every discussion flow test raises `TypeError`.
  - **`reviewers.yaml` setup in flow-test fixtures:** Cards 8/9/10 wire `_reviewers.load(wiki_root)` at the top of every backend `run`. `_reviewers.load` raises when `wiki_root / "reviewers.yaml"` is absent; the `test_stub` carve-out lives in `_reviewers.resolve`, NOT in `_reviewers.load`. So every flow-test fixture must create a valid `reviewers.yaml` BEFORE the backend is invoked. Use the `_test_registry.write_to(wiki_root)` helper (added by card 3, which mkdirs `wiki_root` defensively) to drop a minimal valid registry file at the fixture's `wiki_root`. Concretely, add a single call to `_test_registry.write_to(wiki_root)` inside:
    - `test-review-discussion-flow.py` `_make_fixture` (or equivalent): the fixture's wiki_root resolves to `tmp/container/wiki/` via `_paths.resolve_wiki_path`.
    - `test-review-plan-flow.py` `_make_fixture` (or equivalent): write at the fixture's `wiki_root` (a `tmp_path / "wiki"` dir or similar).
    - `test-review-code-flow.py` `_make_fixture` AND every ad-hoc inline worktree setup that calls `code_run` (look for the test cases the round-3 review identified: tests 3, 4, 7, 12 plus any test in the 14c/14d/14e cluster — grep for `code_run\(` and ensure each call site has a registry-file in its wiki_root, either via the shared fixture or an inline `_test_registry.write_to(...)`).
  - Imports: each test file gains `import _test_registry` (or the equivalent `from _test_registry import write_to`). The fixture helper goes in the unit_tests dir alongside the test files; `sys.path` already covers it (per existing convention in `test-reviewer-modules.py`).
- **Commit:** `test(review): migrate fixtures to roles + registry schema`

### Card 14: Delete `_reviewer_sonnetmax*.py` and `test-reviewer-modules.py`; drop dead `MODE` from `_reviewer_test_stub`

- **Context:**
  - `task/discussion.md`
- **Edits:**
  - `plugins/mill/scripts/_reviewer_test_stub.py`
- **Creates:** none
- **Deletes:**
  - `plugins/mill/scripts/_reviewer_sonnetmax.py`
  - `plugins/mill/scripts/_reviewer_sonnetmax_tool.py`
  - `plugins/mill/unit_tests/test-reviewer-modules.py`
- **Requirements:**
  Remove the three files. Search the project for any remaining import or reference to `_reviewer_sonnetmax`, `_reviewer_sonnetmax_tool`, or `test-reviewer-modules`; the search must be empty before commit. `run-all.py` requires no edit — it uses `HERE.glob("test-*.py")` so the deleted test file disappears from the discovery set automatically.
  Additionally, delete the `MODE = "bulk"` line from `_reviewer_test_stub.py`. The constant was retained in earlier plan revisions "for test compatibility" against `test-reviewer-modules.py`, but that file is being deleted in this card. The new dispatch path in `_reviewer_single.run` reads `spec["tooluse"]` rather than `module.MODE`. After this edit no production or test code references `_reviewer_test_stub.MODE`.
- **Commit:** `chore(review): remove _reviewer_sonnetmax* and test-reviewer-modules`

## Batch Tests

`verify: uv run --project plugins/mill python plugins/mill/unit_tests/run-all.py`. After this batch, the full unit-test suite passes against the new schema. Tests expected to be exercised heavily by the verify run: `test-reviewers.py`, `test-reviewer-single.py`, `test-review-discussion-flow.py`, `test-review-plan-flow.py`, `test-review-code-flow.py`, `test-review-common.py`, `test-review-cli.py`, `test-llm-claude.py`, `test-millpy-implement.py`, `test-millpy-implement-holistic.py`. The deleted `test-reviewer-modules.py` must NOT be invoked. A grep for `cfg\["review"\]` across `plugins/mill/` returns zero matches.
