## Why

当前 CSV/Excel 输出在未显式设置 `allow_formulas` 时，会默认对“疑似公式”的字符串做前缀转义（例如写出为 `"'=1+1"`），以规避 spreadsheet formula injection 风险。

但下游用户反馈该默认行为对不了解背景的人非常困扰：数据中会出现意外的前导 `'`，导致对拍/比对与二次处理变得困难，并且问题往往在更下游才暴露，排查成本高。

因此我们希望在保留安全选项的前提下，将默认行为调整为“允许公式（不转义）”，以减少惊讶与数据污染。

## What Changes

- 默认值调整：所有对外暴露的 `allow_formulas` 开关，缺省时改为等价 `true`（即默认不做公式前缀转义）。
- 保留安全选项：调用方仍可显式设置 `allow_formulas=false` 以启用公式注入防护（escape 模式），并在文档中强调“不可信输入”场景的建议配置。
- 同步规范与实现：更新相关 OpenSpec 规范、实现代码与测试用例，确保 YAML authoring surface、workflow 导出与内建 file sinks 的默认行为一致。

## Capabilities

### New Capabilities
- 无

### Modified Capabilities
- `yaml-dsl-books-resources`: `resources.books.*.allow_formulas` / `export_xlsx.allow_formulas` 缺省值从 `false` 改为 `true`，并相应调整默认转义语义。
- `workflow-shared-output-containers`: workflow 侧 `workflow.resources.books.*.allow_formulas` 缺省值从 `false` 改为 `true`，并相应调整默认转义语义。
- `output-sink-contracts`: 内建 CSV/Excel file sinks 的公式注入防护模式默认从 **escape** 改为 **allow**（仍支持显式选择 escape）。

## Impact

- 行为变化：未显式设置 `allow_formulas` 的 CSV/Excel 输出将不再出现前导 `'` 转义字符。
- 安全注意：对不可信输入，建议调用方显式设置 `allow_formulas=false` 以启用公式注入防护；该变更会降低“默认安全”程度，但提升了默认可用性与数据一致性。
- 影响范围：YAML 资源声明、workflow 资源管理与 sinks（CSV/Excel）均受影响；需要同步更新文档与测试基线。

