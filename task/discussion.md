# Discussion: 36 (A) — Bug-fix batch 3

```yaml
task: 36 (A) — Bug-fix batch 3
slug: mill-misc-fixes-3
status: discussing
parent: main
```

## Problem

Two unrelated mill-side bugs surfaced in the 2026-05-09 issue triage:

**#206 — mill-go cleanliness gate flags pre-existing dirt.** After every successful implementer report, mill-go runs `git -C <worktree> status --porcelain --untracked-files=no` and blocks the batch if the output is non-empty. The check has no notion of "dirt that was there before the batch started" — any tracked-file modification predating mill-go (e.g. user-staged scratch edits left over from a prior session) trips the gate even when none of the implementer's commits touched those files. Reproduced 2026-05-08 on NORCE-DrillingAndWells where a pre-existing `NORCE.Models.Program/Program.cs` modification (visible in `git status` at conversation start, not in any of the implementer's four commits) tripped the gate. Workaround until fixed: `git stash push -- <pre-existing-file>` before re-running.

**#212 — `/git-pr` doesn't enforce the task-files contract.** When `git.require-pr-to-base: true` makes every merge go via PR, a user can reasonably run `/git-pr` directly on a task branch. Nothing in `/git-pr` strips `task/` first, so the PR diff includes every plan file, status snapshot, fix-file, and review. If the PR is squash-merged, all of `task/` lands on `main`. Reproduced on PR #108 (NORCE-DrillingAndWells/Models): `task/discussion.md`, `task/plan/*`, `task/reviews/*`, `task/status.md` accidentally landed in the PR; caught by the user during review and fixed manually with a `git rm -r task/` cleanup commit.

**Why now:** both tripped real users on a real engagement (NORCE-DrillingAndWells, 2026-05-08–09). They're independent, small, and orthogonal — bundle them into one batch instead of spawning two micro-tasks.

## Scope

**In:**

- Cleanliness gate: snapshot `git status --porcelain --untracked-files=no` at batch start, persist it to a sidecar file under `task/`, and at gate time treat only NEW lines (post-snapshot lines absent from the pre-snapshot) as flaggable dirt.
- New helper module `plugins/mill/scripts/_cleanliness.py` exposing `capture_snapshot(worktree, snapshot_path)` and `compute_new_dirt(worktree, snapshot_path) -> list[str]`.
- `millpy-implement.py` initial-dispatch path captures the pre-snapshot alongside `start_sha`. Resume path leaves the existing snapshot untouched.
- `mill-go` SKILL.md section 2b ("Cleanliness gate") rewritten to call `_cleanliness.compute_new_dirt(...)` instead of running raw `git status` and comparing against the empty set.
- `/git-pr` (`plugins/mill/skills/git-pr/SKILL.md`) gains a Step 1.5 "Detect task branch": if `task/status.md` exists at the worktree root, halt with a message redirecting the user to `/mill-merge`. No auto-strip, no prompt.
- Unit tests for `_cleanliness` covering: empty pre + empty post, empty pre + dirty post, dirty pre + identical post, dirty pre + extra post lines, dirty pre + post-snapshot has subset of pre lines, missing snapshot file (treat as empty pre + emit warning).

**Out:**

