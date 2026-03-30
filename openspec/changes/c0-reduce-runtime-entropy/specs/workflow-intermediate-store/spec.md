## ADDED Requirements

### Requirement: workflow typed rows artifact MUST have a stable public import path
系统 MUST 为 workflow typed rows artifact `InMemoryRows` 提供稳定的公开导入路径,并避免跨层绑定内部实现模块路径。

约束:
- `InMemoryRows` MUST 可从稳定 facade 子模块导入(固定为 `scalim.sinks.rows`)。
- 该稳定 facade SHOULD 同时导出 `InMemoryRows` 的必要配套类型/工具(例如 `InMemoryRowsSink`/`in_memory_rows_to_in_memory_csv`/`iter_in_memory_rows_as_main_rows`),作为一组成熟可用入口。
- workflow runtime 与 execution orchestration MUST NOT 直接依赖 `IMPL_ROOT.sinks._internal.*` 路径获取该类型(内部路径可变,非契约)。

#### Scenario: InMemoryRows is importable from a stable facade module
- **WHEN** 调用方从 `scalim.sinks.rows` 导入 `InMemoryRows`
- **THEN** 导入 MUST 成功且类型与 runtime 实际使用的 typed rows artifact 一致
