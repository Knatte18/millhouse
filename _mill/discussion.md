# Discussion: Fix batch-name sanitization (colon/slash on Windows) and implementer skill loading

```yaml
task: Fix batch-name sanitization (colon/slash on Windows) and implementer skill loading
slug: batch-name-and-skill-loading
status: discussing
parent: main
```

## Problem

Three related GitHub bugs (#454, #456, #483) were hotfixed in downstream worktrees/repos and now need to land canonically in `plugins/mill/`. Two are Windows path bugs that break mill-go's prepare stage whenever a plan author writes a batch `name:` containing a colon or a slash; the third is a silent quality gap where spawned implementer/fixer sub-agents never load the language style/comment skills.

**Why now:** All three reproduce on real tasks today. A batch name like `Core fix: emit_prepare` (colon) corrupts the brief/snapshot filename into an NTFS alternate-data-stream so `git add` fails and prepare exits 1 (#454). A batch name like `internal/lock — lift lock primitives` (slash) makes the brief path point at a non-existent subdir, raising `FileNotFoundError` (#456). And a recent mhgo Go task produced ~28 `.go` files with no file-level/`Package` godoc comments because the implementer Haiku never loaded `golang-comments` — the orchestrator-only "load skills" preamble and CLAUDE.md routing table are not propagated to sub-agents (#483).

## Scope

**In:**
- One shared filename-sanitization helper covering the full Windows-unsafe character set, used everywhere a batch name becomes a filename component.
- Fix the brief-filename path in `_agent_dispatch.write_brief` (currently uses the raw batch name as `scope`) — the root cause of both #454 (colon→ADS) and #456 (slash→missing subdir) for briefs.
- Replace the two duplicated inline sanitization snippets in `millpy-implement.py` (snapshot path, lines ~189 and ~210) with the shared helper.
- Language-skill injection into the **per-batch implementer brief** (`templates/implementer-brief.md`, rendered by `millpy-implement.py`) **and the per-batch fixer brief** (`templates/fixer-batch-brief.md`, rendered by `millpy-fix.py`): the renderer language-detects the batch's touched files and injects a non-optional "load these skills" directive.
- An agent-definition backstop line in `agents/mill-implementer.md`.
- Unit tests for the sanitizer, the brief-path fix, and the injection rendering.

**Out:**
- The fail-closed doc-comment **lint gate** (#483's strongest layer). It would require extending every `{lang}-build` skill (golang/csharp/python plugins) with a doc-comment prose checker — a cross-plugin change of its own. File as a follow-up task; not in this scope.
- The **holistic fixer brief** (`fixer-holistic-brief.md`). It spans many batches at once, so "the" language is ambiguous; injection is scoped to the per-batch implementer + per-batch fixer briefs only. Possible follow-up.
- Any change to how plan authors write batch names. Authors stay free to use colons/slashes; the fix makes the tooling tolerate them.
- Languages without a skill plugin. Only Go, Python, C# are detected (the plugins that exist).

## Decisions

### sanitize-helper

- Decision: Add one shared helper (e.g. `sanitize_filename_component(name: str) -> str`) in **`_paths.py`** that replaces every character in the full Windows-unsafe set `: \ / * ? " < > |` with `-` (a single `re.sub(r'[:\\/*?"<>|]', '-', name)`). Use it at every site where a batch name becomes a filename component: the brief filename and the cleanliness-snapshot filename.
- Rationale: One definition kills both filed bugs and the rest of the Windows-reserved characters at once (defense in depth — `*?"<>|` would corrupt filenames the same way if a future batch name used them). `_paths.py` is already imported across the scripts and is the path-hygiene home, avoiding a new module. Sanitizing the slash away (rather than `mkdir`-ing a nested brief dir per #456's literal suggestion) keeps brief/snapshot naming flat and consistent with the already-sanitized snapshot path, and avoids ADS for free.
- Rejected: (a) Minimal `:`/`/`/`\`-only replacement extended inline to `write_brief` — leaves the duplication and ignores the other reserved chars. (b) `brief_path.parent.mkdir(...)` to honor the slash as a real subdir — inconsistent with the snapshot path's sanitize approach and still leaves the colon/ADS problem. (c) A new `_fs.py`/`_text.py` module — unnecessary for one small function.

### brief-filename-fix

- Decision: In `_agent_dispatch.write_brief`, sanitize only the `scope` (batch-name) component when building `brief_path = briefs_dir / f"{role}-{sanitize(scope)}-r{round_n}.md"`. The `role` and `round_n` are tool-controlled and safe. The function keeps returning the actual on-disk path, so the JSON envelope's `brief_path` stays correct.
- Rationale: `write_brief` is the single choke point for both the implementer and fixer brief paths, so fixing it here covers #454 and #456 for all brief callers at once. The `scope`/batch-name value stored in the envelope and used for status lookups must stay the **raw** batch name — only the filename component is sanitized.
- Rejected: Sanitizing at each caller (`emit_prepare`, fix path) — would re-introduce duplication that the shared helper is meant to remove.

### snapshot-dedup

- Decision: Replace both inline `_safe_batch = args.batch_name.replace(...)` occurrences in `millpy-implement.py` with a single call to the shared helper.
- Rationale: Removes duplicated logic; guarantees snapshot and brief filenames sanitize identically.
- Rejected: Leaving the working inline code — it already fixed the snapshot half of #454 but diverges from the brief path and duplicates itself.

### skill-injection

- Decision: The renderer parses the batch file's `Edits:`/`Creates:`/`Context:` references via the existing `_review_common.parse_batch_refs(batch_path) -> list[str]`, maps file extensions to languages (`.go`→go, `.py`→python, `.cs`→csharp), and builds a directive string injected into the brief through a new template token (e.g. `<LANGUAGE_SKILLS>`). The directive is targeted and non-optional, e.g.: _"This batch touches .go files — load `code-quality`, `golang-comments`, `golang-testing` and follow them before editing."_ `code-quality` is **always** included (even when no recognized source language is detected); each detected language additionally contributes `{lang}-comments` and `{lang}-testing`. Multiple languages in one batch → directives for each, `code-quality` once.
- Rationale: Targeted injection beats self-detection — Haiku is weak at voluntarily loading skills (#483's observed failure). Reusing `parse_batch_refs` avoids a second batch parser. Token-based rendering keeps the directive out of the static template body so it can be empty-aware. Always injecting `code-quality` (Q8) means even docs/config-only batches get the language-agnostic quality rules; the rule is simply "code-quality always + per-detected-language comments+testing" (Q4).
- Rejected: (a) Generic agent-only prompt ("detect language yourself") as the sole mechanism — repeats the exact failure just observed. (b) Repo-wide / `mill:workflow` language detection instead of per-batch files — coarser; a batch may touch only one language in a polyglot repo. (c) Injecting the full `{lang}-*` family including `{lang}-build` — `git-commit` already runs `{lang}-build` lint, so build is redundant in the brief.

### agent-def-backstop

- Decision: Add a generic backstop line to `agents/mill-implementer.md`: detect language from edited files and load the matching `{lang}-*` skills before editing. This complements (does not replace) the targeted brief injection.
- Rationale: Defense in depth — covers any future brief path that forgets the token. Cheap, one line.
- Rejected: Relying on the agent-def line alone (#483's "prompt instructions alone repeat the failure mode").

### extension-language-map

- Decision: Cover only the languages with skill plugins today: Go (`.go`), Python (`.py`), C# (`.cs`). Unknown extensions contribute no language (but `code-quality` is still injected per skill-injection above). The map lives next to the directive builder.
- Rationale: Injecting a `{lang}-comments` skill that doesn't exist would be a dead directive. The three language plugins (`golang`, `csharp`, `python`) are the full set present in `plugins/`.
- Rejected: Adding web extensions (`.ts`/`.tsx`/`.js`) — no skill plugins exist for them, so they'd only ever trigger the always-on `code-quality`, which the no-language path already provides.

## Technical context

- **`plugins/mill/scripts/_agent_dispatch.py`** — `write_brief(briefs_dir, role, scope, round_n, prompt_text) -> Path` (line ~86) builds `briefs_dir / f"{role}-{scope}-r{round_n}.md"` from the **raw** `scope`. This is the single brief-path choke point; the sanitize fix goes here. It already does `briefs_dir.mkdir(parents=True, exist_ok=True)` but not on the (now-sanitized, so unnecessary) brief parent.
- **`plugins/mill/scripts/_implementer_common.py`** — `emit_prepare(...)` (line ~99) calls `write_brief` and emits the prepare JSON envelope. The envelope's `scope` field must remain the raw batch name (used downstream for status lookups); only the filename is sanitized inside `write_brief`.
- **`plugins/mill/scripts/millpy-implement.py`** — builds the implementer prompt via `_render.render(implementer-brief.md, {...})` (line ~253) with `BATCH_NAME`, `BATCH_FILE`, etc. Has `batch_file` in hand for language detection. Contains the two duplicated snapshot-sanitize snippets at lines ~189 and ~210 (`.cleanliness-snapshot-{_safe_batch}.txt`). This is where the implementer `<LANGUAGE_SKILLS>` token is computed and passed.
- **`plugins/mill/scripts/millpy-fix.py`** — renders `fixer-batch-brief.md` via `_render.render` (line ~248) with `BATCH_NAME`/`BATCH_FILE`. Same injection token added here. (It also renders `fixer-holistic-brief.md` at line ~298 — out of scope.)
- **`plugins/mill/scripts/_review_common.py`** — `parse_batch_refs(batch_path: Path) -> list[str]` (line ~447) returns the file paths referenced in a batch's `Context:`/`Edits:`/`Creates:`. Reuse for extension→language detection. Consider placing the directive builder (`language_skills_directive(batch_file) -> str`) in a shared module both renderers import — `_agent_dispatch.py` is a reasonable home since it already owns brief writing; mill-plan may choose the exact location.
- **`plugins/mill/templates/implementer-brief.md`** and **`plugins/mill/templates/fixer-batch-brief.md`** — add the `<LANGUAGE_SKILLS>` token in a clear early section (e.g. just before "Implementation discipline" / "Fix discipline"). `_render.render` strips the leading HTML comment; the token must also be documented in that comment's token list.
- **`plugins/mill/agents/mill-implementer.md`** — currently names no skills ("the per-batch brief provides all instructions"). Add the backstop line; keep the existing tools list (`Read, Edit, Write, Bash, Grep, Glob, Skill` — note `Skill` is present, so the agent CAN load skills).
- **`_render.render`** substitutes `<TOKEN>` → value and strips the template's leading HTML comment. Passing an empty string for an unused token renders nothing.
- ASCII-only stdout rule (CLAUDE.md): any `print()`/log added must use ` -- ` / ` -> ` not unicode dashes/arrows.

## Constraints

- No `CONSTRAINTS.md` at hub root was found during exploration.
- **Windows filename safety** is the governing constraint: the sanitizer must strip the full reserved set `: \ / * ? " < > |`. Colons specifically trigger NTFS ADS (silent corruption, not an error at write time — the failure surfaces later at `git add`).
- The **raw batch name** must be preserved everywhere it is used as a logical identifier (status `set_batch_fields`, envelope `scope`, log lines, plan lookups). Sanitization applies **only** to filename components.
- The injected directive must be **non-optional** wording (targeted at a weak self-detector). Keep it short to avoid bloating the brief (`max_implementer_prompt_chars` guard exists in `millpy-implement.py`).
- Follow existing skill names exactly: `code-quality`, `golang-comments`, `golang-testing`, `python-comments`, `python-testing`, `csharp-comments`, `csharp-testing` (the `mill:`/`python:`/`golang:`/`csharp:` plugin namespaces apply when invoked).

## Testing

Unit tests under `plugins/mill/unit_tests/` (`test-<name>.py`, run via `run-all.py`; in-memory/tempfile fixtures, no real git/LLM). Verify commands must start with `PYTHONPATH= ` per CLAUDE.md (Python project).

- **Sanitizer (TDD candidate):** new `test-paths-sanitize.py` (or extend an existing `_paths` test) — table-driven over each unsafe char (`: \ / * ? " < > |`) → `-`, plus a clean name passes through unchanged, plus a name with several unsafe chars. Pure function, ideal for TDD.
- **Brief path (`test-agent-dispatch` / extend):** `write_brief` with a `scope` containing `:` produces a filename with no colon and a real file on disk (no ADS); `write_brief` with a `scope` containing `/` writes a flat file under `briefs_dir` (no `FileNotFoundError`, no nested dir). Assert the returned path exists and round-trips the written text.
- **Snapshot dedup (`test-millpy-implement` / extend):** snapshot path for a colon/slash batch name resolves to a sanitized flat filename matching the sanitizer's output.
- **Injection rendering (TDD candidate):** new `test-language-skills-directive.py` — build a batch file referencing only `.go` files → directive names `code-quality` + `golang-comments` + `golang-testing`; only `.py` → python variants; mixed `.go`+`.py` → both language sets, `code-quality` once; no recognized source files (only `.md`/`.yaml`) → directive still includes `code-quality` and no `{lang}-*`. Then assert the rendered implementer brief and fixer brief contain the directive text for a sample batch.
- No integration test (real git/LLM) is required; all changes are pure-function or template-render and covered by unit tests.

## Q&A log

- **Q:** Sanitization approach? **A:** Shared helper, full Windows-unsafe set `[:\/*?"<>|]`→`-`, replacing the two inline dups.
- **Q:** Where does the helper live? **A:** `_paths.py` (`sanitize_filename_component`).
- **Q:** #483 defense depth? **A:** Brief-template injection + agent-def backstop. Fail-closed lint gate is out of scope (cross-plugin follow-up).
- **Q:** Which skills does the directive name? **A:** `code-quality` always + `{lang}-comments` + `{lang}-testing` per detected language.
- **Q:** How to detect language? **A:** Parse the batch's `Edits:`/`Creates:` via `parse_batch_refs`, map extensions → language.
- **Q:** Which languages to map? **A:** Only those with skill plugins: Go, Python, C#.
- **Q:** Apply injection to the fixer brief too? **A:** Yes — `fixer-batch-brief.md` (per-batch). Holistic fixer stays out of scope.
- **Q:** What's injected when a batch touches no recognized source language? **A:** Still inject `code-quality` (language-agnostic); no `{lang}-*` skills.
