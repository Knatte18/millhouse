# Plan: Review prompt/output file listings resolve plan-relative paths to absolute before display, instead of keeping them relative

```yaml
task: "Review prompt/output file listings resolve plan-relative paths to absolute before display, instead of keeping them relative"
slug: "review-manifest-listings-full-path-clutter"
approved: true
started: "20260904-163712"
parent: "main"
root: ""
verify: PYTHONPATH= uv run --project plugins/mill python plugins/mill/unit_tests/run-all.py --only test-review-common.py test-review-common-guard.py test-review-plan-flow.py test-review-code-flow.py
```

## Batch Index

_The fenced yaml block below is the authoritative DAG mill-go reads to schedule batches._

```yaml
batches:
  - number: 1
    name: display-layer
    file: 01-display-layer.md
    depends-on: []
    verify: PYTHONPATH= uv run --project plugins/mill python plugins/mill/unit_tests/run-all.py --only test-review-common.py test-review-common-guard.py
  - number: 2
    name: plan-review-wiring
    file: 02-plan-review-wiring.md
    depends-on: [1]
    verify: PYTHONPATH= uv run --project plugins/mill python plugins/mill/unit_tests/run-all.py --only test-review-plan-flow.py
  - number: 3
    name: code-review-wiring
    file: 03-code-review-wiring.md
    depends-on: [1]
    verify: PYTHONPATH= uv run --project plugins/mill python plugins/mill/unit_tests/run-all.py --only test-review-code-flow.py test-millpy-merge-in-subagent.py
```

## Shared Decisions

### Decision: display-only layer, resolvers untouched

- **Decision:** Relativization happens only where a path is rendered into prompt text. `resolve_ref_paths()` and `resolve_existing_paths()` keep their current signatures and keep returning absolute `list[Path]`.
- **Rationale:** Those absolute paths are load-bearing -- they feed `_read_for_bulk()`, `git diff` invocations, and `Path.exists()` checks. The leak is at the render boundary, so the fix belongs at the render boundary.
- **Applies to:** all batches

### Decision: `DisplayRoots` is the single rendering authority

- **Decision:** One frozen dataclass `DisplayRoots(project_root, git_root=None, wiki_root=None)` in `_review_common.py`, with a single method that renders one `Path` to a display string. Every display site calls that one method -- no site re-implements the ancestor test.
- **Rationale:** Six display sites re-implementing longest-match logic would drift. `prepare()` in both review modules already receives all three roots, so constructing the value is a one-liner per site.
- **Applies to:** all batches

### Decision: rendering rule -- wiki first, then longest-match, then absolute

- **Decision:** For one absolute `Path`: (1) if `wiki_root` is set and the path is under it, render `wiki/<rel>`; (2) otherwise pick the **longest** of `project_root` / `git_root` that is an ancestor and render relative to it; (3) if no root is an ancestor, render the absolute path unchanged. Always `.as_posix()`.
- **Rationale:** `wiki/<rel>` is the exact token form the plan card wrote, so the manifest round-trips to the plan text. Longest-match handles a plan with a non-empty `root:` sub-path. Rule 3 is the safety valve -- absolute is verbose but never wrong.
- **Applies to:** all batches

### Decision: `roots` is keyword-only and defaults to `None`

- **Decision:** `build_manifest_section`, `bulk_files`, `bulk_files_with_diff`, and `build_reattached_section` each gain a keyword-only `roots: DisplayRoots | None = None`. When `None`, output is byte-identical to today's (absolute). Every production call site passes a real `DisplayRoots`.
- **Rationale:** Keeps the large existing body of helper tests in `test-review-common.py` green and the diff focused on production call sites. The flow-level "no absolute-root prefix in the assembled prompt" assertions are what actually catch a production site left on the default.
- **Applies to:** all batches

### Decision: the `## Path roots` header is emitted by `build_manifest_section`

- **Decision:** When `roots` is not `None`, `build_manifest_section` prepends a `## Path roots` block ahead of its `## Files included (N=...)` heading. No review template is edited; every review template inherits the header because it arrives inside `<ARTEFACT_SECTION>`.
- **Rationale:** A new `<PATH_ROOTS>` template token would mean four template edits plus a `render_prompt` kwarg at five call sites for identical output, with a real risk of one template being missed. Emitting from the manifest builder is one place.
- **Applies to:** all batches

### Decision: tool-use lists carry a resolve-against-stated-root instruction

- **Decision:** Tool-use `read_list` / `batch_list` / `Overview:` / `Batch:` lines are relativized like the manifest, and the surrounding instruction prose is amended to tell the reviewer to resolve each listed path against the root stated in `## Path roots`.
- **Rationale:** `run_tool_use()` in `_llm_claude.py` takes no `cwd` and forwards none, so the reviewer subprocess merely inherits the ambient cwd. That invariant holds in practice but nothing in the review code path sets it, so correctness must not depend on it. Instructing the reviewer to join the stated absolute root makes an absolute path reach `Read` regardless of cwd, while the listing itself stays short.
- **Applies to:** plan-review-wiring, code-review-wiring

### Decision: `build_deletes_section` and `millpy-merge-in-subagent.py` are verified, not changed

- **Decision:** Neither is modified. Each gets a regression assertion pinning that its output is already relative.
- **Rationale:** `build_deletes_section` is fed raw `deletes_union` token strings at all six call sites, never resolved `Path`s. `millpy-merge-in-subagent.py`'s `--files` comes from `git diff --name-only --diff-filter=U`, which emits repo-relative paths. The task brief's claim that both leak absolute paths is inaccurate; the pins keep it that way.
- **Applies to:** display-layer, code-review-wiring

### Decision: `done_gate` stays `null`

- **Decision:** `pipeline.done_gate` is left at `null`; no `mill-config.yaml` change is made by this plan.
- **Rationale:** The lint-command default was evaluated as instructed -- `uvx ruff check .` at the worktree tip reports 1969 pre-existing errors and does not exit 0. Making every future task in this hub depend on that unrelated debt being cleared first is not this task's call. The repo-wide `run-all.py` suite is multiple minutes, so it is not a suitable done-gate either. The overview's module-wide `verify:` covers the cross-batch regression risk from the shared-helper edit instead.
- **Applies to:** all batches

## All Files Touched

- `plugins/mill/scripts/_review_code.py`
- `plugins/mill/scripts/_review_common.py`
- `plugins/mill/scripts/_review_plan.py`
- `plugins/mill/unit_tests/test-millpy-merge-in-subagent.py`
- `plugins/mill/unit_tests/test-review-code-flow.py`
- `plugins/mill/unit_tests/test-review-common.py`
- `plugins/mill/unit_tests/test-review-plan-flow.py`
