# workflow-intermediate-store Specification

## Purpose
TBD - created by archiving change c15-workflow-intermediate-store-optimizations. Update Purpose after archive.

## Requirements

### Requirement: workflow intermediate store MUST support a typed row artifact (`InMemoryRows`)
当 workflow 需要在节点之间传递“纯 Python 数据”（而不是强制落盘/字符串化）时，系统 MUST 支持一个稳定的 typed 中间态结构 `InMemoryRows`：

- `InMemoryRows` MUST 是一个明确的表结构（而不是任意 `object` 图），避免把 workflow 变成“随便塞对象”的隐式耦合点。
- `InMemoryRows` 的值域 MUST 限制在框架既有的 `FieldValue` 口径（例如 `int/float/Decimal/str/bool/None`），以保证：
  - 与现有 sinks 的类型语义可对齐（尤其是 workbook 写入）
  - 失败诊断与序列化/日志输出的可控性
- `InMemoryRows` MUST 采用稳定结构（与 `InMemoryCsv` 类似但值域为 typed）：
  - `header: list[str]`（字段顺序 SSOT）
  - `rows: list[list[FieldValue]]`（每行 MUST 与 `header` 等长，列序一致）

#### Scenario: workflow publishes typed rows as a stable table artifact
- **GIVEN** workflow 节点 A 需要把 typed 表数据作为中间态传递给下游节点
- **WHEN** A 发布一个 `InMemoryRows` artifact
- **THEN** `InMemoryRows` MUST 以 `header` + `rows` 的稳定表结构呈现
- **AND** `rows[*]` 的长度 MUST 与 `header` 等长且列序一致
- **AND** 若 value 不属于 `FieldValue` 值域或行长度不匹配，发布/构造 MUST fail-fast

### Requirement: `InMemoryRows` and `InMemoryCsv` MUST be independent artifacts (no contract coupling)
`InMemoryRows` 与 `InMemoryCsv` 面向不同消费场景，它们的约束 MUST 互不干扰：

- 系统 MUST NOT 因引入 `InMemoryRows` 而改变 `InMemoryCsv` 的既定语义（`list[str]` + `list[list[str]]` + `CSVSink` 等价字符串化）。
- 系统 MAY 在需要时提供显式转换（见下），但 MUST NOT 将“自动生成另一份 artifact”设为硬依赖（避免双份数据常驻导致峰值翻倍）。

#### Scenario: InMemoryRows does not change InMemoryCsv semantics and does not auto-couple
- **GIVEN** workflow-managed pathless CSV 输出产出 `InMemoryCsv`
- **WHEN** workflow 同时启用/使用 `InMemoryRows`
- **THEN** `InMemoryCsv` 的既定语义 MUST 保持不变（字符串化表结构，与 `CSVSink` 规范化等价）
- **AND** 系统 MUST NOT 因 `InMemoryRows` 的存在而自动生成或强制保留另一份 `InMemoryCsv`（除非显式请求转换）

### Requirement: workflow runtime MUST support pure Python dataflow (source) by wiring `InMemoryRows` into downstream demand execution
workflow runtime MUST 支持将上游节点产生的 `InMemoryRows` 作为下游 demand 节点的 `main_rows` 输入（形成 workflow 内部的数据流/源传递）：

- 该 wiring MUST 是显式声明/显式授权（allowlist），避免隐式推断导致数据边界失控。
- 该能力 MUST NOT 放宽 standalone demand 的规则（例如 pathless outputs 的 fail-fast 等），仅用于 workflow 托管场景。

#### Scenario: downstream demand consumes upstream typed rows as `main_rows`
- **GIVEN** workflow 节点 A 产出 `InMemoryRows`（typed）
- **AND** workflow 节点 B 显式声明使用 A 的 `InMemoryRows` 作为自己的 `main_rows`
- **WHEN** B 执行
- **THEN** B MUST 在不落盘/不字符串化的前提下消费该数据（仍遵守既有执行/并发/可观测性边界）

