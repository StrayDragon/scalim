# output-composition Specification

**状态: ✅ 已实现**
## Purpose
支持单次运行的多输出目标组合(多文件或同一容器多逻辑输出),并定义容器命名冲突策略与输出失败策略(`failure_policy`).

## Related Code (as implemented)
- `src/IMPL_ROOT/execution/output_composition.py` (RouterRowSink + targets/meta/audit + failure_policy)
- `src/IMPL_ROOT/execution/output_contracts.py` (OutputSpec/ExportLayout)
- `src/IMPL_ROOT/execution/run_ir.py` (ExecutionRequest.output_composition 装配入口)
- `src/IMPL_ROOT/sinks/sink_excel.py` (ExcelWorkbookSink: workbook 容器型输出)
## Requirements
### Requirement: 多输出组合
系统 SHALL 允许单次运行定义多个输出目标,每个输出目标拥有独立的字段集合、输出绑定与生命周期,并可同时产出.

#### Scenario: 详情 + 汇总多目标
- **WHEN** 运行配置了详情输出与汇总输出两个目标
- **THEN** 系统应同时产出两份结果且互不影响

#### Scenario: 独立输出文件
- **WHEN** 多个输出目标绑定到不同的输出位置
- **THEN** 系统应分别生成独立输出且互不影响

### Requirement: 容器内多逻辑输出
系统 SHALL 支持将多个输出目标写入同一“容器型”输出(例如同一 workbook 的多个 sheet),并允许为每个目标指定逻辑名称.

#### Scenario: 同一 workbook 多 sheet
- **WHEN** 输出目标绑定到同一容器并指定不同逻辑名称
- **THEN** 系统应在同一容器中创建并写入多个逻辑输出

### Requirement: 容器内命名冲突拒绝
系统 MUST 在同一容器内发现输出名称冲突时直接拒绝,以避免隐式改名造成的隐藏问题.

#### Scenario: 逻辑名称冲突
- **WHEN** 两个输出目标在同一容器中使用相同逻辑名称
- **THEN** 系统应快速失败并返回明确的冲突错误

### Requirement: 输出失败策略
系统 SHALL 提供明确的输出失败策略(例如主输出优先或派生输出降级),并保证策略可在运行级别配置.

#### Scenario: 派生输出失败
- **WHEN** 派生输出失败且策略为“主输出优先”
- **THEN** 系统应确保主输出完成且派生输出被标记为失败

#### 默认策略
- 默认 failure policy 为 `all_fail`: 任一输出失败即认为本次 run 失败(以保证报表包完整性与可对拍一致性)。
- 可选策略 `primary_only`: 仅主输出失败才失败;派生输出失败会被记录(用于 meta/audit)且不阻断主输出。

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

### Requirement: meta/audit error 记录默认不泄露敏感异常信息
当输出组合启用 meta/audit(例如 workbook 内的 Meta/Audit sheet)时,系统 MUST 默认避免将异常的原始 `error_message` 直接写入输出文件.

系统 MUST 至少满足以下行为:
- meta/audit MUST 记录 `error_type`
- meta/audit 的 `error_message` MUST 默认为安全摘要(例如空/占位/截断预览),不得包含多行与过长文本
- meta/audit SHOULD 记录稳定的 `error_message_hash`(用于对拍与聚类)
- 系统 MUST 提供显式开关以允许在“可信环境排障”时写入完整 `error_message`

#### Scenario: 默认仅写安全摘要
- **GIVEN** 派生输出(或某个输出目标)在运行中抛出异常且 error_message 含敏感片段(例如 token/SQL/URL)
- **WHEN** 输出组合启用 meta/audit
- **THEN** meta/audit MUST 记录该输出目标的 `error_type`
- **AND** meta/audit MUST NOT 写入原样 `error_message`
- **AND** meta/audit SHOULD 提供 `error_message_hash` 以便聚类/对拍

#### Scenario: 显式开启后允许写完整 message
- **GIVEN** 运行配置显式启用“落完整 error_message”
- **WHEN** 某个输出目标失败并产生异常 message
- **THEN** meta/audit MAY 写入完整 `error_message`
