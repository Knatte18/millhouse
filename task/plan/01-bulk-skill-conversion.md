# Batch: bulk-skill-conversion

```yaml
task: Replace uv-run-project with direct venv Python in SKILL.md invocations
batch: bulk-skill-conversion
number: 1
cards: 1
verify: null
depends-on: []
```

## Batch Scope

This batch applies the cache-form substitution rules from `## Shared Decisions` to every mill SKILL.md file that uses `uv run --project "${CLAUDE_PLUGIN_ROOT}"` or `uv run --project "$CLAUDE_PLUGIN_ROOT"`, except `mill-go/SKILL.md` (handled in Batch 2 because it uses `$PLUGIN_ROOT`) and `mill-setup/SKILL.md` (handled in Batch 3 because it also requires prose updates). Source-tree forms (`uv run --project plugins/mill ...`) are left unchanged in every file. mill-add has both source-tree and cache forms; only the cache forms change.

This is a mechanical text substitution: no logic changes, no script changes, no test changes. Each file is independently transformed; there are no cross-file dependencies inside the batch.

## Cards

### Card 1: Convert cache-form mill-script invocations across 20 SKILL.md files

- **Context:**
  - `task/discussion.md`
- **Edits:**
  - `plugins/mill/skills/mill-abandon/SKILL.md`
  - `plugins/mill/skills/mill-add/SKILL.md`
  - `plugins/mill/skills/mill-autofix/SKILL.md`
  - `plugins/mill/skills/mill-claim/SKILL.md`
  - `plugins/mill/skills/mill-cleanup/SKILL.md`
  - `plugins/mill/skills/mill-color/SKILL.md`
  - `plugins/mill/skills/mill-ghissues-to-tasks/SKILL.md`
  - `plugins/mill/skills/mill-groom/SKILL.md`
  - `plugins/mill/skills/mill-inspect/SKILL.md`
  - `plugins/mill/skills/mill-merge-in/SKILL.md`
  - `plugins/mill/skills/mill-plan/SKILL.md`
  - `plugins/mill/skills/mill-resume/SKILL.md`
  - `plugins/mill/skills/mill-skills-from-scripts/SKILL.md`
  - `plugins/mill/skills/mill-skills-index/SKILL.md`
  - `plugins/mill/skills/mill-spawn/SKILL.md`
  - `plugins/mill/skills/mill-start/SKILL.md`
  - `plugins/mill/skills/mill-status/SKILL.md`
  - `plugins/mill/skills/mill-terminal/SKILL.md`
  - `plugins/mill/skills/mill-vscode/SKILL.md`
  - `plugins/mill/skills/mill-wiki-push/SKILL.md`
