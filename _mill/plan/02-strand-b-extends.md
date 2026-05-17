# Batch: strand-b-extends

```yaml
task: '51 (D) -- Config infra: env interpolation + agents.yaml inheritance'
batch: strand-b-extends
number: 2
cards: 3
verify: uv run --project plugins/mill python plugins/mill/unit_tests/test-reviewers.py
depends-on: []
```

## Batch Scope

Adds `extends: <name>` inheritance to `_reviewers.load()` so flat-form duplicate-heavy entries (today: every `*_tool` variant redeclares `provider` / `model` / `effort` from its base) collapse into a leaf that only declares the overrides. Resolution runs at load time -- the returned registry is still flat dicts with no `extends:` field, so every downstream consumer (`resolve`, `resolve_role`, `validate_role_refs`, every CLI reviewer dispatch) is untouched. The single-string `extends: a` form is the only shape; multi-inheritance (`extends: [a, b]`) is rejected, cluster entries cannot extend and cannot be extended.

After the parser ships (card 4) and is covered by tests (card 5), card 6 flips the shared `wiki/agents.yaml` registry and the `templates/reviewers.yaml` starter to the new extends-form. Per the discussion's rollout decision, the parser change is backwards-compat (handles both flat-form and extends-form) so the registry flip can land alongside the parser in the same merge -- machines that pull main get both at once. The card explicitly does NOT introduce `extends:` into entries that lack a sensible base; it is a behaviour-preserving refactor verified by re-running `_reviewers.load()` on the new yaml and checking each resolved entry matches the pre-flip flat form.

Verify runs the full `test-reviewers.py` suite plus a one-shot script that loads the actual `wiki/agents.yaml` to confirm the refactored registry resolves cleanly.

---

### Card 4: Implement extends-resolution in `_reviewers.load()`

- **Context:** none
- **Edits:**
  - `plugins/mill/scripts/_reviewers.py`
