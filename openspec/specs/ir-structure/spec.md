# ir-structure Specification

## Purpose
定义 IR 层的纯数据边界与依赖约束,确保 spec/ir 不依赖执行与规划层,便于稳定复用、演进与测试.

## Related Concepts
- IR 模块 (spec/ir/)
- 需求 IR (demand.py)
- 字段 IR (fields.py, FieldIr)
- 关系 IR (relations.py)
- 来源 IR (sources.py)
- 纯数据层边界

## Requirements

### Requirement: IR 纯数据层
系统 MUST 保证 `spec/ir` 中的 IR 类型为纯数据/类型层,不依赖 `execution`/`planning`/`sinks` 等执行侧模块.

#### Scenario: IR 模块无执行层依赖
- **WHEN** 仅导入 IR 相关模块
- **THEN** 不会触发 execution/planning/sinks 的导入

### Requirement: IR 结构调整不引入执行依赖
系统 MUST 在 IR 结构调整或拆分时保持纯数据层边界,避免引入执行侧依赖.

#### Scenario: IR 调整后仍无执行依赖
- **WHEN** 调整 IR 相关模块结构
- **THEN** 仍不会触发执行侧模块导入

### Requirement: IR 公开类型命名语义化
系统 MUST 为 IR 层公开 alias/presentation 类型提供语义清晰的命名,并保持其纯类型层定位.

以下命名 MUST 生效:
- `LoaderResultMapCallable`
- `MainSourceRowIterableCallable`
- `LookupKeySpec`
- `CsvFieldPresentationIr`
- `SpreadsheetFieldPresentationIr`
- `PandasFieldPresentationIr`

#### Scenario: 语义化类型命名可导入
- **WHEN** 调用方导入上述 IR 公开类型
- **THEN** 导入 MUST 成功且类型语义与原能力一致

### Requirement: FieldIr.data_key 默认等于 field_id
系统 MUST 保证 `FieldIr.data_key` 在 IR 中为非空字符串.
当构造 `FieldIr` 时未提供 `data_key` 或 `data_key` 为空字符串时,系统 MUST 将其默认设置为 `field_id`.

#### Scenario: data_key 缺省时默认 field_id
- **WHEN** 构造 `FieldIr(field_id="order_id", data_key="")` 或缺省 `data_key`
- **THEN** `FieldIr.data_key` MUST 等于 `"order_id"`
