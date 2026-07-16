# Batch: go-build-tag-retiering-check

```yaml
task: Batch verify/baseline/completeness gates produce false positives or time out
batch: go-build-tag-retiering-check
number: 2
cards: 3
verify: PYTHONPATH= uv run --project plugins/mill python plugins/mill/unit_tests/test-implementer-common.py
depends-on: [1]
```

## Rename mechanic

Not applicable — this batch has no `Moves:` entries.

## Batch Scope

Fixes #642: mill-go's finalize pipeline has no check for Tier-1 (default/untagged) Go build breaks introduced when a batch adds or removes a `//go:build` constraint on a `.go` file, so such a break can go undetected for several batches after the one that introduced it. This batch adds a new automatic finalize-time gate — a `git diff`-based scan for default-build-membership transitions (tag added: file exits default build; tag removed: file enters default build), each triggering the matching compile check (untagged build for an added tag; the specific removed tag's build for a removed tag, restricted to single non-negated non-GOOS/GOARCH custom tags — compound/negated/GOOS constraints are logged and skipped, not translated, since a naive `-tags` translation of an arbitrary boolean expression risks compiling under the wrong tag set). This batch depends on batch 01 (`depends-on: [1]`) purely to serialize edits to `_implementer_common.py`'s explicit-success pipeline region — the two batches are functionally independent gates, but both touch the same file/region and the plan validator's `parallel-modifies-overlap` check requires a dependency edge between batches that write to the same file.

## Cards

### Card 8: Implement the build-tag-transition diff scan and compile check

- **Context:**
  - `plugins/mill/scripts/_subprocess_util.py`
- **Edits:**
  - `plugins/mill/scripts/_implementer_common.py`
