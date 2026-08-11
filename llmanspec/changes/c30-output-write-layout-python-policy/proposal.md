---
depends_on: []
branch: sdd/c30-output-write-layout-python-policy
base_sha: b3336a82238bea802ac481c71413a0c9a5b92730
checkpointed: false
---

# Output write layout Python policy

> 一句话: 用闭集 `OutputWriteLayout`（Python SSOT）统一「行流式 / 列 HOLD / 列 WINDOW」工厂选择与互斥 fail-fast；不进 YAML；默认行为不变。

## Why

写出布局今天拆在 `OutputSpec.streaming`、`ExcelColumnResidency` 与 YAML `output_composition`（强制行式）三处。调用方难发现有效组合；对 books 设 WINDOW 会 fail-fast，但缺少统一「布局」概念。需要可发现的 Python 闭集策略，禁止静默自动切换与 YAML 回流。

## What Changes

- 新增 `OutputWriteLayout`（`StrEnum`）：`row_stream` | `column_hold` | `column_window`
- 挂到 `DemandRunRuntimeOptions` 与 `ExecutionRequest`（Enum-only 入；wire 出 builtin str）
- `_create_file_sink` / run_ir 装配以 **effective layout** 为第一解释
- 优先级：显式 `output_write_layout` > 由 `streaming`+`excel_column_residency` **推导** > 默认（composition→`row_stream`；IR 保持今日默认）
- 互斥 fail-fast：`column_*` + `output_composition`；`column_window` + 非 excel（含 CSV）
- YAML 出现 layout/residency/streaming sink knobs → fail-fast（延续 r176 / r155）
- 迁移窗：保留 `excel_column_residency` 与 `OutputSpec.streaming`；文档化推导表
- 文档：excel-column-residency / New knob gate / capability-matrix 行
- **不**自动按宽表切换；手写 `sink=` 仍绕过工厂

## Capabilities

### New Capabilities

- `runtime-output-write-layout`

### Modified Capabilities

- `yaml-dsl-runtime-policy-boundary`（layout 仅 Python；composition 互斥推广）
- `streaming-output` 或 `output-sink-fastpath`（工厂按 layout 选 sink 的指针级要求）

## Impact

- 自定义：一个 Enum 表达三种意图
- 默认路径无行为漂移（未设 layout 时推导 ≡ 今日）
- Breaking：仅非法组合从「模糊」变为统一 fail-fast 文案；CSV+WINDOW 显式拒绝

## Ethics

- `ethics.risk_level`: medium
- `ethics.prohibited_actions`: YAML 发明 layout；静默忽略冲突；默认 auto 切 layout；memo 绑布局
- `ethics.required_evidence`: 推导表单测 + composition/CSV WINDOW fail-fast + 未设 layout 行为对拍
- `ethics.refusal_contract`: 无推导表与互斥矩阵不得 apply
- `ethics.escalation_policy`: 若需默认改成 WINDOW 或 YAML 旋钮，必须另开 change