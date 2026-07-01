# Triage Report Schema

This file documents the canonical shape of the triage-report contract: the envelope every source adapter produces and the source-agnostic `mill-triage-to-tasks` skill consumes. Each adapter — `_gh_issues.to_contract()` for GitHub issues, `_sandbox_report.read()` for a local sandbox-report.json file — fills in the same fields, set once per adapter, so the analysis half never needs to know or branch on which source produced the envelope.

## File format

```json
{
  "source": "ghissues",
  "meta": {"repo": "owner/repo"},
  "items": [
    {"ref": "586", "title": "sandbox emitter follow-up", "body": "Full issue body text..."},
    {"ref": "591", "title": "triage adapter split", "body": "Full issue body text..."}
  ],
  "ref_prefix": "#",
  "detail_hint": "Run 'gh issue view #{ref}' for full detail.",
  "embed_body": false
}
```

```json
{
  "source": "sandbox-report",
  "meta": {"suite": "loomyard-sandbox"},
  "items": [
    {"ref": "S6", "title": "Verdict S6 — repro mismatch", "body": "FAIL: expected 200, got 500.\n\nRepro steps:\n1. POST /widgets with malformed payload\n2. Observe 500 instead of 400"},
    {"ref": "S7", "title": "Verdict S7 — timeout under load", "body": "FAIL: request exceeded 30s timeout under concurrent load.\n\nRepro steps:\n1. Run load-test.sh with 50 concurrent clients\n2. Observe timeouts after ~2 minutes"}
  ],
  "ref_prefix": "",
  "detail_hint": null,
  "embed_body": true
}
```

## Field table

| Field | Type | Required | Values / notes |
|---|---|---|---|
| `source` | string | yes | `"ghissues"` or `"sandbox-report"` |
| `meta` | object | yes | Adapter-owned passthrough — the analysis half never reads it. `_gh_issues.to_contract()` sets `{"repo": <owner/repo>}`; `_sandbox_report.read()` passes the file's own `meta` field through verbatim, defaulting to `{}` when absent |
| `items` | array of objects | yes | Each item is `{ref: string, title: string, body: string}`. May be an empty array — neither adapter decides "nothing to do"; that split belongs to the entry skill (empty array) and `mill-triage-to-tasks` (every item routed to skip after grouping) |
| `ref_prefix` | string | yes | Prepended to an item's `ref` when writing its Sources bullet. `"#"` for ghissues, `""` for sandbox-report |
| `detail_hint` | string or null | yes (key always present; value may be `null`) | A template containing a `{ref}` placeholder for a "how to see full detail" line. `"Run 'gh issue view #{ref}' for full detail."` for ghissues; `null` for sandbox-report, since the item's `body` already is the full content |
| `embed_body` | boolean | yes | Controls whether an item's `body` is written into the task body under its Sources bullet. `false` for ghissues (the `gh issue view` fallback above makes embedding redundant); `true` for sandbox-report (no external fallback exists once the source JSON file is deleted) |

## Per-Sources-bullet rendering

For every item in `items`, write a Sources bullet of the form `- Sources: <ref_prefix><ref> — <title>`. Immediately following that bullet:

- When the envelope's `detail_hint` is non-null, write the hint line with `{ref}` substituted from that same item's own `ref` — never from any other item's `ref`, even when multiple items land on the same task.
- When `embed_body` is true, write that item's `body` text immediately after the bullet (and after the hint line, when one was written).

This rendering applies identically regardless of where the bullet lands: a brand-new grouped task with one or more source items, or an existing task that an item is appended to via fold-in. A fold-in item gets the same `- Sources: ...` bullet, the same per-item `detail_hint` substitution, and the same `embed_body` handling as it would inside a new task — fold-in is not a special case.

## Produced by / Consumed by

- **Produced by:** `_gh_issues.to_contract()` (`plugins/mill/scripts/_gh_issues.py`) and `_sandbox_report.read()` (`plugins/mill/scripts/_sandbox_report.py`).
- **Consumed by:** `mill-triage-to-tasks` (`plugins/mill/skills/mill-triage-to-tasks/SKILL.md` — forward reference; this skill is written in a later batch of the same task that introduced this schema).
