## Context

当前在 CSV/Excel 输出路径中，若调用方未显式设置 `allow_formulas`，系统会默认启用 spreadsheet formula escaping（例如写出 `"'=1+1"`），以避免公式注入风险。

但该默认策略会引入“数据被污染”的感知：下游用户会遇到意外的前导 `'`，导致对拍/比对、二次处理与排错成本显著上升。

本变更希望在保留安全选项的前提下，将默认策略改为允许公式（不转义），把“安全收紧”变为显式 opt-in。

## Goals / Non-Goals

**Goals:**
- 将所有对外暴露的 `allow_formulas` 缺省值统一调整为等价 `true`，默认不做公式前缀转义（CSV/Excel sinks + workflow books 导出）。
- 保留安全选项：当调用方显式设置 `allow_formulas=false` 时，仍执行既有的 escaping 规则。
- 保持实现一致：YAML authoring surface、workflow 资源解析与 sinks 参数默认值一致，避免不同路径的默认行为分叉。

**Non-Goals:**
- 不修改 escaping 算法本身（识别规则与前缀转义规则保持不变）。
- 不引入基于数据来源的“自动可信/不可信”判断（避免隐式策略）。
- 不重命名参数或引入兼容层（直接升级默认行为）。

## Decisions

- **默认策略**：所有 `allow_formulas` 默认值改为 `True`（allow 模式），由调用方在不可信输入场景显式选择 `False`（escape 模式）。
- **落点统一**：
  - sinks：将内建 CSV/Excel sinks 的构造参数默认值改为 `allow_formulas=True`。
  - workflow/YAML：将 workflow books 资源解析中的默认值改为 `True`，并确保最终 commit/export 边界使用该开关驱动 `escape_excel_formula(...)`。
- **测试覆盖**：更新现有测试用例中的默认预期（不再出现前导 `'`），并保留显式 `allow_formulas=False` 的安全模式测试。

## Risks / Trade-offs

- [安全默认值下降] 默认允许公式会降低对不可信输入的“开箱即安全”程度 → 缓解：保留 `allow_formulas=false` 选项，并在规范/文档中明确推荐在不可信输入时启用 escape。
- [行为变更影响存量用户] 依赖默认 escaping 的用户将观察到输出变化 → 缓解：迁移路径明确（显式设置 `allow_formulas=false`）。

