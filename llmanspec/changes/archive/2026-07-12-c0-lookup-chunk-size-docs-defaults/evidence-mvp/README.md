# Evidence scripts (pinned)

Outputs MUST go under `.tmp/evidence-mvp/` (do not commit).

## Script

`repro_lookup_chunk_calls.py` — synthetic demand proving:

- omit / `0` → 1 loader call
- `lookup_chunk_size=N` → `ceil(unique_keys / N)` calls

```bash
uv run python llmanspec/changes/c0-lookup-chunk-size-docs-defaults/evidence-mvp/repro_lookup_chunk_calls.py
```

## Known results

- 300 keys / chunk 40 → 8 calls (`.tmp/evidence-mvp/exec-call-io/`)
