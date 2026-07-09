# Batch: resolve-scope-core

```yaml
task: Fix codeguide-update scope resolution on stacked branches and resolve_scope.py branch-name parsing
batch: resolve-scope-core
number: 1
cards: 4
verify: PYTHONPATH= "$MILL_PYTHON" plugins/codeguide/unit_tests/test-resolve-scope.py
depends-on: []
```

## Rename mechanic

Not applicable — this batch has no `Moves:` entries.

## Batch Scope

Fixes the core dispatch logic in `plugins/codeguide/scripts/resolve_scope.py` that underlies all three bugs (#611, #617, #621): (1) broaden the single-token dispatch so any git-resolvable ref — not just hex SHAs — routes through the head-rev path, including a literal `..HEAD`-suffixed token; (2) add an optional `--parent <ref>` CLI flag/kwarg that lets a caller override the no-arg mode's base-branch detection, with a graceful fallback to today's git-native detection when the supplied ref doesn't resolve. Extends the existing 13-scenario test file with 5 new scenarios covering both changes plus a regression guard. Adds a one-line doc-accuracy note to `codeguide-update`'s SKILL.md so the `--parent` override isn't undocumented. This batch delivers the complete `resolve_scope.py` public contract (CLI + `enumerate_scope()` Python API) that batch 3's skill-prose changes call into — it does not touch any mill-side code (see Shared Decision "resolve_scope.py stays mill-agnostic").

## Cards

### Card 1: Broaden single-token ref dispatch with literal `..HEAD` stripping

- **Context:** none
- **Edits:**
  - `plugins/codeguide/scripts/resolve_scope.py`
- **Creates:** none
- **Deletes:** none
- **Moves:** none
- **Requirements:**
  - Add a new function `_resolve_ref_token(toplevel: pathlib.Path, token: str) -> str | None`, placed immediately before `enumerate_scope`. Body: if `token` ends with the literal suffix `"..HEAD"`, set `candidate = token[: -len("..HEAD")]`; otherwise `candidate = token`. Run `_git(toplevel, "rev-parse", "--verify", "--quiet", f"{candidate}^{{commit}}")`. Return `candidate` if the call's return code is `0`, else return `None`. Any token containing `..` that is NOT a literal trailing `..HEAD` suffix is passed through unstripped to this same rev-parse check (which will simply fail to resolve it as a ref) — do not add any other `..`-splitting logic (see Shared Decision "literal `..HEAD` suffix stripping only").
  - In `enumerate_scope`, replace the existing `if len(args) == 1:` block's body (currently: `if _TIME_RE.match(token): return _time_scope(...)` followed by `if token.startswith("HEAD~") or token == "HEAD" or _HEX_RE.match(token): return _head_rev_scope(...)`) with: keep the `_TIME_RE.match(token)` check first (unchanged — time-form tokens like `3d`/`1h` must never attempt ref resolution), then call `resolved = _resolve_ref_token(toplevel, token)`; if `resolved is not None`, `return _head_rev_scope(toplevel, resolved)`. Remove the old `token.startswith("HEAD~") or token == "HEAD" or _HEX_RE.match(token)` line entirely — `_resolve_ref_token` subsumes all of hex-SHA, `HEAD`, and `HEAD~N` recognition, since `git rev-parse --verify --quiet <token>^{commit}` resolves all three natively.
  - Delete the now-unreferenced `_HEX_RE = re.compile(r"^[0-9a-f]{7,40}$", re.IGNORECASE)` module constant. Keep `_TIME_RE` — it is still used.
  - Update the module docstring (lines 1-39) to reflect the new dispatch: replace bullet 3 ("HEAD-rev arg...") to describe the general ref-resolution check instead of the narrow regex, and note the `--parent` override in the "No-arg" bullet (bullet 1) and the "Public API" section's CLI usage line (`python resolve_scope.py [--parent <ref>] [<args>]`).
- **Commit:** `fix(codeguide): broaden resolve_scope.py single-token dispatch to any resolvable git ref`

### Card 2: Add `--parent` override with graceful fallback in no-arg mode

- **Context:** none
- **Edits:**
  - `plugins/codeguide/scripts/resolve_scope.py`
- **Creates:** none
- **Deletes:** none
- **Moves:** none
- **Requirements:**
  - Change `_no_arg_scope(toplevel: pathlib.Path) -> tuple[list[pathlib.Path], dict]` to `_no_arg_scope(toplevel: pathlib.Path, parent: str | None = None) -> tuple[list[pathlib.Path], dict]`. Inside: after computing `current_branch`, determine `base_branch` as follows — if `parent is not None`, run `_git(toplevel, "rev-parse", "--verify", "--quiet", f"{parent}^{{commit}}")`; if its return code is `0`, set `base_branch = parent`; otherwise (or if `parent is None`) fall through to `base_branch = _detect_base_branch(toplevel)` exactly as today. Rename the existing local variable that tracks the summary's `parent` field from `parent` to `resolved_parent` (it collides with the new `parent` parameter name) — every other line of the function (the `current_branch != base_branch` check, the committed-diff computation, the staged/unstaged union, the final `summary` dict's `"parent": resolved_parent` and `"base_branch": base_branch` fields) is otherwise unchanged from the current implementation.
  - Change `enumerate_scope(args: list[str], cwd: pathlib.Path | None = None) -> tuple[...]` to `enumerate_scope(args: list[str], cwd: pathlib.Path | None = None, parent: str | None = None) -> tuple[...]`. Change the `if not args: return _no_arg_scope(toplevel)` line to `if not args: return _no_arg_scope(toplevel, parent=parent)`. No other line in `enumerate_scope` changes — `parent` is never consulted when `args` is non-empty (positional args already take priority, matching today's precedence).
  - In `_cli`, add `parser.add_argument("--parent", default=None)` alongside the existing `parser.add_argument("args", nargs="*")`. Change `paths, summary = enumerate_scope(parsed.args)` to `paths, summary = enumerate_scope(parsed.args, parent=parsed.parent)`.
  - Update the module docstring's `Function: enumerate_scope(args, cwd=None) -> (list[Path], dict)` line (near the end of the docstring, alongside the CLI-usage line Card 1 already updates) to `Function: enumerate_scope(args, cwd=None, parent=None) -> (list[Path], dict)`, and add one clause to that line's description noting `parent` is an optional base-branch override consulted only in no-arg mode.
- **Commit:** `feat(codeguide): add --parent override to resolve_scope.py no-arg mode`

### Card 3: Extend test-resolve-scope.py with new scenarios

- **Context:**
  - `plugins/codeguide/scripts/resolve_scope.py`
- **Edits:**
  - `plugins/codeguide/unit_tests/test-resolve-scope.py`
- **Creates:** none
- **Deletes:** none
- **Moves:** none
- **Requirements:**
  - Add Scenario 14: single non-hex branch-name token with a literal `..HEAD` suffix. Setup, as a clear sequence: (1) init a repo, commit `base.py` on `main`; (2) create branch `mill-checkpoint-feature` at the current commit WITHOUT checking it out (`git -C tmp branch mill-checkpoint-feature`) — this freezes the checkpoint ref in place while `main` remains checked out, mirroring how a real `git branch -f "$CHK"` checkpoint works in mill-merge-in; (3) still on `main`, commit `a.py`, then commit `b.py` (two commits advancing `main`'s HEAD past the frozen checkpoint ref). Then call `enumerate_scope(["mill-checkpoint-feature..HEAD"], cwd=tmp)`. Assert `summary["mode"] == "head-rev"` and the resulting path set equals `{"a.py", "b.py"}` — the files committed AFTER the checkpoint ref was created, not on it — mirroring Scenario 8's `HEAD~3` semantics literally (`<base>..HEAD` returns what changed after `<base>`, never `<base>`'s own state).
  - Add Scenario 15: same branch name passed bare (no `..HEAD` suffix) as a single token — `enumerate_scope(["mill-checkpoint-feature"], cwd=tmp)` — asserts identical `mode == "head-rev"` routing and file set as Scenario 14.
  - Add Scenario 16: `--parent` override via the `parent=` kwarg. Build a repo with `origin/HEAD` set to `main` (per existing `_make_repo` helper), create a second branch (e.g. `other-parent`) with a distinguishing commit, then on a `feature` branch call `enumerate_scope([], cwd=tmp, parent="other-parent")`. Assert `summary["parent"] == "other-parent"` and `summary["base_branch"] == "other-parent"`, not `"main"`.
  - Add Scenario 17: `--parent` naming a branch that does NOT resolve locally. On a repo with `origin/HEAD` set to `main`, call `enumerate_scope([], cwd=tmp, parent="nonexistent-deleted-branch")`. Assert `summary["base_branch"] == "main"` (the `_detect_base_branch` fallback fired) and that the call did not raise.
  - Add Scenario 18: single-token explicit-path regression. Call `enumerate_scope(["a.py"], cwd=tmp)` on a repo where no branch/tag/commit is named `a.py` (a plain repo with one commit adding `a.py`). Assert `summary["mode"] == "explicit"` — confirms the broadened ref-check in Card 1 does not misroute a genuine single-token path into `_head_rev_scope()`.
  - Add an inline comment immediately above the existing Scenario 10 assertions (`["a.py", "nonexistent.py"]`) noting this is the two-token explicit-path case and is unaffected by the single-token ref-check broadened in Card 1 (the `len(args) == 1` guard in `enumerate_scope` means multi-token calls never reach `_resolve_ref_token`). No assertion changes needed for Scenario 10 itself.
  - All 13 existing scenarios must continue to pass with zero changes to their bodies or assertions.
- **Commit:** `test(codeguide): cover --parent override and broadened ref dispatch in resolve_scope.py`

### Card 4: Document `--parent` override in codeguide-update SKILL.md

- **Context:** none
- **Edits:**
  - `plugins/codeguide/skills/codeguide-update/SKILL.md`
- **Creates:** none
- **Deletes:** none
- **Moves:** none
- **Requirements:**
  - In the `## Steps` section, step 2 ("Enumerate source files in scope."), append one sentence to the existing paragraph (which currently ends "...parent-branch detection via origin/HEAD/origin/main/origin/master, and the `<parent>..HEAD ∪ current-diff` union for the no-arg-on-task-branch case."): add "An optional `--parent <ref>` token may also be present in `$ARGUMENTS` (forwarded by mill callers such as `git-commit`) and takes precedence over this git-native detection when it resolves to a valid ref; an unresolvable `--parent` falls back to the git-native detection unchanged." This is a doc-accuracy addition only — no change to the documented `$ARGUMENTS` contract in the `## Scope` section above it.
- **Commit:** `docs(codeguide): note --parent override in codeguide-update Step 2`

## Batch Tests

`verify:` runs the full `test-resolve-scope.py` file (18 scenarios after this batch: 13 existing + 5 new), which is the complete test surface for every change in this batch — Cards 1, 2, and 3 all land in this single file/test pair. Card 4 is a documentation-only change with no runnable surface; it is covered by the same batch verify only in the sense that it doesn't break anything, not because it has its own test.
