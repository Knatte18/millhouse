# Batch: display-layer

```yaml
task: "Review prompt/output file listings resolve plan-relative paths to absolute before display, instead of keeping them relative"
batch: "display-layer"
number: 1
cards: 5
verify: PYTHONPATH= uv run --project plugins/mill python plugins/mill/unit_tests/run-all.py --only test-review-common.py test-review-common-guard.py
depends-on: []
```

## Batch Scope

This batch builds the whole display layer inside `_review_common.py` and nothing else: the `DisplayRoots` value type, the `## Path roots` header, and the `roots` keyword on the four display helpers (`build_manifest_section`, `bulk_files`, `bulk_files_with_diff`, `build_reattached_section`). It changes no caller, so review prompts are byte-identical after this batch -- every new keyword defaults to `None`, which reproduces today's absolute output exactly.

The external interface batches 2 and 3 consume is: `DisplayRoots(project_root, git_root=None, wiki_root=None)`, its single path-rendering method, and the `roots=` keyword accepted by those four helpers. Batch-local decision beyond the overview's Shared Decisions: the `## Path roots` header lives inside `build_manifest_section` rather than being a separately-called builder at each site, so callers pass `roots` once and get both blocks.

## Cards

### Card 1: `DisplayRoots` value type and `## Path roots` header

- **Context:**
  - `plugins/mill/unit_tests/run-all.py`
- **Edits:**
  - `plugins/mill/scripts/_review_common.py`
  - `plugins/mill/unit_tests/test-review-common.py`
- **Creates:** none
- **Deletes:** none
- **Moves:** none
- **Requirements:** Add a frozen dataclass `DisplayRoots` to `_review_common.py` with fields `project_root: Path`, `git_root: Path | None = None`, `wiki_root: Path | None = None`, declared `@dataclass(frozen=True)`. Add the `dataclasses` import if the module does not already have one. Give it one public method `render(self, p: Path) -> str` implementing the rendering rule from the overview's `rendering-rule` Shared Decision: (1) if `self.wiki_root` is not `None` and `p` is under it, return `"wiki/" + <p relative to wiki_root>.as_posix()`; (2) otherwise, among `self.project_root` and `self.git_root` (skipping `None`), select the longest root that is an ancestor of `p` and return `<p relative to that root>.as_posix()`; (3) otherwise return `str(p)` unchanged. Perform every ancestor test and every `relative_to` call on `Path.resolve()`-normalised copies of both the root and `p`, so a symlinked or junctioned root still matches -- the relative remainder is identical either way. Use `Path.is_relative_to` for the ancestor test rather than a `try`/`except ValueError`, and be consistent across all three rules. "Longest" means the root with the greatest number of path parts after resolution; when two candidate roots resolve equal, either is correct and the tie may be broken arbitrarily. Also add a module-level function `build_path_roots_section(roots: DisplayRoots) -> str` returning an ASCII-only markdown block whose first line is the heading `## Path roots`, followed by a blank line, then a sentence naming `roots.project_root` as the root every unprefixed path is relative to, then one bullet line per additional root: a `wiki/` bullet naming `roots.wiki_root` emitted only when `wiki_root` is not `None`, and a `git_root` bullet naming `roots.git_root` emitted only when `git_root` is not `None` and its resolved value differs from the resolved `project_root`. Return value carries no trailing newline, matching the convention of the neighbouring `build_manifest_section` and `build_deletes_section`. In `test-review-common.py`, add tests covering: a path directly under `project_root` renders as a bare relative POSIX string; a path under `wiki_root` renders with the `wiki/` prefix; a path under both a `git_root` and a deeper `project_root` renders against the longer of the two; a path under both a `wiki_root` and a deeper `project_root` renders in the `wiki/` form -- this case is what proves rule 1 short-circuits rule 2 rather than merely coexisting with it, and without it the wiki-first ordering is untested; a path under no root renders as the unchanged absolute string; a nested path renders with forward slashes; `git_root=None` and `wiki_root=None` do not raise and fall back to `project_root` then absolute. Add header tests covering: project-root-only produces the heading with no `wiki/` bullet and no `git_root` bullet; a set `wiki_root` produces the `wiki/` bullet; `git_root` equal to `project_root` produces no `git_root` bullet; `git_root` differing from `project_root` produces one. Register the new tests through whatever per-test invocation convention `main()` in that file already uses for its existing cases.
- **Commit:** `feat(review): add DisplayRoots path renderer and Path roots header builder`

### Card 2: `roots` keyword on `build_manifest_section`

- **Context:**
  - `plugins/mill/unit_tests/run-all.py`
- **Edits:**
  - `plugins/mill/scripts/_review_common.py`
  - `plugins/mill/unit_tests/test-review-common.py`
- **Creates:** none
- **Deletes:** none
- **Moves:** none
- **Requirements:** Give `build_manifest_section` in `_review_common.py` a new keyword-only parameter `roots: DisplayRoots | None = None`. When `roots` is `None`, the returned string is byte-identical to today's -- the existing `## Files included (N=0)\n\n(no files)` empty-input return and the existing `- {p}` absolute bullets both stay exactly as they are. When `roots` is not `None`, render each bullet as `- ` followed by `roots.render(p)` instead of `str(p)`, and prepend the output of `build_path_roots_section(roots)` followed by a blank line ahead of the `## Files included (N=...)` heading. The empty-input case with a non-`None` `roots` still emits the `## Path roots` block followed by the unchanged `## Files included (N=0)\n\n(no files)` body. Update the function's docstring to document the new parameter and the prepended header. In `test-review-common.py`, add tests asserting: with `roots` supplied, every bullet is the relative form and the result starts with `## Path roots`; with `roots` omitted, the result still starts with `## Files included (N=` and the bullets are absolute -- this second assertion is the explicit back-compat pin for the existing manifest tests already in that file.
- **Commit:** `feat(review): relativize build_manifest_section bullets via optional roots`

