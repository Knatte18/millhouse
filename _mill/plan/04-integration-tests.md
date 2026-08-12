# Batch: integration-tests

```yaml
task: 'mill-merge/merge-in: squash non-ff rejection, stale-worktree logic, parent-branch detection, conflict resolution'
batch: integration-tests
number: 4
cards: 6
verify: PYTHONPATH= uv run --project plugins/mill python plugins/mill/integration_tests/test-merge.py
depends-on: [1, 2, 3]
```

## Rename mechanic

Not applicable — this batch has no `Moves:` entries.

## Batch Scope

Extends `plugins/mill/integration_tests/test-merge.py` with integration coverage for the three git-plumbing fixes per `_mill/discussion.md`'s `testing-approach` Decision: #824's pre-squash parent fast-forward and rollback-target fix (Cards 9-10), and #817's dead-parent-branch chain-walk (Cards 11-14). Every new scenario follows this file's existing convention (see the `#705` dirty-parent-worktree-preflight and `#736` step-5-guard scenarios already in `main()`): a lightweight, self-contained real git fixture built inline with `_run`/`subprocess.run` at a fresh `SCRATCH / f"merge-test-<name>-{uuid.uuid4().hex[:8]}"` container, asserted with `_assert`, one `print("PASS: ...")` per assertion group — not a reuse of `_setup_trio`'s wiki-backed trio, since none of these six scenarios need a wiki, Home.md, or worktree junctions. #824's scenarios test the exact git sequence `mill-merge/SKILL.md` Step 5 and its Rollback section now prescribe (this file's established convention: "the skills themselves are prose; the test exercises the backing helpers and the exact git sequence the skills prescribe"). #817's scenarios call `_parent_branch.check_liveness` / `resolve_dead_parent` (batch 1) directly against real `archive/<slug>` tags and real `origin` remotes — no SKILL.md prose is invoked. All six cards insert into `main()`'s existing `try:` block, immediately after the line `print("PASS -- mill-merge phase-gate slug-mismatch fallback (#656/#659/#662)")` and before the line `# === Run nested-hub scenario (new test for #497 bug 2) ===` — each card's new `# === ... ===` section goes directly below the previous card's, in card order (9, 10, 11, 12, 13, 14), so the six sections read as one contiguous block ahead of the existing nested-hub scenario.

## Cards

### Card 9: #824 — parent fast-forward success + divergence halt

- **Context:** none
- **Edits:**
  - `plugins/mill/integration_tests/test-merge.py`