- **Creates:** none
- **Deletes:** none
- **Requirements:**

  Apply the following five substitution rules to every file in `Edits:`. Process each file independently; do not aggregate edits. After substitution, the file MUST satisfy: `grep -E 'uv run --project "\$\{?CLAUDE_PLUGIN_ROOT\}?"' <file>` returns zero matches. Source-tree forms (`uv run --project plugins/mill ...`) MUST remain unchanged — confirm by counting `uv run --project plugins/mill` occurrences before and after; the count must be identical for each file.

  **Two shapes per cache-form invocation.** Rules 1–4 below describe Shape A — direct (top-level) shell lines. Rule 5 describes Shape B — calls that appear AFTER `--` inside a `millpy-bg.py` launcher line, which MUST NOT carry the PYTHONPATH= prefix (see the `nested-call-exception` Shared Decision in `00-overview.md`). Identify Shape B by the preceding line: if the previous non-empty line in the same fenced ```bash block ends in `-- \`, the current line is Shape B; otherwise it is Shape A. Specifically the multi-line pattern

  ```
  uv run --project "${CLAUDE_PLUGIN_ROOT}" "${CLAUDE_PLUGIN_ROOT}/scripts/millpy-bg.py" \
      --slug <slug> -- \
      uv run --project "${CLAUDE_PLUGIN_ROOT}" "${CLAUDE_PLUGIN_ROOT}/scripts/<inner-script>.py" [args]
  ```

  contains one Shape A line (the launcher calling `millpy-bg.py`) and one Shape B line (the inner command after `-- \`). They convert differently — Rules 1–4 vs Rule 5.

  Known files containing Shape B nested calls (from current grep): `mill-plan/SKILL.md` (Phase: Plan Review step 2 and step 4.5 — two nested invocations), `mill-start/SKILL.md` (Phase: Discussion Review step 2 — one nested invocation). The implementer MUST also inspect every other file in `Edits:` for nested bg invocations; new ones may exist that this list missed.

  **Rule 1 — Script invocation, braced form.** Replace the pattern
  ```
  uv run --project "${CLAUDE_PLUGIN_ROOT}" "${CLAUDE_PLUGIN_ROOT}/scripts/<script>.py"
  ```
  with
  ```
  PYTHONPATH="${CLAUDE_PLUGIN_ROOT}/scripts" "${CLAUDE_PLUGIN_ROOT}/.venv/Scripts/python.exe" "${CLAUDE_PLUGIN_ROOT}/scripts/<script>.py"
  ```
  Preserve every trailing argument and any line-continuation backticks/backslashes on the line.

  **Rule 2 — Script invocation, unbraced form.** Replace the pattern
  ```
  uv run --project "$CLAUDE_PLUGIN_ROOT" "$CLAUDE_PLUGIN_ROOT/scripts/<script>.py"
  ```
  with
  ```
  PYTHONPATH="${CLAUDE_PLUGIN_ROOT}/scripts" "${CLAUDE_PLUGIN_ROOT}/.venv/Scripts/python.exe" "${CLAUDE_PLUGIN_ROOT}/scripts/<script>.py"
  ```
  (normalise `"$CLAUDE_PLUGIN_ROOT"` → `"${CLAUDE_PLUGIN_ROOT}"` as part of the same edit). Preserve every trailing argument and any line-continuation suffix.

  **Rule 3 — Inline `python -c "..."` with existing PYTHONPATH prefix.** Replace
  ```
  PYTHONPATH="${CLAUDE_PLUGIN_ROOT}/scripts" uv run --project "${CLAUDE_PLUGIN_ROOT}" python -c "..."
  ```
  with
  ```
  PYTHONPATH="${CLAUDE_PLUGIN_ROOT}/scripts" "${CLAUDE_PLUGIN_ROOT}/.venv/Scripts/python.exe" -c "..."
  ```
  The unbraced equivalent (`PYTHONPATH="$CLAUDE_PLUGIN_ROOT/scripts" uv run --project "$CLAUDE_PLUGIN_ROOT" python -c "..."`) is handled the same way, normalising braces.

  **Rule 4 — Inline `python -c "..."` without PYTHONPATH prefix.** Replace
  ```
  uv run --project "${CLAUDE_PLUGIN_ROOT}" python -c "..."
  ```
  with
  ```
  PYTHONPATH="${CLAUDE_PLUGIN_ROOT}/scripts" "${CLAUDE_PLUGIN_ROOT}/.venv/Scripts/python.exe" -c "..."
  ```
  Same for the unbraced form, normalising braces. The PYTHONPATH prefix is ADDED (it was not present in the original).

  **Rule 5 — Shape B nested call after `-- \` (no PYTHONPATH= prefix).** Replace
  ```
  uv run --project "${CLAUDE_PLUGIN_ROOT}" "${CLAUDE_PLUGIN_ROOT}/scripts/<script>.py" [args]
  ```
  with
  ```
  "${CLAUDE_PLUGIN_ROOT}/.venv/Scripts/python.exe" "${CLAUDE_PLUGIN_ROOT}/scripts/<script>.py" [args]
  ```
  ONLY when the line is Shape B — i.e. the previous non-empty line in the same fenced ```bash block ends in `-- \`. The PYTHONPATH= prefix is NOT added; PYTHONPATH is inherited from the outer launcher process environment through `millpy-bg.py`'s worker. Tokens after `--` are passed as argv to `subprocess.run`; a `PYTHONPATH=...` token would be treated as the executable name and the spawn would fail. Same for the unbraced form, normalising braces. The `python -c "..."` nested variant (rare; not currently present in any in-scope file) uses the same prefix-less form: `"${CLAUDE_PLUGIN_ROOT}/.venv/Scripts/python.exe" -c "..."`.

  **DO NOT TOUCH:**
  - Lines containing `uv run --project plugins/mill` (source-tree forms — leave unchanged).
  - Lines containing `PYTHONPATH="plugins/mill/scripts"` (source-tree inline form — leave unchanged).
  - Prose paragraphs describing the old pattern (other than the literal bash code shown above). The prose in `mill-setup/SKILL.md` is updated in Batch 3, not here. No skill in this batch has prose that references the invocation form by name.
  - Any line in a fenced ```yaml or non-bash code block. The substitution applies only inside fenced ```bash blocks and bare-bash command examples.

  **mill-add specific note:** The source-tree form lives at line 90 (`uv run --project plugins/mill plugins/mill/scripts/millpy-add.py <slug>`) — leave unchanged. The other invocations (lines 93, 97, 113, 139, 168 at pre-edit time) are cache forms and convert per the rules above. Line 93 uses the unbraced form (`"$CLAUDE_PLUGIN_ROOT"`) and gets normalised to braced form via Rule 2.

- **Commit:** `refactor(skills): use direct venv Python for cache-form mill-script invocations`

## Batch Tests

This is a documentation-only batch with no runnable code surface. `verify: null` in the batch frontmatter.

Verification is mechanical and is performed by the implementer immediately after applying the edits:

1. For each file in `Edits:`, run `grep -E 'uv run --project "\$\{?CLAUDE_PLUGIN_ROOT\}?"' <file>` — expected zero matches.
2. For each file in `Edits:`, count `uv run --project plugins/mill` occurrences pre-edit and post-edit — counts must be identical (source-tree forms unchanged).
3. For each file in `Edits:`, count `${CLAUDE_PLUGIN_ROOT}/.venv/Scripts/python.exe` occurrences post-edit — expected ≥1 (substitution actually fired).
4. For `mill-plan/SKILL.md` and `mill-start/SKILL.md`, locate every line containing `${CLAUDE_PLUGIN_ROOT}/.venv/Scripts/python.exe` that is preceded by a line ending in `-- \`. Confirm those lines do NOT begin with `PYTHONPATH=` (Shape B nested-call rule). Expected: at least 2 such lines in `mill-plan/SKILL.md`, at least 1 in `mill-start/SKILL.md`.
5. Spot-check three random converted lines for grammatical correctness (proper quoting, line continuations preserved).
