# Discussion: 60 (A) — Branch/slug/claim fixes

```yaml
task: 60 (A) — Branch/slug/claim fixes
slug: mill-branch-slug-fixes
status: discussing
parent: main
```

## Problem

Five interlocking bugs in mill's branch-handling, slug-resolution, and review-subprocess startup. They share a single failure mode: when something at the cwd-or-branch boundary is mildly off (operator launched from the wrong terminal, branch was renamed after `status.md` was written, branch lacks the configured prefix, prefix already has a trailing slash), one of the helpers hard-fails with no structured error envelope and the orchestrator (mill-plan, mill-go, mill-start) has no recovery path. The operator sees a stuck task with no actionable signal — `[mill-bg] EXIT` arrives without a JSON summary line, or `git push` rejects a stale refspec, or `git checkout -b` rejects `hanf//slug`.

Why now: these were tripped successively over the past three weeks of mill self-hosting. Each bug was filed as a separate GitHub issue (#297, #298, #301, #302, #304, #312) and bundled here because they share root causes — slug-derivation strictness, missing-JSON-on-startup-error, and cwd/branch desync — that are simpler to fix coherently than piecemeal.

## Scope

**In:**

- `plugins/mill/scripts/_marker.py` — `slug_from_branch` prefix-mismatch fallback (#297, #302).
- `plugins/mill/scripts/millpy-review-discussion.py`, `millpy-review-plan.py`, `millpy-review-code.py` — emit structured `verdict: ERROR` JSON on every startup-failure path (#298).
- `plugins/mill/scripts/millpy-implement.py` — read branch from `git branch --show-current` at push time, not from `status.md` (#301).
- `plugins/mill/scripts/millpy-claim.py` line 218 — drop the extra `/` in the branch-name construction (#304).
- `plugins/mill/scripts/_status.py` `read_branch` line 703 — drop the same extra `/` in the fallback derivation (same root cause as #304, in-scope per Q6).
- `plugins/mill/scripts/millpy-bg.py` — at launcher startup, validate cwd's current branch resolves to a task slug; emit clear error and exit 1 before spawning the worker (#312, part 2).
- `plugins/mill/skills/mill-plan/SKILL.md` — prelude check before `millpy-bg` invocation; add no-JSON-no-ERROR halt path (consumer-side handling for the rare case where the script crashes without writing JSON at all). The existing step 4.5 ERROR-only retry already handles the JSON path.
- `plugins/mill/skills/mill-start/SKILL.md` — add an analogous step (post-poll, pre-verdict) handling `verdict: ERROR` rounds with the same two-pass cap as mill-plan step 4.5 (#298 consumer side; Q3).
- `plugins/mill/skills/mill-go/SKILL.md` — same ERROR-retry block for code-review CLI invocations (Q3).
- Unit tests for each helper change (`test-marker.py`, `test-status.py`, `test-review-cli-errors.py` or extension to existing review-CLI test).

**Out:**

- `_marker.task_data` semantics beyond what's needed to preserve `slug_from_branch`'s contract — the function already calls `slug_from_branch` and inherits the fix for free.
- Wider review-pipeline refactor: ERROR-handling is added at startup paths only; mid-run failures (LLM timeout, malformed verdict) keep their current behavior.
- `branch_prefix` schema change: the canonical form keeps requiring the operator to include the separator (e.g. `"hanf/"`) per the existing `mill-config.yaml` comment. We do NOT auto-normalize the prefix.
- Auto-cd or auto-rename: millpy-bg refuses to mutate cwd or branch state — it diagnoses and exits.
- Backfilling old `status.md` `branch:` values during read: we use `git branch --show-current` as truth at push time but do not rewrite `status.md`'s `branch:` field.
- `millpy-implement-holistic.py` — not currently using a stale-branch push path; skip unless investigation during plan-writing surfaces a parallel bug there.

## Decisions

### D1: `slug_from_branch` accepts bare branch as slug fallback on prefix mismatch (#297, #302)

- Decision: When `prefix` is configured and `branch` does not start with it, attempt to find `branch` (the literal value, no stripping) in Home.md as a slug. If found, return `branch` as the slug and emit a one-line warning to stderr (`[_marker] warning: branch {branch!r} does not match prefix {prefix!r} but slug exists in Home.md; accepting`). If not found, raise `MarkerError` as before.
- Rationale: Branches without the configured prefix (e.g. `avm-cuda-migration` on a hub where prefix is `"hanf/"`) are legitimate — they exist in Home.md. mill-plan already tolerates such branches in some code paths; mill-go and the review CLIs do not. Symmetry; eliminates the manual `git branch -m` workaround.
- Rejected:
  - "Always raise" — status quo, perpetuates the inconsistency.
  - "Auto-rename branch to add prefix" — modifies operator-owned state; contradicts the "scripts never rewrite cwd/branch" path invariant.

### D2: Review CLIs emit structured `verdict: ERROR` JSON on every startup-failure path (#298)

- Decision: In `millpy-review-discussion.py`, `millpy-review-plan.py`, and `millpy-review-code.py`, every startup-failure path must emit one JSON line on stdout matching the ERROR envelope shape, in addition to its existing stderr message, before exiting 1. Two kinds of call site exist and BOTH must be covered:
  - **Existing `try/except` handlers** (reviewers load, slug resolution, plan-validator failure in plan-CLI): replace `print(str(exc), file=sys.stderr); return 1` with a helper call that prints to stderr AND emits the JSON envelope on stdout, then returns 1.
  - **Currently un-protected calls** (`resolve_wiki_path(...)`, `load_config(...)`, and any other top-level call that can raise — `load_config` raises `ReviewError` per its docstring; `resolve_wiki_path` and `_paths.resolve_git_root` raise `ValueError` / `SystemExit` on wiki-cwd detection): wrap each in a NEW `try/except (ReviewError, ValueError, SystemExit)` block around the call site and route the exception through the same helper. Do NOT rely on the "replace existing handler" language — there is no existing handler around `load_config` or `resolve_wiki_path`; new wrapping is required.

  ERROR envelope shape:

  ```json
  {"type": "<plan|discussion|code>", "round": 0, "verdict": "ERROR", "blocking_count": 0,
   "reviews": [{"scope": "holistic", "verdict": "ERROR", "error": "<msg>"}]}
  ```

  Place the helper in `_review_cli.py` as `print_error_envelope(review_type: str, msg: str) -> None`; the `review_type` literal (`"plan"` / `"discussion"` / `"code"`) is the call-site's responsibility.
- Rationale: Today's contract — "JSON on success, stderr on failure" — is fragile. Every consumer (mill-plan step 4.5 already, mill-start and mill-go after this change) wants a uniform machine-readable envelope so the `[mill-bg] EXIT` poll-loop can dispatch by verdict instead of by exit-code-plus-log-grep.
- Rejected:
  - "Emit JSON only on slug-resolution failure" — inconsistent surface area; the bug-on-the-day will be config load, not slug.
  - "No script change; document in SKILL.md" — keeps the orchestrator/CLI contract fragile and pushes ad-hoc grep-based error parsing into multiple skills.

### D3: ERROR-only retry handling mirrored into mill-start and mill-go (#298 consumer side)

- Decision: Both `plugins/mill/skills/mill-start/SKILL.md` Phase: Discussion Review and `plugins/mill/skills/mill-go/SKILL.md` (code-review invocation site) get an analogous "step 4.5" block: when the JSON envelope contains any `verdict: "ERROR"` review entry, re-run the same CLI without consuming the round counter, up to a two-pass cap. On the second consecutive ERROR pass: halt with `BLOCKED: review ERROR-only round {N}` (in mill-go: `_status.set_blocked` + commit + push as for other blocked paths; in mill-start under `--auto`: same set_blocked behavior; in mill-start interactive: surface to user).
- Rationale: Symmetry with mill-plan step 4.5; ERROR rounds are transient (LLM timeout, slug-prefix drift) and a single retry is cheap. Without consumer-side handling, the structured JSON from D2 produces a slightly nicer halt message but no recovery semantics.
- Rejected:
  - "Only mill-plan handles ERROR" — halts on every transient script failure for discussion/code-review.
  - "Defer consumer-side" — leaves a known gap immediately after D2 lands.

### D4: Branch at push time comes from `git branch --show-current`, not `status.md` (#301)

- Decision: In `millpy-implement.py`, replace the single `branch = _status.read_branch(status_path, cfg=cfg, slug=slug)` call (line 97) with `branch = _subprocess_util.run(["git", "-C", str(project_root), "branch", "--show-current"]).stdout.strip()`. The two push call sites (lines 165 and 246) keep the same `branch` variable. If `git branch --show-current` returns empty, halt with `stuck` JSON envelope (detached HEAD is fatal here, same as in `_marker`).
- Rationale: The worktree's live branch is the truth; `status.md` is a record. Renaming a branch mid-task is intentional and operator-initiated — push must follow the rename automatically.
- Rejected:
  - "Validate match, emit stuck on mismatch" — penalizes intentional renames; produces stuck states the operator must manually reconcile.
  - "Update status.md on push if branches diverge" — write-on-divergence side effects mid-implement; muddies the separation between live state and recorded state.

### D5: `millpy-claim.py` line 218 drops the extra `/` (#304)

- Decision: Change `branch_name = f"{branch_prefix}/{slug}" if branch_prefix else slug` to `branch_name = f"{branch_prefix}{slug}" if branch_prefix else slug` — mirroring `millpy-spawn.py` line 162.
- Rationale: The canonical schema documented in `mill-config.yaml` and `wiki/config.yaml` (`# branch_prefix — prepended directly to the slug (no separator added)`) requires the operator to include the separator. spawn honors it, claim doesn't.
- Rejected:
  - "Auto-strip trailing `/` from prefix and add `/` back" — diverges from documented schema; would silently change behavior for hubs where the operator intentionally omitted a separator.

### D6: `_status.read_branch` fallback drops the same extra `/` (Q6)

- Decision: In `_status.py` line 703, change `derived = f"{prefix}/{slug}" if prefix else slug` to `derived = f"{prefix}{slug}" if prefix else slug`. Also update the `read_branch` docstring at line 681 — currently `Falls back to ``f"{cfg['spawn']['branch_prefix']}/{slug}"``` — to drop the spurious `/`, matching the corrected code.
- Rationale: Same root cause as D5. The fallback path fires when `status.md` is missing or unparseable; in conjunction with D4 (push uses git-show-current) this fallback fires less, but when it does fire it must produce a usable branch name. Fixing it together prevents D4 from masking D6. Docstring fix keeps the documented contract aligned with the code.

### D7: `millpy-bg.py` launcher validates cwd's current branch resolves to a task slug (#312, part 2)

- Decision: In `_launcher_main` after `git_root` is resolved, additionally run `git -C <git_root> branch --show-current`. If the result is empty (detached HEAD) or `_marker.slug_from_branch(Path(git_root), wiki_path, cfg)` raises `MarkerError`, print a clear two-line error to stderr (`mill-bg: cwd appears to be parent worktree (branch={branch!r}); switch to the task-worktree terminal before launching reviews. Expected: any branch with a task slug present in Home.md.`) and exit 1. The launcher must `_paths.resolve_wiki_path(git_root)` + `_config.load_config(wiki_path, git_root)` to call `slug_from_branch` — keep these imports lazy so the worker fast-path (lines 27-85) is unaffected.
- Rationale: The 2026 incident pattern in #312 is "first Bash terminal session, cwd is main worktree, slug == none, review subprocess silently exits 1". Validating at the launcher catches this once for all callers (mill-plan, mill-start, mill-go) instead of duplicating prelude checks in three SKILLs.
- Rejected:
  - "Compare cwd's git-root name to the configured repo name" — brittle (slug names can collide with repo name; container vs. in-place mode changes the name).
  - "Auto-cd to the canonical worktree" — violates the "scripts never rewrite cwd" path invariant.
  - "No millpy-bg change; SKILL prelude only" — splinters enforcement into three SKILLs that drift over time.

### D8: mill-plan / mill-start / mill-go SKILLs get a one-line cwd-validation prelude (#312, part 1)

- Decision: Each SKILL gets a single line under its "before launching millpy-bg" step: *"Verify `pwd` in the Bash terminal matches the task worktree before invoking `millpy-bg`. If `millpy-bg` rejects cwd with the parent-worktree error, halt and instruct the operator to switch to the task-worktree terminal."* In mill-plan SKILL: under Phase: Plan Review, step 2 preamble. In mill-start: under Phase: Discussion Review, step 2 preamble. In mill-go: under each code-review invocation step.
- Rationale: Defense in depth. The operator sees the hint before the launcher fires; the launcher rejects if the operator missed it. Cheap to write, cheap to read.
- Rejected:
  - "Rely on millpy-bg validation alone" — operator sees the launcher rejection without context about what they should have checked.

### D9: Test coverage

- Decision: Add unit-test coverage:
  - `plugins/mill/unit_tests/test-marker.py` — extend existing tests (or add if absent) for the D1 prefix-mismatch-fallback path: branch with no prefix that matches a Home.md slug → returns slug + warning; branch with no prefix that doesn't match → MarkerError.
  - `plugins/mill/unit_tests/test-status.py` — extend `read_branch` tests for the D6 fix: with non-empty prefix `"hanf/"` and slug `"foo"` and missing `status.md`, return `"hanf/foo"` not `"hanf//foo"`.
  - `plugins/mill/unit_tests/test-review-cli.py` — extend the existing file (which already covers `print_error`). Add new test functions covering: `print_error_envelope` shape; for each of the three review CLIs, drive a startup-failure (missing config, unresolvable slug, missing reviewer registry entry) and assert the stdout JSON envelope matches D2's shape with `verdict: "ERROR"` and the error message field populated.
  - `plugins/mill/unit_tests/test-bg-launcher.py` (new) — drive `_launcher_main` with cwd pointing at a fake parent-worktree-shaped fixture (branch returns "main"); assert exit 1 and the parent-worktree-rejection error on stderr. Use `tempfile` + `git init` fixtures already established by other unit tests; no real claude calls.
- Rationale: Each fix has a single concrete behavior that must be exercised; no integration test required.
- Rejected:
  - "Integration test via real mill-go run" — out-of-scope for these fixes; would slow CI.

## Technical context

### Affected files (relative to repo root)

- `plugins/mill/scripts/_marker.py` — `slug_from_branch` (lines 28-68).
- `plugins/mill/scripts/_status.py` — `read_branch` (lines 677-708), specifically line 703.
- `plugins/mill/scripts/millpy-review-discussion.py` — startup paths at lines 45-50 (reviewers load) and 52-59 (slug + run).
- `plugins/mill/scripts/millpy-review-plan.py` — startup paths at lines 81-86 (reviewers) and 88-114 (validator + run).
- `plugins/mill/scripts/millpy-review-code.py` — startup paths at lines 71-76 (reviewers) and 88-104 (slug + run).
- `plugins/mill/scripts/_review_cli.py` — add `print_error_envelope(review_type: str, msg: str) -> None` helper.
- `plugins/mill/scripts/millpy-implement.py` — line 97 (branch read) and lines 162-170 / 245-251 (push).
- `plugins/mill/scripts/millpy-claim.py` — line 218.
- `plugins/mill/scripts/millpy-bg.py` — `_launcher_main` body (lines 94-151).

### Helpers already in scope

- `_paths.resolve_wiki_path(git_root)` — already imported in mill-bg via `_paths`. Lazy-import inside `_launcher_main` to keep the worker fast-path stdlib-only.
- `_config.load_config(wiki_path, worktree_root)` — same.
- `_marker.slug_from_branch(git_root, wiki_path, cfg)` — same; used both as the validator inside `millpy-bg` (D7) and the helper we're modifying (D1).
- `_subprocess_util.run` — already used in `millpy-bg` for `git rev-parse`. Reuse for `git branch --show-current` in D4 and D7.

### Existing patterns to mirror

- `mill-plan` step 4.5's two-pass ERROR-only retry block: pattern for D3's mill-start and mill-go additions.
- `_status.set_blocked` + commit + push: mill-start's existing auto-mode blocked path; D3 mill-start uses the same call site.
- `mill-config.yaml` header comment about `branch_prefix`: the schema authority for D5/D6.

### `_marker.slug_from_branch` post-D1 control flow

```python
if prefix and not branch.startswith(prefix):
    # NEW (D1): try bare branch as slug
    task = next((t for t in tasks if t.slug == branch), None)
    if task is not None:
        print(f"[_marker] warning: branch {branch!r} does not match prefix {prefix!r} but slug exists in Home.md; accepting", file=sys.stderr)
        return branch
    raise MarkerError(f"branch {branch!r} does not start with configured prefix {prefix!r} and is not a known slug")
slug = branch.removeprefix(prefix)
# ... existing post-removeprefix lookup logic
```

Note: the new path needs `tasks` parsed before the prefix check. Move the Home.md read up, or duplicate the parse — recommend moving it up since the parse is cheap (one read of a small markdown file).

### `millpy-bg.py` launcher validation post-D7 sketch

```python
# After git_root resolution, before scratch_dir creation:
import _paths, _config, _marker  # lazy
wiki_path = _paths.resolve_wiki_path(Path(git_root))
cfg = _config.load_config(wiki_path, Path(git_root))
try:
    _marker.slug_from_branch(Path(git_root), wiki_path, cfg)
except _marker.MarkerError as exc:
    branch_result = _subprocess_util.run(["git", "-C", git_root, "branch", "--show-current"])
    branch = branch_result.stdout.strip() or "<detached>"
    print(
        f"mill-bg: cwd appears to be a non-task worktree (branch={branch!r}, error: {exc}). "
        "Switch to the task-worktree terminal before launching reviews.",
        file=sys.stderr,
    )
    return 1
```

The validation runs in the launcher process — adds two file reads and one git invocation per launch; negligible.

## Constraints

From `CLAUDE.md` (project-level):

- ASCII-only `print()` / `_log()` output strings. The new error messages use ` -- ` and ASCII arrows where needed; the example strings above already comply.
- `${CLAUDE_PLUGIN_ROOT}` for intra-plugin paths; not relevant to these changes (we touch script bodies only, not SKILL.md invocation syntax).
- Junction paths never resolved by scripts; all path resolution via `_paths.py`. D7's `_paths.resolve_wiki_path(git_root)` honors this.
- Working state stays on the task branch in `_mill/`; not affected (we don't write to wiki anywhere here).

From `mill-config.yaml` header comment:

- `branch_prefix` is prepended directly with no separator added. Authoritative for D5/D6.

From the `mill-receiving-review` skill (consumed during the review phase here, not by the code under change):

- Not a constraint on the implementation; relevant only to mill-start's own discussion-review loop.

No `CONSTRAINTS.md` at the hub root.

## Testing

### TDD candidates (write tests first)

- **D1 — `slug_from_branch` prefix-mismatch fallback (`test-marker.py`).** Three cases: (a) prefix set, branch starts with prefix → strip + lookup (existing behavior). (b) prefix set, branch does not start with prefix, branch is a known slug → return branch (literal) + warning. (c) prefix set, branch does not start with prefix, branch is not a known slug → `MarkerError`.
- **D6 — `_status.read_branch` fallback (`test-status.py`).** With missing `status.md`, `prefix == "hanf/"`, `slug == "foo"`: result is `"hanf/foo"` (currently `"hanf//foo"`).

### Direct-assertion tests (no TDD ceremony needed)

- **D2 — review CLI ERROR envelope shape (`test-review-cli-errors.py`).** For each of the three CLIs, run with a config-load failure (e.g., missing required key) and assert: exit code 1, stdout contains exactly one JSON line, `json.loads(line)` returns the expected shape with `verdict == "ERROR"` and `reviews[0].verdict == "ERROR"`.
- **D5 — `millpy-claim.py` branch construction.** Existing claim tests probably already assert the branch name; update assertions from `f"{prefix}/{slug}"` to `f"{prefix}{slug}"`. If no test covers this, add one.
- **D7 — `millpy-bg.py` launcher cwd rejection (`test-bg-launcher.py`).** Create a temp dir, `git init`, `git checkout -b main`, write a minimal wiki at the sibling location, run `_launcher_main(["--slug", "test", "--", "/bin/true"])` via subprocess or in-process import; assert exit code 1 and the parent-worktree-rejection string in stderr.

### Manual / integration

- D3 (mill-start ERROR-retry path) and D8 (SKILL preludes) are SKILL-level documentation changes; no automated test is appropriate. Cover via end-to-end smoke when mill self-hosts the next task after this lands.
- D4 (push uses `git branch --show-current`): the next mill-go run on a renamed branch is the natural smoke. Optionally add an integration test under `plugins/mill/integration_tests/` that creates a fixture worktree, renames the branch, calls `millpy-implement.py` with `--resume` in a mocked way — but the production smoke is sufficient.

### Excluded scenarios

- LLM-side error injection — out of scope; the review-CLI changes happen entirely in argv/import/startup paths before any LLM call.
- Concurrent push from another worktree — outside the failure pattern these bugs cover.

## Q&A log

- **Q:** How should `slug_from_branch` behave on prefix mismatch (#297, #302)? **A:** [auto-pick] Try bare branch as slug against Home.md; if hit, accept and warn; otherwise raise. **Why:** Symmetric with mill-plan's existing tolerance; preserves operator workflow; eliminates manual `git branch -m`.
- **Q:** What JSON shape should the review CLIs emit on startup failure (#298)? **A:** [auto-pick] Full `{type, round: 0, verdict: ERROR, blocking_count: 0, reviews: [{scope: holistic, verdict: ERROR, error}]}` envelope on every startup-failure path, on stdout, exit 1, error to stderr for humans. **Why:** Uniform machine-readable contract; every consumer can dispatch by JSON verdict.
- **Q:** Should mill-start and mill-go also handle `verdict: ERROR` rounds, mirroring mill-plan's step 4.5? **A:** [auto-pick] Yes, add the same two-pass ERROR-only retry block with `BLOCKED` halt on the second pass. **Why:** Symmetry; ERROR rounds are transient; one retry is cheap and matches the existing mill-plan pattern.
- **Q:** Where should branch come from at push time (#301)? **A:** [auto-pick] `git branch --show-current` at push time (status.md becomes advisory). **Why:** Worktree's live branch is the truth; rename is intentional; push must follow.
- **Q:** What's the right cwd validation in `millpy-bg.py` (#312)? **A:** [auto-pick] Call `_marker.slug_from_branch` on cwd's branch; halt with a clear error before spawning the worker if it fails. **Why:** Reuses the canonical slug resolver; precisely diagnoses the wrong-terminal case; one enforcement point covers all SKILLs.
- **Q:** Should `_status.read_branch` fallback's `{prefix}/{slug}` slash bug be fixed in scope? **A:** [auto-pick] Yes, in scope as #304's twin. **Why:** Same root cause; single-line repair; must be fixed before #301 lands so the fallback path remains correct.
- **Q:** Should mill-plan / mill-start / mill-go SKILLs get a one-line cwd-validation prelude alongside the millpy-bg validation? **A:** [auto-pick] Yes, single-line prelude under the "before launching millpy-bg" step in each. **Why:** Defense in depth; operator gets the hint before the launcher fires; cheap.
