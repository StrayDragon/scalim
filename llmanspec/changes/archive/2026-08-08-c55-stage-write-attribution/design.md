# Design: write stage 归因

## 现状

```
Plan ops: LOAD / LOAD_REF / COMPUTE  →  timed as loader/compute
Real I/O: pipeline column write / row flush / sink.close()  →  NOT timed as write
```

`stage_map` 虽有 WRITE_*→write，但计划层不产出这些算子 → write 恒 0。

## 方案

**Instrument real sink paths**（推荐），不恢复 PlanBuilder WRITE_*。

1. Column mode：包裹 `_write_main_source_columns` / column target writes。
2. Streaming：在 `_write_row` / finalize drain 累加 write；若处于 load/compute span 内则扣回。
3. Optional：`sink.close()` / workbook save → write 或单独 `finalize` 桶（须在文档与 schema 中标明口径；若进 write，pipeline_end 要能合并进 metrics）。

## 与 c50 关系

c50 先提供 nodes[] / run_stats / 警告底座；c55 修好后 `stages_total.write` 才可作为优化证据。c50 期间文档 MUST 声明 write 归因未完成，避免用户用 write=0 下结论。
