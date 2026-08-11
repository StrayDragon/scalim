# Proposal: output write layout advisory

> 一句话描述: 在 `run_stats` / bench 观测中输出写出布局 **建议**（如宽表可试 IR 列式 WINDOW），默认不改写出行为；opt-in 自动切换另案且须 RSS 门控。

> **状态（2026-08-11）**：设计稿；D3 `OutputWriteLayout` 已落地（c30）；禁止静默 auto。skills/upgrade/ch162 已指向本草案。

## Why

内存优先下「自主」不应等于静默改 sink：误切 HOLD↔WINDOW / 行↔列会改变峰与语义可解释性。  
需要先有 **可观测建议**，让运维/集成方自己决定是否改 `DemandRunRuntimeOptions.output_write_layout` / IR。

## 信息完备性（额外探索结论）

| 时机 | 可得信息 | 足以？ |
|------|----------|--------|
| 装配前 | format / streaming / composition / n_fields / 显式 layout | 够做 **非法组合 fail-fast** 与粗风险标签 |
| 计划期 | target fields、batch_size | 粗估 `n_fields × ?rows`；总行数常未知（流式） |
| 跑后 | 已写行数、write 耗时、peak RSS（若观测） | 够做 **事后建议**；sink 已选定，不宜中途改 |
| 缺口 | 单元格平均体积、磁盘/IO、是否二次 `List[dict]` | 启发式会骗人 |

**结论**：信息够 L1 **advisory**，不够默认 **auto**。错切代价不对称；YAML books 无 WINDOW 位（最多建议迁 IR）。

梯子：L0 显式 Enum（c30）→ L1 建议（本草案）→ L2 opt-in auto（另案+门控）→ L3 默认 auto（不做）。

## What Changes（设计方向）

### L1 建议字段 schema（草案）

挂点候选：`run_stats.hints.write_layout`（或 `notes[]` 一条 typed hint）。仅 `bench` / `bench_plus` / 显式 opt-in；`baseline` 默认关闭。

```json
{
  "write_layout_hint": {
    "suggested": "column_window",
    "current_effective": "column_hold",
    "reason_code": "wide_excel_peak_risk",
    "reason_detail": "n_fields*n_rows=1200000 exceeds threshold",
    "action": "set DemandRunRuntimeOptions(output_write_layout=OutputWriteLayout.COLUMN_WINDOW)",
    "safe": true
  }
}
```

| 字段 | 类型 | 说明 |
|------|------|------|
| `suggested` | `str \| null` | `row_stream` / `column_hold` / `column_window` / null |
| `current_effective` | `str` | 本次实际 effective layout（`.value`） |
| `reason_code` | `str` | 闭集短码：`wide_excel_peak_risk` / `composition_row_only` / `already_optimal` / `insufficient_shape` |
| `reason_detail` | `str` | 人类可读，可含阈值与观测数 |
| `action` | `str` | 可复制的 Python 改法；composition 路径 **禁止** 写「设 WINDOW」 |
| `safe` | `bool` | false=仅信息（如 composition 需迁 IR），true=直接改 options 合法 |

**绝不**在默认路径改 sink。

启发式（初稿，须校准）：
- IR excel + effective `column_hold` + `n_fields * n_rows` 超阈值 → `suggested=column_window`，`safe=true`
- composition/books → `suggested=null`，`reason_code=composition_row_only`，`action` 指向迁 IR，`safe=false`
- 已是 `column_window` 或显式 layout → `already_optimal`
- 行数未知且无 peak 观测 → `insufficient_shape`（可只在 bench 双跑后升级）

### 小样本双跑实验（不进主路径）

目的：用硬证据校准启发式阈值，而不是在热路径猜。

| 项 | 约定 |
|----|------|
| 入口 | 离线脚本 `scripts/bench_output_write_layout_dual_run.py`（`uv run python ... --preset small|medium`）；**禁止**默认 `run_ir` 双写出 |
| 样本 | 同 IR：`COLUMN_HOLD` vs `COLUMN_WINDOW`；rows/cols 取自探针矩阵（≤10GB） |
| 指标 | median 墙钟、peak RSS、行数相等、xlsx 业务列对拍（非字节） |
| 产出 | `.tmp/evidence/c40-write-layout-dual-run/*.json` + 建议阈值候选 |
| 通过标准 | WINDOW RSS 显著更优且行数一致 → 强化 `wide_excel_peak_risk`；否则提高阈值或改 reason |

伪流程：

```text
for shape in shapes:
  run(layout=HOLD)  → wall_h, rss_h, rows_h
  run(layout=WINDOW)→ wall_w, rss_w, rows_w
  assert rows_h == rows_w
  record ratio rss_h/rss_w, wall_w/wall_h
calibrate threshold for L1 hint
```

日后 L2 auto（不在本草案）：用户 opt-in + RSS 不劣于基线 + 值等价 + 可回滚。

## 非目标

- 默认自动切换 layout
- YAML 配置阈值
- 与 memo / overlap cache 绑定
- 在主路径为 advisory 双跑写出

## Capabilities

### New Capabilities

- `observability-output-write-layout-advisory`：建议 schema 与「不改行为」契约

### Modified Capabilities

- `performance-observability` / run_stats：可选 hints 字段

## Impact

- 自主性：人/agent 可读建议后显式改 `OutputWriteLayout`
- 平衡：零默认行为变化；观测税须在 mid shape 上可接受（对齐 c50 税门控精神）
- 转正门控：composition 路径不得建议无效 WINDOW；snapshot 测试；双跑证据校准阈值

## 依赖

- D1 决策矩阵（已文档化）
- D3 `OutputWriteLayout`（c30，已落地）
- skills/upgrade：`2026-08-11-output-write-layout.md`；notebook ch162
