# Batch: mill-start-utf8-fix

```yaml
task: Fix plan validator Moves-target gap, code-review backtick parser, and mill-start encoding crash
batch: mill-start-utf8-fix
number: 3
cards: 1
verify: null
depends-on: []
```

## Batch Scope

The `mill-start` SKILL's documented Phase: Select `get_task` Bash snippet prints `task.get('brief', '')` and `task.get('body', '')` without forcing UTF-8 output. On a Windows console using the cp1252 codepage, any non-cp1252 character in the task body or brief (e.g. `→`) raises `UnicodeEncodeError` and the subprocess exits 1 right after the `STATUS:` line, silently breaking the snippet on the autonomous/agent dispatch path. This batch prepends `PYTHONIOENCODING=utf-8` to the documented invocation, matching the existing repo-wide convention in `_subprocess_util.py` (which always injects `PYTHONIOENCODING=utf-8` into child-process environments for exactly this class of problem), and cross-references the fix from Phase: Explore's prose so a reader reconstructing that phase's re-call doesn't drop the env prefix.

## Cards

### Card 7: Prepend PYTHONIOENCODING=utf-8 to mill-start's get_task snippet and cross-reference it from Phase: Explore

- **Context:** none
- **Edits:**
  - `plugins/mill/skills/mill-start/SKILL.md`
- **Creates:** none
- **Deletes:** none
- **Moves:** none
- **Requirements:** In the `### Phase: Select` section's fenced ` ```bash ` code block, the first line currently reads exactly:
  ```
  PYTHONPATH="${CLAUDE_PLUGIN_ROOT}/scripts" "$MILL_PYTHON" -c "
  ```
  Change it to:
  ```
  PYTHONIOENCODING=utf-8 PYTHONPATH="${CLAUDE_PLUGIN_ROOT}/scripts" "$MILL_PYTHON" -c "
  ```
  (prepend the literal `PYTHONIOENCODING=utf-8 ` token, single trailing space, before the existing `PYTHONPATH=` assignment — do not change anything else in the code block, including the multi-line Python body, the closing `"`, or the surrounding prose). Then, in the `### Phase: Explore` section's first paragraph, the sentence currently begins: "Before exploring the codebase, fetch the task document by re-calling `_client.get_task(wiki_path, slug)` (each Bash call is a fresh subprocess, so the `task` variable from Phase: Select does not persist)." Insert a parenthetical cross-reference immediately after that first sentence (before the next sentence, which begins "Read the proposal from..."), reading: "(use the same `PYTHONIOENCODING=utf-8`-prefixed invocation shown in Phase: Select to avoid the cp1252 `UnicodeEncodeError` on non-ASCII body/brief content.)" Do not change any other prose in Phase: Explore.
- **Commit:** `fix(mill-start): force PYTHONIOENCODING=utf-8 on get_task snippet to avoid cp1252 crash`

## Batch Tests

`verify: null` — this is a documentation-only change to a SKILL.md Bash snippet and surrounding prose; there is no automated test surface for SKILL.md content in the unit suite. Verification is by inspection: the Phase: Select code block's first line must read exactly `PYTHONIOENCODING=utf-8 PYTHONPATH="${CLAUDE_PLUGIN_ROOT}/scripts" "$MILL_PYTHON" -c "`, and Phase: Explore's prose must contain the cross-referencing parenthetical. The plan-level top-level `verify:` (full `run-all.py` suite, run at every batch boundary) provides a repo-wide regression backstop in case this edit is accidentally malformed in a way that breaks an unrelated SKILL-parsing test.
