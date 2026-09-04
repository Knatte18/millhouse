# Discussion: Review prompt/output file listings resolve plan-relative paths to absolute before display, instead of keeping them relative

```yaml
task: Review prompt/output file listings resolve plan-relative paths to absolute before display, instead of keeping them relative
slug: review-manifest-listings-full-path-clutter
status: discussing
parent: main
```

## Problem

Plan cards declare their `Context:` / `Edits:` / `Creates:` / `Deletes:` references as short repo-relative paths (`plugins/mill/scripts/_review_common.py`). The review backend must turn those into absolute paths to actually open the files -- that is `resolve_ref_paths()`'s job, and it is correct. The bug is that the resolved absolute `Path` is then what gets *printed*: nobody converts it back to the relative form before it lands in the reviewer prompt.

The result is that every review prompt (and every persisted review artefact) repeats the same long absolute prefix on every single line. In this container layout that prefix is `/home/knatte/Code/millhouse/wts/<slug>/` -- roughly 50 characters per file. Across a 24-file manifest the same prefix is printed 24 times in `## Files included`, again on every `--- FILE: ... ---` / `--- END FILE: ... ---` delimiter pair, and again in the tool-use `read_list` / `batch_list`. It is pure repeated-prefix noise: it costs prompt tokens, it makes the manifest harder to scan, and it makes the committed review file needlessly machine-specific (an absolute path from one operator's machine is meaningless in another's checkout).

**Why now:** reported directly by the operator on 2026-09-04 after reading a review artefact. No GitHub issue.

## Scope

**In:**

- New display-only path-rendering layer in `plugins/mill/scripts/_review_common.py`: a `DisplayRoots` value type plus a rendering helper and a `## Path roots` header builder.
- `build_manifest_section()` -- render each entry relative to the matching root.
- `bulk_files()` and `bulk_files_with_diff()` -- relativize the `--- FILE: ... ---`, `--- END FILE: ... ---`, `--- DIFF: ... ---`, `--- END DIFF: ... ---` delimiters.
- `build_reattached_section()` (`_review_common.py:1357`) -- the NEED_CONTEXT resume-retry re-attachment. It calls `bulk_files(file_paths)` at line 1368 with no roots, so it emits absolute `--- FILE: ... ---` delimiters into the `retry_prompt`. It takes the same new `roots: DisplayRoots | None` keyword and forwards it to `bulk_files`, threaded from its three call sites: `_review_plan.py:298`, `_review_plan.py:1120`, `_review_code.py:770`.
- `_review_plan.py` prompt assembly: the `read_list` / `batch_list` / `Overview:` / `Batch:` lines at the four sites (batch-mode ~lines 232-253, second batch-mode block ~lines 505-526, holistic ~lines 614-635, run-holistic ~lines 1045-1066).
- `_review_code.py` `_build_artefact_section()` (defined at line 136; the interpolation sites are ~lines 158-188): `batch_list`, `read_list`, `Overview:` line.
- Emitting the `## Path roots` header once per artefact section so the absolute roots are still stated exactly once.
- Unit tests for the new helper and flow-level assertions that assembled prompts carry no absolute-root prefix.

**Out:**

- The plan file format. Plan cards already write relative tokens; `plan-batch.md` needs no change.
- `resolve_ref_paths()` / `resolve_existing_paths()` return types. They keep returning absolute `list[Path]` -- resolution and display stay separate concerns.
- `build_deletes_section()`. It is already fed raw `deletes_union` *tokens* (relative strings), never resolved `Path`s. The task brief's claim that `## Intentionally deleted` leaks absolute paths is **inaccurate** -- verified at `_review_common.py:1281` and its callers `_review_plan.py:253,526,635,1066` and `_review_code.py:188`, all of which pass `sorted(deletes_union)`. No change; add a regression test only.
- `millpy-merge-in-subagent.py`'s `conflicting_files` (line 450). `--files` is supplied by `mill-merge-in/SKILL.md` from `git diff --name-only --diff-filter=U`, which emits repo-relative paths. The brief's claim of "full path per file" here is **inaccurate**. No change; verify only.
- Every other `PROJECT_ROOT` template field (`implementer-brief.md`, `fixer-*-brief.md`, `merge-in-*-brief.md`). Those are deliberate: they tell a sub-agent its cwd for `git -C`. Not a listing, not clutter.
- `_review_discussion.py` -- the discussion reviewer bulks a single file and has no manifest of plan refs.
- Review *output* schema / `review-output.schema.md`. The reviewer will naturally cite relative paths once it is shown relative paths; no schema change is needed to make that happen.