### Requirement: workflow YAML MUST expose `main_rows_from` and compile-time validate explicit deps
系统 MUST 在 workflow YAML authoring surface 中暴露一个显式 wiring 字段,用于声明“本节点的 `main_rows` 来自上游节点的 `InMemoryRows`”：

- 字段: `workflow.runs[*].main_rows_from`
- 结构: mapping,至少包含 `run: <producer_run_id>`

当该字段存在时，workflow 编译期 MUST fail-fast 校验：

- producer `run_id` MUST 存在
- consumer MUST 显式 `depends_on` producer（避免隐式可见性/执行顺序推断）

#### Scenario: missing depends_on fails fast
- **GIVEN** workflow 节点 B 配置 `main_rows_from.run = "A"`
- **WHEN** B 未在 `depends_on` 中声明 `"A"`
- **THEN** workflow 编译 MUST fail-fast
- **AND** 错误信息 MUST 指向 `workflow.runs[*].main_rows_from` 或 `workflow.runs[*].depends_on` 的可诊断路径

### Requirement: execution orchestration MUST pass `main_rows` through `run_ir`
系统 MUST 支持把 workflow wiring 得到的行流注入到 demand 执行边界：

- by `run_ir` 组装的 `engine.run(...)` 调用 MUST 透传 `main_rows`（当其被显式提供时）
- 当 `main_rows` 被提供时，系统 MUST NOT 触发 main source loader（避免“注入了但仍加载主源”的双重输入）

#### Scenario: providing main_rows bypasses main source loader
- **GIVEN** 本次运行显式提供 `main_rows`
- **WHEN** 执行 `run_ir`
- **THEN** main source loader MUST NOT 被调用

### Requirement: workflow MUST capture and release `InMemoryRows` only for referenced producers
为避免无意间常驻大对象，系统 MUST 以“显式引用”为基准启用 typed rows 捕获与生命周期管理：

- 当且仅当某个 producer run_id 被至少一个 consumer 通过 `main_rows_from` 引用时，producer 才 MUST 启用 `InMemoryRows` 捕获与发布
- workflow artifacts 中该 typed artifact 的 `artifact_id` MUST 为稳定值 `in_memory_rows`
- workflow MUST 在“最后一个 consumer 节点结束（done/failed/cancelled 皆视为不再消费）”后释放该 artifact（discard）

#### Scenario: release typed rows after final consumer ends
- **GIVEN** producer 节点 A 的 `in_memory_rows` 被多个 consumer 引用
- **WHEN** 最后一个 consumer 节点结束
- **THEN** workflow MUST discard A 的 `in_memory_rows` artifact

### Requirement: conversion from `InMemoryRows` to `InMemoryCsv` MUST be explicit and stable
当某些 consumer 需要“CSV 等价语义”（例如复用现有 `csv_append`/基于 CSV 的对齐逻辑）时，系统 MAY 提供从 `InMemoryRows` 转换到 `InMemoryCsv` 的显式转换工具/适配层，但该转换 MUST 稳定且可审计：

- 转换 MUST 保留 `header` 字段顺序
- 转换 MUST 对每个 value 采用与 `CSVSink` 等价的规范化：
  - `None` -> `""`
  - 其余 -> `str(value)`

#### Scenario: explicit conversion preserves header order and normalizes values
- **GIVEN** 一个 `InMemoryRows` typed 表（包含 `None` 与非字符串类型值）
- **WHEN** 调用方显式请求将其转换为 `InMemoryCsv`
- **THEN** `header` 字段顺序 MUST 保持不变
- **AND** `None` MUST 转换为 `""`
- **AND** 其它值 MUST 使用 `str(value)` 转换为字符串

## Open Questions (Draft)

- `InMemoryRows` 是否需要携带 `row_id`（以支持更强的 join/lookup 复用），还是通过把 `row_id` 显式作为一个字段列来承载。
- 并发执行下（`ThreadPoolExecutor`），typed artifact 的生命周期与可见性边界是否需要额外的“只读冻结/拷贝”规则，以避免用户自定义 loader/sink 误修改共享对象导致竞态。
