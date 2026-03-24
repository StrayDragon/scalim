## Context

- workflow 的共享 `workbook/sheetbook` 导出使用 `openpyxl` write-only 写入 `.xlsx`,当前对字符串 cell 值不做“公式前缀转义”。（示例：`\"=1+1\"` 会被 Excel 解析为公式）
- `ExcelSink` 已实现 `_escape_excel_formula(value, allow_formulas=...)` 的默认保护与显式放宽,但 workflow 导出与 sink 行为不一致。
- 本仓库的默认使用场景以本地/可信输入为主,但“打开报表即触发公式解析”的脚枪仍然高频且难排障,因此倾向默认保护 + 显式 opt-out。

## Goals / Non-Goals

**Goals:**
- workflow 导出的 `.xlsx` 默认不触发 Excel 公式解析（以最小行为变更实现安全默认）。
- 与 `ExcelSink` 的转义语义保持一致,避免同一项目内不同路径产生不一致的“是否转义”行为。
- 为确有需求的可信场景提供显式 opt-out（`allow_formulas=true`）。

**Non-Goals:**
- 不改变 `ExcelSink` 现有默认语义（仅要求复用同一 SSOT helper,避免 drift）。
- 不引入更通用的“Excel 内容消毒”或链接/DDE 等扩展防护（仅聚焦公式前缀）。
- 不改变 workflow 的 reserved-path/collision precheck 语义与其它输出格式（例如 CSV）。

## Decisions

1) 公式前缀转义算法
- 采用与 `ExcelSink` 一致的规则：
  - 仅对 `str` 生效
  - 若原始字符串以 `'` 开头则保持不变
  - 对 `value.lstrip()` 的首字符,若属于 `{ '=', '+', '-', '@' }`,则在原始字符串前追加 `'`
  - 否则保持不变
- 该规则同时作用于：
  - workbook 的表头行与数据行
  - sheetbook export 的表头行与数据行

2) Opt-out 的配置位置（workflow YAML authoring surface）
- `workflow.resources.workbooks.<workbook_id>.allow_formulas`（默认 `false`）
- `workflow.resources.sheetbooks.<sheetbook_id>.export_xlsx.allow_formulas`（默认 `false`）
- 设计意图：以资源维度放宽,避免“一次 workflow 全局放宽”导致误用。

3) SSOT helper 的放置与复用
- 方案 A：在 workflow 资源模块内复制 `_escape_excel_formula`（实现最小,但容易 drift）。
- 方案 B（推荐）：抽取纯函数 helper 为 SSOT（例如 `src/scalim/utils/*`）,由 `sink_excel` 与 workflow export 共用。
  - 优点：语义统一、避免 drift；helper 为纯函数,不引入额外依赖。
  - 约束：必须保持 `src/scalim/` 运行时兼容 Python 3.6。

4) 生成物/文档治理与 drift gate
- schema 相关 `.gen.json` 为生成物：通过 `just gen-yaml-dsl-schema` / `just gen-yaml-dsl-editor-schema` 刷新,并用 `just schema-drift-check` 兜底。
- 若 workflow YAML 文档需要同步,走 `just gen-docs` 并通过 `just docs-drift-check`。
- OpenSpec 工件必须通过 `just openspec-check`（sanitize + validate）。

## Risks / Trade-offs

- [行为变更] 既有 workflow 若依赖公式解析将被默认转义 → 通过 `allow_formulas=true` 显式放宽。
- [一致性风险] 若 workflow 与 sink 使用不同实现,未来可能 drift → 通过 SSOT helper 复用缓解。
- [测试覆盖] `.xlsx` 读写依赖 openpyxl,测试可能较慢 → 采用最小样例与精确断言（字符串是否被加 `'`）,避免性能阈值断言。