## Decisions

### display-only-layer

- Decision: relativization is a **display-only** layer applied at prompt-assembly time. `resolve_ref_paths()` and `resolve_existing_paths()` keep their current signature and keep returning absolute `list[Path]`.
- Rationale: those absolute paths are load-bearing -- they are handed to `_read_for_bulk()`, to `git diff` invocations, and to `Path.exists()` checks. Changing the return type would touch every one of the 10+ call sites and risk breaking file reads for a purely cosmetic gain. The leak is at the render boundary, so the fix belongs at the render boundary.
- Rejected: (a) returning `(path, display)` tuples or a `ResolvedRef` dataclass from the resolvers -- much larger blast radius, and callers that only want the path now have to unpack; (b) relativizing inside each template renderer -- duplicates the same longest-match logic at all six display sites -- the five artefact-assembly sites (four in `_review_plan.py`, one in `_review_code.py`) plus the NEED_CONTEXT re-attachment site (`build_reattached_section`, reached from three further call sites) -- and guarantees drift.

### display-roots-value-type

- Decision: introduce a small frozen dataclass in `_review_common.py`:

  ```python
  @dataclass(frozen=True)
  class DisplayRoots:
      project_root: Path
      git_root: Path | None = None
      wiki_root: Path | None = None
  ```

  with a method that renders one `Path` to a display string, and a module-level function that builds the `## Path roots` header.
- Rationale: `prepare()` in both `_review_plan.py` and `_review_code.py` already receives exactly `project_root`, `wiki_root`, `git_root` as parameters (`_review_code.py:198-200`), so constructing this object is a one-liner at each prepare site. Bundling them into one value keeps every downstream signature to a single extra keyword argument instead of three.
- Rejected: passing the three roots individually through `build_manifest_section` / `bulk_files` / `bulk_files_with_diff` -- three extra params on four functions is noise; a module-level global set once per prepare -- implicit state, and the unit tests run multiple prepares in one process.

### rendering-rule

- Decision: rendering rule for a single absolute `Path`, in this order:
  1. If `wiki_root` is set and the path is under it -> render as `wiki/<relative-to-wiki_root>` (POSIX separators).
  2. Otherwise, among `project_root` and `git_root` (whichever are set), pick the **longest** root that is an ancestor of the path and render the path relative to it (POSIX separators).
  3. If no root is an ancestor -> render the absolute path unchanged.
- Rationale: the `wiki/` prefix is exactly the token form the plan card wrote (`resolve_ref_paths` strips a literal `wiki/` prefix before joining onto `wiki_root`), so round-tripping to that form makes the manifest match the plan text character-for-character. Longest-match matters because a plan with a `root:` sub-path resolves under `git_root / root`, and `project_root` may itself already end with `root`; picking the longer ancestor yields the shorter, more meaningful relative path. Rule 3 is the safety valve -- a path genuinely outside every root (an absolute `Context:` ref, a temp fixture) must still be unambiguous, and an absolute string is never wrong, only verbose.
- Rejected: (a) project_root-only matching -- would leave every wiki-routed and `root:`-sub-path file absolute, which is a large share of the manifest in plan reviews; (b) a per-file root tag column (`[wiki] Home.md`) -- more visual noise than the prefix it removes, and it does not match the plan token form.

### path-roots-header

- Decision: each artefact section gains a `## Path roots` block, emitted **before** the `## Files included` manifest, listing each non-`None` root once:

  ```text
  ## Path roots

  All paths below are relative to `<project_root>` unless otherwise prefixed.
  - `wiki/` -> `<wiki_root>`
  ```

  The `wiki/` line is emitted only when `wiki_root` is set; a `git_root` line is emitted only when `git_root` differs from `project_root`. The block is built by the same code that builds the manifest and spliced into `<ARTEFACT_SECTION>` -- no review template changes.
