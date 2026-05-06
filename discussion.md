# Discussion: 17 (A) — SKILL.md API accuracy audit + implementer-brief contract fixes

```yaml
task: 17 (A) — SKILL.md API accuracy audit + implementer-brief contract fixes
slug: skill-api-audit
status: discussing
parent: main
```

## Problem

Four documented API mismatches in SKILL.md files and the implementer-brief template have survived two previous fix commits (6aac541, 5e36e1a). They cause silent failures when mill-go, mill-plan, mill-start, or mill-resume sessions follow the documented patterns verbatim: wrong call signatures raise `TypeError`, undocumented CLI flags go unused, and opaque return-type docs cause phase-gate logic to access the wrong dict key. One additional issue causes the implementer to report an unreliable or placeholder `session_id` in its final JSON because it was instructed to read a CLI flag it cannot access.

## Scope

**In:**
- `plugins/mill/skills/mill-go/SKILL.md` — fix `resolve_git_root(Path.cwd())` call, update `_status.read_full()` signature and phase-access pattern
- `plugins/mill/skills/mill-plan/SKILL.md` — fix `resolve_git_root(Path.cwd())` call, document `--max-rounds` flag in option B escape
- `plugins/mill/skills/mill-start/SKILL.md` — fix `resolve_git_root(Path.cwd())` call
- `plugins/mill/skills/mill-resume/SKILL.md` — fix both `resolve_git_root(Path.cwd())` calls (lines 14 and 40)
- `plugins/mill/templates/implementer-brief.md` — replace prose `<this-session-id>` placeholder with a `<SESSION_ID>` render token; update instruction text
- `plugins/mill/scripts/millpy-implement.py` — pass `SESSION_ID` token to `_render.render()`

**Out:**
- No changes to any Python helper signatures or logic beyond the `_render.render()` token addition in `millpy-implement.py`
- No changes to `_forward_output` or any other `millpy-implement.py` logic
- No changes to `_wiki.py`, `_status.py`, `_tasks_md.py`, `_plan_dag.py`
- No changes to other SKILL.md files not listed above
- No changes to plan templates, review templates, or other templates
- No changes to unit or integration tests (the SKILL.md changes are documentation only; the template change is tested by the existing `_render.render()` token-substitution path which is already covered)

## Decisions

### resolve-git-root-call-signature

- Decision: Remove the `Path.cwd()` positional argument from all `_paths.resolve_git_root()` calls in SKILL.md files. The function signature is `def resolve_git_root() -> Path` and reads `git rev-parse --show-toplevel` from the process cwd implicitly. No argument is accepted.
- Rationale: Every affected SKILL.md has `_paths.resolve_git_root(Path.cwd())` which raises `TypeError: resolve_git_root() takes 0 positional arguments but 1 was given` at runtime. The function has always operated on cwd implicitly; there is no variant that accepts a path.
- Rejected: Changing `resolve_git_root()` to accept an optional path arg — would paper over a doc bug by changing production code to match a wrong doc.

### read-full-return-structure

- Decision: Update the `_status.read_full()` signature line in mill-go SKILL.md to show the nested return structure explicitly: `-> {"yaml": dict, "timeline": list[str]}`. Add an explicit code snippet showing `phase = status["yaml"]["phase"]` and `blocked_reason = status["yaml"].get("blocked_reason")` immediately after the signature line, before the phase gate table.
- Rationale: The current doc shows `-> dict` with no structure. A builder following the phase gate table would naturally try `status["phase"]` and get `KeyError`. The actual return is a two-key dict where all YAML fields live under `"yaml"`.
- Rejected: Changing `read_full()` to return a flat dict — would break `millpy-implement.py`, `millpy-inspect.py`, and any other caller that already uses the nested structure correctly.

### max-rounds-option-b

- Decision: Update option B in mill-plan SKILL.md's max-rounds escape section. Where it currently says "B) Shallow — one more review round", add the explicit CLI invocation: `uv run --project "${CLAUDE_PLUGIN_ROOT}" "${CLAUDE_PLUGIN_ROOT}/scripts/millpy-review-plan.py" --max-rounds <N+1>`. Explain that without `--max-rounds`, the script re-reads the configured cap and immediately exits at max-rounds again.
- Rationale: The `--max-rounds` flag in `millpy-review-plan.py` exists specifically for this escape hatch. Without it, option B is non-functional — the script re-reads `review.plan.rounds` from config and the escape provides no extra round.
- Rejected: Having mill-plan bump `review.plan.rounds` in config — config edits are user-visible persistent changes; a one-shot override flag is cleaner.

### session-id-in-brief-template-approach

