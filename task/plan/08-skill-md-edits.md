# Batch: skill-md-edits

```yaml
task: 44 (A) — Bug-fix batch 4
batch: skill-md-edits
number: 8
cards: 7
verify: null
depends-on: [5]
```

## Batch Scope

Seven independent doc edits across three SKILL.md files. Bundled because each is small and they form one coherent operator-doc cleanup. All but Card 20 stand alone; Card 20 (step 4.5) documents the runtime behavior shipped in Batch 5, hence the `depends-on: [5]` edge. No tests; `verify: null`. Sonnet implements each edit in turn (or batches the file-local ones), commits per card.

## Cards

### Card 16: mill-go SKILL.md — fix bare `status.md` → `task/status.md` on lines 106 and 170 (#214)

- **Context:** none
- **Edits:**
  - `plugins/mill/skills/mill-go/SKILL.md`
- **Creates:** none
- **Deletes:** none
- **Requirements:**
  1. On line ~106 (inside the Code Review loop's "If `roles.code-review.batch.reviewer` is null..." paragraph), find the substring `git -C <worktree> add status.md && git -C <worktree> commit -m "mill-go: approve batch {batch_name} (per-batch review disabled)"`. Replace `add status.md` with `add task/status.md`.
  2. On line ~170 (inside the Holistic code review section's step 2, "Commit: `git -C <worktree> add status.md && git -C <worktree> commit -m \"mill-go: holistic reviewing round {H}\"`."), replace `add status.md` with `add task/status.md`.
  3. After the edit, grep the file: `grep -n "add status.md" plugins/mill/skills/mill-go/SKILL.md` must return zero matches (every git-add line referencing status.md is now `add task/status.md`).
- **Commit:** `fix(mill-go): use task/status.md in git-add commands (#214)`

### Card 17: mill-go SKILL.md — add TodoWrite-batch-number Principle

- **Context:** none
- **Edits:**
  - `plugins/mill/skills/mill-go/SKILL.md`
- **Creates:** none
- **Deletes:** none
- **Requirements:** Add a new bullet to the `## Principles` section, immediately after the existing `- **Helper signatures are documented inline.**` bullet (the last one). Bullet text:
  ```
  - **TodoWrite items name batches by number.** Emit todo items as `Implement batch N (<batch-slug>)` — e.g. `Implement batch 1 (foundations)` — so progress in the todo list correlates 1:1 with plan files (`NN-<batch-slug>.md`). Bare names without a number force the operator to cross-reference the Batch Index every time.
  ```
  Match the surrounding bullet style (`- **Title.** Body sentence.`). Do not edit any other section.
- **Commit:** `docs(mill-go): require batch-number prefix in TodoWrite items`

### Card 18: mill-go SKILL.md — wrap `millpy-implement.py` invocations in `millpy-bg.py`

- **Context:**
  - `plugins/mill/scripts/millpy-bg.py`
  - `plugins/mill/scripts/millpy-implement.py`
  - `task/discussion.md`
- **Edits:**
  - `plugins/mill/skills/mill-go/SKILL.md`
- **Creates:** none
- **Deletes:** none
- **Requirements:**
  1. In the Execute loop's step `### 1. Implement`, replace the existing direct invocation pattern (`uv run --project "$CLAUDE_PLUGIN_ROOT" "$CLAUDE_PLUGIN_ROOT/scripts/millpy-implement.py" <batch_name>`) with the millpy-bg wrapping pattern. The new text should:
     - Open with: `Background via millpy-bg:`
     - Provide the bash block:
       ```bash
       uv run --project "$CLAUDE_PLUGIN_ROOT" "$CLAUDE_PLUGIN_ROOT/scripts/millpy-bg.py" \
           --slug implement-<batch_name> -- \
           uv run --project "$CLAUDE_PLUGIN_ROOT" "$CLAUDE_PLUGIN_ROOT/scripts/millpy-implement.py" <batch_name>
       ```
     - Describe the polling: `Returns immediately with pid=<N> log=<abs-path>. Do not use run_in_background: true on the Bash tool — that routes output to CC's temp dir. Poll the log file with cat <log-path> until [mill-bg] EXIT appears. Once it does, read the log and extract the JSON summary line (the last non-empty, non-sentinel line in the log).`
     - Preserve the existing wording about what `millpy-implement.py` atomically does (resolves paths, renders brief, generates session_id, sets state → running, records start_sha and implementer_session, commits/pushes, spawns implementer). State that "the Builder reads the JSON summary from the log file." Drop the now-stale phrase "The Builder reads stdout JSON directly".
     - Keep the existing paragraph about exit-code handling (`Note: the CLI exits 0 when the implementer produced JSON…`) but reword `stdout` references to `the JSON line in the log file`.
  2. In the Execute loop's step `### 3. Code Review loop`, sub-step 4 (`Branch on verdict:`), the `REQUEST_CHANGES` branch invokes `millpy-implement.py <batch_name> --resume --round <N> --review-file <review-file-abs-path>`. Replace with the same millpy-bg wrapping pattern:
     ```bash
     uv run --project "$CLAUDE_PLUGIN_ROOT" "$CLAUDE_PLUGIN_ROOT/scripts/millpy-bg.py" \
         --slug fix-<batch_name>-r<N> -- \
         uv run --project "$CLAUDE_PLUGIN_ROOT" "$CLAUDE_PLUGIN_ROOT/scripts/millpy-implement.py" <batch_name> --resume --round <N> --review-file <review-file-abs-path>
     ```
     Add the same polling / parse-JSON-from-log instructions, matching the new Implement step's wording.
  3. Do NOT change `millpy-implement.py` itself, `millpy-bg.py` itself, or any other SKILL.md file in this card.
  4. Do NOT change the Stuck-escalation logic, the cleanliness-gate logic, or the Blocked path. The retry policy on `stuck_type: transient` (one-retry, fresh session) still applies — the implementer is still re-invoked, just via millpy-bg now. The stuck-escalation prose can stay as-is; only the invocation pattern at the two call sites changes.
  5. Verify: after editing, `grep -n "millpy-implement.py" plugins/mill/skills/mill-go/SKILL.md` should show every invocation goes through `millpy-bg.py --slug ...`. Zero raw `millpy-implement.py <batch_name>` lines outside of the `-- uv run ...` continuation.
- **Commit:** `docs(mill-go): wrap millpy-implement.py invocations in millpy-bg.py`

### Card 19: mill-go SKILL.md — add `## Resume` section

- **Context:**
  - `plugins/mill/scripts/millpy-implement.py`
  - `plugins/mill/scripts/_status.py`
  - `plugins/mill/skills/mill-receiving-review/SKILL.md`
  - `task/discussion.md`
- **Edits:**
  - `plugins/mill/skills/mill-go/SKILL.md`
- **Creates:** none
- **Deletes:** none
- **Requirements:** Insert a new `## Resume` section immediately AFTER the `## Execute — sequential loop` section (and all its sub-sections including the `### Blocked` block) and BEFORE the `## Holistic code review` section. Section content (verbatim, with markdown headings):
  ```
  ## Resume

  When mill-go's Entry-step 5 phase gate routes here (phase is `implementing`, `reviewing`, or `fixing`), the previous run was interrupted mid-batch. The CLIs that mutate task state (`millpy-implement.py`, `millpy-review-code.py`) are atomic — they record state-mutation commits before the heavy work starts and after each transition — so the resume playbook is simple: read the current batch entry and re-invoke the CLI for the current state.

  1. Read `task/status.md`; locate the current batch entry (the single entry whose `state` is non-terminal: `running`, `reviewing`, or `fixing`).
  2. Branch on the batch's `state`:
     - **`running`** — the implementer was mid-implementation. Re-invoke (via `millpy-bg`):
       ```bash
       uv run --project "$CLAUDE_PLUGIN_ROOT" "$CLAUDE_PLUGIN_ROOT/scripts/millpy-bg.py" \
           --slug implement-<batch_name>-resume -- \
           uv run --project "$CLAUDE_PLUGIN_ROOT" "$CLAUDE_PLUGIN_ROOT/scripts/millpy-implement.py" <batch_name> --resume
       ```
       The CLI re-attaches the warm session via the stored `implementer_session`. If `LLMSessionError` propagates (visible as `stuck_type: transient` in the JSON), apply the standard one-retry-fresh policy from Stuck escalation. After parsing the report, continue at Execute step 2b (cleanliness gate).
     - **`reviewing`** — the implementer report was already consumed; the reviewer was running. Re-invoke the per-batch code-review CLI from the start of round `review_round` (read this field from the batch entry):
       ```bash
       uv run --project "$CLAUDE_PLUGIN_ROOT" "$CLAUDE_PLUGIN_ROOT/scripts/millpy-bg.py" \
           --slug review-code-<batch_name>-r<review_round>-resume -- \
           uv run --project "$CLAUDE_PLUGIN_ROOT" "$CLAUDE_PLUGIN_ROOT/scripts/millpy-review-code.py" --batch <batch_name>
       ```
       The CLI's crash-recovery scan handles a written-but-uncommitted review file. After parsing the JSON verdict, continue at Execute step 3 sub-step 3 (load `mill-receiving-review`) and step 4 (branch on verdict).
     - **`fixing`** — the reviewer returned `REQUEST_CHANGES`; the fix-implementer was running. Re-invoke:
       ```bash
       uv run --project "$CLAUDE_PLUGIN_ROOT" "$CLAUDE_PLUGIN_ROOT/scripts/millpy-bg.py" \
           --slug fix-<batch_name>-r<review_round>-resume -- \
           uv run --project "$CLAUDE_PLUGIN_ROOT" "$CLAUDE_PLUGIN_ROOT/scripts/millpy-implement.py" <batch_name> --resume --round <review_round> --review-file <review-file-abs-path>
       ```
       The `<review-file-abs-path>` is the most recent `task/reviews/*-code-review-<batch_name>-r<review_round>.md` file. After parsing the report, continue at Execute step 3 sub-step 5 (max-rounds check) or back to step 3 round N+1 if the fix produced an APPROVE-eligible state on next review.
  3. **No state mutation before resume.** Do NOT pre-emptively flip `state` or call `_status.append_phase` before re-invoking the CLI. The CLI handles state transitions atomically; double-writes corrupt the timeline.
  4. **`mill-receiving-review` is still mandatory.** When resume lands you at any point that reads a review file, load the skill first (per the existing rule at Execute step 3 sub-step 3 and Holistic step 5).
  ```
  Match the existing section formatting (markdown headings, indented bullets, fenced code blocks for bash). Use `${CLAUDE_PLUGIN_ROOT}` consistently. Do not edit the Entry-step 5 table — its existing "resume (see *Resume*)" pointer now resolves to this section.
- **Commit:** `docs(mill-go): document Resume section for non-terminal batch states (#229)`

### Card 20: mill-go SKILL.md — add step 4.5 ERROR-only-aggregate retry to Code Review and Holistic review

- **Context:**
  - `plugins/mill/skills/mill-plan/SKILL.md`
  - `plugins/mill/scripts/_review_code.py`
  - `task/discussion.md`
- **Edits:**
  - `plugins/mill/skills/mill-go/SKILL.md`
- **Creates:** none
- **Deletes:** none
- **Requirements:**
  1. In `## Execute — sequential loop` → `### 3. Code Review loop`, between the existing sub-step 4 (`Branch on verdict:`) and sub-step 5 (`Max-rounds exhaustion.`), insert a new sub-step `4.5`:
     ```
     4.5. **Step 4.5: ERROR-only-aggregate retry (no round consumed)**

        When the JSON envelope from sub-step 2 has top-level `verdict: "ERROR"` (or, equivalently, every entry in `reviews[]` has `verdict: "ERROR"`), skip sub-step 4 entirely and immediately re-run:

        ```bash
        uv run --project "$CLAUDE_PLUGIN_ROOT" "$CLAUDE_PLUGIN_ROOT/scripts/millpy-bg.py" \
            --slug review-code-<batch_name>-retry-r<N> -- \
            uv run --project "$CLAUDE_PLUGIN_ROOT" "$CLAUDE_PLUGIN_ROOT/scripts/millpy-review-code.py" \
                --batch <batch_name> [--extra-file <p> ...]
        ```

        Returns immediately with `pid=<N> log=<abs-path>`. Poll `cat <log-path>` until `[mill-bg] EXIT` appears, then extract the JSON summary line from the log.

        The round counter `N` is **not** consumed — the round produced no reviewable output. On the **second** consecutive run that still has top-level `verdict: "ERROR"`, halt with `BLOCKED: code review ERROR-only round {N}` and surface each entry's `error` string from `reviews[]` to the user. Do NOT auto-retry beyond the second pass. The two-pass cap mirrors mill-plan's existing step 4.5. *(Closes #228 — rate-limit errors no longer mis-dispatch the implementer with a null review file.)*
     ```
     Match the existing prose style of sub-step 4 and sub-step 5. Use `${CLAUDE_PLUGIN_ROOT}` syntax. The fenced bash block uses backslash-continuation matching surrounding examples.
  2. In `## Holistic code review`, insert an analogous step between step 3 (`Background via millpy-bg`) and step 4 (`On APPROVE`). Number it `3.5` to slot between 3 and 4 in the holistic numbering. Content mirrors step 4.5 above but adjusted for holistic:
     - Slug: `review-code-holistic-retry-r<H>`
     - Inner CLI: `"$CLAUDE_PLUGIN_ROOT/scripts/millpy-review-code.py"` (no `--batch` flag for holistic — match the existing step-3 invocation).
     - Halt message: `BLOCKED: holistic code review ERROR-only round {H}`
     - Round counter `H` is not consumed; two-pass cap.
  3. Do NOT change steps 4, 5, 6, 7 of the Holistic review or steps 1, 2, 3, 4, 5 of Code Review. Pure insert.
  4. Cross-reference: ensure the prose mentions that top-level `verdict: "ERROR"` was introduced by `_review_code.py` (and `_review_plan.py`) in Batch 5 — but DO NOT phrase the SKILL.md as a future-tense reference; once Batch 5 lands and this batch follows, both are in place. Use present tense: `When the JSON envelope... has top-level verdict: "ERROR"`.
- **Commit:** `docs(mill-go): add step 4.5 ERROR-only-aggregate retry (#228)`

### Card 21: mill-start SKILL.md — inline `_config.load_config` signature in Entry step 3

- **Context:**
  - `plugins/mill/scripts/_config.py`
- **Edits:**
  - `plugins/mill/skills/mill-start/SKILL.md`
- **Creates:** none
- **Deletes:** none
- **Requirements:** In the `## Entry` section, locate step 3: `3. Load config — deep-merge \`<WIKI_PATH>/config.yaml\` (shared) with \`.millhouse/config.local.yaml\` (gitignored overlay). Read \`review.discussion.rounds\` as \`max_review_rounds\`.` Append (as a new line, indented two spaces to align with the step's body) the inline signature: `   \`signature: _config.load_config(wiki_path: Path, worktree_root: Path) -> dict\``. Match the style of the existing `signature:` lines in steps 1 and 2 of the same `## Entry` block (single backtick wrap, italic-like signature notation). Do not edit any other section.
- **Commit:** `docs(mill-start): name _config.load_config helper inline (#221)`

### Card 22: mill-plan SKILL.md — inline `_config.load_config` signature in Entry step 3

- **Context:**
  - `plugins/mill/scripts/_config.py`
- **Edits:**
  - `plugins/mill/skills/mill-plan/SKILL.md`
- **Creates:** none
- **Deletes:** none
- **Requirements:** In the `## Entry` section, locate step 3: `3. Load config — deep-merge \`<WIKI_PATH>/config.yaml\` with \`.millhouse/config.local.yaml\`. Read \`review.plan.rounds\` as \`max_review_rounds\`.` Append (as a new line, indented two spaces to align with the step's body) the inline signature: `   \`signature: _config.load_config(wiki_path: Path, worktree_root: Path) -> dict\``. Match the style of the existing `signature:` line in step 1 (`_wiki.sync_pull`). Do not edit any other section.
- **Commit:** `docs(mill-plan): name _config.load_config helper inline (#221)`

## Batch Tests

`verify: null`. All seven cards are doc-only edits to SKILL.md files. Sanity check after the batch: `git diff plugins/mill/skills/mill-go/SKILL.md plugins/mill/skills/mill-start/SKILL.md plugins/mill/skills/mill-plan/SKILL.md` shows the expected sets of changes. No source code or tests are touched.
