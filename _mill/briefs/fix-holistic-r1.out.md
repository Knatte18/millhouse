Task: apply NIT-only fixes from holistic code review round 1 for `mill-plan-skilldoc-and-logic-bugs`, per `_mill/briefs/fix-holistic-r1.md`.

One finding in the review file:

**[NIT:consistency] `load_config` call sentence not placed "immediately before" the signature line** (`plugins/mill/skills/mill-plan/SKILL.md:38-42`)
- VERIFY: accurate — implementation places the `cfg = _config.load_config(...)` sentence as the second sentence of the paragraph rather than immediately before the trailing `signature:` line, as the card literally specified.
- HARM CHECK: fix breaks something. The card's literal placement would put the sentence *after* the sentences that read `roles.plan-review.holistic.rounds`/`min_rounds`/`pipeline.*` fields off `cfg` — i.e. it would document reading fields off `cfg` before `cfg` is ever assigned, a real sequencing bug in the runbook prose. The reviewer's own note agrees: "current placement is arguably better."
- Action: **PUSH BACK** — no code change. Reviewer already marked this "Fix: N/A (findings only)".

No tracked modifications, HEAD unchanged from the holistic-fix housekeeping baseline (`fa973787ec28c487f81394247795e1ffd29472e9`) — this is the legitimate no-op case the brief allows for.

{"status":"success","commit_sha":"fa973787ec28c487f81394247795e1ffd29472e9","session_id":"e786c522-74d1-4b10-838b-ddbef4e5c48f"}
