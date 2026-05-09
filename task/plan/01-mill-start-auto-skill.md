# Batch: mill-start-auto-skill

```yaml
task: 41 (A) — mill-start --auto flag
batch: mill-start-auto-skill
number: 1
cards: 1
verify: null
depends-on: []
```

## Batch Scope

Single-card batch that adds the `--auto` flag to `mill-start` by editing one SKILL.md file. The batch delivers: (a) an `argument-hint:` line in the SKILL.md frontmatter declaring the new optional argument; (b) a new `## Auto mode` subsection placed between the introductory paragraph and `## Entry`, specifying how `--auto` changes Phase: Discuss and Phase: Discussion Review behaviour. No external interface is created — downstream skills (`mill-plan`, `mill-go`, `mill-merge`) are unchanged. Batch-local decisions: subsection placement is fixed (immediately after the introductory paragraph, before `## Entry`); cross-references inside `## Phase: Discuss` and `## Phase: Discussion Review` are NOT added (the upstream Auto mode section is the single source for `--auto` rules).

## Cards

### Card 1: Add `--auto` mode to mill-start SKILL.md

- **Context:**
  - `task/discussion.md`
  - `plugins/mill/skills/mill-self-report/SKILL.md`
  - `plugins/mill/skills/conversation/SKILL.md`
  - `plugins/mill/skills/mill-go/SKILL.md`
  - `plugins/mill/skills/mill-receiving-review/SKILL.md`
  - `plugins/mill/templates/discussion.md`
- **Edits:**
  - `plugins/mill/skills/mill-start/SKILL.md`
- **Creates:** none
- **Deletes:** none
- **Requirements:**
  Edit `plugins/mill/skills/mill-start/SKILL.md` to add a new `--auto` flag, with two distinct edits:

  **Edit 1 — frontmatter line.** Insert a new line `argument-hint: "[--auto]"` between the existing `description:` line and the closing `---` of the YAML frontmatter (the SKILL currently has only `name:` and `description:` keys in its frontmatter). The line is the literal string `argument-hint: "[--auto]"` — quoted exactly per the precedent at `plugins/mill/skills/mill-self-report/SKILL.md` line 4 (`argument-hint: "[--auto | free-text steering]"`).

  **Edit 2 — new `## Auto mode` subsection.** Insert a new `## Auto mode` heading and content block between the introductory paragraph (the line "You are a collaborative solution designer…", currently line 8) and the `## Entry` heading (currently line 10). Do NOT modify any text in `## Entry`, `## Phases` (any phase subsection: Color, Select, Active, Explore, Discuss, Discussion File, Discussion Review, Handoff), `## Principles`, or `## Board discipline`. The new subsection MUST contain the following five elements, in order:

  1. **Argument-detection rule.** A one-paragraph opener mirroring `plugins/mill/skills/mill-self-report/SKILL.md` line 63's prose pattern. The wording MUST start with the trigger phrase "If the skill argument is `--auto`" and state that the rules in this subsection override the default operator-interaction behaviour of Phase: Discuss and Phase: Discussion Review. State that the bare `--auto` flag is the only supported form (no `--auto=<value>`).

  2. **Phase: Discuss change.** A bulleted block specifying that under `--auto`:
     - Every operator prompt MUST be formatted as a numbered-options list per the `mill:conversation` rule "the recommended option, if any, MUST be option 1". Free-text questions are forbidden — the SKILL must coerce any candidate question into options.
     - Instead of waiting for operator input, the assistant immediately auto-picks option `1)` (the recommendation).
     - Each auto-pick is appended to discussion.md's `## Q&A log` section.

  3. **Q&A log format extension.** A code-fenced block stating the verbatim entry format used under `--auto`:
     ```
     - **Q:** <question> **A:** [auto-pick] <option-1-label>. **Why:** <rationale>.
     ```
     A one-sentence note that operator-driven entries keep the existing bare format (`- **Q:** … **A:** …`).

  4. **Phase: Discussion Review change.** A bulleted block specifying that under `--auto`:
     - Review still runs up to `max_review_rounds` (no skip).
     - The `mill-receiving-review` skill is still loaded before reading any review file (the existing non-negotiable rule applies). Under `--auto` the PUSH BACK path of the decision tree is unavailable: there is no operator to escalate to. Every gap returned by the reviewer is treated as FIX regardless of the decision-tree outcome (factually-wrong gaps included).
     - On `GAPS_FOUND`, the assistant auto-resolves each gap by adding the missing information to discussion.md using best judgment, commits, **pushes**, and re-runs the review.
     - If gaps remain after `max_review_rounds`: call `_status.append_phase(status_path, "blocked", _timestamp.now_utc_iso())`, then `_status.update_field(status_path, "blocked_reason", "auto: discussion review gaps unresolved after <N> rounds")` (substituting the actual round count for `<N>`), then `git -C <worktree> add task/status.md && git commit -m "mill-start: blocked (auto: discussion review gaps unresolved) for <slug>" && git push`, then halt with that message. Do NOT proceed to Handoff.

  5. **Orthogonality note.** A one-paragraph closer stating that `--auto` is independent from `pipeline.autonomous_mode`: `--auto` is a per-invocation flag controlling Phase: Discuss / Discussion Review behaviour in mill-start; `pipeline.autonomous_mode` is a config key controlling mill-go's stuck-handling. The Auto mode subsection neither reads nor writes `pipeline.autonomous_mode`. Operators opt into each separately.

  Style/format constraints:
  - The subsection heading is exactly `## Auto mode` (level 2, two hashes, sentence case).
  - Every helper named in the prose (`_status.append_phase`, `_status.update_field`, `_timestamp.now_utc_iso`) is rendered in inline code with backticks. Argument values (e.g. `"blocked"`, `"auto: discussion review gaps unresolved after <N> rounds"`) are double-quoted strings.
  - Cross-skill references use bare names (`mill:conversation`, `mill-self-report`, `mill-go`, `mill-receiving-review`) without file paths in prose; SKILL.md path references (e.g. `plugins/mill/skills/mill-self-report/SKILL.md`) are reserved for explicit "see line N of …" pointers.
  - Do NOT add cross-reference notes inside `## Phase: Discuss` or `## Phase: Discussion Review`. The Auto mode subsection is the single upstream source for `--auto` rules; the Phase sections remain unchanged.
  - Do NOT modify `plugins/mill/templates/discussion.md`. The Q&A log format extension is documented in this SKILL only.
  - Do NOT add any new field to `task/status.md` for the `--auto` flag itself. The audit trail lives in discussion.md.
  - Do NOT fire `/mill-self-report --auto` from any phase of mill-start. Self-report is fired by mill-plan / mill-go.

- **Commit:** `feat(mill-start): add --auto flag for hands-off discussion`

## Batch Tests

`verify: null`. The batch is pure SKILL.md prose with no runnable surface — no Python tests, no shell-runnable check, no lint rule applies. Verification is the holistic plan reviewer reading the resulting SKILL.md, then the downstream code review during mill-go. Manual smoke (operator-driven, post-merge): run `/mill-start --auto` against a small spawned task and confirm Phase: Discuss prompts use numbered options with auto-pick `1)`, Phase: Discussion Review behaves per the new rules, and `## Q&A log` entries use the `[auto-pick]` format.
