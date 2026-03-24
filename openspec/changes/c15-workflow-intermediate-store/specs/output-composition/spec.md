## ADDED Requirements

### Requirement: workflow-managed pathless CSV targets MUST support in-memory row sinks
当 output composition 在 workflow 托管场景下处理 pathless CSV target 时，系统 MUST 支持将结果直接写入内存 sink，而不是因为 `path` 为空而拒绝或退化为无输出：
- 该能力仅适用于 workflow 显式托管的 CSV target；普通 standalone run 仍 MUST 按既有规则对 pathless CSV fail-fast
- 内存 sink MUST 保留与现有 CSV 文件输出等价的字段顺序、表头与值规范化语义
- 内存 sink 的产物 MUST 采用稳定的 `InMemoryCsv` 结构:
  - `header: list[str]`（字段顺序 SSOT）
  - `rows: list[list[str]]`（每行 MUST 与 `header` 等长,列序一致）
- 值规范化语义 MUST 与现有 `CSVSink` 等价：
  - `None` MUST 规范化为 `""`
  - 其余值 MUST 规范化为 `str(value)`
- output composition MUST 将这类内存结果以稳定返回值暴露给上层 workflow runtime（例如扩展 `ExecutionResult.in_memory_csv_outputs: dict[str, InMemoryCsv]`）,以供 write nodes 消费

#### Scenario: workflow-managed pathless CSV target materializes in memory
- **WHEN** workflow 托管执行一个 pathless CSV target 且该 target 被 write intents 引用
- **THEN** output composition MUST 产出可供 workflow runtime 获取的内存 CSV 结果
- **AND** 系统 MUST NOT 因 `OutputSpec.path` 为空而拒绝该 target

#### Scenario: standalone pathless CSV target remains invalid
- **WHEN** 非 workflow 托管场景编译或运行 pathless CSV target
- **THEN** 系统 MUST 继续 fail-fast
