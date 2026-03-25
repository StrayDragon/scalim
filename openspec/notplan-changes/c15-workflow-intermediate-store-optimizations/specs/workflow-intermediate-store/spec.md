## ADDED Requirements

### Requirement: workflow intermediate store MUST support a typed row artifact (`InMemoryRows`)
当 workflow 需要在节点之间传递“纯 Python 数据”（而不是强制落盘/字符串化）时，系统 MUST 支持一个稳定的 typed 中间态结构 `InMemoryRows`：

- `InMemoryRows` MUST 是一个明确的表结构（而不是任意 `object` 图），避免把 workflow 变成“随便塞对象”的隐式耦合点。
- `InMemoryRows` 的值域 MUST 限制在框架既有的 `FieldValue` 口径（例如 `int/float/Decimal/str/bool/None`），以保证：
  - 与现有 sinks 的类型语义可对齐（尤其是 workbook 写入）
  - 失败诊断与序列化/日志输出的可控性
- `InMemoryRows` MUST 采用稳定结构（与 `InMemoryCsv` 类似但值域为 typed）：
  - `header: list[str]`（字段顺序 SSOT）
  - `rows: list[list[FieldValue]]`（每行 MUST 与 `header` 等长，列序一致）

### Requirement: `InMemoryRows` and `InMemoryCsv` MUST be independent artifacts (no contract coupling)
`InMemoryRows` 与 `InMemoryCsv` 面向不同消费场景，它们的约束 MUST 互不干扰：

- 系统 MUST NOT 因引入 `InMemoryRows` 而改变 `InMemoryCsv` 的既定语义（`list[str]` + `list[list[str]]` + `CSVSink` 等价字符串化）。
- 系统 MAY 在需要时提供显式转换（见下），但 MUST NOT 将“自动生成另一份 artifact”设为硬依赖（避免双份数据常驻导致峰值翻倍）。

### Requirement: workflow MAY support pure Python dataflow (source) by wiring `InMemoryRows` into downstream demand execution
workflow runtime MAY 支持将上游节点产生的 `InMemoryRows` 作为下游 demand 节点的 `main_rows` 输入（形成 workflow 内部的数据流/源传递）：

- 该 wiring MUST 是显式声明/显式授权（allowlist），避免隐式推断导致数据边界失控。
- 该能力 MUST NOT 放宽 standalone demand 的规则（例如 pathless outputs 的 fail-fast 等），仅用于 workflow 托管场景。

#### Scenario: downstream demand consumes upstream typed rows as `main_rows`
- **GIVEN** workflow 节点 A 产出 `InMemoryRows`（typed）
- **AND** workflow 节点 B 显式声明使用 A 的 `InMemoryRows` 作为自己的 `main_rows`
- **WHEN** B 执行
- **THEN** B MUST 在不落盘/不字符串化的前提下消费该数据（仍遵守既有执行/并发/可观测性边界）

### Requirement: conversion from `InMemoryRows` to `InMemoryCsv` MUST be explicit and stable
当某些 consumer 需要“CSV 等价语义”（例如复用现有 `csv_append`/基于 CSV 的对齐逻辑）时，系统 MAY 提供从 `InMemoryRows` 转换到 `InMemoryCsv` 的显式转换工具/适配层，但该转换 MUST 稳定且可审计：

- 转换 MUST 保留 `header` 字段顺序
- 转换 MUST 对每个 value 采用与 `CSVSink` 等价的规范化：
  - `None` -> `""`
  - 其余 -> `str(value)`

## Open Questions (Draft)

- `InMemoryRows` 是否需要携带 `row_id`（以支持更强的 join/lookup 复用），还是通过把 `row_id` 显式作为一个字段列来承载。
- 并发执行下（`ThreadPoolExecutor`），typed artifact 的生命周期与可见性边界是否需要额外的“只读冻结/拷贝”规则，以避免用户自定义 loader/sink 误修改共享对象导致竞态。