- **Creates:** none
- **Deletes:** none
- **Requirements:**

  Insert new resolution logic into `_reviewers.load()` between the existing duplicate-key detection (around line 70) and the existing per-entry validation loop (around line 78). The pipeline becomes:

  1. (existing) Parse via `yaml.compose` + `yaml.safe_load`, detect duplicate top-level keys.
  2. **(new)** Raw-form extends syntax validation.
  3. **(new)** Extends-cycle detection.
  4. **(new)** Topo-sorted top-down extends resolution (replaces `raw` for steps 5-7).
  5. (existing) Per-entry struct validation, now running on resolved dicts.
  6. (existing) Cluster cross-ref validation.
  7. (existing) `_detect_cycles` over cluster `use:` graph.
  8. Return the resolved registry.

  **Change A -- new step 2 (raw-form extends syntax).** Iterate the raw dict. For each entry whose dict contains an `extends:` key:
  - The value must be a `str`; else append `f"Reviewer {name!r}: 'extends' must be a string"` to errors and skip the rest of the checks for this entry.
  - The string must match an existing key in `raw`; else append `f"Reviewer {name!r}: extends references unknown name {target!r}"`.
  - The target's raw entry, if it exists, must NOT declare `type: cluster`; else append `f"Reviewer {name!r}: extends references {target!r} which declares type 'cluster' (clusters cannot be extended)"`.
  - The current entry must not also declare `type: cluster`; else append `f"Reviewer {name!r}: cluster entries cannot use 'extends'"`. (One entry can violate both this rule and the previous one independently; report each.)

  Do not validate `type: single` on intermediates here -- a chain `c -> b -> a` may have `b` without a raw `type:` (it inherits from `a`). The full required-after-merge check happens in step 5 on resolved entries.

  **Change B -- new step 3 (extends-cycle detection).** Use a tri-colour DFS over the extends-graph (each node has at most one outgoing edge: the value of its `extends:` field if present, else none). On detection of a back-edge, append `f"Cycle detected in extends chain: {' -> '.join(chain)}"` where `chain` is the list of node names visited from the entry node up to and including the back-edge target. Implement in a new private helper `def _detect_extends_cycles(raw: dict) -> list[str]` that returns an error list (empty when no cycles). Caller extends `errors` with the return value. Self-loops (`a: {extends: a}`) are reported as `Cycle detected in extends chain: a -> a`.

  Defensive guard: if a neighbor name is not in the color dict (i.e. the `extends:` value points at an unknown base — already reported by step 2 but not yet raised at this point), skip it with `continue` instead of dereferencing. This mirrors the existing `_detect_cycles` helper at the bottom of `_reviewers.py` and prevents the DFS from crashing with `KeyError` on a known-bad graph.

  After step 3, if `errors` is non-empty for either step 2 or step 3, raise `ReviewerError("\n".join(errors))` immediately. Cycle detection that would dereference an unknown base would crash; failing fast here keeps the next step's pre-conditions clean. (This matches the existing convention of raising at the end of validation -- but here we raise before resolution because resolution requires a valid graph.)

  **Change C -- new step 4 (extends-resolution).** Implement in a new private helper:

  ```python
  def _resolve_extends(raw: dict) -> dict:
      """Top-down extends-chain merge; returns flat dict with no 'extends:' fields."""
  ```

  Algorithm: build the resolution result one entry at a time using memoisation.

  ```python
  resolved: dict[str, dict] = {}
  def _walk(name: str) -> dict:
      if name in resolved:
          return resolved[name]
      entry = raw[name]
      if "extends" not in entry:
          flat = dict(entry)
      else:
          base = _walk(entry["extends"])  # safe: step 3 guaranteed no cycles
          flat = dict(base)
          for k, v in entry.items():
              if k == "extends":
                  continue
              flat[k] = v
      resolved[name] = flat
      return flat
  for name in raw:
      _walk(name)
  return resolved
  ```

  Use `deepcopy` on the child entry's values only if mutable (lists / dicts) appear in any extends-using entry; for the current 15-entry registry every override is a scalar string / bool, so plain dict copy is correct. (If the planner is wrong about this, the cluster cross-ref test would still catch any reference-sharing bug, but the simpler form is fine for the actual data.)

  Assign `raw = _resolve_extends(raw)` once step 4 completes; all subsequent existing validation runs on resolved entries.

  **Change D -- step 5 wording.** The existing per-entry validation already reports `Reviewer {name!r} (single): missing or invalid 'provider'` / `'model'` and `Reviewer {name!r}: unknown type {entry_type!r}`. These messages naturally cover the required-after-merge case: a chain that fails to provide `type` / `provider` / `model` falls into the existing "unknown type" / "missing or invalid provider" branches. No new messages are needed; verify by running test `test_required_field_missing_after_merge_raises` from card 5.

  **Change E -- no public-API change.** `resolve`, `resolve_role`, and `validate_role_refs` are unmodified. They already accept the post-load dict shape and the resolved registry presents that same shape.

  **Change F -- update module docstring.** In the docstring at the top of `_reviewers.py`, add one bullet under the `Validates:` line in the `load()` doc-block:

  ```
  - and entries with `extends: <name>` are resolved top-down at load time
    (single-string form only; cluster entries may neither extend nor be extended;
    cycle detection raises with the chain).
  ```

  Keep the public-API block (`ReviewerError`, `load`, `resolve`, `resolve_role`, `validate_role_refs`) untouched.

- **Commit:** `feat(_reviewers): resolve extends: chains at load time -- flat output, cycle detection, cluster excluded`

---

### Card 5: Add extends unit tests to `test-reviewers.py`

- **Context:**
  - `plugins/mill/scripts/_reviewers.py`
  - `plugins/mill/unit_tests/_test_registry.py`
- **Edits:**
  - `plugins/mill/unit_tests/test-reviewers.py`
