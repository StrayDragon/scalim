## 1. Specs / Authoring Surface

- [x] 1.1 补齐并校验本 change 的增量规范：`openspec/changes/c0-workflow-xlsx-formula-escape/specs/**/spec.md`（覆盖默认转义 + `allow_formulas` opt-out + schema-only 场景）。
- [x] 1.2 更新 workflow YAML authoring surface 的 SSOT 校验逻辑（`src/scalim/dsl/by_yaml/workflow_config.py`）以支持：
  - `workflow.resources.workbooks.<id>.allow_formulas`
  - `workflow.resources.sheetbooks.<id>.export_xlsx.allow_formulas`
- [x] 1.3 更新 YAML DSL schema 的 SSOT（禁止手改生成物），并运行：
  - `just gen-yaml-dsl-schema`（刷新 `src/scalim/dsl/by_yaml/schema/*.gen.json` 等生成物）
  - `just gen-yaml-dsl-editor-schema`（刷新 `frontend/**/schema/*.gen.json` 等生成物）
  - `just schema-drift-check`（确保无 drift）

## 2. Runtime Implementation

- [x] 2.1 抽取/复用 Excel 公式前缀转义的 SSOT helper（Python 3.6 compatible），并确保 `ExcelSink` 与 workflow xlsx export 语义一致。
- [x] 2.2 将 `allow_formulas` 配置下沉到 workflow IR/资源定义（`src/scalim/dsl/by_yaml/runtime/workflow_compile.py`）并在 commit/export 时生效：
  - `src/scalim/dsl/by_yaml/runtime/workflow_resources_workbook.py`
  - `src/scalim/dsl/by_yaml/runtime/workflow_resources_sheetbook.py`
- [x] 2.3 为表头行与数据行统一应用转义规则,并确保 `allow_formulas=true` 完全禁用转义。

## 3. Tests / Docs / Gates

- [x] 3.1 新增回归测试覆盖 workbook 与 sheetbook 导出：
  - 默认转义：`= + - @` 前缀（含前导空白）
  - opt-out：`allow_formulas=true` 保留原始字符串
- [x] 3.2 若需更新 docs（包含 `.gen.`/injected blocks 的页面禁止手改区块内部），更新 SSOT 并运行 `just gen-docs`，再用 `just docs-drift-check` 验收。
- [x] 3.3 通过门禁：
  - `just openspec-check`
  - `just qa`