- **Creates:** none
- **Deletes:** none
- **Moves:** none
- **Requirements:** Add a new private function, e.g. `_go_build_tag_retiering_stuck(project_root: Path, start_sha: str | None, session_id: str | None) -> dict | None`. Behavior:
  1. If `start_sha is None`: return `None` (nothing to diff against).
  2. Run `git diff --unified=0 <start_sha>..HEAD -- '*.go'` via `_subprocess_util.run` (cwd=`project_root`). If the subprocess fails or the diff is empty: return `None`.
  3. If there are no `.go` files in the diff at all: return `None` immediately (this makes the gate a safe no-op for non-Go batches/repos without needing a language-detection config flag).
  4. For each changed `.go` file in the diff, inspect the hunks for lines starting with `+//go:build ` or `-//go:build ` (modern syntax only — legacy `// +build` is explicitly out of scope for this gate; a value-only edit, where a `//go:build` line is both removed and re-added with a different value in the same file, is NOT a membership transition and must be skipped, not treated as an added+removed pair).
  5. Classify each file with exactly one added `//go:build` line and none removed as an **added-tag transition** (file exits the default/untagged build). Classify each file with exactly one removed `//go:build` line and none added as a **removed-tag transition** (file enters the default/untagged build). A file with both an added and a removed `//go:build` line at different values is a value-only edit — skip it (no transition).
  6. **Package resolution:** for each transitioned file, its "affected package" is the immediate directory containing it (Go's one-package-per-directory convention — no import-graph resolution needed). Deduplicate multiple transitioned files in the same directory to a single compile check per unique directory.
  7. For each **added-tag** directory: run `go build ./<dir>/...` (cwd=`project_root`) via `_subprocess_util.run`.
  8. For each **removed-tag** directory: parse the removed constraint (the line content after `//go:build `, trimmed). It qualifies for a compile check only if it is a single bare identifier with no `&&`, `||`, `!`, or parentheses, AND is not a recognized Go `GOOS`/`GOARCH` value (maintain a small fixed set covering the common values: GOOS = `{linux, darwin, windows, freebsd}`; GOARCH = `{amd64, arm64, 386}` — this need not be Go's exhaustive list, since an unrecognized-but-actually-GOOS value just degrades safely to "run the tag as a custom tag," and a false-custom-tag compile attempt with an invalid `-tags` value fails closed as a `verify`-stuck result, which is the safe direction). If it qualifies: run `go build -tags <tag> ./<dir>/...`. If it does NOT qualify (compound/negated/GOOS/GOARCH): print an ASCII-only stderr log line naming the file and the unparsed constraint, and do NOT run a compile check for that directory.
  9. If any compile check from steps 7/8 exits non-zero: return `{"status": "stuck", "stuck_type": "verify", "reason": f"go build-tag retiering check failed: <dir> (<added|removed>-tag transition): <captured output tail>", "session_id": session_id or "unknown"}`.
  10. If all compile checks pass (or there were none to run): return `None`.
  This function must never raise to its caller — wrap subprocess/parsing steps so any failure degrades to `None` (nothing to report) or the stuck dict from step 9, per this batch's own Shared Decision.
- **Commit:** `feat(_implementer_common): add Go build-tag retiering compile-break gate`

### Card 9: Wire the retiering gate into the explicit-success pipeline

- **Context:** none
- **Edits:**
  - `plugins/mill/scripts/_implementer_common.py`
- **Creates:** none
- **Deletes:** none
- **Moves:** none
- **Requirements:** Wire `_go_build_tag_retiering_stuck` into ALL FOUR paths in `_forward_output`/`finalize_from_output` that run a verify-gate-equivalent check followed by `_batch_completeness_stuck` — the explicit-success path AND the three no-JSON-inference fallback paths (batch 01's Card 4 already threads `card_ids`/`cards_done` through all four of these same call sites; insert this gate at each of the same four locations). Scoping the retiering gate to explicit-success only would leave the exact #642 failure mode uncaught on a batch that finalizes via inference (no valid `status` JSON found) but still introduced a genuine Tier-1 compile break — the sibling verify and completeness gates already run on all four paths for this reason, and the retiering gate must match that coverage. At each of the four locations: call `_go_build_tag_retiering_stuck(project_root, start_sha, <that path's own session-identifier variable — the same one already passed to that path's own `_batch_completeness_stuck` call>)` immediately after that path's own verify-gate-equivalent check passes and BEFORE that path's own no-content-commit check (explicit-success path only has this check) and its `_batch_completeness_stuck` call. If it returns a non-`None` stuck dict: attach `commit_sha` via the existing `_attach_commit_sha` helper (mirroring how each path's own verify-gate failure already attaches it), print the JSON, and return — short-circuiting before that path's completeness gate fires, exactly as each path's existing verify-gate failure already does.
- **Commit:** `fix(_implementer_common): run the build-tag retiering gate after verify, before completeness`

### Card 10: Unit tests for the retiering gate

- **Context:**
  - `plugins/mill/scripts/_implementer_common.py`
- **Edits:**
  - `plugins/mill/unit_tests/test-implementer-common.py`
- **Creates:** none
- **Deletes:** none
- **Moves:** none
- **Requirements:** Add cases to `test-implementer-common.py` (continuing its existing single-`main()`-with-inline-numbered-case style) for `_go_build_tag_retiering_stuck`, using a tempfile git repo fixture (consistent with this file's existing fixture pattern — no real LLM, no network): (a) adds `//go:build integration` to a previously-untagged `.go` fixture file → gate detects the added-tag transition and invokes (mocked) `go build ./<dir>/...` for the affected directory; (b) removes a single-custom-tag `//go:build integration` line from a previously-tagged file → gate detects the removed-tag transition and invokes (mocked) `go build -tags integration ./<dir>/...`; (c) removes a compound (`//go:build a && b`), negated (`//go:build !a`), or GOOS-only (`//go:build linux`) constraint → gate logs a skip and does NOT invoke a compile check; (d) a `//go:build` line whose value changes but which is present both before and after (value-only edit) → gate does not fire; (e) no `.go` files changed, or no build-tag lines changed at all → gate returns `None` silently; (f) a mocked compile-check failure (non-zero exit) → gate returns a `stuck_type: verify` dict naming the directory and transition direction; (g) case (f)'s scenario reached via one of the three no-JSON-inference fallback paths in `_forward_output`/`finalize_from_output` (not just the explicit-success path) → confirms Card 9's all-four-paths wiring, not just the explicit-success call site. Mock `_subprocess_util.run` for the `go build`/`go build -tags` invocations (no real Go toolchain required to run this test file).
- **Commit:** `test(implementer-common): cover Go build-tag retiering gate transitions`

## Batch Tests

`verify:` (frontmatter above) runs `test-implementer-common.py` only, since this batch's only `Edits:` target is `_implementer_common.py` and Card 10 is the only test file this batch touches.