- **Creates:** none
- **Deletes:** none
- **Requirements:**

  Add ten new test functions to `test-reviewers.py`, appended after the existing tests (no new section header needed -- the file already groups all tests together). Each test follows the existing pattern: `with tempfile.TemporaryDirectory() as tmp:`, build `wiki = Path(tmp) / "wiki"`, mkdir, write `wiki / "agents.yaml"` via `_write_yaml` with a literal YAML string, then call `_reviewers.load(wiki)`. Assertions match the structure used by `test_load_happy_path` and the existing failure tests. Each test ends with `print("PASS: <short label>")`.

  The ten test functions:

  1. `test_extends_single_level` -- yaml:
     ```yaml
     base:
       type: single
       provider: claude
       model: claude-sonnet-4-6
     child:
       extends: base
       tooluse: true
     ```
     Assert `registry["child"] == {"type": "single", "provider": "claude", "model": "claude-sonnet-4-6", "tooluse": True}` (no `extends` key); assert `registry["base"] == {"type": "single", "provider": "claude", "model": "claude-sonnet-4-6"}` (unchanged).
  2. `test_extends_multi_level` -- three-entry chain `c -> b -> a` where only `a` declares `type/provider/model`, `b` overrides nothing (just `extends: a`), `c` overrides `tooluse: true`. Assert `registry["c"]` resolves to the full merged dict with `tooluse: True` and all three base fields inherited.
  3. `test_extends_child_overrides_parent_scalar` -- yaml has `base` with `model: foo`; `child` with `extends: base` and `model: bar`. Assert `registry["child"]["model"] == "bar"` (child wins).
  4. `test_extends_unknown_base_raises` -- yaml has `child` with `extends: nonexistent` (and `type/provider/model` so the only failure is the missing base). Expect `ReviewerError`; assert `"nonexistent"` appears in `str(exc)`.
  5. `test_extends_cycle_raises` -- yaml:
     ```yaml
     a:
       extends: b
       type: single
       provider: claude
       model: x
     b:
       extends: a
       type: single
       provider: claude
       model: y
     ```
     Expect `ReviewerError`; assert `"Cycle detected"` appears in `str(exc)` AND both `"a"` and `"b"` appear.
  6. `test_extends_self_cycle_raises` -- yaml:
     ```yaml
     a:
       extends: a
       type: single
       provider: claude
       model: x
     ```
     Expect `ReviewerError`; assert `"Cycle detected"` and `"a -> a"` (or equivalent representation including the name twice) appear in `str(exc)`.
  7. `test_extends_target_must_not_be_cluster` -- yaml has a cluster entry `my_cluster: {type: cluster, workers: {use: x, count: 1}, handler: {use: x}}` plus a single `x: {type: single, provider: claude, model: y}` to keep the cluster valid, plus `child: {extends: my_cluster, tooluse: true}`. Expect `ReviewerError`; assert `"my_cluster"` and `"cluster"` appear in `str(exc)`.
  8. `test_cluster_cannot_extend` -- yaml has `a: {type: single, provider: claude, model: x}` and `my_cluster: {type: cluster, extends: a, workers: {use: a, count: 1}, handler: {use: a}}`. Expect `ReviewerError`; assert the error names `my_cluster` and mentions `cluster` (the "cluster entries cannot use 'extends'" message).
  9. `test_required_field_missing_after_merge_raises` -- yaml has `base: {type: single, model: foo}` (no provider) and `child: {extends: base}`. After resolution, `child` inherits `type` and `model` but `provider` is still missing on both `base` and `child`. Expect `ReviewerError`; the existing single-entry validation should fire with `"missing or invalid 'provider'"` for at least one entry. The two-entry shape ensures `_resolve_extends` actually runs the merge path (a single flat entry would be a no-op for the resolver and would not document the post-extends contract).
  10. `test_extends_field_removed_from_output` -- yaml has `a: {type: single, provider: claude, model: x}` and `b: {extends: a}`. Assert `"extends" not in registry["b"]` (the field is stripped from the returned dict).

  `_write_yaml` is already defined at the top of `test-reviewers.py`; reuse it.

  **Tests-list registration (mandatory).** Append each of the ten new test functions to the `tests = [...]` list in `main()` (around line 369 of `test-reviewers.py`) in declaration order. The list is the authoritative registry the runner walks; functions defined but not appended are silently skipped and produce a false-green verify.

- **Commit:** `test(_reviewers): cover extends resolution -- single/multi-level, override, cycle, cluster-rejection, required-after-merge`

---

### Card 6: Refactor `templates/reviewers.yaml` and `wiki/agents.yaml` to extends-form

- **Context:**
  - `plugins/mill/scripts/_reviewers.py`
  - `plugins/mill/scripts/_paths.py`
  - `plugins/mill/scripts/_wiki.py`