- Rationale: the absolute root must still be stated exactly once, both so a tool-use reviewer has an unambiguous fallback and so the persisted review artefact remains interpretable out of context. Splicing into `<ARTEFACT_SECTION>` means all four review templates (`review-plan-batch.md`, `review-plan-holistic.md`, `review-code-batch.md`, `review-code-holistic.md`) inherit it with zero template edits, and there is no risk of one template being updated and another missed.
- Rejected: a new `<PATH_ROOTS>` template token -- four template edits plus a `render_prompt` kwarg at six call sites, for output that is identical.

### keyword-only-optional-roots

- Decision: `build_manifest_section`, `bulk_files`, and `bulk_files_with_diff` each gain a keyword-only `roots: DisplayRoots | None = None`. When `None`, behaviour is exactly today's (absolute paths). Every production call site passes a real `DisplayRoots`.
- Rationale: the existing unit tests in `test-review-common.py` (lines ~884-894, ~1860-1881, ~3417) call these helpers positionally with bare `Path`s and assert on absolute output; a defaulted keyword keeps them green and keeps the diff focused on the production call sites. It also means an ad-hoc caller cannot crash on a missing argument.
- Rejected: a required positional parameter -- forces a mechanical rewrite of unrelated tests in the same commit and buries the real change.
- Guard against the obvious failure mode of an optional param (a production site silently left absolute): the flow-level tests named under **Testing** assert on the *assembled prompt*, so a missed call site fails the suite even though the helper signature tolerates omission.

### tool-use-mode-relative

