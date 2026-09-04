# Batch: code-review-wiring

```yaml
task: "Review prompt/output file listings resolve plan-relative paths to absolute before display, instead of keeping them relative"
batch: "code-review-wiring"
number: 3
cards: 4
verify: PYTHONPATH= uv run --project plugins/mill python plugins/mill/unit_tests/run-all.py --only test-review-code-flow.py test-millpy-merge-in-subagent.py
depends-on: [1]
```

## Batch Scope

This batch wires batch 1's display layer into `_review_code.py`'s single artefact-assembly site and its one NEED_CONTEXT resume-retry branch, updates the one existing test whose assertion is invalidated by the change, and adds the regression pin confirming `millpy-merge-in-subagent.py` never needed touching. It is independent of batch 2 -- the two batches edit disjoint files and share only batch 1's helper API -- so they can run in parallel.

Batch-local decision beyond the overview's Shared Decisions: `_build_artefact_section` is module-private and takes an optional `project_root` today purely to feed `bulk_files_with_diff`'s git-diff scoping. This batch adds `roots` as a separate parameter rather than deriving it from `project_root` inside the function, because the display helper needs the wiki and git roots too, and because conflating the git-scoping root with the display root is precisely the mistake the overview's Shared Decisions warn against.

## Cards

### Card 11: `_build_artefact_section` and its `prepare()` call site

- **Context:**
  - `plugins/mill/scripts/_review_common.py`
- **Edits:**
  - `plugins/mill/scripts/_review_code.py`
- **Creates:** none
- **Deletes:** none
- **Moves:** none
- **Requirements:** Give the module-private `_build_artefact_section` in `_review_code.py` a new keyword-only parameter `roots: DisplayRoots | None = None`, and import `DisplayRoots` from `_review_common` alongside the existing `build_manifest_section` / `bulk_files` / `bulk_files_with_diff` imports. Inside the function, pass `roots=roots` to the `build_manifest_section(all_bulked)` call and to **all three** bulking calls in the bulk-mode branch. There are three, not two, and they are easy to miscount because two of them are mutually exclusive alternatives on the same `if`: on the `start_sha is not None and project_root is not None` branch there is a `bulk_files_with_diff(source_files, ...)` call for the diff-scoped sources **and** a `bulk_files(plan_and_ancestors)` call for the overview, batch files, and ancestors, whose results are concatenated; on the `else` branch there is a single `bulk_files(all_bulked)` call. Every one of the three takes `roots=roots`. The diff-scoped branch is the common production path, not an edge case -- `start_sha` comes from `status.md`'s per-batch entry and is present for essentially every real per-batch code review after the first commit -- so leaving `bulk_files(plan_and_ancestors)` on the default `roots=None` would leak absolute paths on the ordinary path while the manifest directly above it was relative. In the tool-use branch, render the `batch_list` bullets, the `read_list` bullets, and the `Overview:` line through `roots.render(...)` when `roots` is not `None` and through `str(...)` otherwise, preserving the branch's existing backticked bullet form and its `"  (none)"` / `"(none)"` empty fallbacks exactly. Amend the tool-use branch's instruction sentence -- the one directing the reviewer to read the overview, every batch file, and every listed source file -- to add that every path listed is relative to the root stated in the `## Path roots` block above and must be resolved against it before reading; keep the sentence ASCII. Leave the `build_deletes_section(sorted(deletes_union))` call untouched. Then, at the single call site of `_build_artefact_section` inside `prepare()`, construct `DisplayRoots(project_root=project_root, git_root=git_root, wiki_root=wiki_root)` from the three parameters `prepare()` already receives and pass it as `roots=`. Do not remove or repurpose the existing `project_root` argument that call already passes -- it feeds `bulk_files_with_diff`'s git-diff scoping and remains required and separate.
- **Commit:** `feat(review): relativize code-review artefact section paths`

### Card 12: the NEED_CONTEXT resume-retry branch

- **Context:**
  - `plugins/mill/scripts/_review_common.py`
- **Edits:**
  - `plugins/mill/scripts/_review_code.py`
- **Creates:** none
- **Deletes:** none
- **Moves:** none
- **Requirements:** `_review_code.py` has exactly one `build_reattached_section(missing_paths)` call site, in the `verdict == "NEED_CONTEXT"` branch that first calls `resolve_existing_paths(missing_raw, project_root, root, wiki_root=wiki_root, git_root=git_root)` and then splices the returned section into a `retry_prompt`. Construct a `DisplayRoots` from the `project_root`, `git_root`, and `wiki_root` already in that branch's scope and change the call to `build_reattached_section(missing_paths, roots=roots)`. Leave the surrounding `retry_prompt` prose unchanged -- the roots were stated in the original prompt of the same reviewer session, so the resume turn does not restate them. Do not change `resolve_existing_paths`'s arguments or its return handling, and do not touch the `root` local that branch derives from the plan overview.
- **Commit:** `feat(review): relativize NEED_CONTEXT re-attachment paths in _review_code`

