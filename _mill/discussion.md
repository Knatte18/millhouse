# Discussion: Reviewer tool-sandbox: git snapshot guard + fix --allowedTools

```yaml
task: 'Reviewer tool-sandbox: git snapshot guard + fix --allowedTools'
slug: review-sandbox-guard
status: discussing
parent: main
```

## Problem

During `mill-plan` on the `config-move-to-hub` branch, the plan-review reviewer (Sonnet 4.6, `bulk` mode) violated its no-edit contract in rounds 4 and 5: instead of returning a review file, it used `Edit`, `Write`, and `Bash` to mutate sources and made two git commits (`1e004305`, `c7dbdf98`) with `Co-Authored-By: Claude Sonnet 4.6`. Rounds 1-3 of the same session produced correct review files. Output of the broken rounds was prose, no `verdict:` block; `parse_verdict` correctly returned `ERROR` and operator approval was needed manually.

Why now: this is the second observed sandbox failure of a bulk reviewer (#310). The current defense is a four-line `<TOOL_RULE>` injected at the top of the prompt; the reviewer ignored three of its four CRITICAL directives. We need a runtime guarantee, not a prompt-level plea.

Two root causes acting in concert:

1. **Sandbox argv is broken.** `_llm_claude._build_argv` always passes `--allowedTools <value>`. For bulk mode the value is the empty string `""`, which `claude -p` interprets as *"no override -> default allow-list applies"*, not *"no tools"*. The flag was sent (visible in logs) but `Edit`/`Write`/`Bash` were available.
2. **Agentic tuning of Sonnet 4.6.** Given a task framed as "review and report findings" plus tools quietly available, the model overrides soft text constraints when it judges fixing to be more helpful than reporting. Known failure mode of agentic models under soft constraints.

This task closes both: a hard runtime check (git snapshot guard) that fails the review loudly if any state change slipped past, and a correct sandbox argv so the soft directives are no longer the only line of defense.

## Scope

**In:**

- New `worktree_snapshot_guard(project_root)` context manager in `_review_common.py` that captures `HEAD` SHA + `git status --porcelain` before yielding and re-captures on exit; raises `ReviewerOverstepError` (new, subclass of `ReviewError`) on any change.
- Wrap each of `_review_plan.run`, `_review_code.run`, `_review_discussion.run` with the guard — one snapshot per `run()` invocation, covering parallel per-batch fan-out + holistic + NEED_CONTEXT resume retries in a single window.
- Fix `_llm_claude._build_argv`: skip `--allowedTools` when the string is empty; emit `--disallowedTools "Edit,Write,Bash,NotebookEdit"` whenever `allowed_tools` does NOT contain any of `{Edit, Write, Bash, NotebookEdit}` (derivation handled inside `_build_argv` itself — no signature change to `_invoke` or to the `run_*` public functions). This auto-classifies: bulk (empty -> add disallow), tool-use (`Read,Grep,Glob` -> add disallow), implementer (`Read,Edit,Write,Bash,Grep,Glob,Skill` -> skip disallow).
- Prepend an explicit READ-ONLY identity header (verbatim text from proposal) as a new first line in: `review-plan-batch.md`, `review-plan-holistic.md`, `review-code-batch.md`, `review-code-holistic.md`, `review-discussion.md`.
- New unit test `plugins/mill/unit_tests/test-review-guard.py` covering: clean snapshot passes; HEAD change raises `ReviewerOverstepError`; porcelain change with same HEAD raises; new untracked file raises; the error is a `ReviewError` subclass and carries before/after SHA + porcelain diff.
- Extend `plugins/mill/unit_tests/test-llm-claude.py` to assert: `run_bulk` argv omits `--allowedTools` and contains `--disallowedTools Edit,Write,Bash,NotebookEdit`; `run_tool_use` argv contains `--allowedTools Read,Grep,Glob` AND `--disallowedTools Edit,Write,Bash,NotebookEdit`; `run_implementer` argv contains `--allowedTools Read,Edit,Write,Bash,Grep,Glob,Skill` AND does NOT contain `--disallowedTools`. The existing `_build_argv` direct assertion at `test-llm-claude.py:152-154` (the empty-string bulk case currently asserting `argv == [..., "--allowedTools", ""]`) MUST be REPLACED, not augmented: the new shape has no `--allowedTools` entry and adds `--disallowedTools Edit,Write,Bash,NotebookEdit`.

**Out:**

- Auto-rollback (`git reset --hard <before_sha>`) of reviewer commits — fail-loud is enough for v1, per proposal.
- Tool-use-mode-specific guard relaxations — the guard cares about git state, not tool calls; same rule for both modes.
- Extending the denylist beyond `Edit,Write,Bash,NotebookEdit` (e.g. `WebFetch`, `WebSearch`, `TodoWrite`) — the snapshot guard catches state changes regardless of which tool caused them; soft denylist is belt-and-suspenders, minimal list is fine.
- Cluster-reviewer guard plumbing — deferred to task 13.
- Changing reviewer logic, prompt templates, or `<TOOL_RULE>` text beyond the identity header prepend.
- Any change to mill-go's per-batch implementer sandbox.

## Decisions

### snapshot-guard-helper

- Decision: Implement the guard as a Python context manager `worktree_snapshot_guard(project_root: Path)` in `_review_common.py`. The manager runs `git -C <project_root> rev-parse HEAD` and `git -C <project_root> status --porcelain` on `__enter__`, stores both, yields, then re-runs both on `__exit__` and raises `ReviewerOverstepError` if either differs. On exception inside the `with` block the guard re-raises the original exception unchanged (do not swallow `LLMError` / `ReviewError`).
- Rationale: One helper, three backends — shared semantics, single point of change. Context manager is idiomatic Python; the `with` block scopes precisely the reviewer-LLM phase. Using `git -C <root>` keeps it cwd-agnostic, matching the wiki-access conventions.
- Rejected: (a) Inline before/after checks per backend — duplication, drift. (b) Decorator on `_reviewer_single.run` — would fire per LLM call, conflicting with the parallel-fan-out design and producing race-condition misattribution. (c) New `_review_guard.py` module — too small to justify a separate file given how few helpers are involved.

### reviewer-overstep-error-class

- Decision: `ReviewerOverstepError` is a subclass of `ReviewError` declared in `_review_common.py`. Constructor: `ReviewerOverstepError(before_sha: str, after_sha: str, porcelain_diff: str)`. Message text concatenates the three for human inspection.
- Rationale: Existing `except ReviewError` sites at the API layer (`millpy-review-*.py`) keep working unchanged. Callers that care can `isinstance(e, ReviewerOverstepError)` to distinguish overstep from other review errors.
- Rejected: Sibling of `ReviewError` — would require updating every API catch site; no benefit. Separate module — premature factoring.

### no-auto-rollback

- Decision: On overstep detection, raise the error and let it propagate. Do NOT call `git reset --hard <before_sha>`.
- Rationale: Auto-rollback risks erasing legitimate concurrent work in adjacent worktrees if cwd is wrong, and the proposal explicitly defers it. Fail-loud already halts the review pipeline; operator can run `git log` and reset manually with full context. Adding rollback adds a destructive action that the test surface cannot fully exercise without a live git repo.
- Rejected: Auto-rollback to HEAD with working-tree restore — useful long-term, but out-of-scope for v1.

### single-guard-per-run

- Decision: One `with worktree_snapshot_guard(project_root):` wrapping the body of each backend's top-level `run()`. The wrapped block covers parallel `ThreadPoolExecutor` fan-out in `_review_plan`, the holistic call that follows it, NEED_CONTEXT resume retries in all three backends, and template rendering / file writes.
- Rationale: The point is "did the *review pass* mutate state?", not "which specific sub-call did it". A single window keeps the helper trivial and avoids race-condition misattribution when several parallel reviewers run inside one repo. `write_review_file` writes to `_mill/reviews/`, which is an expected output — see decision `expected-output-allowlist` for how the porcelain check accommodates it.
- Rejected: Per-`_reviewer_single.run` snapshots — fine-grained, but in `_review_plan.py`'s parallel fan-out two parallel threads would race and a "good" reviewer could be blamed for another's commit. Section-level snapshots (one for fan-out, one for holistic) — adds complexity without removing the parallel-race problem inside the fan-out.

### expected-output-allowlist

- Decision: `worktree_snapshot_guard` accepts a keyword-only `expected_paths: list[str] | None = None` argument. Porcelain entries whose path matches any entry in `expected_paths` (substring match, normalized to forward slashes) are filtered out of the diff before comparison. HEAD changes are NEVER filtered — any commit is a violation. Each backend passes its own list: `[cfg["paths"]["reviews_dir"]]` for all three; plus `[cfg["paths"]["status_md"]]` is NOT included (the backends do not write to status from inside the guarded block — `_status` writes live in mill-go and the API CLIs around the backend call, not inside `run()`).
- Rationale: `write_review_file` writes to `_mill/reviews/`, producing untracked files that `git status --porcelain` will surface as `??`. Without an allowlist, every clean review trips the guard. Filtering by configured reviews_dir is precise and survives path-config changes.
- Rejected: Filter by file extension (`*.md`) — too broad, would mask reviewer-written `.md` mutations. Filter by reviewer-process PID or file mtime — fragile, platform-dependent. No filter, write review file outside the guard — possible but requires restructuring three backends; the allowlist is smaller and explicit.

### sandbox-argv-fix

- Decision: In `_llm_claude._build_argv`, change the `--allowedTools <allowed_tools>` line to: `*(["--allowedTools", allowed_tools] if allowed_tools else [])`, then append `["--disallowedTools", "Edit,Write,Bash,NotebookEdit"]` whenever `allowed_tools` does NOT contain any of `{"Edit","Write","Bash","NotebookEdit"}` (derive the decision inside `_build_argv` by tokenising `allowed_tools` on comma+whitespace and checking set intersection). No signature change to `_invoke` or to the public `run_bulk` / `run_tool_use` / `run_implementer` functions — `_build_argv` is the only place where this logic lives, and the chain `run_* -> _invoke -> _build_argv` is unchanged in parameter shape.
- Rationale: Empty `--allowedTools ""` is a silent no-op (Claude CLI default-allows). Either omitting the flag or using `--disallowedTools` correctly restricts tools. Combining both is defense in depth: `--allowedTools Read,Grep,Glob` (tool-use mode) plus `--disallowedTools Edit,Write,Bash,NotebookEdit` reads as "definitely allow R/G/G, definitely deny E/W/B/N" with no ambiguity. The denylist `Edit,Write,Bash,NotebookEdit` matches the minimal set named in the proposal — every additional tool we add (WebFetch, WebSearch, TodoWrite) raises false-positive risk without addressing the actual git-mutation failure mode the snapshot guard now handles.
- Rejected: `--tools ""` (CLI's documented "disable all" sentinel) — works for bulk but interacts unpredictably with `--allowedTools` for tool-use; the proposal-aligned approach is safer. `--permission-mode plan` — undocumented behavior for `-p` non-interactive flow; not worth the risk in a defense-in-depth fix. Denying a wider tool set (WebFetch, WebSearch) — out of scope per "denylist beyond E/W/B/N".

### template-identity-header

- Decision: Prepend the following block as the new first paragraph (above the existing "You are an independent ... reviewer" sentence) in each of: `review-plan-batch.md`, `review-plan-holistic.md`, `review-code-batch.md`, `review-code-holistic.md`, `review-discussion.md`:

  ```
  **You are a READ-ONLY reviewer. You MUST NOT call Edit, Write, Bash, or any
  tool that modifies files or runs commands. You MUST NOT make git commits.
  Your sole output is the review file in the format below. If you find issues,
  REPORT them — do NOT fix them.**
  ```

  Separated from the existing first sentence by a blank line. No new template token, no `render_prompt` change.
- Rationale: Direct prepend is the smallest change. Templates are rarely edited; introducing a `<REVIEWER_IDENTITY>` token plus a token-fill in `render_prompt` is more code to maintain for one string. The proposal text is well-tuned (covers tools, git, framing, behavior) so use it verbatim.
- Rejected: New `<REVIEWER_IDENTITY>` template token — premature abstraction. Extend the `_TOOL_RULE_BULK` / `_TOOL_RULE_TOOL_USE` constants — these are already short and tightly scoped to tool-permission semantics; mixing identity framing in dilutes them.

### test-strategy

- Decision: Two test files touched.

  1. New `plugins/mill/unit_tests/test-review-guard.py`: covers `worktree_snapshot_guard` end-to-end against a real `tempfile`-backed git repo. Cases: (a) no changes inside `with` -> no raise; (b) `git commit` inside `with` raises `ReviewerOverstepError` with before != after SHA; (c) untracked file dropped inside `with` raises (porcelain change, same HEAD); (d) modified tracked file (no commit) raises; (e) untracked file inside `expected_paths` directory does NOT raise; (f) commit inside `expected_paths` directory still raises (HEAD changed); (g) `ReviewerOverstepError` is a `ReviewError` subclass; (h) message includes both SHAs and the porcelain diff lines.
  2. Extend `plugins/mill/unit_tests/test-llm-claude.py`: assert that the captured argv from `run_bulk` mock omits `--allowedTools` AND contains `--disallowedTools` with value `Edit,Write,Bash,NotebookEdit`; assert `run_tool_use` argv contains both `--allowedTools Read,Grep,Glob` and `--disallowedTools Edit,Write,Bash,NotebookEdit`; assert `run_implementer` argv contains `--allowedTools Read,Edit,Write,Bash,Grep,Glob,Skill` and does NOT contain `--disallowedTools`.

  Also extend the existing `_build_argv` direct assertions in `test-llm-claude.py` to reflect the new signature (`add_disallow` keyword).

- Rationale: A real-git fixture is cheap for the guard test (one `subprocess.run(["git","init"], ...)` per case) and exercises the exact code path. argv assertions for `_llm_claude` are existing-style mock-capture tests; the existing test already captures argv for `run_implementer`. No new test infrastructure needed.
- Rejected: Pure-mock test of `worktree_snapshot_guard` (monkey-patch `subprocess.run`) — would not catch a porcelain-format parsing bug. Integration test with live `claude` — out of scope.

### preserve-resume-retry-semantics

- Decision: The snapshot guard's `with` block contains the existing NEED_CONTEXT resume-retry logic in each backend (the second `_reviewer_single.run` call). No reordering of the existing control flow.
- Rationale: A successful resume retry that produces a clean review file must not be falsely flagged. The retry runs the same reviewer in the same repo; if it modifies git, that IS a violation. Keeping the retry inside the guard preserves both correctness paths.
- Rejected: Two separate guards (one per call) — pointless when both are inside the same backend invocation; would double the porcelain capture cost.

### test-stub-unaffected

- Decision: The guard is unconditional — no skip-on-test-stub branch. `_reviewer_test_stub` does not touch git, so the guard is a silent no-op for stub-backed tests.
- Rationale: Conditional behavior on reviewer identity adds branches that themselves need tests; better to keep the guard semantics uniform. The existing tests under `_reviewer_test_stub` will continue to pass once the helper is added.
- Rejected: Skip when `spec.provider == "test_stub"` — unneeded complexity. Config-gated bypass — never useful in CI; would be a footgun in prod.

## Technical context

### Affected modules

| File | Change |
|---|---|
| `plugins/mill/scripts/_review_common.py` | Add `ReviewerOverstepError(ReviewError)` class; add `worktree_snapshot_guard(project_root, *, expected_paths=None)` context manager |
| `plugins/mill/scripts/_review_plan.py` | Wrap `run()` body in `with worktree_snapshot_guard(project_root, expected_paths=[cfg["paths"]["reviews_dir"]]):` |
| `plugins/mill/scripts/_review_code.py` | Same — wrap `run()` body |
| `plugins/mill/scripts/_review_discussion.py` | Same — wrap `run()` body |
| `plugins/mill/scripts/_llm_claude.py` | Modify `_build_argv` only: conditional `--allowedTools` emission when value is empty; add `--disallowedTools "Edit,Write,Bash,NotebookEdit"` when `allowed_tools` does NOT contain any of `{Edit,Write,Bash,NotebookEdit}`. `_invoke`, `run_bulk`, `run_tool_use`, and `run_implementer` signatures and bodies are unchanged. |
| `plugins/mill/templates/review-plan-batch.md` | Prepend identity header |
| `plugins/mill/templates/review-plan-holistic.md` | Prepend identity header |
| `plugins/mill/templates/review-code-batch.md` | Prepend identity header |
| `plugins/mill/templates/review-code-holistic.md` | Prepend identity header |
| `plugins/mill/templates/review-discussion.md` | Prepend identity header |
| `plugins/mill/unit_tests/test-review-guard.py` | New file — guard helper coverage |
| `plugins/mill/unit_tests/test-llm-claude.py` | Extend — new argv assertions for the `--allowedTools`/`--disallowedTools` fix |

### Helpers and conventions reused

- `_subprocess_util.run(argv, ...)` — the standard subprocess wrapper. Use it for `git rev-parse` and `git status --porcelain` inside the guard so behavior matches the rest of the codebase (UTF-8 I/O, breadcrumbs, env handling).
- `ReviewError` base class — already declared in `_review_common.py`; existing API-layer catch sites in `millpy-review-*.py` catch it and emit JSON with `verdict: ERROR`.
- `git -C <project_root>` invocation pattern — see `_wiki.py` for the established convention; the guard MUST use this form, never `cd`. `project_root` is always the worktree root and is already a `run()` parameter on all three backends.
- Test-fixture pattern — `test-review-plan-flow.py` uses `subprocess.run(["git", "init"], ...)` inside `tempfile.TemporaryDirectory()`. The new `test-review-guard.py` follows the same pattern.
- Template-render pipeline — `render_prompt(name, **kwargs)` in `_review_common.py` opens the template, substitutes `<TOKEN>` placeholders. Identity-header text contains no `<>` tokens so it passes through untouched.

### Failure-mode tour (what the snapshot guard catches)

| Scenario | HEAD change | Porcelain change | Guard verdict |
|---|---|---|---|
| Reviewer commits a fix | yes | varies | RAISE (HEAD differs) |
| Reviewer writes a file, no commit | no | yes | RAISE (porcelain differs) |
| Reviewer drops untracked debug file | no | yes (??) | RAISE (porcelain differs) |
| Reviewer modifies tracked file in place | no | yes (M) | RAISE (porcelain differs) |
| Clean review pass (review file under reviews_dir) | no | yes (?? reviews/...) | PASS (filtered by `expected_paths`) |
| Backend writes status.md update | no | yes (M _mill/status.md) | PASS or RAISE — irrelevant, backends do not touch status from inside `run()`; if a regression introduces such a write it is correctly flagged |

### Sandbox argv before/after

Before (current, broken for bulk):

```text
cmd /c claude -p --output-format stream-json --verbose
  --model <model> --allowedTools ""
  [--effort <effort>] [--session-id <id> | --resume <id>]
```

After (bulk):

```text
cmd /c claude -p --output-format stream-json --verbose
  --model <model> --disallowedTools Edit,Write,Bash,NotebookEdit
  [--effort <effort>] [--session-id <id> | --resume <id>]
```

After (tool-use):

```text
cmd /c claude -p --output-format stream-json --verbose
  --model <model> --allowedTools Read,Grep,Glob
  --disallowedTools Edit,Write,Bash,NotebookEdit
  [--effort <effort>] [--session-id <id> | --resume <id>]
```

After (implementer — unchanged):

```text
cmd /c claude -p --output-format stream-json --verbose
  --model <model> --allowedTools Read,Edit,Write,Bash,Grep,Glob,Skill
  [--effort <effort>] [--session-id <id> | --resume <id>]
```

Both `--allowedTools` and `--disallowedTools` are documented flags of `claude -p` (verified via `claude --help`).

## Constraints

- ASCII-only `print()` / log output strings. The guard's error message and any new log lines must use `--` not `—` and `->` not Unicode arrow. Docstrings/comments exempt. (CLAUDE.md)
- `${CLAUDE_PLUGIN_ROOT}` for all intra-plugin paths in any new SKILL.md or template — N/A here (this task does not add a skill or new template references).
- Junctions are never followed by code: the guard uses `project_root` (the worktree root, a real path resolved upstream). No `.wiki` / `.active` junction references. (CLAUDE.md)
- Working state writes (`_mill/status.md`, `_mill/reviews/*`) stay on the task branch, never the wiki. The guard's `expected_paths` only allows `_mill/reviews/` mutations. (CLAUDE.md)
- All path resolution through `_paths.py` helpers; no inline string-joining of repo paths. The guard receives `project_root` as an already-resolved `Path`; it does NOT call `_paths` itself.
- ReviewerOverstepError must surface as a `ReviewError` to existing API-layer catch sites — verified by the test in `test-review-guard.py` case (g).
- No live `claude` CLI in unit tests — argv-shape assertions stay mock-based.
- No real LLM in `test-review-guard.py` — it tests the guard helper directly against a tempfile git repo.

## Testing

- `test-review-guard.py` (new): real-tempfile git repo, ~8 cases covering clean / HEAD-change / porcelain-change / expected-paths-filter / exception-shape. Use the `_test_helpers.seed_wiki_config` pattern only if needed (the guard alone does not need wiki config — it only needs a git repo). Aim for <100 lines.
- `test-llm-claude.py` (extend): three new argv assertions per the test-strategy decision. Insert near the existing `run_implementer` argv-capture test, reuse its `_fake_run` / `captured_argv` pattern.
- `test-review-plan-flow.py` / `test-review-code-flow.py` / `test-review-discussion-flow.py` (existing flow tests): no source changes expected — these tests run reviews to completion via `_reviewer_test_stub`, which never mutates git, so the new guard is a no-op. Run them to confirm no regression.
- `python plugins/mill/unit_tests/run-all.py` must pass.

TDD candidate: the snapshot guard helper itself — write `test-review-guard.py` first against a stub implementation that always returns "no change", then implement the real porcelain comparison, then add the four-state matrix.

## Q&A log

- **Q:** Where should the snapshot guard live and at what abstraction? **A:** [auto-pick] Context manager `worktree_snapshot_guard(project_root)` in `_review_common.py`, shared across all three backends. **Why:** Single point of change, idiomatic Python, scopes precisely the reviewer-LLM phase. Decorator on `_reviewer_single.run` would race in the parallel batch fan-out.
- **Q:** Where should `ReviewerOverstepError` live and in what hierarchy? **A:** [auto-pick] Subclass of `ReviewError` in `_review_common.py`. **Why:** Existing API-layer catches keep working; callers can `isinstance` to distinguish when needed.
- **Q:** Should the guard auto-rollback on overstep? **A:** [auto-pick] No — fail-loud only. Raise with before/after SHA + porcelain diff. **Why:** Proposal defers rollback; destructive action is hard to test safely; operator can investigate manually with full context.
- **Q:** Snapshot granularity in the presence of parallel batch fan-out? **A:** [auto-pick] One guard wrapping the entire `run()` function. **Why:** "Did this review pass mutate state?" is the question, not "which sub-call?". Per-call snapshots would misattribute under thread races.
- **Q:** How should `write_review_file` writes (legitimate untracked output) avoid tripping the guard? **A:** [auto-pick] Pass `expected_paths=[cfg["paths"]["reviews_dir"]]` to the guard; porcelain entries matching any expected path are filtered. HEAD changes are never filtered. **Why:** Filtering by configured reviews_dir is precise and survives path-config evolution. Extension-based filters are too broad.
- **Q:** How to fix `--allowedTools ""`? **A:** [auto-pick] Drop the flag when value is empty; add `--disallowedTools Edit,Write,Bash,NotebookEdit` whenever `allowed_tools` does NOT include any of those four. The derivation lives entirely inside `_build_argv` — no signature change to `_invoke` or to `run_bulk`/`run_tool_use`/`run_implementer`. **Why:** Defense in depth — both allow-list and deny-list semantics are explicit. Proposal-aligned tool set. Deriving from `allowed_tools` value keeps the change isolated to one function and self-classifies all three call shapes. `--tools ""` interacts unpredictably with `--allowedTools` in tool-use mode.
- **Q:** How to apply the read-only identity header to templates? **A:** [auto-pick] Prepend verbatim text as the new first paragraph in each of the five review templates. No new render token. **Why:** Smallest change, no new template-fill machinery. Template edits are rare enough that abstraction is premature.
- **Q:** Which templates get the header? **A:** [auto-pick] All five: review-plan-batch, review-plan-holistic, review-code-batch, review-code-holistic, review-discussion. **Why:** The failure was observed in plan-review, but all five share the same agentic-model risk. Cost is one paragraph per file; benefit is uniform contract.
- **Q:** Test coverage scope? **A:** [auto-pick] New `test-review-guard.py` for the helper; extend `test-llm-claude.py` for the argv fix. **Why:** Guard logic deserves its own focused test; argv extension fits the existing argv-capture pattern.
- **Q:** Should the guard skip when `spec.provider == "test_stub"`? **A:** [auto-pick] No — unconditional. **Why:** Stub doesn't touch git, so the guard is a no-op. Conditional bypass adds untested code paths.
- **Q:** What's explicitly out of scope? **A:** [auto-pick] Auto-rollback, tool-use-mode-specific guard rules, denylist beyond E/W/B/N, cluster-reviewer plumbing, reviewer-logic / prompt-template changes beyond the identity header. **Why:** Proposal-aligned scope; each excluded item is either a separate concern or already covered by another mechanism (snapshot guard makes WebFetch/WebSearch denylist redundant).
