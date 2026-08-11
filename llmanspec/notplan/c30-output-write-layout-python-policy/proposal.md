# Proposal: output write layout Python policy

> 一句话描述: 用闭集 Python 策略（`OutputWriteLayout` 或等价）统一解释「行流式 / 列 HOLD / 列 WINDOW」，工厂单一入口校验互斥；不进 YAML；默认保守。

> **状态（2026-08-11）**：已转正为 active SDD `llmanspec/changes/c30-output-write-layout-python-policy/`（Branch binding + Specs landing）；本 notplan 副本仅作指针，以 active change 为准。

## Why

今日写出布局分散在：

- `OutputSpec.streaming`（IR）
- `ExcelColumnResidency`（仅 excel+非 streaming）
- YAML `output_composition` 强制行式

用户/agent 难发现「该设哪个」；非法组合 fail-fast 文案不统一。需要 **可发现的 Python SSOT**，而不是再往 YAML 加字段。

## What Changes（设计方向）

1. **闭集 Enum**（候选名 `OutputWriteLayout`，`StrEnum`）：
   - `ROW_STREAM` — 行式文件 sink（对齐今日 `streaming=True` / YAML books）
   - `COLUMN_HOLD` — 列式缓存到 close（今日 excel/csv `streaming=False` + HOLD）
   - `COLUMN_WINDOW` — 列式行窗（今日 excel `streaming=False` + WINDOW；CSV 若无 WINDOW 语义则 fail-fast 或映射到 HOLD 并文档化）
2. **挂点**：`DemandRunRuntimeOptions`（及 `ExecutionRequest`）；**禁止** YAML authoring。
3. **工厂**：`_create_file_sink` 以 layout 为第一解释；与 `output_composition` 冲突时 fail-fast（ROW_STREAM only）。
4. **迁移**：保留 `OutputSpec.streaming` + `excel_column_residency` 一段窗口，归一到 layout；双写时文档化优先级（显式 layout > 旧字段组合 > 默认）。
5. **默认**：有 composition → `ROW_STREAM`；纯 IR 无 layout → 保持今日默认（行若 streaming 默认 true；列 HOLD）。

## 非目标

- YAML `write.streaming` / residency 字段
- 静默自动按行列数切换 layout
- memo / 跨批 cache

## Capabilities

### New Capabilities

- `runtime-output-write-layout`：闭集写出布局策略与互斥校验。

### Modified Capabilities

- `yaml-dsl-runtime-policy-boundary`：确认 layout 仅 Python
- `output-sink-contracts`：工厂选择与 fail-fast 文案

## Impact

- 自定义面：一个 Enum 表达三种意图；手写 sink 仍可绕过。
- 平衡：默认不变更行为；opt-in 显式 layout。
- 转正门控：非法组合测试全集；capability-matrix + review-checklist 行；New knob gate 记录。

## 与 D4 关系

D4 advisory 只建议「可试 COLUMN_WINDOW」，**不**自动改 layout。