### Card 13: update the invalidated assertion and add flow tests

- **Context:**
  - `plugins/mill/scripts/_review_code.py`
  - `plugins/mill/scripts/_review_common.py`
  - `plugins/mill/unit_tests/_test_helpers.py`
  - `plugins/mill/scripts/_reviewer_test_stub.py`
  - `plugins/mill/unit_tests/run-all.py`
- **Edits:**
  - `plugins/mill/unit_tests/test-review-code-flow.py`
- **Creates:** none
- **Deletes:** none
- **Moves:** none
- **Requirements:** First fix the one existing assertion this batch invalidates. In `test-review-code-flow.py`, test 23 (the `Moves:` source-suppression case, `#686`) builds `new_path` as an absolute path under `project_root` and asserts `f"--- FILE: {new_path} ---" in first_prompt`. Cards 11 and 12 make that delimiter relative, so change this assertion to expect the relative form -- the plan-relative token as the fixture's batch card wrote it -- while leaving the sibling `not in` assertion for the moved-away source, and the accompanying comment explaining what the pair is testing, intact in substance (update the comment's claim that the delimiter carries the resolved absolute path, since that is no longer true). Then add new flow-level tests asserting, for `_build_artefact_section` reached through `prepare()` in both `bulk` and `tool-use` reviewer modes: the captured `prompt_text` contains no occurrence of `str(project_root)`; it contains the expected plan-relative token; and it contains the `## Path roots` heading. The tool-use case must additionally confirm the resolve-against-the-stated-root instruction sentence is present. **The bulk-mode coverage must include a `start_sha`-bearing fixture, not only a plain one.** The existing test 23 fixture sets no `start_sha`, so it exercises only the `else` branch's single `bulk_files(all_bulked)` call; the diff-scoped branch's own `bulk_files(plan_and_ancestors)` call would be left entirely unasserted, which is precisely the call card 11 warns is easy to miss. Either extend one of the file's existing `start_sha`-bearing bulk-mode fixtures (the ones that today assert on `--- DIFF:` / `--- FILE:` delimiter presence) with the "no occurrence of `str(project_root)`" assertion, or add a new `start_sha`-bearing case carrying it. Assert it against a prompt that provably contains both a `--- DIFF:` delimiter and a `--- FILE:` delimiter, so both bulking calls on that branch are covered by the one assertion. Add one further test driving the stub to return a `NEED_CONTEXT` verdict carrying a `## Missing context` bullet and asserting the resulting resume `retry_prompt` contains no occurrence of `str(project_root)` -- the file's existing NEED_CONTEXT case already captures a retry prompt and asserts on its `## Re-attached files` heading, so extend that pattern rather than building a new fixture. Use the file's existing fixture helpers (`_make_fixture`, `_make_batch_file`, `_make_overview`, `_seed_approve`) and its `_reviewer_test_stub` capture pattern, and follow the existing convention of numbering new cases after the highest existing test number rather than renumbering earlier ones.
- **Commit:** `test(review): assert code-review prompts carry no absolute root prefix`

### Card 14: pin `millpy-merge-in-subagent.py`'s conflicting-files list as already-relative

- **Context:**
  - `plugins/mill/scripts/millpy-merge-in-subagent.py`
  - `plugins/mill/unit_tests/run-all.py`
- **Edits:**
  - `plugins/mill/unit_tests/test-millpy-merge-in-subagent.py`
- **Creates:** none
- **Deletes:** none
- **Moves:** none
- **Requirements:** `test-millpy-merge-in-subagent.py` already asserts that the rendered `CONFLICTING_FILES` template value contains the backticked entries `` `a.py` `` and `` `b.py` ``. Strengthen that existing case (or add a sibling assertion immediately alongside it, whichever fits the file's structure better) to additionally assert that the rendered value contains no occurrence of the fixture's absolute project-root string -- pinning that the `--files` argument, which `mill-merge-in` supplies from `git diff --name-only --diff-filter=U` and which is therefore already repository-relative, is rendered verbatim rather than being joined onto a root. Do not modify `millpy-merge-in-subagent.py` itself: this card exists to record that the task brief's claim of a full-path leak there is inaccurate, and to make a future regression fail loudly. Name the assertion's failure message so that intent is obvious from the output alone.
- **Commit:** `test(merge-in): pin conflicting-files list as already-relative`

## Batch Tests

`verify:` runs `plugins/mill/unit_tests/run-all.py --only test-review-code-flow.py test-millpy-merge-in-subagent.py`. `test-review-code-flow.py` is the sole test surface for `_review_code.py`'s prompt assembly and carries both the assertion card 13 must repair and every new assertion it adds. `test-millpy-merge-in-subagent.py` is included because card 14 edits it; it is otherwise untouched by this batch and runs quickly. The scope covers exactly the files this batch edits plus their one production dependency each. The overview's module-wide `verify:` re-runs the common-helper and plan-review suites at the batch boundary, which is what catches any cross-module regression from batch 1's shared-helper edit reaching this batch's boundary.
