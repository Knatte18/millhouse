---
name: mill-descope-batch
description: remove a not-yet-started batch from an approved plan's Batch Index.
---

# mill-descope-batch

Removes one batch from the plan's Batch Index, moves its card file to a sibling `descoped/`
directory, prunes it from `status.md`, and commits + pushes the result on the task branch.

## Run it

```bash
PYTHONPATH="${CLAUDE_PLUGIN_ROOT}/scripts" "$MILL_PYTHON" "${CLAUDE_PLUGIN_ROOT}/scripts/millpy-descope-batch.py" <batch-name>
```

Refuses to run against a batch whose `status.md` state is anything other than `pending` (i.e.
already started or landed), and refuses to remove a batch that other surviving batches still
declare in their `depends-on:`.
