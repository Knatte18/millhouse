# Batch: High-complexity skill fixes

```yaml
task: Audit and clean up stale V2 references
batch: High-complexity skill fixes
number: 4
cards: 4
verify: "PYTHONPATH= bash -c \"! grep -rq '_wiki[.]\\|_tasks_md[.]\\|_sidebar[.]' plugins/mill/skills/mill-setup/SKILL.md plugins/mill/skills/mill-ghissues-to-tasks/SKILL.md plugins/mill/skills/mill-autofix/SKILL.md\""
depends-on: []
```

## Batch Scope

Three skills requiring structural rewrites beyond simple API swaps. mill-setup has six distinct changes (scripts listing, helpers list, clone_or_init, Phase 6 deletion, Phase 6a replacement, and Phase 5 verification update). mill-ghissues-to-tasks rewrites the locked-phase check and append_to_body pattern. mill-autofix rewrites Phase 1b slug enumeration and the Step 2 error-path `_tasks_md.parse` call. Four cards: mill-setup is split into Phase 3 changes (card 12) and Phase 5/6/6a changes (card 13).

## Cards

### Card 12: mill-setup — Phase 3 changes (scripts listing, helpers list, clone_or_init)

- **Context:**
  - `.scratch/v3-wiki-cheatsheet.md`
  - `plugins/mill/scripts/_setup.py`
- **Edits:**
  - `plugins/mill/skills/mill-setup/SKILL.md`
- **Creates:** none
- **Deletes:** none
- **Requirements:**
  Line 3 (description frontmatter): change `seeds config.local.yaml and Home.md` to `seeds config.local.yaml`. Remove the "Home.md" reference since Phase 6 is being deleted (see card 13).

  Line 31 (scripts/ directory listing): remove `_wiki.py` from the list. The listing `_junction.py, _wiki.py, _subprocess_util.py, _render.py, _setup.py` becomes `_junction.py, _subprocess_util.py, _render.py, _setup.py`.

  Line 71 (helpers list): remove `_sidebar (Phase 6a)` and `_wiki (Phase 3, 3.1, 6, 6a)` from the `Helpers used by this skill:` sentence. Keep all other helpers unchanged.

  Line 224 (prose in Phase 3 "Why verbatim copy" block): replace `\`_junction.resolve_target\` and \`_wiki.read_hardlinks\` at runtime` with `\`_junction.resolve_target\` at runtime`.

  Lines 136–148 (Phase 3 `call _wiki.clone_or_init` block): replace `After \`<wiki-dir>\` is computed, call \`_wiki.clone_or_init\`:` with `After \`<wiki-dir>\` is computed, call \`_setup.clone_or_init\`:`. In the bash code block, replace `import _wiki, json` with `import _setup, json` and replace `result = _wiki.clone_or_init(` with `result = _setup.clone_or_init(`. All other arguments stay identical.

  Line 541 (error table): replace `\`clone_or_init\` raises \`WikiSetupError\`...` — if the text currently says `_wiki.clone_or_init`, change the module reference to `_setup.clone_or_init`. If it just says `clone_or_init`, no change needed.
- **Commit:** `docs(mill-setup): fix Phase 3 clone_or_init and scripts listing`

### Card 13: mill-setup — Phase 5 verification, Phase 6 deletion, Phase 6a replacement

- **Context:**
  - `.scratch/v3-wiki-cheatsheet.md`
  - `plugins/mill/scripts/wiki/_client.py`
- **Edits:**
  - `plugins/mill/skills/mill-setup/SKILL.md`
- **Creates:** none
- **Deletes:** none
- **Requirements:**
  Phase 5 verification list (lines 503–504): remove the two bullets:
  - `- \`<WIKI_PATH>/Home.md\` exists and starts with \`# Tasks\``
  - `- \`<WIKI_PATH>/_Sidebar.md\` exists and begins with \`### Navigation\``
  Replace both with a single bullet: `- Wiki daemon starts successfully: \`_client.list_tasks_brief(wiki_path)\` returns without error and Home.md exists in the wiki clone.`

  Delete Phase 6 entirely (lines ~430–448): the heading `### Phase 6 — Initialise or normalise \`Home.md\`` and all its content including the decision table, copy-from-template instruction, and `_wiki.write_commit_push` bash block. In V3 `Home.md` is daemon-rendered and must not be manually seeded.

  Replace Phase 6a entirely (lines ~452–468): delete the heading `### Phase 6a — Initialise \`_Sidebar.md\` via \`_sidebar.regenerate()\`` and all its content (the `_sidebar.regenerate` bash call, the `git -C` status check, and the `_wiki.write_commit_push` commit bash call).

  Replace Phase 6a with a new minimal section:
  ```markdown
  ### Phase 6a — Trigger daemon startup and initial render

  Call `_client.list_tasks_brief(wiki_path)` to start the wiki daemon and trigger
  initial rendering of `Home.md` and `_Sidebar.md` from `tasks.json`. The daemon
  creates `tasks.json` if absent and auto-renders both derived files on first access.

  ```bash
  PYTHONPATH="${CLAUDE_PLUGIN_ROOT}/scripts" "${CLAUDE_PLUGIN_ROOT}/.venv/Scripts/python.exe" -c "
  from pathlib import Path
  from wiki import _client
  _client.list_tasks_brief(Path(r'<wiki-dir>').resolve())
  "
  ```
  ```
- **Commit:** `docs(mill-setup): replace Phase 6/6a and update Phase 5 verification`

### Card 14: mill-ghissues-to-tasks — replace _tasks_md.parse, append_to_body, LOCKED_FOLD_PHASES, write_commit_push, sidebar

