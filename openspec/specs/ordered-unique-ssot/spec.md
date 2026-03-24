# ordered-unique-ssot Specification

## Purpose
TBD - created by archiving change c40-ordered-unique-ssot. Update Purpose after archive.
## Requirements
### Requirement: ordered-unique helper MUST be centralized
系统 MUST 提供一个公共的“去重保序”工具函数作为 SSOT，并要求相关模块复用该函数而不是各自维护副本。

该工具函数 MUST：

- 对输入序列按出现顺序去重
- 输出结果 MUST 可预测且稳定

#### Scenario: duplicates are removed while preserving order
- **WHEN** 输入为 `["a", "a", "b"]`
- **THEN** 输出 MUST 为 `["a", "b"]`（或等价的 tuple 形态）