### Card 3: `roots` keyword on `bulk_files` and `bulk_files_with_diff`

- **Context:**
  - `plugins/mill/unit_tests/run-all.py`
- **Edits:**
  - `plugins/mill/scripts/_review_common.py`
  - `plugins/mill/unit_tests/test-review-common.py`
- **Creates:** none
- **Deletes:** none
- **Moves:** none
- **Requirements:** Give both `bulk_files` and `bulk_files_with_diff` in `_review_common.py` a new keyword-only parameter `roots: DisplayRoots | None = None`. In each function, compute one display string per path -- `roots.render(p)` when `roots` is not `None`, else `str(p)` -- and substitute it into every delimiter interpolation: `--- FILE: {p} ---` and `--- END FILE: {p} ---` in `bulk_files`; the same two plus `--- DIFF: {p} (from {sha}) ---` and `--- END DIFF: {p} ---` in `bulk_files_with_diff`. Do not change the stderr warning strings emitted on a missing or unreadable path -- those are diagnostics for the operator, not prompt text, and an absolute path is the useful form there. Critically, do NOT reuse the display string for the `rel_path` local that `bulk_files_with_diff` already computes for its `git diff -- <path>` argument: that local must keep being derived from `project_root` as it is today, because the git invocation needs a path relative to the repository it runs `git -C` against, which is not necessarily the root the display helper selects. The two values are computed independently and neither replaces the other. Update both docstrings to document the new parameter. In `test-review-common.py`, add tests asserting: `bulk_files` with `roots` emits relative `--- FILE:` and `--- END FILE:` delimiters, and without `roots` still emits the absolute forms the existing tests rely on; `bulk_files_with_diff` with `roots` relativizes both the `FILE` and the `DIFF` delimiter pairs while its git-diff scoping still resolves, exercised through the same git-fixture pattern the file's existing `bulk_files_with_diff` tests already use.
- **Commit:** `feat(review): relativize bulk_files and bulk_files_with_diff delimiters`

### Card 4: `roots` keyword on `build_reattached_section`

- **Context:**
  - `plugins/mill/unit_tests/run-all.py`
- **Edits:**
  - `plugins/mill/scripts/_review_common.py`
  - `plugins/mill/unit_tests/test-review-common.py`
- **Creates:** none
- **Deletes:** none
- **Moves:** none
- **Requirements:** Give `build_reattached_section` in `_review_common.py` a new keyword-only parameter `roots: DisplayRoots | None = None` and forward it to its inner `bulk_files(file_paths)` call as `bulk_files(file_paths, roots=roots)`. The empty-input early return of the empty string is unchanged, and the `## Re-attached files (you said these were missing)` heading text is unchanged -- only the delimiters inside the bulked body become relative. Do not prepend a `## Path roots` block here: this section is spliced into a short resume-turn `retry_prompt`, and the roots were already stated in the original prompt of the same reviewer session. Update the docstring to document the new parameter and to state that the roots header is deliberately not repeated on the resume turn. In `test-review-common.py`, add tests asserting that with `roots` supplied the delimiters are relative and the heading is still present, and that with `roots` omitted the delimiters are still absolute.
- **Commit:** `feat(review): thread roots through build_reattached_section`

### Card 5: pin `build_deletes_section` output as already-relative

- **Context:**
  - `plugins/mill/scripts/_review_common.py`
  - `plugins/mill/unit_tests/run-all.py`
- **Edits:**
  - `plugins/mill/unit_tests/test-review-common.py`
- **Creates:** none
- **Deletes:** none
- **Moves:** none
- **Requirements:** Add a regression test in `test-review-common.py` pinning that `build_deletes_section` emits its input tokens verbatim: given a list of plan-relative token strings, every bullet in the returned block equals `- ` plus the corresponding token unchanged, the `## Intentionally deleted (N=<count>)` heading reports the right count, and no absolute path prefix appears anywhere in the output. Also assert the empty-list input still returns the empty string. Do not add a `roots` parameter to `build_deletes_section` and do not otherwise modify it -- this card exists to pin that the function is already correct because it is fed raw `deletes_union` tokens rather than resolved paths, so a future change cannot silently regress it. Name the test so the pin's intent is obvious from the failure output.
- **Commit:** `test(review): pin build_deletes_section tokens as already-relative`

## Batch Tests

`verify:` runs `plugins/mill/unit_tests/run-all.py --only test-review-common.py test-review-common-guard.py`. `test-review-common.py` is the file every card in this batch extends and is the direct test surface for all four modified helpers plus the new `DisplayRoots` type. `test-review-common-guard.py` is included because it exercises `_review_common.py`'s own module-level invariants; a signature change to four exported helpers in that module is exactly the kind of edit it exists to catch. The batch is scoped to those two files because it changes no caller -- every helper's new parameter defaults to `None` and reproduces today's output byte-for-byte, so no downstream flow test can observe this batch at all. The overview's module-wide `verify:` re-runs the plan and code flow suites at the batch boundary as the cross-package backstop for that claim.
