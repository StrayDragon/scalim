## Why

workflow 的共享 `workbook/sheetbook` 导出会将上游数据以字符串形式写入 `.xlsx`（`openpyxl` write-only）。当 cell 值以 `=`, `+`, `-`, `@` 等前缀开头时,`Excel` 打开文件可能将其解析为公式,形成常见的“导出报表公式注入/脚枪”风险。

同时,`ExcelSink` 已默认做公式前缀转义（并提供 `allow_formulas` 显式放宽）,而 workflow 导出路径目前缺少同等保护,导致同一项目内行为不一致。

## What Changes

- 为 workflow 共享资源导出的 `.xlsx` 增加默认公式前缀转义（对 `workbook` commit 与 `sheetbook` export 生效）：
  - 对字符串值做前缀转义,避免被 `Excel` 解析为公式
  - 默认启用,并提供显式 opt-out（可信场景下允许公式）
- 扩展 workflow YAML authoring surface,提供细粒度 opt-out:
  - `workflow.resources.workbooks.<workbook_id>.allow_formulas`（默认 `false`）
  - `workflow.resources.sheetbooks.<sheetbook_id>.export_xlsx.allow_formulas`（默认 `false`）
- 增加回归测试覆盖：默认转义与 `allow_formulas=true` 放宽两条路径。

**BREAKING**：若既有 workflow 依赖“字符串被写入后由 Excel 解析为公式”的行为,默认转义会使其变为文本。可通过 `allow_formulas=true` 显式恢复旧行为（仅建议用于可信输入/内部场景）。

## Capabilities

### New Capabilities

（无）

### Modified Capabilities

- `workflow-shared-output-containers`: workbook 共享资源导出 `.xlsx` 的字符串写入语义增加默认公式转义,并扩展 authoring surface 支持 `allow_formulas`。
- `workflow-sheetbook-resources`: sheetbook 导出 `.xlsx` 的字符串写入语义增加默认公式转义,并扩展 `export_xlsx` authoring surface 支持 `allow_formulas`。

## Impact

- 受影响实现（预期）：
  - `src/scalim/dsl/by_yaml/runtime/workflow_resources_workbook.py`
  - `src/scalim/dsl/by_yaml/runtime/workflow_resources_sheetbook.py`
  - `src/scalim/dsl/by_yaml/workflow_config.py`（workflow YAML 解析/校验）
  - `src/scalim/dsl/by_yaml/runtime/workflow_compile.py`（将配置下沉到 IR/options）
  - `src/scalim/sinks/sink_excel.py`（建议复用同一 SSOT 转义函数,避免 drift）
- 规范治理：
  - 本 change 的增量规范位于 `openspec/changes/c0-workflow-xlsx-formula-escape/specs/**/spec.md`
  - 行为归档后需同步至 SSOT：`openspec/specs/*/spec.md` 并通过 `just openspec-check`
- 生成物边界：
  - YAML DSL schema/editor schema 为生成物（例如 `src/scalim/dsl/by_yaml/schema/demand.gen.json`、`frontend/**/demand.gen.json`）,不得手改；应更新 SSOT（schema DSL）并运行 `just gen-yaml-dsl-schema` / `just gen-yaml-dsl-editor-schema` / `just schema-drift-check`。

