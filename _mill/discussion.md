# Discussion: mill-go: self-modifying repo + absent worktree venv silently uses stale scripts

```yaml
task: 'mill-go: self-modifying repo + absent worktree venv silently uses stale scripts'
slug: self-modifying-repo-venv
status: discussing
parent: main
```

## Problem

When a millhouse task edits plugin scripts AND the wiki schema those
scripts consume on the same branch, mill-go's holistic and per-batch
reviewer subprocesses crash because they run the **cache's stale
`_reviewers.py`** against the **branch's new `agents.yaml` schema**.

The root cause is mill-go's Step 0 SKIP branch: when the task worktree
contains `plugins/mill/` (because the task edits it) but the worktree
`.venv` is absent (gitignored, never synced), Step 0 prints a hint and
**continues using the cache's `PLUGIN_ROOT` and `MILL_PYTHON`**. This is
the worst possible outcome: no error, just wrong code running. The
mismatch surfaces only indirectly — the reviewer CLI exits 1 with no
JSON, the implementer gets dispatched against a null review file, and
the operator must manually run `uv sync` and restart.

This has fired twice in recent history:
- `implementer-model-config` (#299): `_reviewers.py` looked for the
  renamed `reviewers.yaml`; wiki only had `agents.yaml`.
- `config-env-interpolation` (#313): old `_reviewers.py` saw the new
  `extends:`-syntax entries and threw `unknown type None`.

**Why now:** the pattern is common enough that two consecutive recent
tasks have tripped it. Every self-modifying task that touches both
scripts and wiki schema is a candidate.

## Scope

**In:**
- Edit `plugins/mill/skills/mill-go/SKILL.md` Step 0: replace the SKIP
  branch (currently warns and falls through) with auto-`uv sync` of the
  worktree plugin venv. After sync, promote `PLUGIN_ROOT` and
  `MILL_PYTHON` to worktree paths unconditionally.
- Halt with non-zero exit and a clear stderr message if `uv sync`
  fails — never fall back to the cache.

**Out:**
- `millpy-spawn.py` changes (pre-creating the venv at spawn time).
- `millpy-review-code.py` worktree-local plugin detection.
- mill-start and mill-plan auto-sync (those skills don't run the
  reviewer subprocesses where the stale-schema crash surfaces).
- Optimizing `uv sync` runtime.
- Handling `uv.lock` drift — `uv sync` against a committed lock is
  idempotent; downstream cleanliness gates surface real drift.
- Defensive checks for `pyproject.toml` absence — `plugins/mill/`
  existing in a worktree always means a millhouse self-modifying task.

## Decisions

### inline-vs-helper

- Decision: Inline the sync logic in `mill-go/SKILL.md` Step 0 as bash.
  No new Python helper.
- Rationale: ~10 lines of bash, single caller (mill-go's Step 0),
  bash↔Python round-trip for a one-shot subprocess invocation is more
  ceremony than the logic deserves.
- Rejected: Add `_worktree.ensure_venv()` helper. No other caller exists
  or is anticipated — mill-start and mill-plan are explicitly out of
  scope.

### halt-on-sync-failure

- Decision: If `uv sync` exits non-zero, mill-go halts with `exit 1` and
  a clear stderr message naming the worktree and suggesting manual
  diagnosis. No fallback to cache.
- Rationale: The bug being fixed is silent fall-through to stale cache
  code. A warn-and-continue policy reintroduces it.
- Rejected: Warn and fall back to cache. Equivalent to the current
  broken behavior.

### uv-sync-invocation

- Decision: `uv sync --project plugins/mill` invoked inside a subshell
  that changes cwd to the worktree root:
  `(cd "$WORKTREE_ROOT" && uv sync --project plugins/mill)`. The
  subshell pattern is the **required** form — bare-shell `cd` is
  rejected, but a subshell `cd` is allowed because the parent shell's
  cwd is preserved.
- Rationale: Matches the CLAUDE.md convention for `uv` invocations
  from source-tree paths. Worktree-isolation rules forbid the
  **outer** shell from changing cwd (downstream `git rev-parse` and
  Python invocations rely on the worktree cwd). The subshell isolates
  the `cd` to the `uv sync` process only.
- Rejected: Outer-shell `cd plugins/mill && uv sync`. Forbidden by the
  worktree conversation rules and by mill-go's own subsequent
  `git rev-parse` calls.

### branch-restructure

- Decision: Collapse the two `if`/`elif` branches in Step 0 into a
  single branch. When `plugins/mill/` exists in the worktree, run
  `uv sync` (skip if `.venv/Scripts/python.exe` already exists),
  then unconditionally promote `PLUGIN_ROOT` and `MILL_PYTHON` to the
  worktree paths.
- Rationale: The current `elif` branch (venv absent) is what we're
  removing. The `if` branch (venv present) becomes unconditional after
  the sync guarantees the venv exists.
- Rejected: Keep two branches with a re-check. Pure noise — the sync
  either succeeded (venv exists) or we already halted.

### idempotency

- Decision: Skip `uv sync` when the worktree `.venv/Scripts/python.exe`
  binary already exists. Only run sync when the binary is missing.
- Rationale: `uv sync` against an up-to-date venv is fast (~1-2s) but
  not free, and mill-go is called frequently. The presence of
  `Scripts/python.exe` is a sufficient proxy for "venv is initialized";
  fine-grained drift detection is `uv`'s job, not mill-go's.
- Rejected: Always run `uv sync` for safety. Adds latency on every
  mill-go invocation against an unchanged venv.

## Technical context

**Current Step 0 structure** (`plugins/mill/skills/mill-go/SKILL.md`
lines 14-42, the two-block bash sequence):

Block 1: Resolve `PLUGIN_ROOT` from `${CLAUDE_PLUGIN_ROOT}` or fall back
to `git rev-parse --show-toplevel` + `/plugins/mill`. Sets `MILL_PYTHON`
to `${PLUGIN_ROOT}/.venv/Scripts/python.exe`.

Block 2 (the bug site):

```bash
WORKTREE_PLUGIN_ROOT="$(git rev-parse --show-toplevel)/plugins/mill"
WORKTREE_VENV="${WORKTREE_PLUGIN_ROOT}/.venv/Scripts/python.exe"
if [ -d "$WORKTREE_PLUGIN_ROOT" ] && [ -f "$WORKTREE_VENV" ]; then
    PLUGIN_ROOT="$WORKTREE_PLUGIN_ROOT"
    MILL_PYTHON="$WORKTREE_VENV"
    echo "[mill-go] NOTE: self-modifying repo detected; PLUGIN_ROOT overridden to $PLUGIN_ROOT"
elif [ -d "$WORKTREE_PLUGIN_ROOT" ]; then
    echo "[mill-go] SKIP: self-modifying repo but worktree venv absent -- using cache. Run 'uv sync --project ${WORKTREE_PLUGIN_ROOT}' to enable."
fi
```

**Replacement** (single branch, sync-if-absent, halt-on-failure,
unconditional override):

```bash
WORKTREE_ROOT="$(git rev-parse --show-toplevel)"
WORKTREE_PLUGIN_ROOT="${WORKTREE_ROOT}/plugins/mill"
WORKTREE_VENV="${WORKTREE_PLUGIN_ROOT}/.venv/Scripts/python.exe"
if [ -d "$WORKTREE_PLUGIN_ROOT" ]; then
    if [ ! -f "$WORKTREE_VENV" ]; then
        echo "[mill-go] self-modifying repo: worktree venv absent at ${WORKTREE_PLUGIN_ROOT}/.venv -- running 'uv sync --project plugins/mill'"
        (cd "$WORKTREE_ROOT" && uv sync --project plugins/mill) || {
            echo "[mill-go] HALT: uv sync failed in worktree ${WORKTREE_ROOT} -- cannot run self-modifying task with stale cache scripts. Run 'uv sync --project plugins/mill' manually and re-run /mill-go." >&2
            exit 1
        }
    fi
    PLUGIN_ROOT="$WORKTREE_PLUGIN_ROOT"
    MILL_PYTHON="$WORKTREE_VENV"
    echo "[mill-go] NOTE: self-modifying repo detected; PLUGIN_ROOT overridden to $PLUGIN_ROOT"
fi
```

Note: the inner `(cd "$WORKTREE_ROOT" && uv sync ...)` runs in a
**subshell** — the parent shell's cwd is preserved, satisfying the
worktree-isolation rule. This is the same idiom used in other mill
bash blocks that need a one-shot cwd change without polluting the
outer shell.

**Prose update under the bash block** (currently lines 40-42):

The paragraph starting "Both `PLUGIN_ROOT` and `MILL_PYTHON` are
updated together only when the worktree venv exists..." needs a
rewrite. New text should state:

- When `plugins/mill/` is present in the worktree, the venv is
  guaranteed to be synced (auto-run on first detection); both
  `PLUGIN_ROOT` and `MILL_PYTHON` are unconditionally overridden to
  worktree paths.
- `uv sync` failure halts mill-go; no fallback to cache.
- For non-millhouse repos (no `plugins/mill/` in the worktree), the
  block is a no-op.

**Files touched:**
- `plugins/mill/skills/mill-go/SKILL.md` — the Step 0 bash block
  (lines ~26-42) and the prose paragraph immediately following.

That is the entire surface of this task.

## Constraints

- Worktree-isolation: subshell pattern `(cd ... && uv sync)` is the
  only allowed form. The outer shell's cwd must be preserved for the
  subsequent `git rev-parse` and Python invocations in Step 0.
- ASCII-only stdout/stderr: messages use ` -- ` not `—`. No emojis.
- `uv` must be on PATH — mill-setup already requires it, no defensive
  check needed.
- Windows-only path: `.venv/Scripts/python.exe`. Linux `bin/python` is
  not in scope (existing mill-go is Windows-only).
- The change must remain a no-op for non-millhouse repos using mill as
  a plugin — those have no `plugins/mill/` in the worktree, so the
  outer `if [ -d "$WORKTREE_PLUGIN_ROOT" ]` guard short-circuits.

## Testing

This is a SKILL.md edit only — no Python code changes. Standard mill
unit/integration test suites do not exercise SKILL.md bash blocks.

**Manual verification** (operator runs after the edit lands):

1. **Happy path — fresh self-modifying worktree.** In a worktree where
   `plugins/mill/` exists and `.venv` is absent, run `/mill-go`.
   Expect: stderr line `self-modifying repo: worktree venv absent ... running 'uv sync ...'`, the sync completes, then the override
   message prints, and mill-go proceeds with `MILL_PYTHON` pointing at
   the worktree venv.

2. **Idempotent path — worktree venv already present.** Re-run
   `/mill-go` immediately. Expect: no sync-related stderr (the `[ ! -f $WORKTREE_VENV ]` guard skips the sync), only the override message.

3. **Failure path — broken `pyproject.toml`.** Temporarily corrupt
   `plugins/mill/pyproject.toml` and run `/mill-go`. Expect: stderr
   `HALT: uv sync failed ...`, exit code 1, no Python invocations
   downstream.

4. **No-op path — non-self-modifying worktree.** In a task worktree
   without `plugins/mill/`, run `/mill-go`. Expect: no sync, no
   override, the cache `PLUGIN_ROOT` is used unchanged.

No automated test infrastructure is added — the change is bash inside
a SKILL.md, executed by the operator's CC session, not by Python tests.

## Q&A log

- **Q:** Should the venv-sync logic be inline bash in SKILL.md or extracted to a Python helper like `_worktree.ensure_venv()`? **A:** [auto-pick] Inline in SKILL.md. **Why:** ~10 lines of bash with a single caller; no other consumer exists or is anticipated.
- **Q:** On `uv sync` non-zero exit, should mill-go halt or fall back to cache with a warning? **A:** [auto-pick] Halt with exit 1 + clear stderr. **Why:** The whole point of this task is "no silent fallback to stale cache"; a warn-and-continue policy is identical to the current bug.
- **Q:** Invoke `uv sync` via `--project plugins/mill` from worktree root, or `cd plugins/mill && uv sync`? **A:** [auto-pick] `uv sync --project plugins/mill` in a subshell to preserve cwd. **Why:** Matches CLAUDE.md convention; worktree-isolation rule forbids changing outer shell cwd.
- **Q:** Should `uv.lock` drift inside the worktree be handled by mill-go (stash/restore around sync)? **A:** [auto-pick] Out of scope. **Why:** `uv sync` against a committed lock is idempotent; lock drift is a separate bug; downstream cleanliness gates surface real changes.
- **Q:** Should mill-start and mill-plan get the same auto-sync logic? **A:** [auto-pick] No — scope to mill-go only. **Why:** Matches proposal Scope verbatim; mill-start/mill-plan don't run the reviewer subprocesses where the stale-schema crash surfaces.
- **Q:** Merge the two `if`/`elif` branches in Step 0, or keep the structure and add sync inside the `elif`? **A:** [auto-pick] Merge into one branch. **Why:** After auto-sync the venv is guaranteed; the `elif` "venv absent" case ceases to exist as a distinct path.
- **Q:** Always run `uv sync` for safety, or skip when `.venv/Scripts/python.exe` already exists? **A:** [auto-pick] Skip when binary exists. **Why:** mill-go is called frequently; the sync is ~1-2s against an up-to-date venv; presence of the python binary is a sufficient proxy for "venv initialized".
