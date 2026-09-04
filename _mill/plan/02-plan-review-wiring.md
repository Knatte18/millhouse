# Batch: plan-review-wiring

```yaml
task: "Review prompt/output file listings resolve plan-relative paths to absolute before display, instead of keeping them relative"
batch: "plan-review-wiring"
number: 2
cards: 5
verify: PYTHONPATH= uv run --project plugins/mill python plugins/mill/unit_tests/run-all.py --only test-review-plan-flow.py
depends-on: [1]
```

## Batch Scope

This batch wires batch 1's display layer into every path-rendering site in `_review_plan.py`: the four artefact-assembly sites and the two NEED_CONTEXT resume-retry branches. After it, every plan-review prompt -- per-batch and holistic, bulk and tool-use, first turn and resume turn -- states its roots once and lists files relative to them.

The four assembly sites are spread across three functions and two of them are near-duplicates, which is exactly the shape where one gets updated and the other missed. They are given one card each (with the two sibling sites inside `prepare()` sharing a card, since they are adjacent and mechanically identical) so a missed site is visible in the commit history, and the final card's flow tests assert on each site's own assembled prompt rather than on a single representative one. Batch-local decision beyond the overview's Shared Decisions: each site constructs its own `DisplayRoots` from the roots already in its local scope rather than threading one down from a shared entry point, because the four sites live in three different functions with no common local frame.

## Cards

### Card 6: site 1 -- batch-mode assembly in `_review_one_batch`

- **Context:**
  - `plugins/mill/scripts/_review_common.py`
- **Edits:**
  - `plugins/mill/scripts/_review_plan.py`
- **Creates:** none
- **Deletes:** none
- **Moves:** none
- **Requirements:** In `_review_one_batch` in `_review_plan.py`, after the `resolve_ref_paths` / `resolve_existing_paths` calls that produce `reads`, `ancestors_on_disk`, and `moves_on_disk`, construct one local `roots = DisplayRoots(project_root=project_root, git_root=git_root, wiki_root=wiki_root)` from the parameters already in scope, and import `DisplayRoots` from `_review_common` alongside the existing `build_manifest_section` / `bulk_files` imports. Pass `roots=roots` to the `build_manifest_section(all_bulked)` call and to the `bulk_files(all_bulked)` call in the bulk-mode branch. In the tool-use branch, render the `read_list` bullets through `roots.render(p)` instead of `str(p)`, preserving the site's existing no-backtick `f"- {…}"` bullet form and its `"(none)"` empty fallback, and render the `Overview:` and `Batch:` backtick lines through `roots.render(...)` as well. Amend the tool-use branch's instruction sentence -- the one directing the reviewer to read the source files listed under `Context:` / `Edits:` / `Creates:` -- to add that every path listed is relative to the root stated in the `## Path roots` block above and must be resolved against it before reading. Keep the sentence ASCII. Leave the `build_deletes_section(sorted(deletes_union))` call untouched: it receives raw tokens, not resolved paths.
- **Commit:** `feat(review): relativize plan batch-mode prompt paths in _review_one_batch`

### Card 7: sites 2 and 3 -- the two assembly blocks inside `prepare()`

- **Context:**
  - `plugins/mill/scripts/_review_common.py`
- **Edits:**
  - `plugins/mill/scripts/_review_plan.py`
- **Creates:** none
- **Deletes:** none
- **Moves:** none
- **Requirements:** Apply the same transformation card 6 applied to `_review_one_batch` to both assembly blocks inside `prepare()` in `_review_plan.py`: the second batch-mode block (the one whose resolvers feed `reads` / `ancestors_on_disk` / `moves_on_disk` and whose tool-use branch builds a `read_list`) and the holistic block (the one whose resolvers feed `all_reads` / `all_creates_on_disk` / `holistic_moves_on_disk` and whose tool-use branch builds both a `batch_list` and a `read_list`). In each block construct a local `DisplayRoots` from the `project_root`, `git_root`, and `wiki_root` already in `prepare()`'s scope, pass `roots=` to that block's `build_manifest_section` call and to its `bulk_files` call, and render its `read_list`, `batch_list`, `Overview:`, and `Batch:` interpolations through `roots.render(...)`. Preserve each block's own existing bullet punctuation exactly -- the second batch-mode block's `read_list` uses the no-backtick `f"- {…}"` form while the holistic block's `batch_list` and `read_list` use the backticked `f"- \`{…}\`"` form; this card changes what is rendered, never how it is punctuated. Amend each block's tool-use instruction sentence with the same resolve-against-the-stated-root wording card 6 used, keeping it ASCII. Leave both `build_deletes_section` calls untouched. If constructing the same `DisplayRoots` twice inside one function is redundant because both blocks share `prepare()`'s frame, hoist it to a single local before the first block and reuse it -- but do not hoist it out of `prepare()` into module scope, since the roots are per-invocation values.
- **Commit:** `feat(review): relativize both prepare() assembly blocks in _review_plan`

### Card 8: site 4 -- the run-holistic assembly block inside `run()`

- **Context:**
  - `plugins/mill/scripts/_review_common.py`
- **Edits:**
  - `plugins/mill/scripts/_review_plan.py`
