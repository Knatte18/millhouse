# Batch: mill-go-wire-prior-blocking-digest

```yaml
task: 'mill-go: quality-gate coverage gaps (NIT-fix regressions, missing lint gate)'
batch: mill-go-wire-prior-blocking-digest
number: 3
cards: 3
verify: null
depends-on: [1, 2]
```

## Batch Scope

This batch wires the prior-blocking digest into all three `--nits-only` NIT-fix dispatch sites in `mill-go/SKILL.md`: the per-batch in-flow dispatch (`## Execute` step 4's `APPROVE` branch), the holistic in-flow dispatch (`## Holistic code review` step 4), and the Handoff "Nit-enforcement gate" self-resolve dispatch. It depends on batch 01 (`_prior_blocking.build_digest` must exist to be called) and batch 02 (`millpy-fix.py --prior-blocking` and the `<PRIOR_BLOCKING>` template token must exist for the flag to have any effect). Each site gets: (a) a new instruction block that builds the digest via `_prior_blocking.build_digest` and writes it to a `prior-blocking-*.txt` file under `_mill/briefs/`, and (b) a `--prior-blocking <digest-path>` addition to that site's existing `--nits-only` dispatch args, in both the Agent-mode arg string and the subprocess/psmux bash block. This is prose-only editing of one file (`mill-go/SKILL.md`); no `## Batch Scope`-local decisions beyond what the overview's Shared Decisions already state.

## Cards

### Card 6: wire the per-batch in-flow dispatch (`## Execute` step 4 `APPROVE` branch)

- **Context:**
  - `plugins/mill/scripts/_prior_blocking.py`
- **Edits:**
  - `plugins/mill/skills/mill-go/SKILL.md`
- **Creates:** none
- **Deletes:** none
- **Moves:** none
- **Requirements:**
  - Locate the per-batch NIT-fix dispatch under `## Execute` step "4."'s `APPROVE` branch — the block beginning "`APPROVE` — If `nit_count > 0` in the envelope, dispatch one cold-start NIT-only fix pass:" and containing the Agent-mode dispatch sentence "`<cli> = millpy-fix.py` and `<args> = --scope batch --batch-name <batch_name> --review-file <review-file-abs-path> --round <N> --nits-only`" plus its paired subprocess/psmux `millpy-bg.py` invocation of `millpy-fix.py --scope batch --batch-name <batch_name> --review-file <review-file-abs-path> --round <N> --nits-only`.
  - Immediately before that dispatch (i.e. after the "Dispatch the NIT-fix pass whenever `nit_count > 0`..." paragraph, before the Agent-mode sentence), insert a new instruction block titled to parallel the existing "**Prior-notes digest (round N > 1 only).**" step already present earlier in the same `### 3. Code Review loop` section (its step "1.5."). Title the new block **"Prior-blocking digest."** (no round-conditional in the title, per `digest-scans-current-disk-state-no-round-boundary`), containing this invocation:
    ```bash
    PYTHONPATH="${CLAUDE_PLUGIN_ROOT}/scripts" "$MILL_PYTHON" -c "
    import _prior_blocking, pathlib
    digest = _prior_blocking.build_digest(pathlib.Path('<reviews_dir-abs-path>'), scope='batch', batch_name='<batch_name>')
    pathlib.Path('<briefs_dir>/prior-blocking-<batch_name>-r<N>.txt').write_text(digest, encoding='utf-8')
    "
    ```
    followed by one sentence: unlike the existing prior-notes digest above, this is called at every round with no `N > 1` guard — `build_digest` returns `""` when there is no prior BLOCKING history yet, and `millpy-fix.py` renders an empty digest file as `"(none)"`, so the round-1 case needs no special-casing here.
  - Append `--prior-blocking <briefs_dir>/prior-blocking-<batch_name>-r<N>.txt` to the Agent-mode dispatch's `<args>` string, immediately after `--nits-only`.
  - Append `--prior-blocking <briefs_dir>/prior-blocking-<batch_name>-r<N>.txt` to the subprocess/psmux `millpy-fix.py` invocation line, immediately after `--nits-only`.
- **Commit:** `feat(mill-go): wire prior-blocking digest into per-batch NIT-fix dispatch`

### Card 7: wire the holistic in-flow dispatch (`## Holistic code review` step 4)

- **Context:**
  - `plugins/mill/scripts/_prior_blocking.py`
- **Edits:**
  - `plugins/mill/skills/mill-go/SKILL.md`
- **Creates:** none
- **Deletes:** none
- **Moves:** none
- **Requirements:**
  - Locate the holistic NIT-fix dispatch under `## Holistic code review` step "4." — the block beginning "On `APPROVE`: If `nit_count > 0` in the envelope, dispatch one cold-start NIT-only fix pass:" and containing the Agent-mode dispatch sentence "`<cli> = millpy-fix.py` and `<args> = --scope holistic --review-file <review-file-abs-path> --round {H} --nits-only`" plus its paired subprocess/psmux `millpy-bg.py` invocation of `millpy-fix.py --scope holistic --review-file <review-file-abs-path> --round {H} --nits-only`.
  - Immediately before that dispatch, insert the same style of **"Prior-blocking digest."** block used in Card 6 (parallel to this section's own existing "**Prior-notes digest (round H > 1 only).**" step "2.5."), containing:
    ```bash
    PYTHONPATH="${CLAUDE_PLUGIN_ROOT}/scripts" "$MILL_PYTHON" -c "
    import _prior_blocking, pathlib
    digest = _prior_blocking.build_digest(pathlib.Path('<reviews_dir-abs-path>'), scope='holistic')
    pathlib.Path('<briefs_dir>/prior-blocking-holistic-r{H}.txt').write_text(digest, encoding='utf-8')
    "
    ```
    followed by the identical no-round-guard-needed sentence used in Card 6.
  - Append `--prior-blocking <briefs_dir>/prior-blocking-holistic-r{H}.txt` to the Agent-mode dispatch's `<args>` string, immediately after `--nits-only`.
  - Append `--prior-blocking <briefs_dir>/prior-blocking-holistic-r{H}.txt` to the subprocess/psmux `millpy-fix.py` invocation line, immediately after `--nits-only`.
- **Commit:** `feat(mill-go): wire prior-blocking digest into holistic NIT-fix dispatch`

### Card 8: wire the Handoff "Nit-enforcement gate" self-resolve dispatch

- **Context:**
  - `plugins/mill/scripts/_prior_blocking.py`
- **Edits:**
  - `plugins/mill/skills/mill-go/SKILL.md`
- **Creates:** none
- **Deletes:** none
- **Moves:** none
- **Requirements:**
  - Locate the **"Nit-enforcement gate."** paragraph under `## Handoff`, specifically the sentence beginning "Dispatch the NIT-fix pass for that review file using the identical CLI, args, and dispatch-mode handling already documented for the in-flow NIT-fix pass: see `## Execute` step 4's `APPROVE` branch for the per-batch shape (`<cli> = millpy-fix.py`, `<args> = --scope batch --batch-name <scope> --review-file <review-file-abs-path> --round <N> --nits-only`) or `## Holistic code review` step 4 for the holistic shape (`--scope holistic --review-file <review-file-abs-path> --round <H> --nits-only`); `<N>`/`<H>` are read from the review filename."
  - Immediately before that sentence, insert the same **"Prior-blocking digest."** block style used in Cards 6/7, adapted to this site's already-in-hand loop variables: `<scope>` (either a batch name or the literal string `"holistic"`) and the round number parsed from the matched review filename. Use `scope='batch', batch_name='<scope>'` when `<scope>` is a per-batch scope name, or `scope='holistic'` (no `batch_name`) when `<scope> == "holistic"`, writing to `<briefs_dir>/prior-blocking-<scope>-r<N>.txt` or `<briefs_dir>/prior-blocking-holistic-r<H>.txt` respectively (same naming convention as Cards 6/7).
  - Amend the "using the identical CLI, args, and dispatch-mode handling already documented for the in-flow NIT-fix pass" sentence to add: that identical shape now includes `--prior-blocking <digest-path>` too (per Cards 6/7's edits to those two sites), so this site's dispatch carries it automatically with no separate argument string of its own — this site remains a pure textual pointer to Sites A/B's exact argument shapes, unchanged in structure.
- **Commit:** `feat(mill-go): wire prior-blocking digest into Handoff nit-enforcement gate dispatch`

## Batch Tests

`verify: null` — this batch edits only `mill-go/SKILL.md`, a prose orchestration document with no runnable test surface of its own; the underlying mechanism it wires together (`_prior_blocking.build_digest`, the `millpy-fix.py --prior-blocking` flag and render-token threading) is already fully covered by batch 01's and batch 02's unit tests. The SKILL.md procedural sequencing is verified by careful self-review during plan-writing/review instead, matching this task's discussion's Testing section.
