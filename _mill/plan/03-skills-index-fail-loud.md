# Batch: skills-index-fail-loud

```yaml
task: Fix daemon health-check race, finalize env-var delivery, skills-index drop, and encoding crash
batch: skills-index-fail-loud
number: 3
cards: 2
verify: PYTHONPATH= uv run --project plugins/mill python plugins/mill/unit_tests/test-skills-index.py
depends-on: []
```

## Batch Scope

Fixes #589: `millpy-skills-index.py`'s `_extract_frontmatter(text)` catches `yaml.YAMLError` (e.g. from a `description:` value containing an unquoted bare `: ` substring) and returns `None`, which `_scan()` treats identically to "no `---` frontmatter block at all" — printing a generic "missing frontmatter" message and silently dropping the skill from `SKILLS.md` with no indication a parse actually failed. This batch makes the two failure modes distinguishable: a genuine YAML parse failure raises a dedicated `FrontmatterParseError`, which `_scan()` catches and reports with the actual underlying `yaml.YAMLError` message, naming the offending file. The skill is still dropped from the index either way (a scanner cannot safely guess intent from malformed YAML) — the fix is diagnosability, not tolerance.

## Cards

### Card 5: Distinguish parse-error from missing-frontmatter in `millpy-skills-index.py`

- **Context:** none
- **Edits:**
  - `plugins/mill/scripts/millpy-skills-index.py`
- **Creates:** none
- **Deletes:** none
- **Moves:** none
- **Requirements:** Add a new exception class `FrontmatterParseError(Exception)` at module level (after the existing imports, before `_repo_root()`), storing the offending file `path` and the original `yaml.YAMLError` (e.g. `def __init__(self, path: Path, original_exc: yaml.YAMLError) -> None:` setting `self.path = path` and `self.original_exc = original_exc`, calling `super().__init__(...)` with a formatted message). Add a `path: Path` parameter to `_extract_frontmatter(text: str, path: Path) -> dict | None`. Change its `except yaml.YAMLError: return None` clause to `except yaml.YAMLError as exc: raise FrontmatterParseError(path, exc) from exc`. Update `_extract_frontmatter`'s one call site inside `_scan()` to pass `skill_md` as the new `path` argument. In `_scan()`, wrap the `_extract_frontmatter(text, skill_md)` call in a `try`/`except FrontmatterParseError as exc:` that prints `f"[skills-index] {exc.path}: frontmatter YAML parse error: {exc.original_exc}"` to `sys.stderr` and then `continue`s the loop (skipping this `SKILL.md`, same as today's drop behavior, but with a distinguishing message). The existing `if fm is None or "name" not in fm or "description" not in fm:` branch and its "missing frontmatter" message stay exactly as-is for the no-`---`-block and missing-key cases — only the new `FrontmatterParseError` path gets the new message.
- **Commit:** `fix(skills-index): fail loudly on frontmatter YAML parse errors instead of silent drop (#589)`

### Card 6: Add `test-skills-index.py` covering parse-error vs missing-frontmatter

- **Context:**
  - `plugins/mill/scripts/millpy-skills-index.py`
  - `plugins/mill/unit_tests/test-abandon.py`
  - `plugins/mill/unit_tests/_test_helpers.py`
- **Edits:** none
- **Creates:**
  - `plugins/mill/unit_tests/test-skills-index.py`
- **Deletes:** none
- **Moves:** none
- **Requirements:** Following the `importlib.util.spec_from_file_location` pattern used in `test-abandon.py` (needed because `millpy-skills-index.py`'s hyphenated filename cannot be `import`ed directly) to load `millpy-skills-index.py` as a module, write a unit test file with a `main()` entry point using the same `ok()`/`fail()` harness pattern as `test-wiki-client-retry.py`, using `safe_temp_dir()` from `_test_helpers` to build a fixture directory tree `<tmp>/plugins/testplugin/skills/<name>/SKILL.md`, and calling the loaded module's `_scan(repo_root)` directly against that fixture tree. Cover three cases: (a) **valid frontmatter** — a `SKILL.md` with a properly quoted `description:` value is included in `_scan()`'s returned dict under the `testplugin` key. (b) **no frontmatter block** — a `SKILL.md` with no `---`-delimited block at all is absent from `_scan()`'s result, and capturing stderr (via `contextlib.redirect_stderr` to an `io.StringIO`) shows a message containing "missing frontmatter". (c) **unquoted-colon parse failure (#589 repro)** — a `SKILL.md` whose `description:` value contains a bare unquoted `: ` substring (e.g. `description: One-shot: does a thing`) is absent from `_scan()`'s result, and the captured stderr message contains "parse error" (or equivalent distinguishing text) and does NOT contain "missing frontmatter" — asserting the two failure modes are now distinguishable per Card 5's fix.
- **Commit:** `test(skills-index): cover frontmatter parse-error vs missing-frontmatter distinction (#589)`

## Batch Tests

`verify:` runs `test-skills-index.py` (new, single-file scope) — the only file exercising `millpy-skills-index.py`'s frontmatter-handling logic; no other existing test references this script.
