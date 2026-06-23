# Batch: reviewer-anti-oscillation

```yaml
task: "Fix nit-enforcement gate, Windows verify false-positive, reviewer oscillation, and scope-violation handling"
batch: reviewer-anti-oscillation
number: 4
cards: 5
verify: PYTHONPATH= uv run --project plugins/mill python plugins/mill/unit_tests/run-all.py --only test-review-code-flow.py test-review-common.py
depends-on: [2]
```

## Batch Scope

Fixes #518a — the code reviewer re-escalates settled non-issues because it gets no prior-round context. Adds a curated "settled non-blocking" digest path: a new `--prior-notes <file>` CLI arg on `millpy-review-code.py`, threaded into `_review_code.prepare()` as an always-set `prior_nonblocking` kwarg (default `"(none)"`), rendered into the code-review templates as a new `<PRIOR_NONBLOCKING>` token with an escalation-justification rule. mill-go assembles the digest from the previous round's review file and passes `--prior-notes`. The `reviews/` read-ban stays. Depends on batch 2 (shared `mill-go/SKILL.md` write ordering). Runs in parallel with batch 3.

## Cards

### Card 11: --prior-notes CLI arg on millpy-review-code

- **Context:**
  - `plugins/mill/scripts/_review_code.py`
- **Edits:**
  - `plugins/mill/scripts/millpy-review-code.py`
- **Creates:** none
- **Deletes:** none
- **Requirements:** Add an optional `--prior-notes <path>` argument to `millpy-review-code.py` (mirror the existing `--extra-file` argument's wiring). Pass `args.prior_notes` (path or `None`) into BOTH dispatch branches: the `--stage prepare` branch's `prepare(...)` call AND the `--stage full` branch's `run(...)` call (around lines 127 and 175). The full/`run()` path is the dominant subprocess/psmux dispatch — omitting it there would silently drop the digest. Do not change behaviour when the flag is absent.
- **Commit:** `feat(review-code): add --prior-notes CLI argument (prepare + run)`

### Card 12: thread prior_nonblocking into prepare() unconditionally

- **Context:**
  - `plugins/mill/scripts/_review_common.py`
  - `plugins/mill/scripts/millpy-review-code.py`
- **Edits:**
  - `plugins/mill/scripts/_review_code.py`
- **Creates:** none
- **Deletes:** none
- **Requirements:** In `_review_code.prepare()`, add a keyword-only `prior_notes: Path | None = None` parameter. Build the digest string: if `prior_notes` is a readable file, use its text; otherwise use the literal `"(none)"`. ALWAYS set `prompt_kwargs["prior_nonblocking"]` to that string (unconditionally — `render_prompt` raises `KeyError` on any unresolved `<TOKEN>` once the templates carry `<PRIOR_NONBLOCKING>`, so a missing default would crash round 1). The kwarg key `prior_nonblocking` maps to the `<PRIOR_NONBLOCKING>` template token via the existing upper-casing in `render_prompt`. ALSO add the same `prior_notes: Path | None = None` keyword-only parameter to `_review_code.run(...)` (signature at line 404) and forward it to the `prepare(...)` call that `run()` makes internally — otherwise the `--stage full`/subprocess path never sees the digest. Do not touch `_review_common.py`.
- **Commit:** `feat(review-code): thread prior_notes through prepare() and run()`

### Card 13: add <PRIOR_NONBLOCKING> section to code-review templates

- **Context:**
  - `plugins/mill/scripts/_review_code.py`
- **Edits:**
  - `plugins/mill/templates/review-code-holistic.md`
  - `plugins/mill/templates/review-code-batch.md`
- **Creates:** none
- **Deletes:** none
- **Requirements:** Add a `<PRIOR_NONBLOCKING>` token to both code-review templates with surrounding instruction: "The following items were judged non-blocking in a prior round. Do NOT escalate any of them to BLOCKING unless NEW information justifies it -- a new diff, a real reproducible failure, or a concrete in-repo convention. If you escalate, you MUST state the new information explicitly." Also add an in-repo-analog anchoring line: "Prefer the convention already used by analogous code in the provided source files over a stricter alternative." This card ONLY adds the `<PRIOR_NONBLOCKING>` token (plus its surrounding instruction) — it must NOT remove, move, or alter the existing `<TOOL_RULE>` token. The literal "Do NOT read `reviews/`" string is NOT in the template; it is produced at render time by `_review_common.build_tool_rule` (`_TOOL_RULE_*`) and substituted into `<TOOL_RULE>`, so leaving that token in place preserves the read-ban. The `<PRIOR_NONBLOCKING>` token renders to `(none)` on round 1.
- **Commit:** `feat(review-templates): inject prior-non-blocking digest + escalation rule`

### Card 14: mill-go assembles and passes the prior-notes digest

- **Context:**
  - `plugins/mill/scripts/millpy-review-code.py`
  - `plugins/mill/scripts/_review_common.py`
- **Edits:**
  - `plugins/mill/skills/mill-go/SKILL.md`
- **Creates:** none
- **Deletes:** none
- **Requirements:** In `mill-go/SKILL.md`'s code-review dispatch (per-batch and holistic), before round N>1 add a step that extracts from the previous round's review file (same scope) each `### [NIT]`/non-blocking finding's heading title plus a one-line reason, writes them to a digest file under `_mill/briefs/` (or `.scratch/`), and passes `--prior-notes <digest-path>` in the `millpy-review-code.py` dispatch `<args>`. Round 1 passes no `--prior-notes` (digest defaults to `(none)`). State that the `reviews/` read-ban for the reviewer is unchanged — only the curated digest reaches it. ASCII-only.
- **Commit:** `feat(mill-go): feed prior-round non-blocking digest to code reviewer`

### Card 15: tests for prior-notes plumbing and token rendering

- **Context:**
  - `plugins/mill/scripts/_review_code.py`
  - `plugins/mill/templates/review-code-holistic.md`
- **Edits:**
  - `plugins/mill/unit_tests/test-review-code-flow.py`
  - `plugins/mill/unit_tests/test-review-common.py`
- **Creates:** none
- **Deletes:** none
- **Requirements:** In `test-review-code-flow.py`, assert that `prepare()`/`run()` with a `--prior-notes` file renders the digest text into the prompt under the `<PRIOR_NONBLOCKING>` token, and that without it the prompt renders `(none)` (round 1) without raising `KeyError`. Assert the rendered prompt still contains the `Do NOT read reviews/` tool-rule text and the new escalation-justification clause. Use the existing stub-reviewer harness. In `test-review-common.py`, add a render-level case if the existing `render_prompt` tests are the right home for the token-default assertion; otherwise keep the assertions in the flow test.
- **Commit:** `test(review-code): cover prior-notes digest and token default`

## Batch Tests

`verify:` runs `test-review-code-flow.py` and `test-review-common.py` — the suites covering reviewer prompt construction and `render_prompt`. The `mill-go/SKILL.md` edit (digest assembly) has no unit surface and is plan-reviewer validated. Key scenarios: digest-present vs absent rendering, no-KeyError on round 1, read-ban text preserved.