- Forward-compatibility with task 33's `task/` → `_mill/` rename. Task 33 owns updating both fixes when it lands.
- Detection beyond `task/status.md`. We do not also check `.millhouse/active.slug.md` (redundant; task/status.md is the direct signal we care about — it's what would land in the PR diff).
- Untracked files (`--untracked-files=no` flag preserved). Out of scope; matches existing gate behavior.
- Per-file content hashing or status-code-aware diffing. Line-set diff on raw porcelain text is sufficient for the reported repro cases.
- Changing the gate's response on stuck (`blocked` flow). Only the dirt-detection logic changes; downstream phase transitions, `_status.set_batch_field` calls, and commit messages stay as today.
- Touching `mill-merge`'s own cleanup commit semantics. The sidecar file lives under `task/` so `mill-merge`'s existing `git rm -r task/` removes it implicitly.
- Fixing `/git-pr` for users without mill installed (they don't have `task/status.md` so the new detection is a no-op for them).
- Adding a "draft PR" workflow for mid-task collaborator review. Out of scope; document the workaround (push branch + use GitHub UI) in the redirect message.

## Decisions

### #212-fix-strategy — refuse + redirect

- **Decision:** When `/git-pr` runs from a worktree containing `task/status.md`, halt before any push/PR-creation work with: "This is a mill task branch — `task/` files would land in the PR. Use `/mill-merge` to handle the cleanup commit, archive tag, and Home.md flip in one shot. For mid-task collaborator review, push the branch directly with `git push` and use the GitHub UI to open a draft PR."
- **Rationale:** Strict; prevents any divergence between two PR-creation paths. `mill-merge` already implements cleanup-commit + archive + flip + PR (in `git.require-pr-to-base: true` mode). Forking that machinery into `/git-pr` would mean two places to maintain and two places to forget. The trade-off — a user mid-task can't get a draft PR via `/git-pr` — is mitigated by the documented `git push` workaround in the redirect message.
- **Rejected:**
  - **Auto-strip task/ before pushing.** Tempting but the strip commit removes state mill-go reads on resume (`task/status.md` is how `phase` is read). Subsequent `mill-go` runs would either re-create `task/` (causing churn) or fail. Hidden coupling. Rejected.
  - **Prompt user with both options on each invocation.** Adds UX friction for the same divergence problem. Rejected.

### #206-snapshot-persistence — sidecar file under task/

- **Decision:** Pre-batch porcelain output is written to `task/.cleanliness-snapshot-<batch_name>.txt` at the moment `start_sha` is captured (initial dispatch only — not on `--resume`). The cleanliness gate reads this file, runs the post-batch porcelain, and computes the line-set diff `post − pre` to decide whether to block.
- **Rationale:** Sidecar text I/O is the simplest persistence shape — no YAML schema changes, no risk of a multi-line porcelain blob bloating `task/status.md` past the readable threshold. The dot-prefix keeps it out of casual `ls` output. `mill-merge`'s existing `git rm -r task/` cleanup commit auto-removes it; no separate teardown logic needed. The file is committed on the task branch by the same `mill-go: start batch <name>` commit that records `start_sha`, so recovery after crash already works (the sidecar is in HEAD when mill-go re-enters).
- **Rejected:**
  - **New batch field in status.md (multi-line YAML block).** Pollutes `status.md` with raw porcelain output (which can be tens of lines), complicates `_status` helpers (they currently mutate single-value fields), and makes hand-inspection of `status.md` harder. Rejected.
  - **In-memory only in mill-go.** Lost on resume after crash; breaks the same resume contract `start_sha` already honors via `status.md`. Rejected.

### #206-diff-algorithm — line-set diff on raw porcelain output

- **Decision:** Treat the porcelain output as a set of lines (e.g. ` M file.txt`, `?? other.txt` though we use `--untracked-files=no` so untracked never appears). Pre-batch lines and post-batch lines are normalized only by stripping a trailing newline; otherwise compared verbatim. New dirt = post-set − pre-set.
- **Rationale:** Matches the proposal language ("flag NEW or NEWLY-MODIFIED entries"). Simple, no extra git invocations, deterministic. A file that was `M` pre-batch and is still `M` post-batch produces an identical line in both sets — dropped from new-dirt. A file that was `M` pre-batch and is `MM` post-batch produces two different lines — flagged (genuinely "newly-modified", staged-vs-unstaged divergence). A file that didn't appear pre-batch but does post-batch is flagged. A file that appeared pre-batch but not post-batch is implicitly fine (no operation needed).
- **Rejected:**
  - **Filename-set diff (drop any pre-existing dirty file regardless of status code).** False negative: an implementer could stage extra modifications to a pre-existing dirty file and the gate would never notice. The line-set form catches the `M` → `MM` divergence. Rejected.
  - **Per-file content hash compare.** More robust against hostile edge cases (e.g. file content changed back-and-forth) but the bug we're fixing is "tracked dirt at start trips the gate", not adversarial edits. Over-engineered. Rejected.

### #206-helper-module — new `_cleanliness.py` (unit-testable)

- **Decision:** Diff logic lives in a new module `plugins/mill/scripts/_cleanliness.py` with two functions:
  - `capture_snapshot(worktree: Path, snapshot_path: Path) -> None` — runs `git -C <worktree> status --porcelain --untracked-files=no`, writes stdout to `snapshot_path`. Creates parent directories if needed.
  - `compute_new_dirt(worktree: Path, snapshot_path: Path) -> list[str]` — runs the same `git status`, reads `snapshot_path` (treats missing as empty + emits a `[cleanliness]` warning to stderr), returns `sorted(post_lines - pre_lines)`.
- **Rationale:** Keeps `mill-go` SKILL.md instructions short ("call `_cleanliness.compute_new_dirt(...)`; if non-empty, block"). The pure functions are unit-testable with no real git — fixtures can write porcelain text directly. Matches the existing `_status` / `_paths` / `_review_common` pattern of small flat helpers.
- **Rejected:**
  - **Inline in `mill-go` SKILL.md + `millpy-implement.py`.** Diff logic split across two languages (markdown instructions + Python script) is harder to test and harder to reason about. Rejected.
  - **Reuse `_status`.** Cleanliness is not status; loading it onto `_status` muddles responsibility. Rejected.

### #206-snapshot-path — `task/.cleanliness-snapshot-<batch>.txt`

- **Decision:** One snapshot file per batch, lives at `task/.cleanliness-snapshot-<batch_name>.txt`. The batch name is the same string used elsewhere (`batch_name` in `mill-go` SKILL.md, `--batch` argument to review CLIs).
- **Rationale:** Per-batch (not per-task) because each batch starts from a different sha and may have different pre-existing dirt — though in practice dirt only changes between batches if the user manually edited files mid-run. Per-batch matches `start_sha`'s own scope. Dot-prefix keeps the file out of casual editor file-trees.
- **Rejected:**
  - **One snapshot per task at a fixed path.** Wrong scope — pre-existing dirt at batch 3's start may differ from batch 1's start.
  - **Snapshot under `.scratch/`.** `.scratch/` is gitignored; the snapshot must be committed so it survives crash/resume on another machine.

### #212-detection — `task/status.md` presence

- **Decision:** `/git-pr` Step 1.5 checks `(<git_root>/task/status.md).exists()`. If true, halt with the redirect message described under #212-fix-strategy. No additional checks.
- **Rationale:** `task/status.md` is the direct, single signal that `task/` would land in the PR diff. `.millhouse/active.slug.md` would also indicate a task worktree, but checking it adds zero coverage — any worktree with `active.slug.md` also has `task/status.md` (mill-spawn writes both). Using only `task/status.md` is simpler and the failure mode is identical.
- **Rejected:**
  - **Check `task/status.md` OR `.millhouse/active.slug.md`.** Belt-and-suspenders without real coverage gain. Rejected.
  - **Check both `task/` AND `_mill/` for forward-compat with task 33.** Task 33 explicitly owns the rename and its own forward-compat. Doubling up here just creates two places to update later. Rejected.

## Technical context

### Cleanliness gate code paths (#206)

- **Capture site:** `plugins/mill/scripts/millpy-implement.py`, around lines 118–133 (initial-dispatch branch). Existing code captures `start_sha` via `git rev-parse HEAD`. Add the snapshot capture immediately after that, before `_status.set_batch_fields(...)`. Snapshot path resolves as `project_root / "task" / f".cleanliness-snapshot-{args.batch_name}.txt"`. Add the new file to the existing `git add task/status.md` invocation so the snapshot is included in the `mill-go: start batch <name>` commit (change to `git add task/status.md task/.cleanliness-snapshot-<batch>.txt`).
- **Gate site:** `plugins/mill/skills/mill-go/SKILL.md`, section "2b. Cleanliness gate" (line ~91). Replace the raw `git status --porcelain --untracked-files=no` call with `_cleanliness.compute_new_dirt(worktree, task_dir / f".cleanliness-snapshot-{batch_name}.txt")`. The non-empty check stays, the blocked-state writes stay. Update the example/wording.
- **Resume safety:** `millpy-implement.py --resume` (lines ~118 onward in the `if not args.resume:` branch) does not re-capture. The original snapshot file persists on the task branch. `compute_new_dirt` reads the same path on resume.
- **Crash safety:** if mill-go crashes after `start_sha` is committed (and so is the snapshot file in the same commit) but before the cleanliness gate runs, mill-go's resume path continues into the gate which reads the existing snapshot file. No new state machine.
- **Helper signature documentation:** `mill-go` SKILL.md's helper-signature pattern requires inline signatures wherever a helper is named. Add:
  - `signature: _cleanliness.compute_new_dirt(worktree: Path, snapshot_path: Path) -> list[str]`
- **`millpy-implement.py` integration:** the script has its own helper imports near the top (`_paths`, `_status`, `_implementer_sonnet`, etc.). Add `_cleanliness` to that import list.

### `/git-pr` changes (#212)

- **Edit site:** `plugins/mill/skills/git-pr/SKILL.md`, after Step 1 ("Validate branch") and before Step 2 ("Determine base branch"). Renumber subsequent steps OR insert as Step 1.5 (the SKILL.md uses numbered headings — pick the convention with the smallest diff; "1.5" works given the file's style).
- **Halt message wording:**

  > This is a mill task branch — `task/` files would land in the PR. Use `/mill-merge` to handle the cleanup commit, archive tag, and Home.md flip in one shot. For mid-task collaborator review, push the branch directly with `git push` and open a draft PR via the GitHub UI.

- **Detection target:** the working-tree path `<git_root>/task/status.md`. Resolve `git_root` via `git rev-parse --show-toplevel` (the SKILL.md already uses raw `git` invocations rather than `_paths`).
- **`mill-merge` already handles the PR path:** `git.require-pr-to-base: true` triggers `mill-merge`'s PR branch (line ~88 of `mill-merge` SKILL.md). The redirect points users at the right tool.

### Existing patterns to follow

- Helper modules are flat under `plugins/mill/scripts/`, named `_<topic>.py`. Examples: `_status.py`, `_paths.py`, `_cleanliness.py` follows.
- Helpers do not have `if __name__ == "__main__":` blocks (per CLAUDE.md "Helpers hold only production code").
- Unit tests live at `plugins/mill/unit_tests/test-<name>.py`. Run via `python plugins/mill/unit_tests/run-all.py`. Each test file is a script with bare `assert` statements (no pytest); fixtures use `tempfile.TemporaryDirectory()` / in-memory text. No real git, no real LLM. New file: `plugins/mill/unit_tests/test-cleanliness.py`.
- For Python in this repo: 4-space indent, `pathlib.Path` over `os.path`, `subprocess.run(..., check=False, text=True, capture_output=True)` style. Match `_status.py` / `millpy-implement.py` for tone.

### Files touched (summary)

- **New:** `plugins/mill/scripts/_cleanliness.py`
- **New:** `plugins/mill/unit_tests/test-cleanliness.py`
- **Modified:** `plugins/mill/scripts/millpy-implement.py` (capture snapshot + add to commit)
- **Modified:** `plugins/mill/skills/mill-go/SKILL.md` (section 2b uses `_cleanliness.compute_new_dirt`)
- **Modified:** `plugins/mill/skills/git-pr/SKILL.md` (insert Step 1.5)

## Constraints

- **Junctions/hardlinks rule (CLAUDE.md "Path invariants"):** all paths resolved programmatically. Snapshot file path is computed from `project_root / "task" / ...` — never via `.wiki` or `.active`.
- **`${CLAUDE_PLUGIN_ROOT}` rule:** the SKILL.md edits keep using `${CLAUDE_PLUGIN_ROOT}/scripts/...` in operator-facing examples; the Python helper imports use bare module names (resolved via `PYTHONPATH`).
- **Working state lives on the task branch:** the snapshot file is under `task/`, committed on the task branch by `millpy-implement.py`'s existing batch-start commit. Never written to the wiki.
- **No skill is allowed to call destructive operations as a shortcut.** `/git-pr`'s halt path on detection is *non-destructive* — no commits, no pushes, no `task/` strip. Just exit with the redirect message.
- **`mill-go` Builder discipline:** keep the gate's runtime cost flat. The new helper is a single Python call, no extra LLM round-trips.

## Testing

### `_cleanliness` (unit-testable, TDD candidate)

Prefer TDD here. Write tests first against the spec; implement the helper to pass them. Test file: `plugins/mill/unit_tests/test-cleanliness.py`.

Required scenarios:

- **Empty pre + empty post → no new dirt, returns `[]`.**
- **Empty pre + dirty post → all post lines flagged.**
- **Dirty pre + identical post → no new dirt (the original repro case).** The fix must pass this.
- **Dirty pre + post is a strict superset → only the extra lines are flagged.**
- **Dirty pre + post is a subset (a pre-existing dirty file got committed in the batch) → no new dirt.**
- **Pre includes `M file.txt`, post includes `MM file.txt` → `MM file.txt` is flagged (status-code change, "newly-modified").**
- **Missing snapshot file → treat as empty pre + emit a `[cleanliness]` warning on stderr; still returns the post-set verbatim.** Verify the warning is emitted (capture stderr).
- **Whitespace/CRLF normalization:** snapshot written and read on Windows (CRLF) must produce the same set as on Unix (LF). Test with both line endings as input — strip terminators before set-comparison.
- **`capture_snapshot` writes the exact `git status --porcelain --untracked-files=no` stdout.** Mock the `subprocess.run` call (or use a temp git repo fixture; the existing unit-test convention uses temp dirs without real git, so prefer mocking).

### `millpy-implement.py` integration

- Manual integration test (no automated harness for the CLI): run mill-spawn → mill-plan → manually dirty a tracked file in the worktree → run mill-go → confirm the dirt does NOT block the batch and that the cleanliness gate passes. Repeat without pre-existing dirt to confirm the gate still fires on implementer-introduced dirt.
- Smoke check: confirm `task/.cleanliness-snapshot-<batch>.txt` is created and committed by the `mill-go: start batch <name>` commit.

### `/git-pr` change

- Manual: in a task worktree (with `task/status.md` present), run `/git-pr` and confirm it halts with the redirect message. Confirm no `git push`, no `gh pr create` runs.
- Manual: in a non-task worktree (no `task/status.md`), run `/git-pr` and confirm normal flow proceeds.

### `mill-go` SKILL.md change

Skill instructions are not unit-tested; rely on the integration smoke test above plus mill-receiving-review at SKILL.md review time.

### Test scenarios that must be covered

- Original #206 repro: pre-existing tracked-file modification at batch start, no implementer commit touches it. Gate must NOT fire.
- Genuine implementer dirt: implementer modifies a tracked file but doesn't commit. Gate MUST fire.
- Implementer modifies a file that was pre-existing dirty AND adds further uncommitted modifications. Gate MUST fire (caught by line-set diff via status-code change `M` → `MM`).
- #212 repro: a task branch with `task/status.md` present; `/git-pr` halts before push.

## Q&A log

- **Q:** For #212, refuse + redirect, auto-strip, or prompt? **A:** Refuse + redirect. Strict; matches proposal recommendation.
- **Q:** For #206, where is the pre-batch snapshot persisted? **A:** Sidecar file under `task/` at `task/.cleanliness-snapshot-<batch>.txt`.
- **Q:** Diff algorithm for #206? **A:** Line-set diff on raw porcelain output (post − pre). Catches `M` → `MM` divergence; matches the "NEW or NEWLY-MODIFIED" wording.
- **Q:** Where does the snapshot capture live in `millpy-implement.py`? **A:** Initial-dispatch branch only, alongside `start_sha` capture. Resume path leaves the snapshot untouched.
- **Q:** Forward-compat with task 33's `task/` → `_mill/` rename? **A:** No. Task 33 owns updating both fixes when it lands.
- **Q:** `/git-pr` detection target? **A:** `task/status.md` only. `.millhouse/active.slug.md` adds no coverage; rejected.
- **Q:** Snapshot scope — per-task or per-batch? **A:** Per-batch. Dirt at batch 3's start may differ from batch 1's; matches `start_sha`'s scope.
- **Q:** Diff logic in a helper module or inline? **A:** New helper `_cleanliness.py`. Unit-testable; matches the `_status` / `_paths` flat-helper pattern.
- **Q:** Does the snapshot file need to be committed? **A:** Yes — it must survive crash/resume across machines. Added to the existing `mill-go: start batch <name>` commit.
- **Q:** Does the snapshot need separate teardown? **A:** No. `mill-merge`'s existing `git rm -r task/` cleanup commit removes it implicitly.
