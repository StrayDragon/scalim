# Proposal: output write layout advisory

> 一句话描述: 在 `run_stats` / bench 观测中输出写出布局 **建议**（如宽表可试 IR 列式 WINDOW），默认不改写出行为；opt-in 自动切换另案且须 RSS 门控。

> **状态（2026-08-11）**：**搁置实现**。L1 `run_stats` hint / auto **不做**；调优知识改走 **docs + `agentdev/skills`**（quick）。草案 change 已撤回。研究页仍保留：[`research/write-layout-advisory-explainer.html`](research/write-layout-advisory-explainer.html)。D3 `OutputWriteLayout` 已落地（c30）。

## Why

内存优先下「自主」不应等于静默改 sink：误切 HOLD↔WINDOW / 行↔列会改变峰与语义可解释性。  
需要先有 **可观测建议**，让运维/集成方自己决定是否改 `DemandRunRuntimeOptions.output_write_layout` / IR。

**现行交付偏好**：用文档/skills 让人与 agent **显式选型**，暂不接 run_stats 机器 hint。

## 信息完备性（额外探索结论）

| 时机 | 可得信息 | 足以？ |
|------|----------|--------|
| 装配前 | format / streaming / composition / n_fields / 显式 layout | 够做 **非法组合 fail-fast** 与粗风险标签 |
| 计划期 | target fields、batch_size | 粗估 `n_fields × ?rows`；总行数常未知（流式） |
| 跑后 | 已写行数、write 耗时、peak RSS（若观测） | 够做 **事后建议**；sink 已选定，不宜中途改 |
| 缺口 | 单元格平均体积、磁盘/IO、是否二次 `List[dict]` | 启发式会骗人 |

**结论**：信息够 L1 **advisory**，不够默认 **auto**。错切代价不对称；YAML books 无 WINDOW 位（最多建议迁 IR）。

梯子：L0 显式 Enum（c30）→ L1 建议（本草案，**搁置**）→ L2 opt-in auto（另案+门控）→ L3 默认 auto（不做）。

## What Changes（设计方向 — 搁置）

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

启发式（初稿，须校准；现作文档阈值参考）：
- IR excel + effective `column_hold` + `n_fields * n_rows` 超约 **百万格** → 可建议 `column_window`
- composition/books → 勿建议 WINDOW；引导迁 IR
- 已是 `column_window` 或显式 layout → 已最优
- 行数未知且无 peak 观测 → 信息不足

### 小样本双跑实验（不进主路径）

| 项 | 约定 |
|----|------|
| 入口 | 离线脚本 `scripts/bench_output_write_layout_dual_run.py`（`--preset small|medium`） |
| 产出 | `.tmp/evidence/c40-write-layout-dual-run/*.json`（不入库） |
| medium 摘要 | RSS H/W ≈ 2.5–4.9×；墙钟 W/H ≈ 1.02；业务行数相等 |

## 非目标

- 默认自动切换 layout
- YAML 配置阈值
- 与 memo / overlap cache 绑定
- 在主路径为 advisory 双跑写出
- **（现行）实现 L1 run_stats hint** — 搁置

## 正确性（文档应强调）

合法 IR 列式路径下 HOLD↔WINDOW **业务格子等价**；xlsx 字节不必相等；非法组合 fail-fast。详见 research HTML。

## Research

- [`research/write-layout-advisory-explainer.html`](research/write-layout-advisory-explainer.html)
