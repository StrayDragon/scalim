# language: zh-CN
# capability: ir-structure
# purpose: 定义 IR 层的纯数据边界与依赖约束,确保 spec/ir 不依赖执行与规划层,便于稳定复用、演进与测试. [scope-review-2026-07-13-c25-xlsx-ir-path-presence]
# scope: src/scalim/

功能: ir-structure

  @req:r60 @human
  场景: IR 纯数据层
    - 系统 MUST 保证 `spec/ir` 中的 IR 类型为纯数据/类型层,不依赖 `execution`/`planning`/`sinks` 等执行侧模块.

  @req:r304 @human
  场景: IR 结构调整不引入执行依赖
    - 系统 MUST 在 IR 结构调整或拆分时保持纯数据层边界,避免引入执行侧依赖.

  @req:r427 @human
  场景: IR 公开类型命名语义化
    - 系统 MUST 为 IR 层公开 alias/presentation 类型提供语义清晰的命名,并保持其纯类型层定位. 以下命名 MUST 生效: - `LoaderResultMapCallable` - `MainSourceRowIterableCallable` - `LookupKeySpec` - `CsvFieldPresentationIr` - `SpreadsheetFieldPresentationIr` - `PandasFieldPresentationIr`

  @req:r521 @human
  场景: FieldIr.data_key 默认等于 field_id
    - 系统 MUST 保证 `FieldIr.data_key` 在 IR 中为非空字符串. 当构造 `FieldIr` 时未提供 `data_key` 或 `data_key` 为空字符串时,系统 MUST 将其默认设置为 `field_id`.
  @req:r60 @human
  场景: ir-模块无执行层依赖
    - 必须成立：当 仅导入 IR 相关模块；那么 不会触发 execution/planning/sinks 的导入
    当 仅导入 IR 相关模块
    那么 不会触发 execution/planning/sinks 的导入
  @req:r304 @human
  场景: ir-调整后仍无执行依赖
    - 必须成立：当 调整 IR 相关模块结构；那么 仍不会触发执行侧模块导入
    当 调整 IR 相关模块结构
    那么 仍不会触发执行侧模块导入
  @req:r427 @human
  场景: 语义化类型命名可导入
    - 必须成立：当 调用方导入上述 IR 公开类型；那么 导入 MUST 成功且类型语义与原能力一致
    当 调用方导入上述 IR 公开类型
    那么 导入 MUST 成功且类型语义与原能力一致
  @req:r521 @human
  场景: data-key-缺省时默认-field-id
    - 必须成立：当 构造 `FieldIr(field_id="order_id", data_key="")` 或缺省 `data_key`；那么 `FieldIr.data_key` MUST 等于 `"order_id"`
    当 构造 `FieldIr(field_id="order_id", data_key="")` 或缺省 `data_key`
    那么 `FieldIr.data_key` MUST 等于 `"order_id"`
