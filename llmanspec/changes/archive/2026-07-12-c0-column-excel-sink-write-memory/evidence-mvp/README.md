# Evidence scripts (pinned)

Outputs MUST go under repo `.tmp/evidence-mvp/` (do not commit result bins/xlsx).

## Scripts

| Script | Purpose |
|---|---|
| `repro_write_only_ab.py` | Fresh-process A/B: force `write_only=False` vs production `write_only=True` close |
| `repro_peak_measure.py` | Measure current `ColumnExcelSink` peak RSS / close time at a given shape |

## Commands

```bash
# A/B (default 50k×300)
uv run python llmanspec/changes/c0-column-excel-sink-write-memory/evidence-mvp/repro_write_only_ab.py --rows 50000 --cols 300

# Peak retest (e.g. 100k×300)
uv run python llmanspec/changes/c0-column-excel-sink-write-memory/evidence-mvp/repro_peak_measure.py --rows 100000 --cols 300 --max-rss-gb 28
```

## Known results (local, 2026-07-12)

- A/B 50k×300: peak 5.52GB → 1.23GB; close 103s → 77s (`.tmp/evidence-mvp/column-excel-write-only-ab/20260712T084537Z/`)
- Climb pre-fix: 300k×300 peak 26.45GB (non-write_only era)