- **Edits:**
  - `plugins/mill/templates/reviewers.yaml`
  - `wiki/agents.yaml`
- **Creates:** none
- **Deletes:** none
- **Requirements:**

  Both files are rewritten to use extends-form for every entry that has a clear base. The behaviour-preserving check is: each resolved entry post-flip equals its pre-flip flat form (key-for-key).

  **Change A -- `plugins/mill/templates/reviewers.yaml` (worktree-local edit).** Replace the file content with:

  ```yaml
  # plugins/mill/templates/reviewers.yaml -- fresh-setup default reviewer registry.
  # Copied to wiki/reviewers.yaml by mill-setup. Consumed by _reviewers.py.
  # Names match [a-z0-9_-]+. type: single or cluster.
  #
  # `extends: <name>` lets a leaf entry inherit from another single entry.
  # The child may override any field; resolution happens at load time.

  sonnetmax:
    type: single
    provider: claude
    model: claude-sonnet-4-6
    effort: max

  sonnetmax_tool:
    extends: sonnetmax
    tooluse: true

  sonnetmedium:
    extends: sonnetmax
    effort: medium
  ```

  Edit via the standard `Edit` tool on the worktree file. The change lands as part of the task-branch commit (same commit as the wiki/agents.yaml change in this card).

  **Change B -- `wiki/agents.yaml` (wiki repo edit).** Replace the file's content with the extends-form below. Because this file lives in the wiki repo (a sibling clone, NOT the task worktree), mutation must go through the wiki helpers. `_wiki.write_commit_push` only stages, commits, and pushes -- it does NOT write file content. The caller writes the file first, then passes the relative path (as `list[str]`) to the helper. Signature: `write_commit_push(wiki_path: Path, relative_paths: list[str], commit_msg: str, *, slug: str) -> None`.

  Implementation pattern:

  ```python
  from pathlib import Path
  import _paths, _wiki

  git_root = _paths.resolve_git_root()
  wiki_path = _paths.resolve_wiki_path(git_root)
  new_text = (
      "# wiki/agents.yaml -- reviewer registry. Resolved by _reviewers.load().\n"
      "# Use `extends: <name>` to inherit from another single entry.\n"
      "\n"
      "g25flash:\n"
      "  type: single\n"
      "  provider: gemini\n"
      "  model: gemini-2.5-flash\n"
      "\n"
      "g25flash_tool:\n"
      "  extends: g25flash\n"
      "  tooluse: true\n"
      "\n"
      "g25pro:\n"
      "  type: single\n"
      "  provider: gemini\n"
      "  model: gemini-2.5-pro\n"
      "\n"
      "g25pro_tool:\n"
      "  extends: g25pro\n"
      "  tooluse: true\n"
      "\n"
      "g3flash_preview:\n"
      "  type: single\n"
      "  provider: gemini\n"
      "  model: gemini-3-flash-preview\n"
      "\n"
      "g3flash_preview_tool:\n"
      "  extends: g3flash_preview\n"
      "  tooluse: true\n"
      "\n"
      "haiku:\n"
      "  type: single\n"
      "  provider: claude\n"
      "  model: claude-haiku-4-5-20251001\n"
      "\n"
      "opusmax:\n"
      "  type: single\n"
      "  provider: claude\n"
      "  model: claude-opus-4-7\n"
      "  effort: max\n"
      "\n"
      "opushigh:\n"
      "  extends: opusmax\n"
      "  effort: high\n"
      "\n"
      "opusmedium:\n"
      "  extends: opusmax\n"
      "  effort: medium\n"
      "\n"
      "sonnetmax:\n"
      "  type: single\n"
      "  provider: claude\n"
      "  model: claude-sonnet-4-6\n"
      "  effort: max\n"
      "\n"
      "sonnetmax_tool:\n"
      "  extends: sonnetmax\n"
      "  tooluse: true\n"
      "\n"
      "sonnethigh:\n"
      "  extends: sonnetmax\n"
      "  effort: high\n"
      "\n"
      "sonnetmedium:\n"
      "  extends: sonnetmax\n"
      "  effort: medium\n"
  )
  # Write the file first; the helper only stages/commits/pushes.
  (wiki_path / "agents.yaml").write_text(new_text, encoding="utf-8")
  _wiki.write_commit_push(
      wiki_path,
      ["agents.yaml"],
      "refactor(agents.yaml): collapse tool/effort variants via extends:",
      slug="config-env-interpolation",
  )
  ```

  The implementer can execute this as an inline Python one-liner (the standard `PYTHONPATH=... .venv/Scripts/python.exe -c "..."` pattern documented in CLAUDE.md) or as a short scratch script under `.scratch/`. Either approach is acceptable; the requirement is that `_wiki.write_commit_push` is the mechanism (never `cd .wiki/`, never raw `Edit` on the wiki file).

  Note the mapping audited against the pre-flip wiki/agents.yaml:
  - 14 entries pre-flip; 14 entries post-flip (no entries dropped or added).
  - `g25flash_tool` inherits `provider/model` from `g25flash` and adds `tooluse: true`.
  - `g25pro_tool` inherits from `g25pro` similarly.
  - `g3flash_preview_tool` inherits from `g3flash_preview` similarly.
  - `opushigh` / `opusmedium` inherit `type/provider/model` from `opusmax` and override `effort`.
  - `sonnetmax_tool` inherits from `sonnetmax` and adds `tooluse: true`.
  - `sonnethigh` / `sonnetmedium` inherit `type/provider/model` from `sonnetmax` and override `effort`.
  - `haiku` has no base to inherit from (different model family with no `*high` siblings) -- stays flat.

  **Change C -- post-flip behaviour-preservation verification.** After both file edits, run this one-liner from the task worktree to confirm the resolved registry equals the pre-flip flat form (the helper compares against the canonical name list):

  ```bash
  PYTHONPATH="plugins/mill/scripts" uv run --project plugins/mill python -c "
  import sys
  sys.path.insert(0, 'plugins/mill/scripts')
  from pathlib import Path
  import _paths, _reviewers
  wp = _paths.resolve_wiki_path(_paths.resolve_git_root())
  reg = _reviewers.load(wp)
  expected = {'g25flash', 'g25flash_tool', 'g25pro', 'g25pro_tool', 'g3flash_preview',
              'g3flash_preview_tool', 'haiku', 'opushigh', 'opusmax', 'opusmedium',
              'sonnethigh', 'sonnetmax', 'sonnetmax_tool', 'sonnetmedium'}
  assert set(reg.keys()) == expected, f'name set drifted: {set(reg.keys()) ^ expected}'
  for entry in reg.values():
      assert 'extends' not in entry, f'extends not stripped: {entry}'
      assert entry.get('type') == 'single'
      assert isinstance(entry.get('provider'), str)
      assert isinstance(entry.get('model'), str)
  print('PASS: wiki/agents.yaml resolves to 14 valid flat single entries')
  "
  ```

  This is an inline verification step, not a committed test (the unit test suite already covers the parser via card 5; this check confirms the actual deployed yaml file). The implementer reports its output in the commit message body or in the PR description but does not check the script in.

  **Single commit on the task branch.** The two file edits land in one commit: the worktree-local `templates/reviewers.yaml` is staged via `git add plugins/mill/templates/reviewers.yaml && git commit -m "..."` AFTER `_wiki.write_commit_push` has separately committed `wiki/agents.yaml` to the wiki repo. The two commits share intent but live in different repos (millhouse task branch vs wiki main); this is the same pattern as task `implementer-model-config`'s wiki-and-template batch.

- **Commit:** `refactor(reviewers.yaml,wiki/agents.yaml): collapse tool/effort variants via extends:`

## Batch Tests

`verify: uv run --project plugins/mill python plugins/mill/unit_tests/test-reviewers.py` -- runs the full reviewers test suite, including the ten new extends tests added by card 5. Green means: (a) single-level / multi-level extends resolve correctly; (b) every reject path (unknown base, cycle, self-cycle, cluster-target, cluster-extends, missing required-after-merge) raises with the documented message text; (c) the `extends:` field is stripped from the returned dict; (d) all 14 pre-existing tests still pass (cluster behaviour, role validation, resolve, etc.). Card 6's behaviour-preservation check on the live `wiki/agents.yaml` (the inline one-liner) runs once at the end of card 6 implementation; its output is included in the commit message or PR notes but is not a committed test.
