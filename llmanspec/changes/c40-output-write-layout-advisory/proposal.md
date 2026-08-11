---
depends_on: []
---

# Output write layout advisory（L1）

> 一句话: 在 opt-in 观测中输出写出布局**建议**（如宽表可试 `column_window`）；默认不改 sink；禁止静默 auto。  
> 来源: `llmanspec/notplan/c40-output-write-layout-advisory/` → 本草案；依赖已落地的 c30 `OutputWriteLayout`。  
> 研究页: `research/write-layout-advisory-explainer.html`

## Why

宽表 Excel 用 `COLUMN_WINDOW` 实测峰值显著低于 `COLUMN_HOLD`，但默默切换会改变峰值时机与可复现性。  
需要 **可观测建议** 让人/agent 显式改 `DemandRunRuntimeOptions.output_write_layout`，而不是热路径猜。

## What Changes（草案范围）

### A. 阈值校准（原路线 1）

- 采信离线双跑证据（不进主路径）: `scripts/bench_output_write_layout_dual_run.py`
- medium 结果（2026-08-11，`.tmp/evidence/.../dual_run.json`，不入库）:

| shape | cells 量级 | RSS 比 H/W | 墙钟比 W/H | suggest_window |
|-------|------------|-------------|------------|---------------|
| m_20k_50 | ~102 万格 | 2.46× | 1.019 | true |
| m_50k_50 | ~255 万格 | 4.87× | 1.025 | true |
| m_20k_100 | ~202 万格 | 3.54× | 1.022 | true |

- **初稿启发式候选**（须在 propose/apply 固化为闭集常量 + 可测）:
  - `wide_excel_peak_risk`: IR excel + effective `column_hold` + `n_fields * n_rows >= 1_000_000`（约百万格）→ 建议 `column_window`，`safe=true`
  - 或/兼: 有 peak 观测且（启发式体积）相对阈值偏高时升级建议
  - `composition_row_only` / `already_optimal` / `insufficient_shape` 见下方 schema
- 双跑脚本仅校准；**禁止**默认 `run_ir` 双写出

### B. 挂点草案（原路线 2）

| 候选挂点 | 现状 | 建议用法 |
|----------|------|----------|
| `run_stats` → `hints.write_layout` 或 `notes[]` typed | `WorkflowStatsAccumulator.build_run_stats` 已有 `notes` 字典；`schema=scalim_run_stats/v1` | **首选**：扩展 typed hint；仅 `bench`/`bench_plus`/显式 opt-in |
| `PerformanceConfig.include_advisor_hints` | 已有阶段占比/cache 文本 hints（`performance_presentation._iter_advisor_hints`） | **可复用开关哲学**；write-layout 宜 structured JSON，勿只塞英文长句 |
| 默认 baseline 观测 | 无 | **关闭**；零默认行为变化 |

需要实现期补齐的输入：`current_effective` layout（装配后）、`n_fields`、`n_rows`（跑后）、是否 composition、是否显式 layout。装配前只能粗标签，不能安全 auto。

### L1 hint schema（草案）

```json
{
  "suggested": "column_window",
  "current_effective": "column_hold",
  "reason_code": "wide_excel_peak_risk",
  "reason_detail": "n_fields*n_rows=1200000 exceeds threshold",
  "action": "set DemandRunRuntimeOptions(output_write_layout=OutputWriteLayout.COLUMN_WINDOW)",
  "safe": true
}
```

`reason_code` 闭集: `wide_excel_peak_risk` | `composition_row_only` | `already_optimal` | `insufficient_shape`

### 正确性立场（研究结论摘要）

在 **合法 IR 列式路径**（`format=excel`、`streaming=False`、无 composition、pipeline 按 batch `set_row_ids`）下，HOLD↔WINDOW **业务格子等价**（测试矩阵对拍；双跑 `rows_equal`）。  
**不是** xlsx 字节相等；非法组合 **fail-fast** 而非静默错写。详见 `research/write-layout-advisory-explainer.html` §正确性。

## 非目标

- 默认 / 静默自动切换 layout
- YAML 配置阈值或 layout
- 主路径为 advisory 双跑写出
- L2 opt-in auto（另案 + RSS 门控）

## Capabilities

### New Capabilities

- `observability-output-write-layout-advisory`: L1 建议 schema 与「不改行为」契约

### Modified Capabilities

- `performance-observability` / run_stats: 可选 hints（opt-in）

## Impact

- 默认写出行为 **不变**
- 观测税仅在 bench / 显式开关
- composition 路径不得建议无效 WINDOW（`safe=false` + 迁 IR）

## Open Questions（propose 前拍板）

1. hint 落 `run_stats.hints.write_layout` vs 扩展现有 performance advisor？
2. 百万格阈值是否改为「格数 + peak_mb」双条件？
3. 是否需要 snapshot 契约测（hint JSON 形状）？

## Research

- 通俗说明 + 双跑图 + 假想 hint UI: [`research/write-layout-advisory-explainer.html`](research/write-layout-advisory-explainer.html)
- 旁路 canvas（IDE）: Cursor canvases `output-write-layout-advisory-explainer.canvas.tsx`（同源内容）
- 证据目录（本地）: `.tmp/evidence/c40-write-layout-dual-run/`（gitignored）

## Next

正式化: `/llman-sdd-propose` → design/tasks → `change start` → specs landing → apply。
