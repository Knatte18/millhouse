# Batch: contract-adapters

```yaml
task: "Split mill-ghissues-to-tasks into source adapter + source-agnostic analysis"
batch: contract-adapters
number: 1
cards: 3
verify: "PYTHONPATH= uv run --project plugins/mill python plugins/mill/unit_tests/run-all.py --only test-gh-issues.py test-sandbox-report.py"
depends-on: []
```

## Rename mechanic

Not applicable — this batch has no `Moves:` entries.

## Batch Scope

This batch delivers the two Python halves of the triage-report contract: the ghissues-side mapper (`_gh_issues.to_contract()`) and the new sandbox-report-side reader/validator (`_sandbox_report.py`), plus the schema document (`triage-report.schema.md`) that pins the contract shape down for every later batch. It is one batch because all three pieces describe the same envelope `{source, meta, items[{ref,title,body}], ref_prefix, detail_hint, embed_body}` and must agree byte-for-byte — splitting them risks one piece drifting from the other two before the shared skill (batch 2) ever consumes them. This batch has no dependencies and is the external interface every later batch is written against: batch 2 (`mill-triage-to-tasks`) is written assuming `to_contract()` and `_sandbox_report.read()` already exist and return exactly this shape.

No batch-local decisions beyond `## Shared Decisions` in the overview.

## Cards

### Card 1: `_gh_issues.to_contract()` ghissues adapter mapping

- **Context:**
  - `_mill/discussion.md`
  - `plugins/mill/scripts/_gh_issues.py`
- **Edits:**
  - `plugins/mill/scripts/_gh_issues.py`
  - `plugins/mill/unit_tests/test-gh-issues.py`
