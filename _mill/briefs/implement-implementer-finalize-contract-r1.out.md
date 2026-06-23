All 5 cards implemented, verified green, and pushed. Here is a summary of what was done:

**Card 6** (`_implementer_common.py`): Added `_batch_completeness_stuck` and `_in_scope_dirty_stuck` helpers. Added `card_count`, `task_dir`, `parent_branch` keyword-only params to both `_forward_output` and `finalize_from_output`. Wired both gates in the self-reported-success branch after the no-content-commit check.

**Card 7** (`_implementer_common.py`): Added completeness gate calls before each of the three inferred-success emit points in the `try` block.

**Card 8** (`millpy-implement.py`): Added `import re` and `import _parent_branch`. Compute `card_count` (regex count of `### Card N:` headings), `parent_branch` (non-interactive resolve, fallback `None`). Pass all three to both `finalize_from_output` and `_forward_output`.

**Card 9** (`implementer-brief.md`): Added anti-yield directive at top of Implementation discipline, mandatory pre-report self-check in Report section, and extended Test Integrity Guardrail with prohibition on dropping tests and on Shared-Decision-violating shortcuts.

**Card 10** (`test-implementer-common.py`): Added cases 27a, 27b (completeness gate), 28c, 28d (dirty-tree gate), 29e (backward compat). Fixed case 28c fixture to use a proper parent branch so `README.md` is in `owned_paths` and detectable as in-scope dirty.

{"status":"success","commit_sha":"e0270ae85e734d5808d7f60b8e5b3f5b22f882d4","session_id":"b79e4b22-ac17-4ec9-8974-02c19d9e672c"}