- Decision: the tool-use `read_list` / `batch_list` / `Overview:` / `Batch:` lines are relativized too, exactly like the bulk-mode manifest.
- Rationale: a tool-use reviewer runs with cwd set to the task worktree (`_llm_claude.run_tool_use` passes `cwd` through, and agent-mode dispatch inherits the orchestrator's worktree cwd), so a project-root-relative path resolves correctly for a `Read`. The `## Path roots` header directly above gives the absolute root as a fallback if the reviewer needs to disambiguate. Leaving tool-use absolute while the manifest immediately above it is relative would be actively confusing -- the two lists name the same files.
- Rejected: keeping absolute paths in tool-use mode only.

### need-context-round-trip

- Decision: no change to `parse_missing_context()` / `_RE_MISSING_CONTEXT_BULLET` (`_review_common.py:1302,1323`). Treat the round-trip as a verified non-regression, not a work item.
- Rationale: a reviewer that emits `NEED_CONTEXT` lists paths under `## Missing context`; those tokens are fed straight back into `resolve_ref_paths()`. Today the reviewer echoes absolute paths, which happen to survive because `Path("/abs") / "/abs/x"` yields the absolute path. After this change the reviewer echoes *relative* tokens, which is the shape `resolve_ref_paths` is actually designed for. The round-trip gets strictly better; no code change is needed to achieve it.

## Technical context

Everything lives under `plugins/mill/scripts/`.

**`_review_common.py`** -- the shared review backend, and the home of the new code:

- `resolve_ref_paths()` (line 888) -- resolves raw ref strings to absolute `Path`s. Routing order: `wiki/`-prefixed -> `wiki_root`; else `git_root / root / raw`, then `project_root / root / raw` (or `project_root / raw` when no `root`), then `git_root / raw`. Returns `list[Path]`. **Not modified.**
- `resolve_existing_paths()` (line ~1020) -- same routing, silent-drop on miss, used for cross-batch ancestor creates and `Moves:` sources. **Not modified.**
- `bulk_files()` (line 1174) -- emits `--- FILE: {p} ---\n{contents}\n--- END FILE: {p} ---`. Two interpolations to relativize.
- `bulk_files_with_diff()` (line ~1194) -- same delimiters plus `--- DIFF: {p} (from {sha}) ---` / `--- END DIFF: {p} ---`. Four interpolations. Note it *already* computes `rel_path = p.relative_to(project_root).as_posix()` internally (with a `ValueError` fallback to `str(p)`) for the `git diff -- <path>` argument; that existing local is the same idea as the new helper but is used only for the git invocation, not for display. Do not conflate the two -- the git call needs a path relative to the repo it is running `git -C` against, which is not necessarily the same root the display helper picks.
- `build_manifest_section()` (line 1258) -- `- {p}` bullets under `## Files included (N=...)`.
- `build_deletes_section()` (line 1281) -- takes `list[str]` tokens. Already relative. **Not modified.**
- `build_reattached_section()` (line 1357) -- returns `## Re-attached files (you said these were missing)` followed by `bulk_files(file_paths)` (line 1368). This is the **sixth display site** and it is easy to miss: it does not build an `artefact_section` at all, it builds a separate short `retry_prompt` sent as a *resume* turn into the same reviewer session after a `NEED_CONTEXT` verdict. Left unfixed it produces the worst possible split -- the reviewer sees a relative manifest and relative `--- FILE: ---` delimiters in turn 1, then absolute delimiters for the same files in turn 2 of the same conversation, which is precisely the confusion the `tool-use-mode-relative` decision rejects. Gains the same `roots: DisplayRoots | None = None` keyword and forwards it to `bulk_files`.

**`_review_plan.py`** -- four prompt-assembly sites, all with the same shape (`manifest = build_manifest_section(...)` then either a tool-use `read_list` or a `bulk_files()` call):

- **Site 1 -- batch-mode**, inside `_review_one_batch()` (def line 134): resolvers at 192-207, `build_manifest_section` at 232, `read_list` at 235, `Overview:`/`Batch:` backtick lines at ~239-240, deletes at 253.
- **Site 2 -- second batch-mode block**, inside `prepare()` (def line 382): resolvers at 461-471, manifest at 505, `read_list` at 508, deletes at 526.
- **Site 3 -- holistic**, also inside `prepare()`: resolvers at 577-587, manifest at 614, `batch_list` at 617, `read_list` at 618, deletes at 635.
- **Site 4 -- run-holistic**, inline inside `run()` (def line 750): resolvers at 1008-1018, manifest at 1045, `batch_list` at 1048, `read_list` at 1049, deletes at 1066.

`_review_plan.py` also has **two NEED_CONTEXT resume-retry branches** that are not artefact-assembly sites but do build a display list: line 298 (inside `_review_one_batch`) and line 1120 (inside `run()`). Each resolves `missing_paths` via `resolve_existing_paths(missing_raw, project_root, root, wiki_root=wiki_root, git_root=git_root)` and then calls `build_reattached_section(missing_paths)`. Every root needed to construct a `DisplayRoots` is already in scope at both branches, so threading is a one-argument change at each.

Note the inconsistency to preserve-or-normalise deliberately: the per-batch `read_list` uses `f"- {p}"` (no backticks) while the holistic `batch_list`/`read_list` use `f"- \`{p}\`"`. Backticking is cosmetic and orthogonal to this task -- keep each site's existing backtick convention, change only the path rendering.

**`_review_code.py`** -- one assembly site, the module-private `_build_artefact_section()` (defined at line 136, called once at line 349): `all_bulked` -> `build_manifest_section` (158), tool-use `batch_list` (161) / `read_list` (162), bulk-mode `bulk_files` / `bulk_files_with_diff` (~173-177), deletes (188). Its `prepare()` (line ~196) already takes `project_root`, `wiki_root`, `git_root` -- `_build_artefact_section` currently receives only an optional `project_root`, so it needs the new `roots` argument threaded in from `prepare` at the line-349 call. `_review_code.py` also has **one NEED_CONTEXT resume-retry branch** at line 770, structurally identical to `_review_plan.py`'s two: `resolve_existing_paths(...)` -> `build_reattached_section(missing_paths)` -> `retry_prompt`, with all roots already in scope.

**Review templates** (`plugins/mill/templates/review-{plan,code}-{batch,holistic}.md`) reference `--- FILE: <path> ---` in their source-grounding rule prose. That prose stays valid verbatim -- the delimiter shape is unchanged, only the `<path>` inside it gets shorter. No template edits.

**Gotchas:**

- ASCII-only in `print()`/`_log()` output per CLAUDE.md. The `->` in the `## Path roots` header goes into a prompt string, not stdout, so it is fine, but keep the header ASCII anyway for consistency.
- Use `.as_posix()` on every relative render so Windows and Linux produce identical prompts (and identical committed review artefacts).
- `Path.relative_to` raises `ValueError` when the path is not under the root; use `Path.is_relative_to` (Python 3.9+) for the ancestor test rather than try/except, or catch `ValueError` -- either is fine, be consistent.
- Roots must be compared in resolved form. `project_root` / `git_root` may arrive with symlink or junction components; call `.resolve()` on both the roots and the candidate path before the ancestor test, but render from the *original* path's relative remainder so the output is not surprising. Simplest correct approach: resolve both sides for the comparison and for `relative_to`, since the relative remainder is identical either way.
- `DisplayRoots` is `frozen=True` so it can be constructed once per `prepare()` and threaded read-only.

## Testing

**TDD candidates (write the test first):**

1. `DisplayRoots` rendering helper, in `plugins/mill/unit_tests/test-review-common.py`:
   - path directly under `project_root` -> bare relative POSIX string.
   - path under `wiki_root` -> `wiki/<rel>` prefix.
   - path under both `git_root` and a deeper `project_root` -> renders against the **longer** root.
   - path under no root -> absolute string, unchanged.
   - Windows-style nested path renders with forward slashes.
   - `git_root=None` / `wiki_root=None` -> no crash, falls back to `project_root` then absolute.
2. `## Path roots` header builder:
   - project_root only -> single line, no `wiki/` line, no git line.
   - `wiki_root` set -> `wiki/` line present.
   - `git_root == project_root` -> no separate git line (no redundant duplicate root).
   - `git_root != project_root` -> git line present.

**Regression / behaviour tests:**

3. `build_manifest_section(paths, roots=...)` emits relative bullets; `build_manifest_section(paths)` (no `roots`) still emits absolute bullets -- pins the back-compat default that the existing tests at `test-review-common.py:1860-1881` rely on.
4. `bulk_files(paths, roots=...)` -> `--- FILE: <rel> ---` and `--- END FILE: <rel> ---`. Existing not-found-skip and directory-skip behaviour (lines ~884, ~3417) unchanged.
5. `bulk_files_with_diff(..., roots=...)` -> both the `FILE` and the `DIFF` delimiter pairs relativized, and the internal `git diff -- <path>` argument still uses the repo-relative path it uses today (assert the diff still resolves, e.g. via the existing fixture pattern in the file).
6. `build_deletes_section` regression: given raw tokens, output bullets equal the tokens verbatim -- pins that this section was already correct and stays correct.

**Flow-level tests (the real guard against a missed call site):**

7. In `plugins/mill/unit_tests/test-review-plan-flow.py`: cover the **four canonical `_review_plan.py` assembly sites** named in Scope and Technical context -- batch-mode (`_review_one_batch`, manifest at line 232), second batch-mode block (inside `prepare()`, manifest at line 505), holistic (manifest at 614), run-holistic (manifest at 1045). These are four *sites spread across three different functions* -- `_review_one_batch` (defined line 134) holds site 1 (manifest 232); `prepare()` (defined line 382) holds sites 2 and 3 (manifests 505 and 614); `run()` (defined line 750) holds site 4 inline (manifest 1045, `batch_list`/`read_list` 1048-1049). Site 4 is therefore reached through `run()`'s own holistic dispatch path, not through `prepare()`. They are not bulk/tool-use mode variants of one site -- the two per-batch blocks are near-duplicates and it is exactly the kind of pair where one gets updated and the other missed. For each site assert the generated `prompt_text` contains **no occurrence of `str(project_root)`**, does contain the expected relative token (e.g. `path/a`), and contains the `## Path roots` heading. Additionally exercise both `bulk` and `tool-use` reviewer modes at whichever sites support both, so the `read_list` / `batch_list` interpolations are covered as well as the manifest and the `--- FILE: ---` delimiters. If the existing test harness cannot reach one of the four sites directly, that is itself a finding for mill-plan to solve -- do not drop the site from coverage, since the flow-level assertion is the only guard against a production call site left on the defaulted-`None` `roots` path.
8. In `plugins/mill/unit_tests/test-review-code-flow.py`: same three assertions for `_build_artefact_section` in both `bulk` and `tool-use` reviewer modes.
8b. **NEED_CONTEXT resume `retry_prompt` coverage** -- a unit test for `build_reattached_section(paths, roots=...)` asserting relative `--- FILE: ---` / `--- END FILE: ---` delimiters (and that the no-`roots` call still emits absolute, per the back-compat default), plus at least one flow-level test that drives a reviewer stub to return `NEED_CONTEXT` with a `## Missing context` bullet and asserts the resulting `retry_prompt` contains no occurrence of `str(project_root)`. This site is invisible to items 7-9, which only assert on the primary `prompt_text`.
9. `millpy-merge-in-subagent.py` verification: an assertion (or, if no natural home exists, a documented manual check recorded in the plan) that `conflicting_files` renders the `--files` argument verbatim -- pinning that repo-relative input stays repo-relative and that this file needs no change.

**Scenarios that must be covered:** empty manifest (`N=0`, `(no files)` unchanged); a plan with a non-empty `root:` sub-path; a manifest mixing project-root, wiki-root, and outside-any-root paths in one list; tool-use mode and bulk mode for both plan and code reviews.

Run the suite via `plugins/mill/unit_tests/run-all.py` with a `PYTHONPATH=` (empty) prefix per the project's verify-command convention.

## Q&A log

- **Q:** Where should relativization happen -- display-only layer, resolve-time return-type change, or per-template? **A:** [auto-pick] Display-only layer in `_review_common.py`. **Why:** the resolvers' absolute paths are load-bearing for file reads and `git diff`; the leak is purely at the render boundary, so fixing it there keeps the blast radius to the six display sites (five artefact-assembly sites plus the NEED_CONTEXT re-attachment).
- **Q:** How should multiple roots (project, git, wiki) be rendered? **A:** [auto-pick] `DisplayRoots` dataclass with longest-match-wins and a `wiki/` prefix for wiki-routed paths. **Why:** `wiki/<rel>` is exactly the token form the plan card wrote, so the manifest round-trips to the plan text; longest-match handles `root:` sub-path plans correctly.
- **Q:** Should the new `roots` parameter be optional or required on the shared helpers? **A:** [auto-pick] Keyword-only, defaulting to `None` (absolute, today's behaviour). **Why:** keeps the existing `test-review-common.py` helper tests green and the diff focused; the flow-level prompt assertions are what actually catch a missed production call site.
- **Q:** Should tool-use `read_list` / `batch_list` also go relative, given the reviewer must `Read` those paths itself? **A:** [auto-pick] Yes, relative, with the `## Path roots` header stating the absolute root once. **Why:** tool-use reviewers run with cwd at the task worktree so relative Reads resolve; a relative manifest sitting directly above an absolute read-list would be confusing.
- **Q:** Does `millpy-merge-in-subagent.py`'s `conflicting_files` need fixing? **A:** [auto-pick] No -- verify only, no code change. **Why:** `--files` comes from `git diff --name-only --diff-filter=U` via `mill-merge-in/SKILL.md`, which emits repo-relative paths; the task brief's claim of full paths there is inaccurate.
- **Q:** Does the `## Intentionally deleted` section need fixing? **A:** [auto-pick] No -- add a regression test only. **Why:** `build_deletes_section` is fed raw `deletes_union` token strings at all six call sites, never resolved `Path`s; the brief's claim is inaccurate here too.
- **Q:** Where should the root header live -- spliced into `<ARTEFACT_SECTION>`, or a new template token? **A:** [auto-pick] Spliced into `<ARTEFACT_SECTION>` by the manifest builder. **Why:** all four review templates inherit it with zero template edits and no risk of one template being missed.
- **Q:** Should `--- DIFF: ... ---` delimiters be relativized too? **A:** [auto-pick] Yes. **Why:** same leak, same display path, same fix -- leaving one delimiter family absolute would be arbitrary.
- **Q:** What is the test strategy? **A:** [auto-pick] Helper + header unit tests in `test-review-common.py`, plus flow-level assertions in `test-review-plan-flow.py` / `test-review-code-flow.py` that assembled prompts contain no absolute root prefix. **Why:** the flow-level assertions are the only thing that catches a production call site left on the defaulted-`None` path.
- **Q:** Round-3 review found a sixth display site -- `build_reattached_section()`, the NEED_CONTEXT resume re-attachment -- absent from Scope, Technical context, and the test plan. Add it, or argue it out of scope? **A:** [auto-pick] Add it as a first-class in-scope site. **Why:** it calls `bulk_files` with no roots, so it would keep emitting absolute `--- FILE: ---` delimiters into the `retry_prompt` -- and because that retry is a *resume* turn in the same reviewer session, the reviewer would see relative paths in turn 1 and absolute paths for the same files in turn 2. The flow-level guard relied on by `keyword-only-optional-roots` asserts only on the primary `prompt_text`, so nothing would have caught it.
