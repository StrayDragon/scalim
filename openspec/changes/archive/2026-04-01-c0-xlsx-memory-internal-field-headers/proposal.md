## Why

`xlsx_memory` 是 workflow 内部数据容器,但当前实现把用户可见表头(`name` / 自定义 header)与内部字段键空间混在一起。自 `header_fields_output_by` 默认变为 `name` 后,display header 会泄漏进 `book_sheet_rows` 与后续 `normalize.index_by_key` / relation 链路,迫使用户在每个中间 metrics output 上反复补 `header_fields_output_by: field_id`。

这不是配置易用性问题,而是语义边界错误: 用户自定义 header 本质上是结果侧元信息,不应进入内部数据管道。

## What Changes

- 将 `xlsx_memory` 明确定义为内部数据容器: 内部链路只允许使用 canonical field key(当前实现以 `field_id` 为主)。
- 对 `xlsx_memory`, `book_sheet_rows` 与 sheetbook 内部存储一律返回/保存 canonical field key,不得泄漏 display header。
- 对 `xlsx_memory`, `align_by=header` 视为非法配置并 fail-fast; 内部对齐只允许按 canonical field key。
- 保留结果侧导出能力: 当 `xlsx_memory` 配置 `export_xlsx` 时,导出 `.xlsx` 仍可按 effective `header_fields_output_by` 显示表头。
- 导出 header 元数据只存放在 `sheetbook` 内部 plan 结构中,不进入通用 workflow-managed artifact 语义。
- 不新增 YAML DSL 字段,不改变 `xlsx_file` 行为,不处理值类型字符串化问题。

## Capabilities

### New Capabilities
- None.

### Modified Capabilities
- `yaml-dsl-books-resources`: 明确 `xlsx_memory` 内部只认 canonical field key,`align_by=header` 对 `xlsx_memory` 非法,`header_fields_output_by` 仅影响最终导出显示。
- `workflow-sheetbook-resources`: 明确 `sheetbook`/`book_sheet_rows` 对 `xlsx_memory` 的内部读取契约始终返回 canonical field key,导出 header 元数据仅存在于 sheetbook plan 的结果侧导出路径。

## Impact

- 受影响代码主要在 `src/scalim/execution/output_composition.py`, `src/scalim/workflow/resources_sheetbook.py`, `src/scalim/workflow/resources.py`, `src/scalim/workflow/loaders.py`, `src/scalim/dsl/by_yaml/runtime/output_composition_yaml.py`, `src/scalim/dsl/by_yaml/workflow_compile.py`。
- 受影响 DSL/规范主要在 `openspec/specs/yaml-dsl-books-resources/spec.md` 与 `openspec/specs/workflow-sheetbook-resources/spec.md`。
- 这是破坏性语义收紧: 任何依赖 `xlsx_memory + align_by=header` 的 workflow 都需要改为 canonical field key 对齐。
- 值类型丢失问题将另行以独立 proposal 调研,不并入本 change。
