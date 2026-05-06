# Batch: session-id-template

```yaml
task: 17 (A) — SKILL.md API accuracy audit + implementer-brief contract fixes
batch: session-id-template
cards: 2
verify: "uv run --project plugins/mill python -m py_compile plugins/mill/scripts/millpy-implement.py"
depends-on: [skill-md-fixes]
```

## Batch Scope

Fix issue D: the implementer-brief.md template instructs the spawned Claude Code session to read its `session_id` from the `--session-id` CLI flag, but a spawned Claude session cannot access its own launch flags. Fix by adding a `<SESSION_ID>` render token to the template (the CLI already generates the UUID before rendering the brief) and updating the instruction text to tell the implementer to copy the UUID from the brief example. The `millpy-implement.py` render call must also be updated to pass the token. Two cards: one for the template edits, one for the script edit.

## Cards

### Card 5: implementer-brief.md — replace session_id placeholder with render token

- **Reads:**
  - `plugins/mill/templates/implementer-brief.md`
- **Modifies:**
  - `plugins/mill/templates/implementer-brief.md`
- **Creates:** none
- **Deletes:** none
- **Requirements:**
  The `## Report` section of `implementer-brief.md` contains two JSON examples (success and stuck) each followed by a bolded instruction block. Both occurrences must be updated.

  **Edit 1 — success JSON example:**
  Find:
  ```
  {"status":"success","commit_sha":"<last-HEAD-sha>","session_id":"<this-session-id>"}
  ```
  Replace with:
  ```
  {"status":"success","commit_sha":"<last-HEAD-sha>","session_id":"<SESSION_ID>"}
  ```

  **Edit 2 — success instruction block:**
  Find the bold instruction that immediately follows the success JSON fenced block:
  ```
  **`session_id` MUST be the exact UUID passed to you via the `--session-id` flag (you can read it from your own command-line arguments or echo it as given). Do not invent or paraphrase the value. mill-go uses this field to correlate the report with the spawned session.**
  ```
  Replace with:
  ```
  **`session_id` MUST be exactly `<SESSION_ID>` (the UUID shown in the example above — it was injected into this brief when it was rendered). Copy it verbatim.**
  ```

  **Edit 3 — stuck JSON example:**
  Find:
  ```
  {"status":"stuck","stuck_type":"transient|verify|logic","reason":"<one-line>","commit_sha":"<last-HEAD-sha>","session_id":"<this-session-id>"}
  ```
  Replace with:
  ```
  {"status":"stuck","stuck_type":"transient|verify|logic","reason":"<one-line>","commit_sha":"<last-HEAD-sha>","session_id":"<SESSION_ID>"}
  ```

  **Edit 4 — stuck instruction block:**
  Find the bold instruction that immediately follows the stuck JSON fenced block:
  ```
  **`session_id` MUST be the exact UUID passed to you via the `--session-id` flag (you can read it from your own command-line arguments or echo it as given). Do not invent or paraphrase the value. mill-go uses this field to correlate the report with the spawned session.**
  ```
  Replace with:
  ```
  **`session_id` MUST be exactly `<SESSION_ID>` (the UUID shown in the example above — it was injected into this brief when it was rendered). Copy it verbatim.**
  ```

  After all four edits, confirm that no occurrence of `<this-session-id>` remains in the file and that both instruction blocks have been updated.

  Note: `<SESSION_ID>` is a render token that will be substituted by `_render.render()` at runtime. Inside the fenced json code block in the template, it will appear literally as `<SESSION_ID>` until rendering. This is correct — `_render.render()` strips the HTML comment and substitutes all `<TOKEN>` patterns including those inside code fences.

- **Commit:** `fix(implementer-brief): inject SESSION_ID token into report JSON examples`

### Card 6: millpy-implement.py — add SESSION_ID token to render call

- **Reads:**
  - `plugins/mill/scripts/millpy-implement.py`
  - `plugins/mill/scripts/_render.py`
- **Modifies:**
  - `plugins/mill/scripts/millpy-implement.py`
- **Creates:** none
- **Deletes:** none
- **Requirements:**
  In the initial dispatch path (not the fix-cycle resume path), find the `_render.render()` call for `implementer-brief.md`. The call currently looks like:
  ```python
          prompt_text = _render.render(template_path, {
              "TASK_TITLE": task_title,
              "SLUG": slug,
              "BATCH_NAME": args.batch_name,
              "BATCH_FILE": str(batch_file),
              "OVERVIEW_FILE": str(project_root / "plan" / "00-overview.md"),
              "PROJECT_ROOT": str(project_root),
              "WIKI_PATH": str(wiki_path),
              "SELF_FIX_ROUNDS": str(self_fix_rounds),
              "ROUND": "1",
          })
  ```
  Add `"SESSION_ID": session_id,` as a new entry in the token dict, after the `"ROUND": "1",` line:
  ```python
          prompt_text = _render.render(template_path, {
              "TASK_TITLE": task_title,
              "SLUG": slug,
              "BATCH_NAME": args.batch_name,
              "BATCH_FILE": str(batch_file),
              "OVERVIEW_FILE": str(project_root / "plan" / "00-overview.md"),
              "PROJECT_ROOT": str(project_root),
              "WIKI_PATH": str(wiki_path),
              "SELF_FIX_ROUNDS": str(self_fix_rounds),
              "ROUND": "1",
              "SESSION_ID": session_id,
          })
  ```
  The `session_id` variable is in scope at this point (it was assigned via `session_id = str(uuid.uuid4())` earlier in the same branch). Do not modify the fix-cycle resume path's `_render.render()` call (which uses `implementer-fix.md`).

- **Commit:** `fix(millpy-implement): pass SESSION_ID token to implementer-brief render`

## Batch Tests

`verify: uv run --project plugins/mill python -m py_compile plugins/mill/scripts/millpy-implement.py` — confirms the Python file has no syntax errors after the token dict edit.