- **Context:**
  - `.scratch/v3-wiki-cheatsheet.md`
- **Edits:**
  - `plugins/mill/skills/mill-ghissues-to-tasks/SKILL.md`
- **Creates:** none
- **Deletes:** none
- **Requirements:**
  Line 70 (fold-in phase check): replace `parse Home.md via \`_tasks_md.parse()\` and inspect the target Task's phase. When the phase is in \`_tasks_md.LOCKED_FOLD_PHASES\` (i.e. one of \`"active"\`, \`"ready-to-merge"\`, \`"pr-pending"\`)` with `call \`task = _client.get_task(wiki_path, target_slug)\` and inspect \`task["status"]\`. When the status is in the locked set (\`"active"\`, \`"ready-to-merge"\`, \`"pr-pending"\`)`. Also replace `. Use \`_tasks_md.LOCKED_FOLD_PHASES\` as the source of truth — never duplicate the tuple in this SKILL.md or anywhere else.` with `. Use the locked set \`{"active", "ready-to-merge", "pr-pending"}\` as the source of truth.`

  Line 121 (fold-in body append): replace `call \`_tasks_md.append_to_body(home_text, target_slug, f"- Sources: #{N} — {issue_title}")\` to add a Sources: bullet to the target body` with `call \`task = _client.get_task(wiki_path, target_slug); new_body = (task["body"] or "") + f"\\n- Sources: #{N} — {issue_title}"; _client.upsert_task(wiki_path, target_slug, body=new_body)\` to append the Sources: bullet`.

  Line 122 (write Home.md step): replace `Write Home.md + any new \`proposal-<slug>.md\` files to the wiki and push via \`_wiki.write_commit_push\`.` with `Each \`_client.upsert_task\` call commits and pushes to the wiki remote automatically. New task entries go through \`_client.upsert_task(wiki_path, slug, title=..., brief=..., body=...)\`; new proposals are written to \`body=\` (the daemon renders \`proposal-<slug>.md\` from that field).`

  Line 123 (sidebar step): delete `3. Regenerate the sidebar (\`_sidebar.regenerate\`) and commit if it changed.` entirely. Renumber subsequent steps (old 4 → new 3, etc.).

  Lines 159–160 (Board discipline): replace `\`_tasks_md.LOCKED_FOLD_PHASES\` is the source of truth — never duplicate the tuple.` with `The locked set \`{"active", "ready-to-merge", "pr-pending"}\` is the source of truth — never duplicate it.` Replace `Fold-in always appends a \`"- Sources: #N — <issue title>"\` bullet to the target body via \`_tasks_md.append_to_body\`.` with `Fold-in always appends a \`"- Sources: #N — <issue title>"\` bullet via \`_client.get_task\` + \`_client.upsert_task(..., body=...)\`.`
- **Commit:** `docs(mill-ghissues-to-tasks): replace stale V2 wiki refs`

### Card 15: mill-autofix — replace Phase 1b slug extraction and Step 2 error-path _tasks_md.parse

- **Context:**
  - `.scratch/v3-wiki-cheatsheet.md`
- **Edits:**
  - `plugins/mill/skills/mill-autofix/SKILL.md`
- **Creates:** none
- **Deletes:** none
- **Requirements:**
  Phase 1b "Load Home.md and extract existing slugs" (lines 54–77): rename the section to `### 1b. Load existing slugs from wiki`. Replace the Home.md read + `_TASK_HEADING_RE` slug extraction pattern with:
  ```bash
  PYTHONPATH="${CLAUDE_PLUGIN_ROOT}/scripts" "$MILL_PYTHON" -c "
  import json, _paths
  from wiki import _client
  wiki_path = _paths.resolve_wiki_path(_paths.resolve_git_root())
  tasks = _client.list_tasks_brief(wiki_path)
  print(json.dumps([t['slug'] for t in tasks]))
  "
  ```
  `existing_home_slugs` is the set of slugs returned by this call: `existing_home_slugs = {t["slug"] for t in _client.list_tasks_brief(wiki_path)}`. Remove the `_TASK_HEADING_RE` regex definition, the `open("<wiki_path>/Home.md", ...)` call, and the regex match loop. The section text changes from "Read `<wiki_path>/Home.md` and extract the set of existing slugs..." to "Call `_client.list_tasks_brief(wiki_path)` and extract the set of existing slugs: `existing_home_slugs = {t['slug'] for t in tasks}`."

  Step 2 error-handling path (lines 201–212): replace the bash block that calls `import _tasks_md, sys; ... home_text = Path(sys.argv[1]).read_text(...); tasks = _tasks_md.parse(home_text); t = next((t for t in tasks if t.slug == sys.argv[2]), None); ... print(t.phase or 'unmarked')` with:
  ```bash
  PYTHONPATH="${CLAUDE_PLUGIN_ROOT}/scripts" "$MILL_PYTHON" -c "
  import sys, _paths
  from wiki import _client
  wiki_path = _paths.resolve_wiki_path(_paths.resolve_git_root())
  task = _client.get_task(wiki_path, sys.argv[1])
  if task is None:
      print('not-found')
  else:
      print(task.get('status') or 'unmarked')
  " "<slug>"
  ```
  This call no longer needs `<wiki_path>/Home.md` as a CLI argument. The field is `task["status"]` (not `t.phase`).
- **Commit:** `docs(mill-autofix): replace Phase 1b slug extraction and Step 2 _tasks_md.parse`

## Batch Tests

All three files are pure documentation (SKILL.md). The verify command greps for `_wiki[.]`, `_tasks_md[.]`, and `_sidebar[.]` across all three files and asserts zero matches.
