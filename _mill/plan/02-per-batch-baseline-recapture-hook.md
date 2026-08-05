# Batch: per-batch-baseline-recapture-hook

```yaml
task: mill-go's one-shot pre-batch-1 baseline can't cover a task's own later per-batch-baseline capability
batch: per-batch-baseline-recapture-hook
number: 2
cards: 3
verify: null
depends-on: [1]
```

## Batch Scope

Wires the per-batch baseline recapture mechanism into `mill-go/SKILL.md`:
one new shared subsection defining the self-hosting-gated check-and-invoke
block (consuming batch 1's `_paths.is_self_hosting_task` helper), plus two
small, locally-scoped references to that block at the two dispatch-mode-
specific hook points inside `### 1. Implement`. This batch is pure
markdown orchestration — no Python changes, no automated test (matches
the existing "0.5. Baseline pre-flight" step's own precedent of having no
dedicated unit test beyond the underlying `_run_baseline_stage` /
`_enumerate_batch_verify_triples` coverage, which this batch does not
modify).

## Cards

### Card 3: Add "### 0.6. Per-batch baseline recapture (self-hosting only)" subsection

- **Context:**
  - `plugins/mill/scripts/_paths.py`
  - `plugins/mill/scripts/_status.py`
  - `plugins/mill/scripts/_plan_dag.py`
  - `plugins/mill/scripts/millpy-implement.py`
  - `CLAUDE.md`
- **Edits:**
  - `plugins/mill/skills/mill-go/SKILL.md`
- **Creates:** none
- **Deletes:** none
- **Moves:** none
- **Requirements:** Insert a new `### 0.6. Per-batch baseline recapture (self-hosting only)` subsection into `plugins/mill/skills/mill-go/SKILL.md`, positioned immediately after the end of the existing `### 0.5. Baseline pre-flight (first batch of the task only)` section and immediately before the `### 1. Implement` heading (today these two headings are directly adjacent, around line 408-410). Do not modify `### 0.5.`'s own text. Insert this content verbatim (adjust only if repo prose style requires trivial wording smoothing, but preserve every identifier, path, and behavioral rule exactly):

  ```markdown
  ### 0.6. Per-batch baseline recapture (self-hosting only)

  This is a shared check-and-invoke block, referenced (not duplicated) from
  two different insertion points in "### 1. Implement" below — see the
  Agent-mode and subprocess/psmux dispatch branches there. It exists only
  to backfill a still-missing per-batch `verify_baseline_failures` baseline
  for a self-hosting task's own plan, using the task worktree's own copy of
  `millpy-implement.py` rather than the frozen `${CLAUDE_PLUGIN_ROOT}`
  cache — the cache is provably a no-op for this purpose since it never
  reflects this task's own in-progress commits.

  **Session-scoped cadence flag.** Before "## Execute — sequential loop"
  begins, initialize a local Builder variable
  `baseline_recapture_attempted = False`. This variable is never persisted
  to status.md or any file — it resets to `False` whenever a mill-go
  session (re)starts, matching the existing in-memory-only precedent of
  the Agent-mode `agent_id` handle (see "## Agent-mode dispatch" step 3).

  **Trigger check.** At the hook point, run all of:
  1. `baseline_recapture_attempted is False`.
  2. `_paths.is_self_hosting_task(git_root)` is `True`.
  3. This batch's entry in `_status.read_batches(status_path)` (matched by
     `name == <batch_name>`) has `verify_baseline_failures` still `None`.
  4. This batch's own resolved `verify:` command is non-`None` — resolved
     the same way `_enumerate_batch_verify_triples` resolves it: look up
     this batch's `file` in `_plan_dag.extract_batch_index(overview_text)`,
     read that file's frontmatter via `_plan_dag._read_batch_frontmatter`,
     and pass it through `_plan_dag.parse_verify_field(frontmatter,
     worktree_root, git_root)` — a non-`None` first element of the
     returned tuple satisfies this condition.

  If all four hold, proceed to Invoke below. If any one is false, skip
  this step entirely — no logging needed for the skip itself (the
  once-per-run budget and non-self-hosting no-op are both expected,
  high-frequency states, not anomalies).

  **Invoke.** Set `baseline_recapture_attempted = True` immediately
  (before running the command below), so the attempt is consumed even if
  the invocation itself fails or hangs. Then run, from the task worktree
  (same cwd convention as "0.5. Baseline pre-flight" above):

  ```bash
  PYTHONPATH="<git_root>/plugins/mill/scripts" "$MILL_PYTHON" "<git_root>/plugins/mill/scripts/millpy-implement.py" --stage baseline
  ```

  Substitute the literal `git_root` path resolved at Path Setup — do NOT
  use `${CLAUDE_PLUGIN_ROOT}` here; this is the one deliberate, narrow
  exception to the cache-form convention (see the plan overview's
  "cache-vs-worktree execution path for the retry" Shared Decision and
  root `CLAUDE.md`'s "Hard constraints" / "Path invariants"). Parse the
  two JSON lines this call prints, in the identical shape "0.5. Baseline
  pre-flight" already documents (first line:
  `{"stage": "baseline", "substage": "module_wide", "result":
  "computed"|"cached"|"error"|"skipped", "value": ...}`; second line:
  `{"stage": "baseline", "substage": "per_batch", "computed": [...],
  "cached": [...], "errored": {...}}`), and log a one-line ASCII-only
  summary of the `per_batch` line's counts.

  **Failure handling.** Any failure of this invocation — non-zero exit,
  timeout, malformed or missing JSON output on either line, or `--stage
  baseline` not yet existing in the worktree's mid-development code — is
  logged (ASCII-only) and treated as a no-op: proceed to this batch's
  normal strict-mode finalize exactly as if no recapture had been
  attempted. Never escalate to `stuck`/blocked over a recapture failure.
  ```

- **Commit:** `docs(mill-go): add per-batch baseline recapture block`

### Card 4: Reference the recapture block at the Agent-mode hook point

- **Context:**
  - `plugins/mill/skills/mill-go/SKILL.md`
- **Edits:**
  - `plugins/mill/skills/mill-go/SKILL.md`
- **Creates:** none
- **Deletes:** none
- **Moves:** none
- **Requirements:** In `### 1. Implement`, immediately after the existing sentence "If `dispatch == agent`: follow the Agent-mode dispatch pattern (see "## Agent-mode dispatch" above) with `<cli> = millpy-implement.py` and `<args> = <batch_name>`." (currently its own paragraph, directly before the `If dispatch == subprocess or psmux` paragraph), insert one new sentence/paragraph, locally scoped to this call site only — do NOT edit the shared "## Agent-mode dispatch" section's own step 6 definition:

  ```markdown
  For this dispatch instance only, immediately before step 6 of the
  pattern above (`--stage finalize`) runs, execute the "### 0.6. Per-batch
  baseline recapture (self-hosting only)" check.
  ```
- **Commit:** `docs(mill-go): wire recapture hook into Agent-mode implement dispatch`

### Card 5: Reference the recapture block at the subprocess/psmux hook point

- **Context:**
  - `plugins/mill/skills/mill-go/SKILL.md`
- **Edits:**
  - `plugins/mill/skills/mill-go/SKILL.md`
- **Creates:** none
- **Deletes:** none
- **Moves:** none
- **Requirements:** In `### 1. Implement`, immediately before the existing paragraph "If `dispatch == subprocess` or `psmux`: background via millpy-bg:" (the one immediately preceding the ` ```bash ... millpy-bg.py --slug implement-<batch_name> ... ``` ` block), insert one new sentence, locally scoped to this call site only:

  ```markdown
  Immediately before this backgrounded dispatch is launched, execute the
  "### 0.6. Per-batch baseline recapture (self-hosting only)" check — this
  mode has no separate finalize call to hook before, so the check must run
  ahead of the dispatch itself.
  ```
- **Commit:** `docs(mill-go): wire recapture hook into subprocess/psmux implement dispatch`

## Batch Tests

`verify: null` — this batch only edits `plugins/mill/skills/mill-go/SKILL.md`, which is markdown-driven orchestration with no automated test surface (matches the existing precedent of the "0.5. Baseline pre-flight" step itself, which likewise has no dedicated unit test beyond `_run_baseline_stage`'s own coverage — unchanged by this batch). The mechanism's end-to-end behavior is inherently visible only on a live self-hosting mill-go run, per `_mill/discussion.md`'s Testing section.