- **Creates:** none
- **Deletes:** none
- **Moves:** none
- **Requirements:**
  - Add `to_contract(issues: list[dict[str, Any]], repo: str) -> dict[str, Any]` to `_gh_issues.py`, placed after `fetch_one()` and before `close_with_comment()`. Maps each issue dict in `issues` (each shaped like one entry of `fetch()`'s return value: `number, title, body, labels, createdAt`) into a contract item `{"ref": str(issue["number"]), "title": issue["title"], "body": issue["body"]}`. Returns the full contract envelope: `{"source": "ghissues", "meta": {"repo": repo}, "items": <mapped list, same order as input>, "ref_prefix": "#", "detail_hint": "Run 'gh issue view #{ref}' for full detail.", "embed_body": False}`. `fetch()` and `fetch_one()` are not modified — `to_contract()` takes their output as input, it does not replace them.
  - Add a docstring on `to_contract()` matching the style of `fetch()`/`fetch_one()` (one-line summary, `Args:`, `Returns:`).
  - Update the module docstring's `Public API:` list at the top of `_gh_issues.py` to add a `to_contract(issues, repo) -> dict` entry, one line, same format as the existing four entries (e.g. `to_contract(issues, repo) -> dict: Maps fetch()-shaped issue dicts into the triage-report contract shape (see plugins/mill/templates/triage-report.schema.md).`).
  - In `test-gh-issues.py`, add a new test function (e.g. `test_to_contract_maps_issues_to_triage_contract() -> int`) following the exact style of the existing `test_detect_repo_*` functions: an `errors = 0` counter, `PASS:`/`FAIL:` prints to stdout/stderr per the file's convention, return the error count. Build 2–3 in-memory issue dicts (no subprocess mocking needed — `to_contract()` is a pure function) and assert: each item's `ref` equals `str(issue["number"])`; `result["meta"]["repo"]` equals the passed `repo` argument; `result["ref_prefix"] == "#"`; `"{ref}" in result["detail_hint"]`; `result["embed_body"] is False`; `result["source"] == "ghissues"`; item `title`/`body` pass through unchanged; item ordering matches input ordering.
  - Call the new test function from `main()` exactly like the existing `test_detect_repo_*` calls (`errors += test_to_contract_maps_issues_to_triage_contract()`), placed after the existing `test_detect_repo_*` calls and before the final `if errors:` block.
- **Commit:** `feat(gh-issues): add to_contract() for triage-report contract mapping`

### Card 2: `_sandbox_report.py` adapter + tests

- **Context:**
  - `_mill/discussion.md`
  - `plugins/mill/scripts/_gh_issues.py`
  - `plugins/mill/unit_tests/test-gh-issues.py`
- **Edits:** none
- **Creates:**
  - `plugins/mill/scripts/_sandbox_report.py`
  - `plugins/mill/unit_tests/test-sandbox-report.py`
- **Deletes:** none
- **Moves:** none
- **Requirements:**
  - `_sandbox_report.py`: same overall style as `_gh_issues.py` — module docstring with a `Public API:` section documenting `read(path: Path) -> dict`, a dedicated exception class `SandboxReportError(RuntimeError)` (mirrors `GhError`), `from __future__ import annotations`, stdlib-only imports (`json`, `pathlib.Path`, `typing.Any`) plus `_paths` only if needed for path resolution (not required — `read()` takes an already-resolved `Path`).
  - `read(path: Path) -> dict[str, Any]`:
    - Open and parse `path` as JSON. On file-not-found or `json.JSONDecodeError`, raise `SandboxReportError` with a message naming the path and the underlying error.
    - Require the parsed top-level value to be a JSON object (dict). Require `data.get("source") == "sandbox-report"` — on any other value (including missing key), raise `SandboxReportError` naming the path and the actual `source` value found (treat this as "wrong file passed", per `_mill/discussion.md` Decision "`_sandbox_report.py` validates strictly").
    - Require `items` to be present and to be a JSON array (list) — raise `SandboxReportError` if the key is missing or not a list. An empty list (`[]`) is valid and must NOT raise (per `_mill/discussion.md`: `read()` never decides "nothing to do" — that split belongs to the entry skill / shared skill in later batches).
    - For each entry in `items`: require it to be a dict with non-empty string values for `ref`, `title`, `body` — raise `SandboxReportError` naming the offending item's index and the missing/empty field on any violation.
    - Track every `ref` seen so far in a `set`; if any `ref` repeats, raise `SandboxReportError` naming the duplicate `ref` value.
    - On success, return `{"source": "sandbox-report", "meta": data.get("meta", {}), "items": [{"ref": i["ref"], "title": i["title"], "body": i["body"]} for i in items], "ref_prefix": "", "detail_hint": None, "embed_body": True}`. `meta` is passed through verbatim from the file's own `meta` field, defaulting to `{}` when the field is absent — this function never reads or interprets `meta`'s contents.
    - Any `print()`/error output stays ASCII-only (no em-dash, no `->` — spell out ` -- ` / ` -> `) per project convention.
  - `test-sandbox-report.py`: same hand-rolled style as `test-gh-issues.py` (`errors = 0` counter, `PASS:`/`FAIL:` prints, `main() -> int` returning the error count, `sys.exit(main())` at the bottom, the same `HUB = Path(__file__).resolve().parent.parent.parent.parent` + `sys.path.insert` header to import `_sandbox_report`). Use `tempfile.TemporaryDirectory()` + `json.dump()` to write fixture files, then call `_sandbox_report.read(Path(...))`. Cover, at minimum, one test (function or inline block in `main()`) per case:
    1. Valid file with two well-formed items → returns `ref_prefix == ""`, `detail_hint is None`, `embed_body is True`, items map correctly, and `meta` equals the file's own `meta` value when present.
    2. Valid file where the `meta` key is entirely absent → returned `meta == {}`.
    3. Valid file with `items: []` → returns successfully with `items == []` (no exception).
    4. An item missing `ref` (or `title`, or `body`) → `read()` raises `SandboxReportError`.
    5. `source` set to something other than `"sandbox-report"` (e.g. `"ghissues"` or missing entirely) → raises `SandboxReportError`.
    6. Two items sharing the same `ref` → raises `SandboxReportError` naming that `ref`.
    7. A file containing invalid JSON syntax → raises `SandboxReportError`.
    8. A file whose top-level parsed JSON value is not an object (e.g. a bare JSON array or string) → raises `SandboxReportError` (not an uncaught `AttributeError` from calling `.get()` on a non-dict).
- **Commit:** `feat(sandbox-report): add _sandbox_report.py contract reader with tests`

### Card 3: `triage-report.schema.md` contract documentation

- **Context:**
  - `_mill/discussion.md`
  - `plugins/mill/templates/review-output.schema.md`
  - `plugins/mill/scripts/_gh_issues.py`
  - `plugins/mill/scripts/_sandbox_report.py`
- **Edits:** none
- **Creates:**
  - `plugins/mill/templates/triage-report.schema.md`
- **Deletes:** none
- **Moves:** none
- **Requirements:**
  - Mirror `review-output.schema.md`'s structure: an H1 title, a one-paragraph framing statement, a `## File format` section with a fenced example, a field table, and cross-reference sections. No `---` frontmatter (reserved for SKILL.md and plugin manifests).
  - Document the full envelope shape with a field table (field name, type, required, values/notes) covering exactly: `source` (string, required, `"ghissues" | "sandbox-report"`), `meta` (object, required, adapter-owned passthrough — "the analysis half never reads it"), `items` (array of objects, required, each `{ref: string, title: string, body: string}`), `ref_prefix` (string, required, prepended to `ref` when writing a Sources bullet), `detail_hint` (string or null, required key — value may be `null`, a template containing a `{ref}` placeholder), `embed_body` (boolean, required, controls whether an item's `body` is written into the task body under its Sources bullet).
  - Include two full JSON examples: one `ghissues`-sourced contract (2 items) and one `sandbox-report`-sourced contract (use/adapt the example from the originating issue: items keyed by `ref` like `"S6"`, `title`, `body` containing a verdict + repro steps).
  - Document the per-Sources-bullet rendering convention as prose (not code): for every item, write `- Sources: <ref_prefix><ref> — <title>`; immediately follow with the `detail_hint` line (substituting that item's own `ref` into the `{ref}` placeholder) when `detail_hint` is non-null; immediately follow with the item's `body` text when `embed_body` is true. State explicitly that this applies identically whether the item lands in a brand-new grouped task or is appended via fold-in to an existing task.
  - Add a short "Produced by / Consumed by" section: produced by `_gh_issues.to_contract()` and `_sandbox_report.read()` (cite both file paths); consumed by `mill-triage-to-tasks` (cite the skill path once it exists — `plugins/mill/skills/mill-triage-to-tasks/SKILL.md` — as a forward reference, since that skill is written in batch 2).
- **Commit:** `docs(triage-report): add contract schema doc`

## Batch Tests

`verify:` runs `run-all.py --only test-gh-issues.py test-sandbox-report.py` — covers Card 1's extension to `test-gh-issues.py` and Card 2's new `test-sandbox-report.py`. Card 3 is a pure documentation file with no runnable surface; it is verified by Card 1/2's tests staying green (the schema doc must describe exactly what those two modules implement) and by manual read-through during code review.
