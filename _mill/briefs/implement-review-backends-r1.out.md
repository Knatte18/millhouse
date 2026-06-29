All 4 test files pass. Final structured status report:

```json
{
  "session_id": "c9490a3d-749d-4af8-ae06-c5f94fc1f397",
  "batch": "04-review-backends",
  "status": "DONE",
  "verify": "PASS",
  "cards": [
    {"id": 18, "title": "Bulk Move sources for plan review", "status": "committed", "commit": "0f3d703e"},
    {"id": 19, "title": "Bulk Move targets in code review", "status": "committed", "commit": "275411dd", "note": "Combined with Card 20 (import dependency)"},
    {"id": 20, "title": "Pure planned-rename finding helper", "status": "committed", "commit": "275411dd", "note": "Combined with Card 19"},
    {"id": 21, "title": "Splice advisory rename NIT into per-batch finalize", "status": "committed", "commit": "a5c5bddf"},
    {"id": 22, "title": "Detect language from move endpoints", "status": "committed", "commit": "0583aad6", "note": "Amended to fix pre-existing PARENT_BRANCH token gap in test_render_implementer_brief"}
  ]
}
```
