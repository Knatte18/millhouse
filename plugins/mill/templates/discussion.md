<!--
Template: `<WIKI_PATH>/active/<slug>/discussion.md` — written by mill-start
at the start of Phase: Discussion File.

Tokens: <TASK_TITLE>, <SLUG>, <PARENT_BRANCH>.

The rendered file must be SELF-CONTAINED: a fresh mill-plan session with
zero conversation history must be able to write a complete implementation
plan from this file alone. Fill every section in place; do not leave
heading-only skeletons. Delete this HTML comment before writing.
-->
# Discussion: <TASK_TITLE>

```yaml
task: <TASK_TITLE>
slug: <SLUG>
status: discussing
parent: <PARENT_BRANCH>
```

## Problem

_One or two paragraphs stating the problem in the user's terms. No
jargon the user didn't introduce first. Include **why now** — what
changed, what broke, what deadline._

## Scope

**In:** _bullet list of what this task changes._

**Out:** _bullet list of what it explicitly does not touch. Anything a
reader might assume is included but isn't belongs here._

## Decisions

_One subsection per design decision. Each subsection states the
decision, the rationale, and the rejected alternatives (briefly)._

### <decision-short-name>

- Decision: …
- Rationale: …
- Rejected: …

## Technical context

_What mill-plan needs to know about the codebase to write the plan:
relevant modules, shared helpers to reuse, gotchas discovered during
exploration. Link to files where useful._

## Constraints

_Enumerate constraints from CONSTRAINTS.md if present, plus any
discovered during discussion. Absent constraints section → delete the
heading before writing; don't leave it empty._

## Testing

_Per-module test approach. Name the TDD candidates explicitly. Identify
scenarios that must be covered. Avoid prescribing exact assertion
shapes — that's mill-plan's job._

## Q&A log

_Running record of the most important questions the user answered.
Not a verbatim transcript — the distilled decisions belong under
Decisions. This section captures the edge cases and tie-breakers that
would otherwise be lost. One entry per line:_

- **Q:** … **A:** …