- **Creates:** none
- **Deletes:** none
- **Moves:** none
- **Requirements:** Apply the same transformation to the holistic assembly block inlined inside `run()` in `_review_plan.py` -- the block whose resolvers feed `all_reads` / `all_creates_on_disk` / `run_hol_moves_on_disk` and whose tool-use branch builds a `batch_list` and a `read_list`. Construct a local `DisplayRoots` from the `project_root`, `git_root`, and `wiki_root` in `run()`'s scope, pass `roots=` to that block's `build_manifest_section` and `bulk_files` calls, render its `batch_list`, `read_list`, `Overview:`, and `Batch:` interpolations through `roots.render(...)` preserving the block's existing backticked bullet form, and amend its tool-use instruction sentence with the same resolve-against-the-stated-root wording. Leave its `build_deletes_section` call untouched. This block is reached through `run()`'s own holistic dispatch path, not through `prepare()`, so it needs its own `DisplayRoots` construction -- do not attempt to share one with card 7's.
- **Commit:** `feat(review): relativize run() holistic prompt paths in _review_plan`

### Card 9: the two NEED_CONTEXT resume-retry branches

- **Context:**
  - `plugins/mill/scripts/_review_common.py`
- **Edits:**
  - `plugins/mill/scripts/_review_plan.py`
- **Creates:** none
- **Deletes:** none
- **Moves:** none
- **Requirements:** In `_review_plan.py` there are exactly two `build_reattached_section(missing_paths)` call sites -- one inside `_review_one_batch` and one inside `run()`. Each sits in a `verdict == "NEED_CONTEXT"` branch that first calls `resolve_existing_paths(missing_raw, project_root, root, wiki_root=wiki_root, git_root=git_root)` and then splices the returned section into a `retry_prompt`. At each site construct a `DisplayRoots` from the `project_root`, `git_root`, and `wiki_root` already in that branch's scope -- or reuse the one the enclosing function already built for its assembly block, if it is still in scope at that point -- and change the call to `build_reattached_section(missing_paths, roots=roots)`. Leave the surrounding `retry_prompt` prose ("Please continue your review using the re-attached files above. The original prompt is already in your session context.") unchanged: the roots were stated in the original prompt of the same session, so the resume turn does not restate them. Do not change `resolve_existing_paths`'s arguments or its return handling.
- **Commit:** `feat(review): relativize NEED_CONTEXT re-attachment paths in _review_plan`

### Card 10: flow tests for all four assembly sites and both resume branches

- **Context:**
  - `plugins/mill/scripts/_review_plan.py`
  - `plugins/mill/scripts/_review_common.py`
  - `plugins/mill/unit_tests/_test_helpers.py`
  - `plugins/mill/scripts/_reviewer_test_stub.py`
  - `plugins/mill/unit_tests/run-all.py`
- **Edits:**
  - `plugins/mill/unit_tests/test-review-plan-flow.py`
- **Creates:** none
- **Deletes:** none
- **Moves:** none
- **Requirements:** Add flow-level tests to `test-review-plan-flow.py` covering each of the four assembly sites individually, using the file's existing fixture helpers (`_make_plan_fixture`, `_make_batch_file`, `_make_overview`, `_seed_approve`) and its existing `_reviewer_test_stub` capture pattern (`stub.captured_prompts()`), and following the existing convention of numbering new cases after the highest existing test number rather than renumbering earlier ones. For each site assert three things about that site's own captured `prompt_text`: it contains no occurrence of `str(project_root)`; it contains the expected plan-relative token as written in the fixture's batch card; and it contains the `## Path roots` heading. Reach the four sites through the entry points that actually dispatch them -- `_review_plan.prepare` with a batch scope for the batch-mode blocks, `_review_plan.prepare` with the holistic scope for the holistic block, and `_review_plan.run` with `holistic_only=True` for the run-holistic block -- rather than asserting on a single representative prompt. Exercise both `bulk` and `tool-use` reviewer modes at the sites that support both, so the `read_list` and `batch_list` interpolations are covered alongside the manifest and the `--- FILE:` delimiters; the tool-use assertions must additionally confirm the resolve-against-the-stated-root instruction sentence is present. Add one further test driving the stub to return a `NEED_CONTEXT` verdict carrying a `## Missing context` bullet, then asserting the resulting resume `retry_prompt` contains no occurrence of `str(project_root)` -- this is the only coverage the re-attachment site gets, since the other assertions only ever inspect the first-turn prompt. If one of the four assembly sites turns out not to be reachable through any existing entry point in this harness, treat that as a defect to solve rather than a site to drop: add whatever fixture the site needs, because these assertions are the only guard against a production call site left on the default `roots=None`.
- **Commit:** `test(review): assert plan-review prompts carry no absolute root prefix`

## Batch Tests

`verify:` runs `plugins/mill/unit_tests/run-all.py --only test-review-plan-flow.py`. That file is the sole test surface for `_review_plan.py`'s prompt assembly and is where card 10 adds every new assertion. The scope is deliberately one file: this batch edits `_review_plan.py` and that test file only, and `_review_plan.py` has no other test consumer. Cards 6 through 9 are individually unverifiable in isolation -- they change prompt text with no assertion attached until card 10 lands -- which is why card 10 asserts per-site rather than once: a site missed in cards 6 to 8 fails its own named test, not a generic aggregate. The overview's module-wide `verify:` additionally re-runs the common-helper and code-review suites at the batch boundary so a regression leaking out of this module is caught here rather than in batch 3.
