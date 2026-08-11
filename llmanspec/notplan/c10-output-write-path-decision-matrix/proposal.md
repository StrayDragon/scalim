# Proposal: output write path decision matrix

> 一句话描述: 固化「run_demand / workflow / IR → 哪个 sink」决策矩阵与形状推荐，澄清有手动无自动，避免把 `ExcelColumnResidency` 误当成 YAML books 开关。

> **状态（2026-08-11）**：文档已落地到站点页与 perf 判断链路；本目录为 draft 壳，便于日后 `llman-sdd-propose` 若需补 specs/checklist 行。

## Why

集成方与 agent 常误以为：

- 在 `DemandRunRuntimeOptions.excel_column_residency=WINDOW` 下 YAML books 会变列式流式；
- 或框架会按宽表/长表自动选行/列 sink。

实际：YAML books 强制行式；WINDOW 仅 IR `excel`+`streaming=False`；**无自动选型**。

## What Changes

- 人类文档：`docs/doc/getting-started/excel-column-residency.md` 增加「run_demand/workflow 能设什么」与形状推荐表。
- 判断链路：`llmanspec/notplan/2026-08-11-perf-roi-judgment-chain.md` §9。
- Agent 指引可交叉引用上述页（`streaming-column-excel-guidance.md`）。
- **无运行时行为变更。**

## Capabilities

### Modified Capabilities

- `governance-docs` / getting-started：写出路径决策矩阵为公开口径 SSOT。

## Impact

- 降低假开关与错误 WINDOW 用法；不改变默认写出路径。
- 后续 D3 策略面收敛应引用本矩阵，避免双源。