- Decision: Add a `SESSION_ID` render token to `implementer-brief.md`. Replace the prose `<this-session-id>` placeholder in both the success and stuck JSON examples with `<SESSION_ID>`. Replace the full instruction block that currently reads "`session_id` MUST be the exact UUID passed to you via the `--session-id` flag (you can read it from your own command-line arguments or echo it as given). Do not invent or paraphrase the value. mill-go uses this field to correlate the report with the spawned session." with: "`session_id` MUST be exactly `<SESSION_ID>` (the UUID shown in the example above — it was injected into this brief when it was rendered). Copy it verbatim." This replacement applies to both occurrences of the instruction block (success JSON and stuck JSON). In `millpy-implement.py`, add `"SESSION_ID": session_id` to the token dict passed to `_render.render()`.
- Rationale: A spawned Claude Code session cannot access the `--session-id` CLI flag used to launch it. The flag is consumed by the `claude` runner for session tracking; it is not exposed as a `sys.argv` entry or environment variable inside the running agent. The CLI already generates and knows the session UUID before rendering the brief, so embedding it as a token is the zero-risk path. Note: mill-go does not use `session_id` from the JSON for any functional purpose (resume uses `implementer_session` from status.md, which the CLI writes directly). The field is informational only.
- Rejected: CLI-patch approach (`_forward_output` reads `session_id` from `_implementer_sonnet.run()` and overwrites the JSON) — requires changing `_forward_output`'s signature, adds complexity, and is not necessary given the field is informational.

## Technical context

### Affected files and locations

- `plugins/mill/scripts/_paths.py:90` — `def resolve_git_root() -> Path:` — no args.
- `plugins/mill/scripts/_status.py:483` — `def read_full(status_path: Path) -> dict:` returns `{"yaml": dict, "timeline": list[str]}`. All status YAML fields (phase, blocked_reason, plan, etc.) live under `result["yaml"]`.
- `plugins/mill/scripts/millpy-review-plan.py:31-36` — `--max-rounds` arg defined: `parser.add_argument("--max-rounds", type=int, default=None, ...)`.
- `plugins/mill/scripts/millpy-implement.py:149` — `session_id = str(uuid.uuid4())` generated before the render call; `_render.render()` call is at line ~198 with existing token dict.
- `plugins/mill/templates/implementer-brief.md:66-77` — success/stuck JSON examples with `<this-session-id>` prose placeholders and the "read from `--session-id` flag" instruction.
- `plugins/mill/scripts/_implementer_sonnet.py` — `run()` returns `(text, session_id)`. The second element is the actual session_id extracted from Claude's stream events. `millpy-implement.py` currently discards it with `output, _ = _implementer_sonnet.run(...)`.

### `_render.render()` token substitution

`_render.render(template_path, tokens)` substitutes `<TOKEN>` placeholders verbatim. The HTML comment block at the top of templates is stripped. Adding a new token requires only adding the key to the dict; no changes to `_render.py` needed. The `<SESSION_ID>` token follows the same pattern as `<TASK_TITLE>`, `<SLUG>`, etc.

### SKILL.md instruction contract

SKILL.md files are loaded as prompts — they are not Python and are not executed. All "signature:" lines are documentation for the LLM session. A wrong signature causes the LLM to call the function incorrectly; there is no static type check.

### mill-go phase gate and read_full

The phase gate in mill-go (Entry step 5) calls `_status.read_full(status_path)` and branches on `phase`. Current doc implies `status["phase"]`; correct is `status["yaml"]["phase"]`. The `blocked_reason` field referenced in the `blocked` row is similarly at `status["yaml"].get("blocked_reason")`.

## Testing

All SKILL.md changes are documentation — no automated test coverage applies. Verify manually by running a mill-start → mill-plan → mill-go sequence in a test worktree.

For `millpy-implement.py` template token addition:
- The existing `millpy-implement.py` integration test (if any) should still pass unchanged; the only change is adding one entry to the token dict.
- The `implementer-brief.md` template change (`<SESSION_ID>` token) should be verified by checking the rendered brief in a test run: the UUID from `millpy-implement.py:149` should appear verbatim in the success/stuck JSON examples.
- No new unit tests are needed: `_render.render()` token substitution is already tested; the addition of a new token to an existing call site is not a novel code path.

## Q&A log

- **Q:** Issue D — template approach, CLI-patch, or both? **A:** Template approach only. The field is informational; no need to also patch `_forward_output`.
- **Q:** Should mill-start SKILL.md be fixed here (it has the same `resolve_git_root(Path.cwd())` bug)? **A:** Yes — included in scope.
- **Q:** Any issues beyond A–D? **A:** No.
