# Batch: skill-error-retry-and-cwd-preludes

```yaml
task: 60 (A) — Branch/slug/claim fixes
batch: skill-error-retry-and-cwd-preludes
number: 5
cards: 3
verify: null
depends-on: [2, 4]
```

## Batch Scope

SKILL-level documentation updates carrying D3 (consumer-side ERROR-only retry mirroring mill-plan/mill-go's existing Step 4.5 into mill-start) and D8 (one-line cwd-validation prelude before each `millpy-bg` invocation in mill-plan, mill-start, and mill-go SKILLs).

Notable scope-narrowing discovered during planning: mill-go SKILL **already has** Step 4.5 ERROR-only-aggregate retry blocks for both per-batch code review (lines 219-234) and holistic code review (around line 328). D3 for mill-go therefore reduces to a verification, not an insertion. mill-start does NOT have an analogous block — that is the substantive addition.

`verify: null` because these are documentation-only changes. The discussion explicitly notes: "D3 (mill-start ERROR-retry path) and D8 (SKILL preludes) are SKILL-level documentation changes; no automated test is appropriate."

External interface: the wording "Before invoking `millpy-bg`, verify ..." that the operator reads when running each SKILL.

## Cards

### Card 10: mill-plan SKILL — D8 cwd-validation prelude

- **Context:**
  - `_mill/discussion.md`
- **Edits:**
  - `plugins/mill/skills/mill-plan/SKILL.md`
- **Creates:** none
- **Deletes:** none
- **Requirements:** Add a single-paragraph prelude immediately before the `millpy-bg` invocation at line 108 (the "2. Invoke the CLI as a subprocess:" step) in Phase: Plan Review. Insert between line 106 (`The commit message uses validator-fix...`) and line 108 (`2. Invoke the CLI as a subprocess:`):

  > **Before invoking `millpy-bg`**: verify `pwd` in the Bash terminal matches the task worktree. If `millpy-bg` rejects cwd with the parent-worktree error (`mill-bg: cwd appears to be a non-task worktree`), halt and instruct the operator to switch to the task-worktree terminal.

  Use Markdown blockquote prefix `> `. Single sentence, ASCII-only. Apply the same prelude (verbatim) before the Step 4.5 ERROR-only retry `millpy-bg` invocation at line 130-140 (the `plan-review-retry-r<N>` block) and before the Step 1.5 `plan-validator-fix` `millpy-bg` invocation. **Note for Step 1.5**: today the SKILL describes the `plan-validator-fix` re-run as prose ("mill-plan re-runs the review CLI via millpy-bg (slug `plan-validator-fix`...)") without an explicit fenced bash block. The implementer must check whether a bash block exists at that site. If a bash block is present, place the prelude blockquote immediately above it. If only prose exists (the present case), place the prelude blockquote immediately before the prose sentence that triggers the re-run, so the operator reads the cwd guidance before reaching the re-run instruction. Search the whole file for every `PYTHONPATH=.*millpy-bg.py` AND for every prose mention of `millpy-bg` that triggers an invocation; ensure each is preceded by the prelude blockquote. There must be no `millpy-bg` invocation site (fenced or prose-only) in mill-plan SKILL that lacks the prelude.
- **Commit:** `docs(mill-plan): add cwd-validation prelude before millpy-bg`

### Card 11: mill-start SKILL — add ERROR-only retry step + D8 prelude

- **Context:**
  - `plugins/mill/skills/mill-go/SKILL.md`
  - `_mill/discussion.md`
- **Edits:**
  - `plugins/mill/skills/mill-start/SKILL.md`
- **Creates:** none
- **Deletes:** none
- **Requirements:** Two distinct edits.

  **Edit A — D8 prelude.** Immediately before the `millpy-bg` invocation at line 108 of Phase: Discussion Review (step 2), insert the same blockquote-prefixed sentence as Card 10:

  > **Before invoking `millpy-bg`**: verify `pwd` in the Bash terminal matches the task worktree. If `millpy-bg` rejects cwd with the parent-worktree error (`mill-bg: cwd appears to be a non-task worktree`), halt and instruct the operator to switch to the task-worktree terminal.

  Place it between line 107 (the "Each round:" enumeration line for step 1 / before step 2) and the step-2 fenced bash block. ASCII-only.

  **Edit B — Step 3.5 ERROR-only retry**. After step 3 ("BEFORE reading the review file, load the `mill-receiving-review` skill...", line ~118 area) and before step 4a (line 120 `On APPROVE...`), insert a new sub-step modeled on mill-go's Step 4.5 ERROR-only-aggregate retry (mill-go SKILL.md lines 219-234). The mill-start variant:

  ```markdown
  3.5. **Step 3.5: ERROR-only-aggregate retry (no round consumed)**

     When the JSON envelope from step 2 has top-level `verdict: "ERROR"` (or, equivalently, every entry in `reviews[]` has `verdict: "ERROR"`), skip steps 4a / 4b / 5 entirely and immediately re-run:

     ```bash
     PYTHONPATH="${CLAUDE_PLUGIN_ROOT}/scripts" "${CLAUDE_PLUGIN_ROOT}/.venv/Scripts/python.exe" "${CLAUDE_PLUGIN_ROOT}/scripts/millpy-bg.py" \
         --slug review-discussion-retry-r<N> -- \
         "${CLAUDE_PLUGIN_ROOT}/.venv/Scripts/python.exe" "${CLAUDE_PLUGIN_ROOT}/scripts/millpy-review-discussion.py"
     ```

     Returns immediately with `pid=<N> log=<abs-path>`. Poll `cat <log-path>` until `[mill-bg] EXIT` appears, then extract the JSON summary line.

     The round counter `N` is **not** consumed -- the round produced no reviewable output. On the **second** consecutive run that still has top-level `verdict: "ERROR"`, halt with `BLOCKED: discussion review ERROR-only round {N}` and surface each entry's `error` string from `reviews[]` to the user. Under `--auto` mode, halt by calling `_status.set_blocked(status_path, f"auto: discussion review ERROR-only round {N}", timestamp=_timestamp.now_utc_iso())`, then `git -C <worktree> add <status_path> && git commit -m "mill-start: blocked (auto: discussion review ERROR) for <slug>" && git push`. Do NOT auto-retry beyond the second pass. The two-pass cap mirrors mill-go's Step 4.5.
  ```

  The triple-backtick fences inside the inserted block must use the same nesting that mill-go SKILL uses for its own Step 4.5 — verify by re-reading mill-go SKILL lines 219-234 before inserting. Use the same blockquote-prelude D8 line at the head of the new `millpy-bg` invocation inside Step 3.5 (the prelude must precede every `millpy-bg` invocation in mill-start SKILL, including the new one inside Step 3.5).

  Inserted text uses ASCII-only stdout/stderr strings; em-dashes inside docstrings/comments are preserved if mirroring mill-go's wording verbatim — note that mill-go SKILL itself uses em-dashes in prose (this is Markdown content, not stderr/stdout from Python, so the ASCII rule does not apply). The inserted Markdown matches mill-go's existing prose style.
- **Commit:** `docs(mill-start): add ERROR-only retry step + cwd-validation prelude`

### Card 12: mill-go SKILL — D8 cwd-validation prelude (verify D3 already present)

- **Context:**
  - `_mill/discussion.md`
- **Edits:**
  - `plugins/mill/skills/mill-go/SKILL.md`
- **Creates:** none
- **Deletes:** none
- **Requirements:** Two parts.

  **Part A — Verify existing D3 block.** Before any edit, read `mill-go/SKILL.md` lines 219-234 and confirm the Step 4.5 ERROR-only-aggregate retry block exists for per-batch code review, AND read around line 320-340 to confirm the holistic-code-review variant also exists. Both should be present today. If either is missing, follow the same template as Card 11's Step 3.5 insertion (using the appropriate `review-code` invocation, `<batch_name>` substitution, and the `BLOCKED: ... code review ERROR-only round {N}` halt message). If both are present, no change needed for D3 in mill-go.

  **Part B — D8 prelude.** Add the same blockquote-prefixed sentence as Card 10 immediately before every `millpy-bg` invocation in mill-go SKILL. Concretely, search the file for every occurrence of `PYTHONPATH=...millpy-bg.py` and confirm a `>` blockquote with the prelude text immediately precedes each fenced bash block. Sites known to need it (verify by grep): Section 1 Implement (line ~141), Section 3 Code Review step 2 (line ~192), Section 3 Step 4.5 retry (line ~223), Section 3 REQUEST_CHANGES fix (line ~210), Resume sections (multiple), Holistic code review (line ~317), Holistic Step 4.5 retry. Use one identical sentence verbatim across every site:

  > **Before invoking `millpy-bg`**: verify `pwd` in the Bash terminal matches the task worktree. If `millpy-bg` rejects cwd with the parent-worktree error (`mill-bg: cwd appears to be a non-task worktree`), halt and instruct the operator to switch to the task-worktree terminal.

  Do not paraphrase or shorten — uniform wording across SKILLs is the point. ASCII-only.
- **Commit:** `docs(mill-go): add cwd-validation prelude before millpy-bg`

## Batch Tests

`verify: null`. SKILL-level documentation. End-to-end smoke is exercised the next time mill-go runs (Card 12) or mill-start runs in auto-mode against a transient-LLM-failure (Card 11 Step 3.5). Implementer should NOT add documentation-validation tests.
