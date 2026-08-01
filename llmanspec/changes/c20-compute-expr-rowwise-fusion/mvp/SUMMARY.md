# 一次本机跑数摘要（可复现）

命令：

```bash
uv run python llmanspec/changes/c20-compute-expr-rowwise-fusion/mvp/repro_nxm_framework_tax.py --runs 3
```

默认参数：`rows=4000`，`wide_fields=40`，`narrow_fields=2`，`deps=2`。

| 对照 | 结果（本机 sample） |
|------|---------------------|
| 引擎：40 字段 vs 2 字段薄 call_by | 端到端耗时约 **5.2×**（字段多了 20×，时间约 5×——还有固定开销，但量级同向） |
| 引擎调用次数 | wide `160000` = 4000×40；narrow `8000` = 4000×2 |
| 微循环依赖读取 | field-major `320000` = N×M×D；row-wise `8000` = N×D；比值 **40×** |
| 微循环耗时 | row-wise 相对 field-major 约 **2.8×** 更快（上界直觉，非已落地引擎） |

完整 JSON：`evidence/sample-result.json`。

## 设计收口（与引擎落地对齐）

| 项 | 钉死 |
|----|------|
| deps | 完全相同才进一组 |
| 行 / 列 | 行可融合；列 sink 不融合 |
| memo | EXP memo 命中 → 整组不融合 |
| 调用次数 | 融合后仍 `N×M`（不少调 calculator） |
| 与 c10 | 两 change；共享物化原语 |
