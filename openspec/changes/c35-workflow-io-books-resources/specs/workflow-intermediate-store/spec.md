## MODIFIED Requirements

### Requirement: `InMemoryRows` and `InMemoryCsv` MUST be independent artifacts (no contract coupling)
`InMemoryRows` 与 `InMemoryCsv` 面向不同消费场景，它们的约束 MUST 互不干扰：

- 系统 MUST NOT 因引入 `InMemoryRows` 而改变 `InMemoryCsv` 的既定语义（`list[str]` + `list[list[str]]` + `CSVSink` 等价字符串化）。
- 系统 MAY 在需要时提供显式转换（见下），但 MUST NOT 将“自动生成另一份 artifact”设为硬依赖（避免双份数据常驻导致峰值翻倍）。

#### Scenario: InMemoryRows does not change InMemoryCsv semantics and does not auto-couple
- **GIVEN** workflow 托管场景下存在一个内存 CSV 等价 artifact `InMemoryCsv`（实现细节；不再通过 pathless CSV authoring surface 触发）
- **WHEN** workflow 同时启用/使用 `InMemoryRows`
- **THEN** `InMemoryCsv` 的既定语义 MUST 保持不变（字符串化表结构，与 `CSVSink` 规范化等价）
- **AND** 系统 MUST NOT 因 `InMemoryRows` 的存在而自动生成或强制保留另一份 `InMemoryCsv`（除非显式请求转换）

### Requirement: workflow runtime MUST support pure Python dataflow (source) by wiring `InMemoryRows` into downstream demand execution
workflow runtime MUST 支持将上游节点产生的 `InMemoryRows` 作为下游 demand 节点的 `main_rows` 输入（形成 workflow 内部的数据流/源传递）：

- 该 wiring MUST 是显式声明/显式授权（allowlist），避免隐式推断导致数据边界失控。
- 该能力 MUST NOT 放宽 standalone demand 的既有校验/失败语义,仅用于 workflow 托管场景。

#### Scenario: downstream demand consumes upstream typed rows as `main_rows`
- **GIVEN** workflow 节点 A 产出 `InMemoryRows`（typed）
- **AND** workflow 节点 B 显式声明使用 A 的 `InMemoryRows` 作为自己的 `main_rows`
- **WHEN** B 执行
- **THEN** B MUST 在不落盘/不字符串化的前提下消费该数据（仍遵守既有执行/并发/可观测性边界）

