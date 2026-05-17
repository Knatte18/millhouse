# Batch: merge-in-intent-aware

```yaml
task: 59 (A) -- Small infra fixes batch 8
batch: merge-in-intent-aware
number: 3
cards: 2
verify: null
depends-on: []
```

## Batch Scope

Makes the merge-in conflict subagent intent-aware (#314). Today the subagent prompt only contains the list of conflicting files; it has no signal about whether the local branch's intent was to keep, modify, or delete each file. A live task that explicitly deleted `plugins/mill/templates/reviewers.yaml` was silently undone by the resolver re-introducing the file from main. Fix: gather task-intent excerpts (discussion.md + the YAML/path-bullet portion of each plan file) and inject them as a new `<TASK_INTENT>` token in the conflict brief. The template gets the new token; the dispatcher gets a `_collect_task_intent` helper that produces the string. `verify` is `null` because this is a prompt-shape change with no runnable surface; end-to-end verification is operator-side on a synthetic DU-conflict reproduction.

## Cards

### Card 4: Add `<TASK_INTENT>` token to the conflict brief template

- **Context:**
  - `plugins/mill/templates/merge-in-verify-brief.md`
- **Edits:**
  - `plugins/mill/templates/merge-in-conflict-brief.md`
- **Creates:** none
- **Deletes:** none
- **Requirements:** Update `plugins/mill/templates/merge-in-conflict-brief.md` as follows. (1) Top HTML comment block (lines 1-5): add a third bullet documenting the new token: `  <TASK_INTENT>     -- excerpts from this branch's _mill/discussion.md and _mill/plan/*.md so the resolver can recognize an intentional delete or rewrite. Empty string when neither is present.` (2) Between the line `Your sole job is to resolve git conflict markers in the listed files, stage each resolved file, and report success. Do NOT commit. Do NOT run \`git merge --continue\` -- the SKILL does that after receiving \`{"status":"success"}\`.` and the existing `## Conflicting files` heading, insert a new section: `## Task intent` followed by an explanatory paragraph and the token: `These excerpts describe what THIS branch is trying to accomplish. When the merge introduces a parent-side change that conflicts with this branch's intent, the resolution preserves THIS branch's intent. In particular: if a file appears under a batch's ``Deletes:`` list and the merge introduces a modified version of that file from the parent, the resolution is to delete the file (your branch's intent overrides). Stage the deletion with ``git -C <PROJECT_ROOT> rm <file>``.` then a blank line, then the literal token `<TASK_INTENT>`. The empty-string render produces a section with the heading, the explanation, and an empty body -- the model still sees the intent guidance even when no excerpts are available. (3) After the `## Instructions` section (between step 4 `Run \`git -C <PROJECT_ROOT> add <file>\` to stage the resolved file.` and the `Never use \`git checkout --ours\`...` line), add a new instruction step `5. For modify/delete (DU) conflicts: if Task intent above lists this file under a batch's ``Deletes:``, run ``git -C <PROJECT_ROOT> rm <file>`` instead of editing; that stages the intentional deletion.` (4) The existing JSON report shape and Tools section remain unchanged. Keep ASCII-only output language; do not introduce em-dashes or right-arrow Unicode.
- **Commit:** `feat(merge-in-conflict-brief): add <TASK_INTENT> token and DU-conflict guidance (#314)`

### Card 5: Collect task intent in `_run_conflicts` and pass to the template

- **Context:**
  - `plugins/mill/scripts/_render.py`
  - `plugins/mill/templates/merge-in-conflict-brief.md`
- **Edits:**
  - `plugins/mill/scripts/millpy-merge-in-subagent.py`
- **Creates:** none
- **Deletes:** none
- **Requirements:** In `plugins/mill/scripts/millpy-merge-in-subagent.py`, add a new module-level private helper `def _collect_task_intent(project_root: Path) -> str:`. Behaviour:
  1. Compute `mill_dir = project_root / "_mill"`. If `mill_dir.is_dir()` is False, return the empty string `""`.
  2. Build the output as a list of strings, joined by `"\n\n"`.
  3. If `(mill_dir / "discussion.md").is_file()`, append `### From discussion.md\n\n<full file contents>` (read via `read_text(encoding="utf-8")`).
  4. For each `*.md` file in `sorted((mill_dir / "plan").glob("*.md"))` (skip silently if `mill_dir / "plan"` does not exist):
     - Read the file text.
     - Extract the top fenced-YAML block (first substring between ``` ```yaml ``` ``` and the next ``` ``` ```; include the fence lines for readability).
     - Extract every line that matches the regex `^-\s*\*\*(Edits|Creates|Deletes):\*\*(?P<inline>.*)$` and handle both forms (inline single-line `- **Deletes:** \`path/file.py\`` and multi-line with indented sub-bullets). The matching pattern: first check the `(?P<inline>...)` capture; if non-empty after `.strip()`, extract backtick tokens from it directly via `re.findall(r"\`([^\`]+)\`", inline)` (mirrors `_parse_edits_only` in `_plan_validate.py:114-119`). Only fall through to the sub-bullet scan when the inline capture is empty. The sub-bullet scan uses the same `^\s+-\s*(.+)$` shape as `_plan_validate.py:54`. Inline the small regexes locally; do NOT import `_plan_validate` to keep this helper free of cross-module deps. Preserve the original bullet line plus any sub-bullets verbatim in the output -- the subagent reads them, not a re-rendered string.
     - Append `### From _mill/plan/<filename>\n\n<yaml-block>\n\n<header-bullets>` to the output list.
  5. Return the joined string (empty when neither source is present).
  In `_run_conflicts` (current line 108), after constructing `conflicting_files` (line 113), call `task_intent = _collect_task_intent(project_root)` and add `"TASK_INTENT": task_intent` to the `_render.render(...)` tokens dict on line 116. Order of dict keys does not matter; `_render` substitutes by name. Leave `_run_verify_fix` (line 139) unchanged -- the verify-fix template does not receive `<TASK_INTENT>`.
  Add a one-line comment above the new helper: `# DU-conflict resolution needs branch intent; the resolver had no signal before #314.` -- the comment captures the WHY per CLAUDE.md commenting rules.
- **Commit:** `feat(millpy-merge-in-subagent): pass task intent to conflicts subagent (#314)`

## Batch Tests

`verify: null`. The change is prompt-shape only; no runnable assertion shape captures "the LLM now sees intent". End-to-end verification is operator-driven on a synthetic DU-conflict reproduction (run a merge-in against a branch that deleted a file the parent modified; confirm the resolver's prompt now includes the `<TASK_INTENT>` section and the resolution is the deletion).