- **Creates:** none
- **Deletes:** none
- **Moves:** none
- **Requirements:**
  - Read the file's existing `_run`/`_assert`/fixture-building conventions in full before writing this card's code — in particular the `#705` dirty-parent-worktree-preflight scenario's structure (already part of this same `Edits:` file), which this card's fixtures mirror closely.
  - Insert a new section titled `# === #824: pre-squash parent fast-forward (success + divergence halt) ===` at the insertion point described in Batch Scope above.
  - **Success sub-scenario** — replicates the race: `origin/<parent_branch>` moves after the parent worktree's local ref last synced, and the new fast-forward step (Card 3 of batch 2) prevents the push rejection that would otherwise occur.
    1. Build a fresh container `container_ff = SCRATCH / f"merge-test-ff-{uuid.uuid4().hex[:8]}"`. Init a bare `origin_ff = container_ff / "origin.git"` (`git init --bare -b main`). Clone it to `parent_ff = container_ff / "parent"` and configure `user.email`/`user.name` (mirror the existing fixture-setup pattern used for `container_dirty` etc.). Commit an initial file on `main` and push to `origin_ff`.
    2. Clone `origin_ff` a second time to a throwaway `advancer_ff = container_ff / "advancer"`, commit a new file there ("simulates another thread's concurrent squash-merge landing on origin"), and push it to `origin_ff main`. Do NOT fetch this into `parent_ff` yet — `parent_ff`'s local `main` is now stale relative to `origin_ff/main`, reproducing the race.
    3. Create a child branch on `parent_ff`: `git -C parent_ff checkout -b test/ff-success-child`, add a feature file, commit.
       Check back out to `main` on `parent_ff` before the next step (Step 5's squash runs against the parent's `main`, not the child branch).
    4. Run the fast-forward step exactly as Card 3 of batch 2 documents: `git -C parent_ff fetch origin main` then `git -C parent_ff merge --ff-only origin/main`. Assert both exit 0. Assert `git -C parent_ff rev-parse main` now equals `git -C origin_ff rev-parse main` (the parent worktree's local ref caught up).
    5. Run the squash: `git -C parent_ff merge --squash test/ff-success-child`, commit, then `git -C parent_ff push origin main`. Assert the push exits 0 (proving the non-fast-forward rejection this fix prevents does not occur).
    - `print("PASS: #824 pre-squash parent fast-forward prevents the non-ff push rejection")`.
  - **Divergence-halt sub-scenario** — the parent worktree has a local-only commit AND `origin` has independently advanced (a genuine two-sided divergence — neither ref is an ancestor of the other); the fast-forward must fail loudly instead of discarding either side. A one-sided advance (only local ahead, `origin` unmoved) is NOT sufficient to reproduce this: `git merge --ff-only` treats that case as "Already up to date" and exits 0 (a fast-forward trivially exists), so the fixture must genuinely diverge both refs or the assertion below is asserting behavior git does not actually produce.
    1. Build a fresh container `container_ff_halt = SCRATCH / f"merge-test-ff-halt-{uuid.uuid4().hex[:8]}"`. Init a bare `origin_ff_halt`, clone to `parent_ff_halt`, commit + push an initial file on `main`, same pattern as above.
    2. Advance `origin_ff_halt/main` independently by one commit, via a throwaway `advancer_ff_halt = container_ff_halt / "advancer"` clone (mirroring the Success sub-scenario's step 2 — nested inside `container_ff_halt` so no separate `finally:`-block registration is needed, same as `advancer_ff` above) — push it to `origin_ff_halt main`. Do NOT fetch this into `parent_ff_halt` yet.
    3. On `parent_ff_halt`, commit a second, DIFFERENT file directly to local `main` WITHOUT pushing it — `parent_ff_halt`'s local `main` now has one local-only commit neither present in, nor an ancestor of, `origin_ff_halt/main`'s new tip (both sides added different commits on top of the same shared base), a genuine two-sided divergence.
    4. Capture `local_before = git -C parent_ff_halt rev-parse main` and the working tree's file listing before the next step.
    5. Run `git -C parent_ff_halt fetch origin main` (exits 0 — divergence is between local refs, not the fetch itself) then `git -C parent_ff_halt merge --ff-only origin/main`. Assert this second command exits non-zero (git refuses `--ff-only` when neither ref is a fast-forward of the other).
    6. Assert nothing was mutated: `git -C parent_ff_halt rev-parse main` still equals `local_before`, and `git -C parent_ff_halt status --porcelain` is empty — proving the halt leaves the parent worktree exactly as it was (matching the "nothing has been mutated yet at this halt point" rollback-exemption rationale in batch 2 Card 4).
    - `print("PASS: #824 parent fast-forward halts (does not reset --hard) when the parent worktree has genuinely diverged from origin")`.
  - **Register both new containers in `main()`'s existing `finally:` block**, matching the established pattern already used there for `container_dirty`/`container_retry`/`container_untracked`/`container_step5_guard` (one `if "X" in locals():` entry per container in EACH of the two branches): add `if "container_ff" in locals(): print(f"Scratch preserved: {container_ff}", file=sys.stderr)` and the equivalent `container_ff_halt` line to the `if failed:` branch, and add the matching `if "container_ff" in locals(): _safe_rmtree.safe_rmtree(container_ff, allowed_root=container_ff, ignore_errors=True)` and the equivalent `container_ff_halt` block to the `else:` (success-cleanup) branch. Without this, every test run leaks these two directories under `.scratch/` unboundedly.
- **Commit:** `test(mill): integration coverage for #824 pre-squash parent fast-forward`

### Card 10: #824 — rollback resets to origin, not checkpoint

- **Context:**
  - `plugins/mill/integration_tests/test-merge.py`
- **Edits:**
  - `plugins/mill/integration_tests/test-merge.py`
- **Creates:** none
- **Deletes:** none
- **Moves:** none
- **Requirements:**
  - Insert a new section titled `# === #824: Steps 1-5 rollback resets to origin/<parent_branch>, not the child checkpoint ===` immediately after Card 9's section.
  - **Repro (old, buggy target) then fix (new, correct target)** — mirrors this file's existing `#648`/`#736` repro-then-fix pattern.
    1. Build a fresh container `container_rb = SCRATCH / f"merge-test-rollback-{uuid.uuid4().hex[:8]}"`. Init a bare `origin_rb`, clone to `parent_rb`, commit + push an initial file on `main`.
    2. Advance `origin_rb/main` past `parent_rb`'s local `main` by one commit, via a throwaway `advancer_rb` clone (same pattern as Card 9 step 2), and fetch it into `parent_rb` (`git -C parent_rb fetch origin main`) so `refs/remotes/origin/main` is populated — but do NOT fast-forward `parent_rb`'s local `main` yet, so local `main` and `origin/main` now point at two different commits (`local_sha` and `origin_sha` respectively).
    3. Create `mill-checkpoint-demo` on `parent_rb` pointing at a THIRD, unrelated commit — check out a throwaway branch, commit an unrelated file, then `git -C parent_rb branch -f mill-checkpoint-demo <that-commit's-sha>` — representing the child worktree's own pre-merge-in history, which per the #824 bug report is unrelated to the parent's state. Capture `checkpoint_sha`.
    4. **Repro:** run the OLD rollback command, `git -C parent_rb reset --hard mill-checkpoint-demo`. Assert `git -C parent_rb rev-parse HEAD` now equals `checkpoint_sha` — proving the old command lands the parent worktree on unrelated child history (the bug).
       `print("PASS: repro -- old rollback target (mill-checkpoint-<name>) lands parent worktree on unrelated child history (#824)")`.
    5. Reset `parent_rb` back to `local_sha` (`git -C parent_rb reset --hard <local_sha>`) to undo the repro step before proving the fix.
    6. **Fix:** run the NEW rollback command Card 4 of batch 2 documents, `git -C parent_rb reset --hard origin/main`. Assert `git -C parent_rb rev-parse HEAD` now equals `origin_sha` (`git -C origin_rb rev-parse main`) — proving the fix lands the parent worktree on the correct, live parent state regardless of which Steps 1-5 failure triggered the rollback.
       `print("PASS: fix -- rollback resets parent worktree to origin/<parent_branch> (#824)")`.
  - **Register `container_rb` in `main()`'s existing `finally:` block**, same pattern as Card 9's registration requirement: an `if "container_rb" in locals():` entry with the preserve-print in the `if failed:` branch, and the matching `_safe_rmtree.safe_rmtree(container_rb, allowed_root=container_rb, ignore_errors=True)` entry in the `else:` branch.
- **Commit:** `test(mill): integration coverage for #824 rollback-target fix`

### Card 11: #817 — torn-down-parent chain resolves; never-pushed and no-status-file both fall back

- **Context:**
  - `plugins/mill/integration_tests/test-merge.py`
  - `plugins/mill/scripts/_parent_branch.py`
- **Edits:**
  - `plugins/mill/integration_tests/test-merge.py`
- **Creates:** none
- **Deletes:** none
- **Moves:** none
- **Requirements:**
  - Insert a new section titled `# === #817: dead-parent-branch detection (torn-down + never-pushed) ===` immediately after Card 10's section.
  - **Shared fixture setup for both sub-scenarios:**
    1. Build a fresh container `container_dead = SCRATCH / f"merge-test-dead-parent-{uuid.uuid4().hex[:8]}"`. Init a bare `origin_dead = container_dead / "origin.git"` (`-b main`). Clone to `repo_dead = container_dead / "repo"`, configure `user.email`/`user.name`, commit + push an initial file on `main`.
    2. `cfg_dead = {"spawn": {"branch_prefix": "test/"}, "git": {"base_branch": "main"}}` — construct this dict directly in the test (no `_config.load_config` call needed; `resolve_dead_parent` only reads these two nested keys).
  - **Sub-scenario (a): torn-down parent (archive tag present, chain-walk resolves).**
    1. On `repo_dead`, create `test/parent-task` off `main`, add a file, commit. Push it to `origin_dead` (`git -C repo_dead push origin test/parent-task`), then delete it from `origin_dead` (`git -C repo_dead push origin --delete test/parent-task`) — reproducing the "merged and torn down" shape: the branch existed, was pushed, and is now gone from the remote, exactly as `mill-cleanup`'s `_delete_remote_branch` leaves it.
    2. Commit a cleanup commit on `test/parent-task` locally (do NOT push it — the branch is already deleted on origin, matching the real archive flow where the cleanup commit happens right before tagging): add a status file at the fixture-internal path _mill/status.md (no backticks — this is fixture content the test writes at runtime, not a project source file this card reads) with content `"phase: done\ntask: Parent task\nparent: main\n"`, commit it, THEN append one more trivial commit ("chore: pre-merge cleanup" style, mirroring the real `_mill/` removal semantics is not required here — the test only needs the tag to point one commit AFTER the status.md-bearing commit). Tag the tip: `git -C repo_dead tag archive/parent-task test/parent-task`.
    3. Call `_parent_branch.resolve_dead_parent("test/parent-task", repo_dead, cfg_dead)`. Assert the result equals `{"outcome": "resolved", "branch": "main", "hops": ["parent-task"]}`.
       `print("PASS: #817 chain-walk resolves a torn-down (merged-and-archived) parent to its own live parent")`.
  - **Sub-scenario (b): never-pushed parent (no archive tag, falls back to base_branch).**
    1. On `repo_dead`, create `test/never-pushed` LOCALLY off `main` (no push to `origin_dead` at all — reproducing the "never pushed" shape). Do not tag it.
    2. Call `_parent_branch.resolve_dead_parent("test/never-pushed", repo_dead, cfg_dead)`. Assert the result equals `{"outcome": "fallback", "reason": "no-tag", "branch": "main", "hops": ["never-pushed"]}`.
       `print("PASS: #817 chain-walk falls back to base_branch when no archive tag exists (never-pushed parent)")`.
  - **Sub-scenario (c): archived parent whose pre-cleanup tree has no status.md at either layout (the other fallback-(b) sub-case Batch 1 Card 2 step 4 and step 5 document, distinct from sub-scenario (a)'s "no `parent:` row" and Card 14's "legacy `task/` layout" cases).**
    1. On `repo_dead`, create `test/no-status-file` off `main`, add an UNRELATED file (e.g. `feature.txt`, no status.md at any path), commit, add one more trivial commit on top, tag `archive/no-status-file` at the tip. Do not push.
    2. Call `_parent_branch.resolve_dead_parent("test/no-status-file", repo_dead, cfg_dead)`. Assert the result equals `{"outcome": "fallback", "reason": "chain-end", "branch": "main", "hops": ["no-status-file"]}` — proving the function correctly falls back when both the `git show archive/no-status-file~1:_mill/status.md` and `git show archive/no-status-file~1:task/status.md` attempts fail (neither path exists in that tree at all), rather than raising or misclassifying this as `no-tag`.
       `print("PASS: #817 chain-walk falls back to chain-end when neither _mill/status.md nor task/status.md exists in the archived tree")`.
  - **Register `container_dead` in `main()`'s existing `finally:` block**, same pattern as Cards 9/10's registration requirement: an `if "container_dead" in locals():` entry with the preserve-print in the `if failed:` branch, and the matching `_safe_rmtree.safe_rmtree(container_dead, allowed_root=container_dead, ignore_errors=True)` entry in the `else:` branch. `container_dead` is reused unchanged by Cards 12, 13, and 14 (same container, same registration — those cards do not need a second registration).
- **Commit:** `test(mill): integration coverage for #817 dead-parent detection (torn-down + never-pushed + no-status-file)`

### Card 12: #817 — two chained dead-parent hops resolve through both to a live branch

- **Context:**
  - `plugins/mill/integration_tests/test-merge.py`
  - `plugins/mill/scripts/_parent_branch.py`
- **Edits:**
  - `plugins/mill/integration_tests/test-merge.py`
- **Creates:** none
- **Deletes:** none
- **Moves:** none
- **Requirements:**
  - Insert a new section titled `# === #817: two chained dead-parent hops resolve to the live branch at the end of the chain ===` immediately after Card 11's section, reusing `container_dead`, `repo_dead`, `origin_dead`, `cfg_dead` from Card 11 (same fixture, same container — do not rebuild it).
  - Push a genuinely live branch distinct from `main` to act as the chain's live endpoint: `git -C repo_dead checkout -b release/1.0 main`, commit a trivial file, `git -C repo_dead push origin release/1.0`. Check back out to `main` afterward.
  - Build `test/task-c`: branch off `main`, add a status file at the fixture-internal path _mill/status.md (no backticks — fixture content, not a project source file) with `"phase: done\ntask: Task C\nparent: release/1.0\n"`, commit, add one more trivial commit on top, tag `archive/task-c` at the tip. Do not push `test/task-c` to origin (it is dead — same "never pushed" or "torn down" shape either way; the chain-walk only cares that `check_liveness` on it returns `False`, and it is not pushed here so that is guaranteed).
  - Build `test/task-b`: branch off `main`, add a status file at the fixture-internal path _mill/status.md (no backticks — fixture content, not a project source file) with `"phase: done\ntask: Task B\nparent: test/task-c\n"` (its parent is the STILL-DEAD `test/task-c`, not yet the live branch), commit, add one more trivial commit on top, tag `archive/task-b` at the tip. Do not push `test/task-b` to origin.
  - Call `_parent_branch.resolve_dead_parent("test/task-b", repo_dead, cfg_dead)`. Assert the result equals `{"outcome": "resolved", "branch": "release/1.0", "hops": ["task-b", "task-c"]}` — the walk starts at `task-b` (dead), follows its parent to `task-c` (also dead), follows THAT parent to `release/1.0` (live), and stops there. Two hops recorded, not one, proving the loop actually iterates rather than only resolving the first hop.
  - `print("PASS: #817 chain-walk resolves through two chained dead-parent hops to the live branch at the end of the chain")`.
- **Commit:** `test(mill): integration coverage for #817 multi-hop dead-parent chain resolution`

### Card 13: #817 — cycle hits the 10-hop cap and halts

- **Context:**
  - `plugins/mill/integration_tests/test-merge.py`
  - `plugins/mill/scripts/_parent_branch.py`
- **Edits:**
  - `plugins/mill/integration_tests/test-merge.py`
- **Creates:** none
- **Deletes:** none
- **Moves:** none
- **Requirements:**
  - Insert a new section titled `# === #817: a genuine cycle hits the 10-hop cap and halts with outcome: cycle ===` immediately after Card 12's section, reusing `container_dead`/`repo_dead`/`cfg_dead`.
  - Build two dead branches that point at each other, forming a cycle with no live endpoint ever reachable:
    - `test/cycle-x`: branch off `main`, add a status file at the fixture-internal path _mill/status.md (no backticks — fixture content, not a project source file) with `"phase: done\ntask: Cycle X\nparent: test/cycle-y\n"`, commit, add one more trivial commit on top, tag `archive/cycle-x` at the tip. Do not push.
    - `test/cycle-y`: branch off `main`, add a status file at the fixture-internal path _mill/status.md (no backticks — fixture content, not a project source file) with `"phase: done\ntask: Cycle Y\nparent: test/cycle-x\n"`, commit, add one more trivial commit on top, tag `archive/cycle-y` at the tip. Do not push.
  - Call `_parent_branch.resolve_dead_parent("test/cycle-x", repo_dead, cfg_dead)` (uses the default `max_hops=10`). Assert the result's `"outcome"` is `"cycle"` and `len(result["hops"]) == 10` (the loop runs exactly `max_hops` iterations, alternating `cycle-x`/`cycle-y`, and never finds a live branch or a chain-end).
  - `print("PASS: #817 chain-walk caps at 10 hops and reports outcome: cycle for a pathological cycle")`.
- **Commit:** `test(mill): integration coverage for #817 cycle-detection hop cap`

### Card 14: #817 — legacy `task/status.md` layout fallback

- **Context:**
  - `plugins/mill/integration_tests/test-merge.py`
  - `plugins/mill/scripts/_parent_branch.py`
  - `plugins/mill/scripts/_paths.py`
- **Edits:**
  - `plugins/mill/integration_tests/test-merge.py`
- **Creates:** none
- **Deletes:** none
- **Moves:** none
- **Requirements:**
  - Insert a new section titled `# === #817: legacy task/status.md layout is read via the same _mill/-then-task/ fallback order ===` immediately after Card 13's section, reusing `container_dead`/`repo_dead`/`cfg_dead`.
  - Build `test/legacy-task`: branch off `main`, add the status file at the LEGACY fixture-internal path task/status.md (no backticks — fixture content, not a project source file; NOT the _mill/status.md path used by the other cards in this batch) with content `"phase: done\ntask: Legacy task\nparent: main\n"`, commit, add one more trivial commit on top, tag `archive/legacy-task` at the tip. Do not push.
  - Call `_parent_branch.resolve_dead_parent("test/legacy-task", repo_dead, cfg_dead)`. Assert the result equals `{"outcome": "resolved", "branch": "main", "hops": ["legacy-task"]}` — proving the `git show archive/legacy-task~1:_mill/status.md` attempt fails (no such path in that tree) and the function falls back to `git show archive/legacy-task~1:task/status.md`, per batch 1 Card 2's documented fallback order, rather than misclassifying this hop as a chain-end.
  - `print("PASS: #817 chain-walk falls back to the legacy task/status.md layout instead of misclassifying it as chain-end")`.
- **Commit:** `test(mill): integration coverage for #817 legacy task/status.md layout fallback`

## Batch Tests

`verify:` runs the full `test-merge.py` file (`PYTHONPATH= uv run --project plugins/mill python plugins/mill/integration_tests/test-merge.py`) — every scenario in the file, including the pre-existing flat-hub, nested-hub, and nested-verify-plan scenarios, plus all six new scenarios this batch adds. Unbounded (whole-file) rather than a narrower `--only`-style scope is correct here because this is a single self-contained script with no test-selection flag of its own (unlike the unit-test suite's `run-all.py --only`) — running it end-to-end is the only way to run any part of it, and every existing scenario in the file already passes today, so this is not new unbounded scope, just the existing invocation.
